MODE = "real"

from flask import Flask, jsonify, request, send_from_directory
import traceback
import requests
import os, sqlite3, json, datetime

# 匯入自定義模組（沿用你原有的設計）
from ai_model_use import get_network_config
from fetch_traffic import fetch_telemetry_data

app = Flask(__name__)

DB_FILE = os.path.join(os.path.dirname(__file__), "history.db")

# ---------- SQLite 初始化與存取 ----------
def ensure_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            user_note TEXT,
            hosts_json TEXT,
            matrix_json TEXT,
            evaluation_result TEXT,
            preview TEXT
        )
    """)
    conn.commit()
    conn.close()

def save_history(user_note, hosts, matrix, evaluation_result):
    hosts_json = json.dumps(hosts, ensure_ascii=False)
    matrix_json = json.dumps(matrix, ensure_ascii=False)
    created_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # 取一小段摘要做列表預覽
    preview_src = (evaluation_result or "").replace("\n", " ")
    preview = (preview_src[:180] + "…") if len(preview_src) > 180 else preview_src

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        INSERT INTO history (created_at, user_note, hosts_json, matrix_json, evaluation_result, preview)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (created_at, user_note, hosts_json, matrix_json, evaluation_result, preview))
    conn.commit()
    new_id = c.lastrowid
    conn.close()
    return new_id, created_at

def get_history_page(page:int, page_size:int):
    page = max(1, page)
    page_size = max(1, min(page_size, 100))
    offset = (page - 1) * page_size

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM history")
    total = c.fetchone()[0]

    c.execute("""
        SELECT id, created_at, user_note, preview
        FROM history
        ORDER BY id DESC
        LIMIT ? OFFSET ?
    """, (page_size, offset))
    rows = c.fetchall()
    conn.close()

    items = []
    for rid, created_at, user_note, preview in rows:
        items.append({
            "id": rid,
            "created_at": created_at,
            "user_note": user_note or "",
            "preview": preview or ""
        })
    return total, items

def get_history_item(item_id:int):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        SELECT id, created_at, user_note, hosts_json, matrix_json, evaluation_result
        FROM history
        WHERE id = ?
    """, (item_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    rid, created_at, user_note, hosts_json, matrix_json, evaluation_result = row
    return {
        "id": rid,
        "created_at": created_at,
        "user_note": user_note or "",
        "hosts_json": hosts_json or "[]",
        "matrix_json": matrix_json or "[]",
        "evaluation_result": evaluation_result or ""
    }

# 啟動時確保 DB 存在
ensure_db()

@app.route('/')
def index():
    try:
        return send_from_directory(app.static_folder, 'index.html')
    except Exception as e:
        print("[ERROR - index route]", traceback.format_exc())
        return jsonify({
            "status": "error",
            "message": "Failed to load index.html",
            "error": str(e)
        }), 500

@app.route('/api/fetch', methods=['POST'])
def api_fetch():
    try:
        data = fetch_telemetry_data(mode=MODE)
        if data is None:
            return jsonify({
                "success": False,
                "message": "Failed to fetch telemetry data from backend.",
                "error": "Backend telemetry endpoint is unreachable."
            }), 502
        return jsonify({
            "success": True,
            "message": "Telemetry data fetched successfully.",
            "data": data
        }), 200
    except requests.RequestException as e:
        print("[ERROR - fetch telemetry - request]", traceback.format_exc())
        return jsonify({
            "success": False,
            "message": "Failed to fetch telemetry data.",
            "error": str(e)
        }), 500
    except Exception as e:
        print("[ERROR - fetch telemetry - general]", traceback.format_exc())
        return jsonify({
            "success": False,
            "message": "Unexpected error occurred while fetching telemetry data.",
            "error": str(e)
        }), 500

@app.route('/api/evaluate', methods=['POST'])
def api_evaluate():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "未接收到資料"}), 400

        hosts = data.get("hosts", [])
        matrix = data.get("matrix", [])
        user_input = data.get("user_note", "")

        # 取得設定回覆（沿用你的模型流程）
        try:
            result_string, commands_string, saving_string = get_network_config(user_input, mode=MODE)
        except ValueError as ve:
            print("[ERROR - get_network_config - ValueError]", traceback.format_exc())
            return jsonify({
                "status": "error",
                "message": "輸入格式錯誤，請檢查內容",
                "error": str(ve)
            }), 400
        except Exception as inner_e:
            print("[ERROR - get_network_config - general]", traceback.format_exc())
            return jsonify({
                "status": "error",
                "message": "取得網路設定時發生錯誤",
                "error": str(inner_e)
            }), 500

        # 格式化節能百分比
        try:
            saving_float = float(saving_string.strip('%'))
            saving_percent = f"{saving_float:.1f}%"
        except Exception:
            saving_percent = saving_string

        word_result = (
            "使用者備註回覆\n"
            + result_string
            + "\n=======================================================================\n"
            + "節能路徑設定指令參考\n"
            + commands_string
            + "\n=======================================================================\n"
            + f"\n以上操作預計可以減少 {saving_percent} 之能源消耗"
        )

        # 寫入歷史
        _new_id, _created_at = save_history(user_input, hosts, matrix, word_result)

        return jsonify({
            "status": "ok",
            "str_updated_links": {},     # 先保留你的前端邏輯欄位
            "evaluation_result": word_result
        })
    except Exception as e:
        print("[ERROR - api_evaluate]", traceback.format_exc())
        return jsonify({
            "status": "error",
            "message": "系統內部錯誤，請聯絡管理員。",
            "error": str(e)
        }), 500

# ---------- 新增：歷史查詢（分頁） ----------
@app.route('/api/history', methods=['GET'])
def api_history():
    try:
        page = int(request.args.get("page", 1))
        page_size = int(request.args.get("page_size", 10))
        total, items = get_history_page(page, page_size)
        return jsonify({
            "status": "ok",
            "page": page,
            "page_size": page_size,
            "total": total,
            "items": items
        })
    except Exception as e:
        print("[ERROR - api_history]", traceback.format_exc())
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/history/<int:item_id>', methods=['GET'])
def api_history_one(item_id):
    try:
        item = get_history_item(item_id)
        if not item:
            return jsonify({"status": "error", "message": "查無此紀錄"}), 404
        return jsonify({"status": "ok", "item": item})
    except Exception as e:
        print("[ERROR - api_history_one]", traceback.format_exc())
        return jsonify({"status": "error", "message": str(e)}), 500

BACKEND_URL = "http://localhost:8000"

@app.route('/api/act', methods=['POST'])
def api_act():
    """Proxy to backend /act endpoint (HOTL Stage 2: execute)"""
    try:
        payload = request.get_json() or {}
        resp = requests.post(f"{BACKEND_URL}/act", json=payload, timeout=120)
        return jsonify(resp.json()), resp.status_code
    except Exception as e:
        print("[ERROR - api_act]", traceback.format_exc())
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/act/restore', methods=['POST'])
def api_act_restore():
    """Proxy to backend /act/restore endpoint"""
    try:
        payload = request.get_json() or {}
        resp = requests.post(f"{BACKEND_URL}/act/restore", json=payload, timeout=120)
        return jsonify(resp.json()), resp.status_code
    except Exception as e:
        print("[ERROR - api_act_restore]", traceback.format_exc())
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host="127.0.0.1", port=5000)
