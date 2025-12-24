import requests
import uuid
import time

BASE_URL = "http://localhost:8001"

def test_security():
    print("--- Security Verification v2 ---")
    
    # 1. Register a user
    print("\n1. Registering user...")
    register_payload = {
        "email": f"test_{uuid.uuid4().hex[:8]}@example.com",
        "password": "testpassword123",
        "name": "Test User",
        "is_admin": True
    }
    resp = requests.post(f"{BASE_URL}/v1/auth/register", json=register_payload)
    print(f"Status: {resp.status_code}")
    print(f"Body: {resp.json()}")
    if resp.status_code != 200: return
    
    user_id = resp.json()["user_id"]
    
    # 2. Login
    print("\n2. Logging in...")
    login_payload = {
        "email": register_payload["email"],
        "password": register_payload["password"]
    }
    resp = requests.post(f"{BASE_URL}/v1/auth/token", json=login_payload)
    print(f"Status: {resp.status_code}")
    print(f"Body: {resp.json()}")
    if resp.status_code != 200: return
    
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # 3. Access protected endpoint with JWT
    print("\n3. Accessing /v1/auth/keys with JWT...")
    resp = requests.get(f"{BASE_URL}/v1/auth/keys", headers=headers)
    print(f"Status: {resp.status_code}")
    print(f"Count: {len(resp.json())}")
    
    # 4. Create API Key
    print("\n4. Creating API Key...")
    key_payload = {
        "name": "My Verification Key",
        "client_id": "verify_script",
        "scopes": ["memories:read", "memories:write"],
        "is_admin": False
    }
    resp = requests.post(f"{BASE_URL}/v1/auth/keys", json=key_payload, headers=headers)
    print(f"Status: {resp.status_code}")
    if resp.status_code != 200: return
    
    api_key = resp.json()["api_key"]
    print(f"API Key: {api_key}")
    
    # 5. Access memories with API Key
    print("\n5. Accessing /v1/memories with X-API-KEY...")
    key_headers = {"X-API-KEY": api_key}
    resp = requests.get(f"{BASE_URL}/v1/memories", headers=key_headers)
    print(f"Status: {resp.status_code}")
    print(f"Body: {resp.json()}")

    # 6. Test unauthorized
    print("\n6. Testing unauthorized access...")
    resp = requests.get(f"{BASE_URL}/v1/memories")
    print(f"Status: {resp.status_code} (Expected 401)")

if __name__ == "__main__":
    test_security()
