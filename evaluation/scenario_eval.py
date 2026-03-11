#!/usr/bin/env python3
"""
ESG 節能策略離線評估腳本 v2
==============================
根據 ESG 期末報告的流量情境定義，產生 synthetic traffic data，
比較多種節能演算法在不同情境下的表現。

比較方法：
  1. RL + Heuristic（載入已訓練的 RL model 產生閾值 + heuristic 決策）
  2. Heuristic-only（固定閾值: bufLow=0.3, utilHi=0.5, utilCap=0.9）
  3. Heuristic-aggressive（激進閾值: bufLow=0.5, utilHi=0.7, utilCap=0.95）
  4. Greedy baseline（貪婪法：按使用率排序，盡可能關閉低使用率的 link）

流量情境（來自報告）：
  1. 離峰（off-peak）：平均鏈路使用率 < 0.3
  2. 高峰（high）：平均鏈路使用率 0.6 ~ 0.8
  3. 尖峰（peak）：平均鏈路使用率 >= 0.9
  4. 離峰突增（surge）：部分鏈路從 <0.3 突增至 0.6~0.8

拓樸：17 節點、33 條實體 link（66 雙向），頻寬 7000 Mbps / link

Usage:
  cd /home/r11921A18/EVE-NG/esgbackend/telemetry
  /home/r11921A18/EVE-NG/esgbackend/venv/bin/python /home/r11921A18/EVE-NG/evaluation/scenario_eval.py
"""

import sys
import os
import json
import copy
import logging
import warnings
import numpy as np
import networkx as nx
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# Suppress noisy logs during evaluation
logging.basicConfig(level=logging.WARNING)
warnings.filterwarnings("ignore")

# Path setup
TELEMETRY_DIR = Path(__file__).resolve().parent.parent / "esgbackend" / "telemetry"
sys.path.insert(0, str(TELEMETRY_DIR))
os.chdir(TELEMETRY_DIR)

# ╔═══════════════════════════════════════════════════════════════╗
# ║  1. Topology                                                   ║
# ╚═══════════════════════════════════════════════════════════════╝
HARDCODED_LINKS = [
    (0, 1), (0, 2), (0, 3), (0, 8),
    (1, 3), (1, 8),
    (2, 3), (2, 8),
    (3, 4), (3, 5), (3, 6), (3, 7), (3, 8), (3, 9), (3, 10), (3, 14),
    (4, 8), (5, 14), (6, 8), (7, 8),
    (8, 9), (8, 14),
    (9, 11), (9, 12), (9, 13), (9, 15), (9, 16),
    (10, 14), (11, 14), (12, 14), (13, 14),
    (14, 15), (14, 16),
]

ALL_BIDIR_LINKS = []
for u, v in HARDCODED_LINKS:
    ALL_BIDIR_LINKS.append(f"S{u+1}-S{v+1}")
    ALL_BIDIR_LINKS.append(f"S{v+1}-S{u+1}")

NUM_NODES = 17
NUM_PHYSICAL_LINKS = len(HARDCODED_LINKS)  # 33
LINK_BW_MBPS = 7000
LINK_BW_BPS = LINK_BW_MBPS * 1e6 / 8  # bytes/sec

# Energy model (from report: Cisco ASR 9010 measurement)
WATTS_PER_PORT = 35        # Closing a port saves ~30-40W
WATTS_BASE_CHASSIS = 860   # Base chassis idle power

# ╔═══════════════════════════════════════════════════════════════╗
# ║  2. Traffic scenario generators                                ║
# ╚═══════════════════════════════════════════════════════════════╝
def generate_scenario_traffic(scenario: str, seed: int = 42) -> dict:
    """
    Generate synthetic traffic (bytes/sec) per bidirectional link.
    Returns {link_name: float}.
    """
    rng = np.random.RandomState(seed)
    traffic = {}

    if scenario == "off_peak":
        for link in ALL_BIDIR_LINKS:
            traffic[link] = rng.uniform(0.05, 0.30) * LINK_BW_BPS
    elif scenario == "high":
        for link in ALL_BIDIR_LINKS:
            traffic[link] = rng.uniform(0.50, 0.85) * LINK_BW_BPS
    elif scenario == "peak":
        for link in ALL_BIDIR_LINKS:
            traffic[link] = rng.uniform(0.85, 1.0) * LINK_BW_BPS
    elif scenario == "surge":
        surge_indices = set(rng.choice(len(ALL_BIDIR_LINKS),
                                       size=int(len(ALL_BIDIR_LINKS) * 0.4),
                                       replace=False))
        for i, link in enumerate(ALL_BIDIR_LINKS):
            if i in surge_indices:
                traffic[link] = rng.uniform(0.60, 0.85) * LINK_BW_BPS
            else:
                traffic[link] = rng.uniform(0.05, 0.25) * LINK_BW_BPS
    else:
        raise ValueError(f"Unknown scenario: {scenario}")
    return traffic


def avg_util(traffic: dict) -> float:
    return np.mean([traffic[l] / LINK_BW_BPS for l in traffic])

# ╔═══════════════════════════════════════════════════════════════╗
# ║  3. Graph utilities                                            ║
# ╚═══════════════════════════════════════════════════════════════╝
def build_graph(exclude_physical=None):
    """Build NetworkX graph, optionally excluding physical link tuples."""
    exclude_physical = exclude_physical or set()
    G = nx.Graph()
    G.add_nodes_from(range(NUM_NODES))
    for u, v in HARDCODED_LINKS:
        key = (min(u, v), max(u, v))
        if key not in exclude_physical:
            G.add_edge(u, v)
    return G


def is_connected(exclude_physical):
    return nx.is_connected(build_graph(exclude_physical))


def bidir_to_physical(closed_bidir: list) -> set:
    """Convert bidirectional link names to physical (undirected) tuple set."""
    phys = set()
    for link in closed_bidir:
        a, b = link.split("-")
        a, b = int(a[1:]) - 1, int(b[1:]) - 1
        phys.add((min(a, b), max(a, b)))
    return phys


def physical_to_bidir(phys_set: set) -> list:
    """Convert physical tuples back to bidirectional link name list."""
    result = []
    for u, v in phys_set:
        result.append(f"S{u+1}-S{v+1}")
        result.append(f"S{v+1}-S{u+1}")
    return result

# ╔═══════════════════════════════════════════════════════════════╗
# ║  4. Evaluation metrics                                         ║
# ╚═══════════════════════════════════════════════════════════════╝
def compute_metrics(traffic: dict, closed_bidir: list) -> dict:
    closed_phys = bidir_to_physical(closed_bidir)
    n_closed = len(closed_phys)
    connected = is_connected(closed_phys)

    # Energy savings
    energy_saved_w = n_closed * 2 * WATTS_PER_PORT
    total_port_energy = NUM_PHYSICAL_LINKS * 2 * WATTS_PER_PORT
    saving_ratio = energy_saved_w / total_port_energy if total_port_energy > 0 else 0

    # Overload check on open links
    closed_set = set(closed_bidir)
    open_utils = []
    for link in ALL_BIDIR_LINKS:
        if link not in closed_set:
            open_utils.append(traffic[link] / LINK_BW_BPS)
    max_open_util = max(open_utils) if open_utils else 0
    overloaded_count = sum(1 for u in open_utils if u > 0.95)

    return {
        "closed_physical": n_closed,
        "open_physical": NUM_PHYSICAL_LINKS - n_closed,
        "saving_ratio": saving_ratio,
        "saved_watts": energy_saved_w,
        "connected": connected,
        "max_open_util": max_open_util,
        "overloaded": overloaded_count,
        "closed_names": closed_bidir,
    }

# ╔═══════════════════════════════════════════════════════════════╗
# ║  5. Algorithm implementations                                  ║
# ╚═══════════════════════════════════════════════════════════════╝

# ---- 5a. Clean heuristic (report's algorithm, parameterized) ----
def heuristic_algorithm(traffic: dict, bufLow=0.3, utilHi=0.5, utilCap=0.9) -> list:
    """
    Heuristic from the ESG report:
      - Close a bidirectional link pair if BOTH directions have:
          link_utilization <= utilHi  (buffer check simplified: no real buffer data)
      - Keep link if either direction > utilCap
      - Ensure network stays connected
      - Ensure no open link exceeds utilCap after redistribution (simplified)

    Since we don't have buffer data in synthetic traffic, we use utilization only
    and treat bufLow as a secondary threshold.
    """
    # Compute per physical link: max utilization of both directions
    phys_util = {}
    for u, v in HARDCODED_LINKS:
        key = (u, v)
        fwd = f"S{u+1}-S{v+1}"
        rev = f"S{v+1}-S{u+1}"
        u_fwd = traffic.get(fwd, 0) / LINK_BW_BPS
        u_rev = traffic.get(rev, 0) / LINK_BW_BPS
        phys_util[key] = max(u_fwd, u_rev)

    # Sort by utilization (lowest first) - close low-util links first
    sorted_links = sorted(phys_util.items(), key=lambda x: x[1])

    closed_phys = set()
    for (u, v), util in sorted_links:
        # Only close if utilization is below threshold
        if util > utilHi:
            continue
        # Don't close if above capacity threshold
        if util > utilCap:
            continue
        # Try closing this link
        candidate = closed_phys | {(min(u, v), max(u, v))}
        # Safety: check connectivity
        if is_connected(candidate):
            closed_phys = candidate

    return physical_to_bidir(closed_phys)


# ---- 5b. Greedy baseline ----
def greedy_algorithm(traffic: dict, utilCap=0.90) -> list:
    """
    Greedy: close as many links as possible, starting from lowest utilization,
    while maintaining connectivity and not exceeding utilCap on any remaining link.
    """
    phys_util = {}
    for u, v in HARDCODED_LINKS:
        fwd = f"S{u+1}-S{v+1}"
        rev = f"S{v+1}-S{u+1}"
        phys_util[(u, v)] = max(traffic.get(fwd, 0), traffic.get(rev, 0)) / LINK_BW_BPS

    sorted_links = sorted(phys_util.items(), key=lambda x: x[1])
    closed_phys = set()

    for (u, v), util in sorted_links:
        candidate = closed_phys | {(min(u, v), max(u, v))}
        if is_connected(candidate):
            closed_phys = candidate

    return physical_to_bidir(closed_phys)


# ---- 5c. RL + Heuristic (backend's actual implementation) ----
def rl_heuristic_algorithm(traffic: dict) -> list:
    """Use the backend's RL model + heuristic. Convert traffic to dict format."""
    try:
        from rl_model import RLModelManager
        manager = RLModelManager(use_mock=False)
        # Provide traffic in dict format with correct max-capacity
        dict_traffic = {}
        for link, bps in traffic.items():
            dict_traffic[link] = {
                "traffic": bps,
                "max-capacity": LINK_BW_BPS,
                "output-drops": 0,
                "output-queue-drops": 0,
            }
        return manager.predict_links_to_close(dict_traffic)
    except Exception as e:
        return [], str(e)


# ╔═══════════════════════════════════════════════════════════════╗
# ║  6. Main evaluation                                            ║
# ╚═══════════════════════════════════════════════════════════════╝
SCENARIOS = {
    "off_peak": "離峰 (Off-Peak)",
    "high":     "高峰 (High)",
    "peak":     "尖峰 (Peak)",
    "surge":    "離峰突增 (Surge)",
}

METHODS = {
    "rl_heuristic": {
        "name": "RL+Heuristic",
        "fn": lambda t: rl_heuristic_algorithm(t),
    },
    "heuristic_default": {
        "name": "Heuristic (default)",
        "fn": lambda t: heuristic_algorithm(t, bufLow=0.3, utilHi=0.5, utilCap=0.9),
    },
    "heuristic_aggressive": {
        "name": "Heuristic (aggressive)",
        "fn": lambda t: heuristic_algorithm(t, bufLow=0.5, utilHi=0.7, utilCap=0.95),
    },
    "greedy": {
        "name": "Greedy",
        "fn": lambda t: greedy_algorithm(t, utilCap=0.9),
    },
}

NUM_TRIALS = 5


def run_one(scenario_key: str, seed: int) -> dict:
    traffic = generate_scenario_traffic(scenario_key, seed)
    utilization = avg_util(traffic)
    row = {"scenario": scenario_key, "seed": seed, "avg_util": utilization}

    for method_key, method_info in METHODS.items():
        try:
            closed = method_info["fn"](copy.deepcopy(traffic))
            if isinstance(closed, tuple):
                closed = closed[0]  # Handle error return
        except Exception as e:
            closed = []
        metrics = compute_metrics(traffic, closed)
        row[method_key] = metrics

    return row


def main():
    print("=" * 80)
    print("  ESG 節能策略離線評估 v2")
    print("  Offline Evaluation of Energy-Saving Strategies")
    print("=" * 80)

    # Verify scenarios
    print("\n--- 流量情境驗證 ---")
    for sc in SCENARIOS:
        t = generate_scenario_traffic(sc, seed=42)
        print(f"  {sc:12s}: avg_utilization = {avg_util(t):.3f}")

    # Run
    print(f"\n--- 開始評估 ({NUM_TRIALS} trials × {len(SCENARIOS)} scenarios × {len(METHODS)} methods) ---")
    all_results = []

    for sc_key, sc_name in SCENARIOS.items():
        print(f"\n  [{sc_name}]")
        for trial in range(NUM_TRIALS):
            seed = 42 + trial * 7
            print(f"    Trial {trial+1}/{NUM_TRIALS} (seed={seed})...", end=" ", flush=True)
            row = run_one(sc_key, seed)
            all_results.append(row)

            parts = []
            for mk, mi in METHODS.items():
                m = row[mk]
                parts.append(f"{mi['name']}: {m['closed_physical']} links ({m['saving_ratio']:.0%})")
            print(" | ".join(parts))

    # ═══════════════════════════════════════════════════════════
    # Summary table
    # ═══════════════════════════════════════════════════════════
    print("\n" + "=" * 120)
    print("  ESG 節能策略評估結果總表")
    print(f"  拓樸: {NUM_NODES} 節點, {NUM_PHYSICAL_LINKS} 條鏈路, 頻寬 {LINK_BW_MBPS} Mbps")
    print(f"  評估時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}, 每情境 {NUM_TRIALS} 次取平均")
    print("=" * 120)

    # Group by scenario
    by_scenario = defaultdict(list)
    for r in all_results:
        by_scenario[r["scenario"]].append(r)

    # Print header
    method_names = [METHODS[mk]["name"] for mk in METHODS]
    header = f"{'情境':<18} {'平均Util':>8}"
    for mn in method_names:
        header += f" | {mn:^22}"
    print(header)

    subheader = f"{'':18} {'':>8}"
    for _ in method_names:
        subheader += f" | {'關閉':>4} {'節能率':>6} {'連通':>4} {'壅塞':>4}"
    print(subheader)
    print("-" * 120)

    summary_data = {}

    for sc_key in SCENARIOS:
        trials = by_scenario[sc_key]
        sc_name = SCENARIOS[sc_key]
        mean_util = np.mean([t["avg_util"] for t in trials])

        line = f"{sc_name:<18} {mean_util:>8.3f}"
        sc_summary = {"avg_util": float(mean_util)}

        for mk in METHODS:
            closed_avg = np.mean([t[mk]["closed_physical"] for t in trials])
            saving_avg = np.mean([t[mk]["saving_ratio"] for t in trials])
            conn_ok = all(t[mk]["connected"] for t in trials)
            overload_avg = np.mean([t[mk]["overloaded"] for t in trials])

            conn_str = "OK" if conn_ok else "FAIL"
            line += f" | {closed_avg:>4.1f} {saving_avg:>6.1%} {conn_str:>4} {overload_avg:>4.1f}"

            sc_summary[mk] = {
                "avg_closed": float(closed_avg),
                "avg_saving": float(saving_avg),
                "connected": conn_ok,
                "avg_overloaded": float(overload_avg),
            }

        print(line)
        summary_data[sc_key] = sc_summary

    print("-" * 120)

    # ═══════════════════════════════════════════════════════════
    # Detailed per-trial results
    # ═══════════════════════════════════════════════════════════
    print("\n\n--- 各 Trial 詳細 ---")
    for sc_key in SCENARIOS:
        trials = by_scenario[sc_key]
        print(f"\n  [{SCENARIOS[sc_key]}]")
        for t in trials:
            parts = [f"seed={t['seed']:3d}, util={t['avg_util']:.3f}"]
            for mk in METHODS:
                m = t[mk]
                parts.append(f"{METHODS[mk]['name']}: close={m['closed_physical']:2d} "
                             f"({m['saving_ratio']:.0%}) "
                             f"{'OK' if m['connected'] else 'FAIL'}")
            print("    " + " | ".join(parts))

            # Show which links were closed
            for mk in METHODS:
                m = t[mk]
                if m["closed_names"]:
                    phys = bidir_to_physical(m["closed_names"])
                    link_strs = [f"S{u+1}-S{v+1}" for u, v in sorted(phys)]
                    print(f"      {METHODS[mk]['name']:25s}: {', '.join(link_strs)}")

    # ═══════════════════════════════════════════════════════════
    # Save JSON
    # ═══════════════════════════════════════════════════════════
    output_dir = Path(__file__).resolve().parent
    output_file = output_dir / "eval_results.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "config": {
                "num_nodes": NUM_NODES,
                "num_physical_links": NUM_PHYSICAL_LINKS,
                "link_bandwidth_mbps": LINK_BW_MBPS,
                "watts_per_port": WATTS_PER_PORT,
                "num_trials": NUM_TRIALS,
                "methods": {mk: mi["name"] for mk, mi in METHODS.items()},
            },
            "summary": summary_data,
            "all_trials": [
                {
                    "scenario": r["scenario"],
                    "seed": r["seed"],
                    "avg_util": r["avg_util"],
                    **{mk: {
                        "closed": r[mk]["closed_physical"],
                        "saving": r[mk]["saving_ratio"],
                        "connected": r[mk]["connected"],
                        "overloaded": r[mk]["overloaded"],
                        "closed_links": [f"S{u+1}-S{v+1}" for u, v in sorted(bidir_to_physical(r[mk]["closed_names"]))],
                    } for mk in METHODS}
                }
                for r in all_results
            ],
        }, f, ensure_ascii=False, indent=2)

    print(f"\n\n結果已儲存至: {output_file}")
    print("完成!")


if __name__ == "__main__":
    main()
