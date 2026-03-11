# 🌐 Network Traffic Visualization & AI Energy Saving Recommendation

## 📌 Overview
This project provides a **web-based platform** for:
- Visualizing a **17×17 network traffic matrix**  
- Rendering the **network topology graph** with D3.js  
- Submitting traffic data and receiving **AI-driven energy-saving strategies**  
- Storing and browsing **historical analysis results**

The backend is built with **Flask (Python)** and connects to AI/telemetry services, while the frontend uses **HTML, CSS, and JavaScript (D3.js)** for visualization.

---

## 🏗️ Project Structure
```
.
├── app.py              # Flask backend (API routes, DB handling, evaluation logic)
├── fetch_traffic.py    # Fetches telemetry data (test mode & API mode)
├── ai_model_use.py     # Connects to AI backend for strategy generation
├── history.db          # SQLite database (auto-created for history storage)
├── static/
│   ├── index.html      # Frontend page (traffic matrix + topology visualization)
│   ├── script.js       # D3.js logic + traffic submission & history modal
│   ├── style.css       # Styling for matrix, graph, modal, etc.
```

---

## ⚙️ Installation

### 1. Clone repository
```bash
git clone <your_repo_url>
cd <your_repo_name>
```

### 2. Setup Python environment
```bash
python3 -m venv venv
source venv/bin/activate   # Linux/macOS
venv\Scripts\activate      # Windows
```

### 3. Install dependencies
```bash
pip install flask requests
```

---

## 🚀 Usage

### 1. Start Flask backend
```bash
export AI_BACKEND_URL=http://127.0.0.1:8000
python app.py
```
This will:
- Initialize `history.db`
- Start API server (default: `http://127.0.0.1:5000`)

Security note:
- You may run `esgbackend` on `0.0.0.0:8000`, but block public access on port `8000` by firewall.
- Access frontend from your laptop using SSH tunnel:
```bash
ssh -L 5000:127.0.0.1:5000 r11921A18@140.112.18.217
```
- Then open `http://127.0.0.1:5000` on local browser.

### 2. Open frontend
Go to [http://127.0.0.1:5000](http://127.0.0.1:5000) in your browser.  
You will see:
- **Matrix table** (input or auto-filled traffic values)  
- **Graph visualization** (animated flows with red/black arrows)  
- **Buttons** for:
  - Fetching latest telemetry data  
  - Submitting traffic + notes to AI model  
  - Viewing historical records  

---

## 🔌 API Endpoints

- **`POST /api/fetch`**  
  Fetches latest telemetry data (random test mode or real API).  

- **`POST /api/evaluate`**  
  Sends traffic matrix & user note to AI backend (`ai_model_use.py`),  
  receives strategy and energy-saving percentage.  

- **`/api/history` (internal)**  
  Handles SQLite history storage & retrieval.  

---

## 🖥️ Frontend Features
- **Matrix editor**: 17×17 switch matrix auto-filled with random/test traffic  
- **D3.js topology graph**:
  - Red arrows = traffic from smaller ID → larger ID  
  - Black arrows = traffic from larger ID → smaller ID  
  - Link thickness & color intensity = traffic volume  
  - Nodes with glowing pulse when active  
- **Modal-based history viewer** with pagination  

---

## 📊 Example Workflow
1. Click **"取得最新流量資訊"** → system fetches telemetry  
2. Enter **user note/question** (e.g., "Suggest energy saving paths without closing S1-S2")  
3. Click **"問題提交&取得節能策略"** → AI backend responds with:  
   - Suggested strategy  
   - CLI commands  
   - Expected energy-saving percentage  
4. Results are displayed in frontend and stored in history

---

## 🗄️ Database
SQLite `history.db` auto-created with:
- `created_at` – timestamp  
- `user_note` – user input text  
- `hosts_json` / `matrix_json` – raw data  
- `evaluation_result` – AI analysis result  
- `preview` – summary snippet for modal list  

---

## 📌 Requirements
- Python 3.8+  
- Flask  
- Requests  
- Browser with JavaScript enabled (tested with Chrome)  

---

## 📖 License
This project is intended for research/demo purposes. Add your license here.
