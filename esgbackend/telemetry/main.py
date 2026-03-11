import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import json
import re, os, torch, textwrap, numpy as np
from pathlib import Path
from unsloth import FastLanguageModel
from dotenv import load_dotenv
from collect import collect_link_traffic, fetch_generic_counters_legacy
from rl_model import get_rl_manager
from rag_system import get_rag_system
from restconf_processor import process_predicted_links, build_shutdown_commands
load_dotenv()

# ────────────────────── 配置設定 ──────────────────────────
USE_RAG = False  # Set to True to enable RAG, False to disable
# ────────────────────── 載入LLM模型 ──────────────────────────
MAX_SEQ_LEN  = 2048
MODEL_NAME   = "taide/Llama-3.1-TAIDE-LX-8B-Chat"
print("Loading model… (只載一次)")
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name     = MODEL_NAME,
    max_seq_length = MAX_SEQ_LEN,
    load_in_4bit   = True,                # 🔧 4-bit 量化→ 8 GB VRAM 夠用
    token          = os.getenv("HUGGINGFACE_TOKEN", ""),
)           
print("Model on", model.device)

# ────────────────────── 載入RL模型 ───────────────────
# 初始化RL模型管理器 (使用真實訓練好的模型)
rl_manager = get_rl_manager(use_mock=False)
print(f"🤖 RL Model Info: {rl_manager.get_model_info()}")

# ────────────────────── 載入RAG系統 ───────────────────
# 初始化RAG系統 (根據配置決定是否啟用)
if USE_RAG:
    try:
        rag_system = get_rag_system("all-MiniLM-L6-v2")
        print("📚 RAG System initialized with free local embeddings")

        # 嘗試載入Guide.docx文檔
        try:
            rag_system.load_documents("Guide.docx")
            print("✅ Guide.docx loaded into RAG system")
        except Exception as e:
            print(f"⚠️ Failed to load Guide.docx: {e}")
            print("📝 You can load documents later using the /load-document endpoint")
    except Exception as e:
        print(f"⚠️ RAG System initialization failed: {e}")
        print("📝 RAG features will be disabled")
        rag_system = None
else:
    rag_system = None
    print("🚫 RAG System disabled by configuration (USE_RAG = False)")

# ────────────────────── ❸ System prompt ───────────────────
SYSTEM_PROMPT = textwrap.dedent(f"""你是 Cisco IOS XR 網管助手，你將被提供網路流量資料，請分析資料後，輸出分析結果，請簡短扼要，不要輸出指令，不超過2000字元""")

# ────────────────────── ❄ Dynamic Links Generation ───────────
def get_dynamic_links():
    """Generate LINKS dynamically from topology data"""
    try:
        from collect import get_dynamic_interface_mapping
        
        # Get dynamic interface mapping which contains all link information
        interface_mapping = get_dynamic_interface_mapping()
        
        # Extract unique links from the mapping keys
        links = set()
        for link_name in interface_mapping.keys():
            links.add(link_name)
        
        # Convert to sorted list for consistency
        dynamic_links = sorted(list(links))
        print(f"🔗 Generated {len(dynamic_links)} dynamic links from topology")
        return dynamic_links
        
    except Exception as e:
        print(f"⚠️  Error generating dynamic links: {e}")
        print("🔄 Falling back to static LINKS")
        return STATIC_LINKS

# ────────────────────── ❹ Telemetry 產生器 (略)… ───────────
# Static fallback LINKS (kept for backup)
# Fixed 2026-03-10: matched to UNL network_id physical links
# Removed non-existent: S10-S15/S15-S10, S2-S5/S5-S2, S6-S7/S7-S6, S7-S8/S8-S7
STATIC_LINKS = [
    "S1-S2", "S1-S3", "S1-S4", "S1-S9",
    "S2-S1", "S2-S4", "S2-S9",
    "S3-S1", "S3-S4", "S3-S9",
    "S4-S1", "S4-S2", "S4-S3", "S4-S5", "S4-S6", "S4-S7",
    "S4-S8", "S4-S9", "S4-S10", "S4-S11", "S4-S15",
    "S5-S4", "S5-S9",
    "S6-S4", "S6-S15",
    "S7-S4", "S7-S9",
    "S8-S4", "S8-S9",
    "S9-S1", "S9-S2", "S9-S3", "S9-S4", "S9-S5",
    "S9-S7", "S9-S8", "S9-S10", "S9-S15",
    "S10-S4", "S10-S9", "S10-S12", "S10-S13",
    "S10-S14", "S10-S16", "S10-S17",
    "S11-S4", "S11-S15",
    "S12-S10", "S12-S15",
    "S13-S10", "S13-S15",
    "S14-S10", "S14-S15",
    "S15-S4", "S15-S6", "S15-S9", "S15-S11",
    "S15-S12", "S15-S13", "S15-S14", "S15-S16", "S15-S17",
    "S16-S10", "S16-S15",
    "S17-S10", "S17-S15",
]

# Generate dynamic links at startup
LINKS = get_dynamic_links()

def generate_random_traffic(links=LINKS, min_traffic=1, max_traffic=1_000):
    traffic = {}
    for link in links:
        src, dst = link.split("-")
        fwd_key, rev_key = f"{src}-{dst}", f"{dst}-{src}"
        if fwd_key not in traffic:
            traffic[fwd_key] = random.randint(min_traffic, max_traffic)
        if rev_key not in traffic:
            traffic[rev_key] = random.randint(min_traffic, max_traffic)
    return traffic
def default_collector():
    """default Telemetry 產生器。"""
    return generate_random_traffic()

def collector(use_rates=True, measurement_interval=10):
    """完整 Telemetry 產生器 - uses dynamic links from topology with real-time rates。
    
    Args:
        use_rates (bool): If True, collect traffic rates; if False, use cumulative counters
        measurement_interval (int): Seconds between measurements for rate calculation
    
    Returns:
        dict: Traffic data (rates in bytes/sec or cumulative bytes)
    """
    if use_rates:
        from collect import collect_traffic_rates
        return collect_traffic_rates(LINKS, measurement_interval=measurement_interval)
    else:
        return collect_link_traffic(LINKS)

# ────────────────────── ❺ RL模型預測函數 ───────────────────
def predict_links_to_close_rl(telemetry_data: dict) -> list:
    """
    使用RL模型預測應該關閉哪些link
    
    Args:
        telemetry_data: 即時流量數據
        
    Returns:
        list: 應該關閉的link列表
    """
    try:
        return rl_manager.predict_links_to_close(telemetry_data)
    except Exception as e:
        print(f"❌ Error in RL prediction: {e}")
        return ["L1", "L3", "L6"]  # 預設值

# ────────────────────── ❻ LLM 推論 ─────────────────────────
def llm_inference(user_prompt: str = None, predicted_links: list = None):
    """
    LLM inference with RAG enhancement
    
    Args:
        user_prompt: Custom user prompt (optional)
        predicted_links: Pre-filtered links to close (optional, if None will predict using RL)
    """
    telemetry_data = collector() ## link utilization
    
    # Use provided filtered links or predict using RL
    if predicted_links is not None:
        links_to_close = predicted_links
        print(f"🔒 Using filtered links to close: {links_to_close}")
    else:
        links_to_close = predict_links_to_close_rl(telemetry_data)
        print(f"🤖 RL predicted links to close: {links_to_close}")
    
    # Calculate energy saving based on bidirectional link pairs
    def find_bidirectional_pairs_in_telemetry(telemetry_data):
        """Find bidirectional pairs in telemetry data, matching the algorithm logic"""
        bidirectional_pairs = {}
        
        for link_name in telemetry_data.keys():
            if '-' not in link_name:
                continue
                
            src, dst = link_name.split('-')
            reverse_link = f"{dst}-{src}"
            
            # Check if reverse link exists in telemetry
            if reverse_link in telemetry_data:
                # Create canonical name (alphabetically sorted)
                canonical_name = f"{min(src, dst)}-{max(src, dst)}"
                
                # Only add if not already processed
                if canonical_name not in bidirectional_pairs:
                    bidirectional_pairs[canonical_name] = (link_name, reverse_link)
        
        return bidirectional_pairs
    
    def count_closed_pairs(links_to_close, bidirectional_pairs):
        """Count how many bidirectional pairs are being closed"""
        closed_pairs = set()
        
        for link in links_to_close:
            if '-' not in link:
                continue
                
            src, dst = link.split('-')
            canonical_name = f"{min(src, dst)}-{max(src, dst)}"
            
            # Check if this canonical pair exists in our bidirectional pairs
            if canonical_name in bidirectional_pairs:
                closed_pairs.add(canonical_name)
        
        return len(closed_pairs)
    
    # Find all bidirectional pairs in telemetry data
    bidirectional_pairs = find_bidirectional_pairs_in_telemetry(telemetry_data)
    total_pairs = len(bidirectional_pairs)
    
    # Count how many pairs are being closed
    closed_pairs_count = count_closed_pairs(links_to_close, bidirectional_pairs)
    
    print(f"🔋 Energy calculation: {closed_pairs_count} bidirectional pairs to close out of {total_pairs} total pairs")
    print(f"🔗 Raw counts: {len(links_to_close)} directional links to close, {len(telemetry_data)} total telemetry links")
    print(f"📊 Bidirectional pairs found: {list(bidirectional_pairs.keys())[:5]}{'...' if len(bidirectional_pairs) > 5 else ''}")
    
    if total_pairs > 0:
        base_energy_saving = closed_pairs_count / total_pairs
        energy_saving = min(1.0, base_energy_saving * 2)  # Double the percentage, cap at 100%
        print(f"🔋 Energy saving: {energy_saving:.3f} ({energy_saving:.1%}) - {closed_pairs_count}/{total_pairs} pairs (doubled)")
    else:
        energy_saving = 0.0
        print(f"🔋 No bidirectional pairs found, energy saving = 0%")
    
    # Process predicted links into RESTCONF commands
    file_commands, api_commands, configs, commands_file, config_files = process_predicted_links(links_to_close)
    print(f"📁 RESTCONF commands saved to: {commands_file}")
    ## 
    telemetry_json = json.dumps(telemetry_data, ensure_ascii=False)
    
    # Use custom prompt or default
    if user_prompt:
        prompt = user_prompt
    else:
        prompt = f"請根據上述資料，關閉 {', '.join(links_to_close)}，整理輸出相關參考資料"
    
    # Enhance prompt with RAG
    if rag_system is not None:
        try:
            enhanced_prompt = rag_system.enhance_prompt(prompt, SYSTEM_PROMPT)
            print(f"📚 RAG enhanced prompt with relevant documents")
        except Exception as e:
            print(f"⚠️ RAG enhancement failed: {e}")
            enhanced_prompt = prompt
            print(f"📝 Using original prompt without RAG")
    else:
        enhanced_prompt = prompt
        print(f"📝 RAG system not available, using original prompt")

    full_prompt = (
        f"以下是即時流量資料（JSON）：\n{telemetry_json}\n\n"
        f"{enhanced_prompt}"
    )

    chat = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": full_prompt},
    ]

    input_ids = tokenizer.apply_chat_template(
        chat,
        tokenize=True,
        add_generation_prompt=True,
        return_tensors="pt",
    ).to("cuda")                           # 🔧 張量也搬到 GPU

    with torch.no_grad():
        outputs = model.generate(
            input_ids       = input_ids,
            max_new_tokens  = 256,
            do_sample       = True,
            temperature     = 0.7,
            top_p           = 0.9,
        )

    generated = outputs[0, input_ids.shape[-1]:]
    # Format commands without escape characters
    formatted_commands = []
    for cmd in api_commands:
        # Remove any remaining escape characters
        clean_cmd = cmd.replace('\\', '').replace('\n', ' ').replace('\'', '"')
        formatted_commands.append(clean_cmd)
    
    # Create detailed instructions with shutdown modification steps
    shutdown_instructions = f"節能路徑設定指令參考，請根據上述資料，關閉 {', '.join(links_to_close)}，關閉的RESTCONF命令為{formatted_commands}"

    final_instructions = """
    重要操作步驟
    1. 執行 GET 命令獲取當前介面配置並保存到 JSON 檔案
    2. 編輯 JSON 檔案，在 interface-configuration 中新增 "shutdown":[null] 欄位
    範例修改前
    {{"interface-configuration":{{{"active":"act", "interface-name":"GigabitEthernet0/0/0/0", "Cisco-IOS-XR-ipv4-network":{{"addresses":{{"primary":{{"address":"10.0.4.1","netmask":"255.255.255.252"}}}}}}}}}}}
    
    範例修改後
    {{"interface-configuration":{{{"active":"act", "shutdown":[null], "interface-name":"GigabitEthernet0/0/0/0", "Cisco-IOS-XR-ipv4-network":{{"addresses":{{"primary":{{"address":"10.0.4.1","netmask":"255.255.255.252"}}}}}}}}}}}

    3. 執行 PUT 命令將修改後的配置套用到設備
    """
    
    return tokenizer.decode(generated, skip_special_tokens=True).strip() + final_instructions , shutdown_instructions , energy_saving

# ────────────────────── ❼ FastAPI 端點 (原樣) ──────────────
app = FastAPI(
    title       = "XR Telemetry + LLM Demo",
    description = "產生Telemetry，並用 UnsLoTH Llama-3.1 taide 產 RESTCONF 指令",
    version     = "1.0.0",
)

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/telemetry")
async def get_telemetry():
    try:
        # 獲取原始telemetry數據
        raw_data = collector(use_rates=True, measurement_interval=10)
        
        # 只返回整數值
        formatted_data = {}
        for link, value in raw_data.items():
            if isinstance(value, (int, float)):
                formatted_data[link] = int(round(value))
            else:
                formatted_data[link] = value
        
        return formatted_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
@app.get("/input")
async def get_input():
    try:
        return {"input": "input"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

from pydantic import BaseModel
from typing import Optional

class OutputRequest(BaseModel):
    message: Optional[str] = None

def parse_protected_links(message: str) -> list:
    """Parse user message to extract protected links from brackets []
    
    Args:
        message: User message that may contain protected links like [S1-S4]
        
    Returns:
        list: List of protected link names (including bidirectional pairs)
    """
    if not message:
        return []
    
    # Find all content within square brackets
    bracket_matches = re.findall(r'\[([^\]]+)\]', message)
    protected_links = []
    
    for match in bracket_matches:
        # Split by comma or space to handle multiple links in one bracket
        links = re.split(r'[,\s]+', match.strip())
        for link in links:
            link = link.strip()
            if link and '-' in link:  # Basic validation for link format
                protected_links.append(link)
                
                # Add bidirectional link (S6-S15 -> also protect S15-S6)
                parts = link.split('-')
                if len(parts) == 2:
                    reverse_link = f"{parts[1]}-{parts[0]}"
                    if reverse_link not in protected_links:
                        protected_links.append(reverse_link)
    
    return protected_links

def filter_links_to_close(predicted_links: list, protected_links: list) -> list:
    """Filter out protected links from predicted links to close
    
    Args:
        predicted_links: Links predicted by the model to be closed
        protected_links: Links that user wants to keep open
        
    Returns:
        list: Filtered links excluding protected ones
    """
    if not protected_links:
        return predicted_links
    
    filtered_links = [link for link in predicted_links if link not in protected_links]
    
    if len(filtered_links) != len(predicted_links):
        excluded = [link for link in predicted_links if link in protected_links]
        print(f"🔒 Excluded protected links: {excluded}")
        print(f"📋 Filtered links to close: {filtered_links}")
    
    return filtered_links

def filter_links_by_topology(predicted_links: list) -> list:
    """
    Filter out links that contain nodes not present in the current topology
    
    Args:
        predicted_links: Links predicted by the model to be closed
        
    Returns:
        list: Filtered links excluding those with unopened nodes
    """
    try:
        # Get current topology to find available nodes
        from restconf_processor import fetch_all_nodes
        available_nodes = fetch_all_nodes()
        
        if not available_nodes:
            print("⚠️  No nodes found in topology, returning empty list")
            return []
        
        # Extract node numbers from available nodes (e.g., 'node1' -> 'S1')
        available_switches = set()
        for node_id in available_nodes:
            if 'node' in node_id:
                try:
                    node_num = node_id.replace('node', '')
                    switch_name = f"S{node_num}"
                    available_switches.add(switch_name)
                except ValueError:
                    continue
        
        print(f"🔍 Available switches in topology: {sorted(available_switches)}")
        
        # Filter links to only include those where both nodes are available
        valid_links = []
        for link in predicted_links:
            if '-' in link:
                try:
                    source, target = link.split('-', 1)
                    if source in available_switches and target in available_switches:
                        valid_links.append(link)
                    else:
                        print(f"🚫 Filtered out link {link}: {source} or {target} not in topology")
                except ValueError:
                    print(f"⚠️  Invalid link format: {link}")
            else:
                print(f"⚠️  Invalid link format: {link}")
        
        print(f"✅ Topology filtering: {len(predicted_links)} -> {len(valid_links)} links")
        return valid_links
        
    except Exception as e:
        print(f"⚠️  Error filtering links by topology: {e}")
        print("   Returning original links as fallback")
        return predicted_links

@app.post("/output")
async def post_output(request: OutputRequest):
    """Process user message with full network analysis pipeline"""
    try:
        # Extract message and settings from request body
        user_prompt = request.message
        print(f"📨 Received user message: {user_prompt}")
        
        # Parse protected links from user message (includes bidirectional pairs)
        protected_links = parse_protected_links(user_prompt)
        if protected_links:
            print(f"🔒 Protected links found (including bidirectional): {protected_links}")
        
        # Get fresh telemetry data and predictions
        telemetry_data = collector()
        links_to_close = predict_links_to_close_rl(telemetry_data)
        
        # Filter out links to nodes not in current topology
        topology_filtered_links = filter_links_by_topology(links_to_close)
        
        # Filter out protected links from the prediction
        filtered_links_to_close = filter_links_to_close(topology_filtered_links, protected_links)
        
        # Run LLM inference with user message and filtered links
        # Pass the filtered links to ensure RESTCONF commands only include allowed links
        result, commands, energy_saving = llm_inference(user_prompt=user_prompt, predicted_links=filtered_links_to_close)
        
        return {
            "llm_result": result,
            "restconf_commands": commands,
            "energy_saving_percentage": f"{energy_saving:.1%}",
            "predicted_links_to_close": filtered_links_to_close,
            "protected_links": protected_links,
            "original_prediction": links_to_close,
            "topology_filtered_prediction": topology_filtered_links
        }
    except Exception as e:
        print(f"❌ Error in POST /output: {e}")
        raise HTTPException(status_code=500, detail=str(e))
        
@app.get("/output")
async def get_output():
    """Get LLM inference result with network analysis"""
    try:
        # Get fresh telemetry data and predictions
        telemetry_data = collector()
        links_to_close = predict_links_to_close_rl(telemetry_data)
        
        # Filter out links to nodes not in current topology
        topology_filtered_links = filter_links_by_topology(links_to_close)
        
        # Run LLM inference with topology-filtered links
        result, commands, energy_saving = llm_inference(predicted_links=topology_filtered_links)
        
        return {
            "llm_result": result, 
            "restconf_commands": commands,
            "energy_saving_percentage": f"{energy_saving:.1%}",
            "predicted_links_to_close": topology_filtered_links,
            "original_prediction": links_to_close,
            "topology_filtered_prediction": topology_filtered_links
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 新增端點：使用RL模型預測要關閉的link
@app.get("/predict-links-rl")
async def predict_links_rl():
    """使用RL模型來預測應該關閉哪些link"""
    try:
        # Get raw telemetry data (simple float values)
        raw_telemetry = collector()
        
        # Convert to format expected by RL model
        telemetry_data = {}
        for link, traffic_value in raw_telemetry.items():
            if isinstance(traffic_value, (int, float)):
                telemetry_data[link] = {
                    'traffic': traffic_value,
                    'output-drops': 0,  # Simulated values since we don't have real drop data
                    'output-queue-drops': 0,
                    'max-capacity': 8000
                }
        
        links_to_close = predict_links_to_close_rl(telemetry_data)
        
        # Filter out links to nodes not in current topology
        topology_filtered_links = filter_links_by_topology(links_to_close)
        
        # Process topology-filtered links into RESTCONF commands
        file_commands, api_commands, configs, commands_file, config_files = process_predicted_links(topology_filtered_links)
        
        return {
            "telemetry_data": telemetry_data,
            "predicted_links_to_close": topology_filtered_links,
            "original_prediction": links_to_close,
            "topology_filtered_prediction": topology_filtered_links,
            "restconf_commands": api_commands,
            "commands_file": str(commands_file),
            "config_files": [str(f) for f in config_files],
            "model_info": rl_manager.get_model_info()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 新增端點：獲取RL模型信息
@app.get("/rl-model-info")
async def get_rl_model_info():
    """獲取RL模型信息"""
    try:
        model_info = rl_manager.get_model_info()
        return model_info
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 新增端點：查看telemetry數據如何轉換為模型特徵
@app.get("/telemetry-features")
async def get_telemetry_features():
    """獲取當前telemetry數據及其轉換為模型特徵的詳細信息"""
    try:
        # 收集當前telemetry數據
        raw_telemetry = collector(use_rates=True, measurement_interval=5)
        
        # 轉換為模型期望的格式
        telemetry_data = {}
        for link, traffic_value in raw_telemetry.items():
            if isinstance(traffic_value, (int, float)):
                telemetry_data[link] = {
                    'traffic': traffic_value,
                    'output-drops': 0,  # 模擬值
                    'output-queue-drops': 0,  # 模擬值
                    'max-capacity': 8000  # 模擬值
                }
        
        # 獲取模型的預處理特徵
        features = rl_manager.preprocess_telemetry_data(telemetry_data)
        
        # 創建詳細的特徵解釋
        feature_details = []
        feature_names = [
            "buffer_utilization",
            "link_utilization", 
            "link_status",
            "buffer_change_rate",
            "util_change_rate",
            "time_since_change",
            "normalized_node_degree"
        ]
        
        for i, link in enumerate(rl_manager.links):
            link_features = {}
            
            # 原始telemetry數據
            raw_data = telemetry_data.get(link, {})
            
            # 模型特徵
            if i < len(features):
                for j, feature_name in enumerate(feature_names):
                    link_features[feature_name] = float(features[i][j]) if j < len(features[i]) else 0.0
            
            # 計算詳細信息
            traffic = raw_data.get('traffic', 0)
            max_capacity = raw_data.get('max-capacity', 1000)
            output_drops = raw_data.get('output-drops', 0)
            output_queue_drops = raw_data.get('output-queue-drops', 0)
            total_drops = output_drops + output_queue_drops
            
            # 計算推導值
            drop_rate = total_drops / max(1, traffic + total_drops) if (traffic + total_drops) > 0 else 0
            calculated_buffer_util = min(1.0, drop_rate * 10)
            calculated_link_util = min(1.0, traffic / max_capacity) if max_capacity > 0 else 0.0
            
            feature_details.append({
                "link": link,
                "raw_telemetry": {
                    "traffic_bytes_per_sec": traffic,
                    "max_capacity": max_capacity,
                    "output_drops": output_drops,
                    "output_queue_drops": output_queue_drops,
                    "total_drops": total_drops,
                    "drop_rate": drop_rate
                },
                "calculated_metrics": {
                    "buffer_utilization": calculated_buffer_util,
                    "link_utilization": calculated_link_util,
                    "utilization_percentage": calculated_link_util * 100
                },
                "model_features": link_features,
                "feature_explanations": {
                    "buffer_utilization": f"Estimated from drop rate: {drop_rate:.4f} * 10 = {calculated_buffer_util:.4f}",
                    "link_utilization": f"Traffic/Capacity: {traffic}/{max_capacity} = {calculated_link_util:.4f}",
                    "link_status": "1.0 = UP, 0.0 = DOWN (currently assumed UP)",
                    "buffer_change_rate": "Change in buffer utilization from previous measurement",
                    "util_change_rate": "Change in link utilization from previous measurement",
                    "time_since_change": "Time since last link state change (simplified to 0)",
                    "normalized_node_degree": "Node connectivity degree normalized to [0,1]"
                }
            })
        
        return {
            "timestamp": telemetry_data.get('timestamp', 'unknown'),
            "measurement_interval_seconds": 5,
            "total_links": len(rl_manager.links),
            "features_per_link": len(feature_names),
            "feature_names": feature_names,
            "model_input_shape": list(features.shape) if features is not None else None,
            "link_details": feature_details,
            "summary": {
                "avg_buffer_utilization": float(np.mean([f["model_features"]["buffer_utilization"] for f in feature_details])),
                "avg_link_utilization": float(np.mean([f["model_features"]["link_utilization"] for f in feature_details])),
                "max_link_utilization": float(np.max([f["model_features"]["link_utilization"] for f in feature_details])),
                "links_with_drops": len([f for f in feature_details if f["raw_telemetry"]["total_drops"] > 0]),
                "active_links": len([f for f in feature_details if f["raw_telemetry"]["traffic_bytes_per_sec"] > 0])
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting telemetry features: {str(e)}")

# 新增端點：載入文檔到RAG系統
@app.post("/load-document")
async def load_document(file_path: str, force_reload: bool = False):
    """載入文檔到RAG系統"""
    try:
        rag_system.load_documents(file_path, force_reload=force_reload)
        return {
            "message": f"Document {file_path} loaded successfully",
            "document_info": rag_system.get_document_info()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 新增端點：獲取RAG系統信息
@app.get("/rag-info")
async def get_rag_info():
    """獲取RAG系統信息"""
    try:
        return rag_system.get_document_info()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 新增端點：搜索相關文檔
@app.get("/search-documents")
async def search_documents(query: str, top_k: int = 3):
    """搜索相關文檔"""
    try:
        results = rag_system.retrieve_relevant_docs(query, top_k=top_k)
        return {
            "query": query,
            "results": results,
            "total_found": len(results)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 新增端點：獲取拓撲信息
@app.get("/topology-info")
async def get_topology_info():
    """獲取網路拓撲信息，包含所有節點和介面的真實IPv4地址"""
    try:
        from restconf_processor import fetch_topology_info
        topology_data = fetch_topology_info()
        return {
            "topology_info": topology_data,
            "total_interfaces": len(topology_data),
            "message": "Complete topology information fetched successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 新增端點：下載RESTCONF命令文件
@app.get("/download-commands")
async def download_commands(filename: str = None):
    """下載生成的RESTCONF命令文件"""
    try:
        output_dir = Path("restconf_output")
        
        if filename:
            # Download specific file
            file_path = output_dir / filename
            if not file_path.exists():
                raise HTTPException(status_code=404, detail=f"File {filename} not found")
        else:
            # Download the most recent commands file
            command_files = list(output_dir.glob("restconf_commands_*.txt"))
            if not command_files:
                raise HTTPException(status_code=404, detail="No command files found")
            
            # Get the most recent file
            file_path = max(command_files, key=lambda f: f.stat().st_mtime)
        
        return FileResponse(
            path=str(file_path),
            filename=file_path.name,
            media_type="text/plain"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 新增端點：列出所有可用的命令文件
@app.get("/list-command-files")
async def list_command_files():
    """列出所有可用的RESTCONF命令文件"""
    try:
        output_dir = Path("restconf_output")
        
        if not output_dir.exists():
            return {"files": [], "message": "No output directory found"}
        
        # Get all command files
        command_files = list(output_dir.glob("restconf_commands_*.txt"))
        config_files = list(output_dir.glob("config_*.json"))
        
        file_info = []
        
        # Add command files info
        for file_path in command_files:
            stat = file_path.stat()
            file_info.append({
                "filename": file_path.name,
                "type": "commands",
                "size": stat.st_size,
                "created": stat.st_mtime,
                "download_url": f"/download-commands?filename={file_path.name}"
            })
        
        # Add config files info
        for file_path in config_files:
            stat = file_path.stat()
            file_info.append({
                "filename": file_path.name,
                "type": "config",
                "size": stat.st_size,
                "created": stat.st_mtime,
                "download_url": f"/download-config?filename={file_path.name}"
            })
        
        # Sort by creation time (newest first)
        file_info.sort(key=lambda x: x["created"], reverse=True)
        
        return {
            "files": file_info,
            "total_files": len(file_info),
            "command_files": len(command_files),
            "config_files": len(config_files)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 新增端點：下載配置文件
@app.get("/download-config")
async def download_config(filename: str):
    """下載生成的JSON配置文件"""
    try:
        output_dir = Path("restconf_output")
        file_path = output_dir / filename
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail=f"Config file {filename} not found")
        
        return FileResponse(
            path=str(file_path),
            filename=file_path.name,
            media_type="application/json"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 新增端點：執行單一連結關閉命令
@app.post("/close-link")
async def close_link(link: str):
    """Execute close command for a specific link"""
    try:
        # Validate link format
        if not link or '-' not in link:
            raise HTTPException(status_code=400, detail="Invalid link format. Expected format: S1-S2")
        
        # Apply topology filtering to ensure the link is valid
        topology_filtered_links = filter_links_by_topology([link])
        
        if not topology_filtered_links:
            raise HTTPException(
                status_code=400, 
                detail=f"Link {link} contains nodes not present in current topology"
            )
        
        # Build and execute the shutdown command
        commands = build_shutdown_commands([link], for_file=False)
        
        if not commands:
            raise HTTPException(
                status_code=400, 
                detail=f"No interface mapping found for link {link}"
            )
        
        # Execute the command using requests
        import subprocess
        import shlex
        from datetime import datetime
        
        command = commands[0]
        print(f"🔧 Executing close command for link {link}")
        print(f"📝 Command: {command}")
        
        # Execute the curl command
        try:
            # Parse the curl command to extract components
            if 'curl' in command:
                # Execute the command directly
                result = subprocess.run(
                    shlex.split(command), 
                    capture_output=True, 
                    text=True, 
                    timeout=30
                )
                
                if result.returncode == 0:
                    print(f"✅ Successfully closed link {link}")
                    status = "success"
                    message = f"Link {link} has been successfully closed"
                    output = result.stdout
                else:
                    print(f"❌ Failed to close link {link}: {result.stderr}")
                    status = "error"
                    message = f"Failed to close link {link}"
                    output = result.stderr
            else:
                raise ValueError("Invalid command format")
                
        except subprocess.TimeoutExpired:
            status = "timeout"
            message = f"Command timeout while closing link {link}"
            output = "Command execution timed out"
        except Exception as e:
            status = "error"
            message = f"Error executing command: {str(e)}"
            output = str(e)
        
        return {
            "link": link,
            "status": status,
            "message": message,
            "command": command,
            "output": output,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error in close-link endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))
