import requests
import json

BASE_URL = "http://127.0.0.1:8200/v1/auth"
LEGACY_KEY = "cortex_secret_key_2025"

def test_key_management():
    print("Testing Key Management API...")
    
    # 1. Create a key
    payload = {
        "name": "Integration Test Key",
        "client_id": "test_client_id",
        "scopes": ["memories:read", "context"],
        "is_admin": False
    }
    
    headers = {
        "X-API-KEY": LEGACY_KEY,
        "Content-Type": "application/json"
    }
    
    r = requests.post(f"{BASE_URL}/keys", headers=headers, json=payload)
    print(f"Create Key Status: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        new_key = data["api_key"]
        print(f"[PASS] Generated Key: {new_key}")
        
        # 2. List keys
        r = requests.get(f"{BASE_URL}/keys", headers=headers)
        print(f"List Keys Status: {r.status_code}")
        if r.status_code == 200:
            keys = r.json()
            print(f"[PASS] Found {len(keys)} keys.")
            
            # 3. Verify new key works
            r = requests.get("http://127.0.0.1:8200/v1/memories?limit=1", headers={"X-API-KEY": new_key})
            print(f"Verify New Key Status: {r.status_code}")
            if r.status_code == 200:
                print("[PASS] New key works for memory search.")
            else:
                print(f"[FAIL] New key failed: {r.text}")
        else:
            print(f"[FAIL] List keys failed: {r.text}")
    else:
        print(f"[FAIL] Create key failed: {r.text}")

if __name__ == "__main__":
    test_key_management()
