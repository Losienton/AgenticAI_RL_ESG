# Agent Change Log (esgbackend + esgdemo)

- Generated at: `2026-02-09 00:37:57 CST`
- `esgdemo` HEAD: `9ffecf9`
- `esgbackend` HEAD: `d51abd5`

## 1) Final code changes kept in repo

### A. `esgdemo`

1. `esgdemo/ai_model_use.py`
- Added `import os`
- Changed:
  - from: `BASE_URL = "http://140.112.175.181:8000"`
  - to: `BASE_URL = os.getenv("AI_BACKEND_URL", "http://127.0.0.1:8000")`

2. `esgdemo/fetch_traffic.py`
- Added `import os`
- Changed:
  - from: `BASE_URL = "http://140.112.175.181:8000"`
  - to: `BASE_URL = os.getenv("AI_BACKEND_URL", "http://127.0.0.1:8000")`

### B. `esgbackend`

1. `esgbackend/telemetry/main.py`
- Added endpoint:
  - `GET /health`
  - Returns: `{"status": "ok"}`

## 2) Changes tried but reverted back

1. `esgdemo/app.py`
- Tried lock-down mode:
  - `app.run(debug=False, host="127.0.0.1", port=5000)`
- Reverted to original (current):
  - `app.run(debug=True, host="0.0.0.0", port=5000)`

2. `esgbackend/deploy.sh`
- Tried lock-down mode:
  - `uvicorn main:app --host 127.0.0.1 --port 8000`
- Reverted to original (current):
  - `uvicorn main:app --host 0.0.0.0 --port 8000`

## 3) Operational actions performed (non-code)

1. Created/used Python virtual environments:
- `esgbackend/venv`
- `esgdemo/venv`

2. Started services with tmux sessions:
- `esg-backend`
- `esg-demo`

3. Verified topology and service health during process:
- KVM VM `eve-ng-pro` running
- ODL RESTCONF topology reachable
- xrv9 (`node9`) mount readable

## 4) Current runtime notes

1. `tmux ls` at log time:
- `esg-backend: 1 windows`
- `esg-demo: 1 windows`

2. Runtime-generated files changed (not hand-edited source):
- `__pycache__/...`
- `uvicorn.log`
- `telemetry/unsloth_compiled_cache/...`
- `.locks/...`

These are execution artifacts and can be excluded from commits if desired.

## 5) Suggested commit scope (if you want clean source-only commit)

Include only:
- `esgdemo/ai_model_use.py`
- `esgdemo/fetch_traffic.py`
- `esgbackend/telemetry/main.py`

Exclude runtime artifacts:
- `venv/`
- `__pycache__/`
- `uvicorn.log`
- `telemetry/unsloth_compiled_cache/`

## 6) Update at 2026-02-09 (Security hardening + fetch fix)

### A. `esgdemo`

1. `esgdemo/app.py`
- Updated `/api/fetch`:
  - If telemetry fetch fails (`data is None`), now returns:
    - `success: false`
    - HTTP status `502`
  - Prevents frontend false-positive success response.
- Current run config at bottom:
  - `app.run(debug=True, host="127.0.0.1", port=5000)`

2. `esgdemo/fetch_traffic.py`
- Replaced hardcoded backend URL with env-driven setting:
  - from: `BASE_URL = "http://140.112.175.181:8000"`
  - to: `BASE_URL = os.getenv("AI_BACKEND_URL", "http://127.0.0.1:8000")`
- Added request timeout:
  - `REQUEST_TIMEOUT = float(os.getenv("AI_BACKEND_TIMEOUT", "8"))`
  - used in `requests.get(..., timeout=REQUEST_TIMEOUT)`

3. `esgdemo/README.md`
- Added secure startup note:
  - export `AI_BACKEND_URL=http://127.0.0.1:8000`
  - use SSH tunnel: `ssh -L 5000:127.0.0.1:5000 r11921A18@140.112.18.217`

### B. `esgbackend`

1. `esgbackend/deploy.sh`
- Local deploy now binds backend to loopback only:
  - from: `--host 0.0.0.0`
  - to: `--host 127.0.0.1`
- Output message updated to `http://127.0.0.1:8000`.

2. `esgbackend/README.md`
- Updated API startup example to `--host 127.0.0.1`
- Replaced public-IP API examples with loopback URLs.
