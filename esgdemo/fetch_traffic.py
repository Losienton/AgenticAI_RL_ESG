import requests
import json
import random
import os

# API base URL
BASE_URL = os.getenv("AI_BACKEND_URL", "http://127.0.0.1:8000")
REQUEST_TIMEOUT = float(os.getenv("AI_BACKEND_TIMEOUT", "30"))

def fetch_telemetry_data(mode="test"):
    """Fetch and display raw telemetry JSON data."""
    if mode == "test":
        # Fixed 2026-03-10: matched to UNL network_id physical links (33 links x 2 = 66 entries)
        test_keys = [
            "S1-S2","S2-S1","S1-S3","S3-S1","S1-S4","S4-S1","S1-S9","S9-S1",
            "S2-S4","S4-S2","S2-S9","S9-S2",
            "S3-S4","S4-S3","S3-S9","S9-S3",
            "S4-S5","S5-S4","S4-S6","S6-S4","S4-S7","S7-S4","S4-S8","S8-S4",
            "S4-S9","S9-S4","S4-S10","S10-S4","S4-S11","S11-S4","S4-S15","S15-S4",
            "S5-S9","S9-S5","S6-S15","S15-S6","S7-S9","S9-S7","S8-S9","S9-S8",
            "S9-S10","S10-S9","S9-S15","S15-S9",
            "S10-S12","S12-S10","S10-S13","S13-S10",
            "S10-S14","S14-S10","S10-S16","S16-S10","S10-S17","S17-S10",
            "S11-S15","S15-S11","S12-S15","S15-S12","S13-S15","S15-S13",
            "S14-S15","S15-S14","S15-S16","S16-S15","S15-S17","S17-S15",
        ]
        data = {key: random.randint(50, 1000) for key in test_keys}

        return data
    
    else:
        try:
            response = requests.get(f"{BASE_URL}/telemetry", timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            data = response.json()
            # print("\n🔶 Raw Telemetry JSON Data:")
            # print(json.dumps(data, indent=2, ensure_ascii=False))            
            return data
        
        except requests.RequestException as e:
            print(f"Error fetching telemetry data: {e}")
            return None
