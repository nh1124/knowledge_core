import requests
import uuid
import time
from jose import jwt

BASE_URL = "http://localhost:8000"
SECRET_KEY = "cortex_internal_secret_key_change_me_in_prod"
ALGORITHM = "HS256"

def test_security_v3():
    print("--- Security Verification v3 ---")
    
    email = f"v3_{uuid.uuid4().hex[:6]}@example.com"
    password = "password123"
    
    # 1. Register
    print("\n1. Registering user...")
    resp = requests.post(f"{BASE_URL}/v1/auth/register", json={
        "email": email,
        "password": password,
        "name": "V3 Tester"
    })
    print(f"Status: {resp.status_code}, Response: {resp.json()}")
    assert resp.status_code == 200
    user_id = resp.json()["user_id"]

    # 2. Login
    print("\n2. Logging in...")
    resp = requests.post(f"{BASE_URL}/v1/auth/login", json={
        "email": email,
        "password": password
    })
    print(f"Status: {resp.status_code}")
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 3. Test /v1/auth/me
    print("\n3. Testing /v1/auth/me...")
    resp = requests.get(f"{BASE_URL}/v1/auth/me", headers=headers)
    print(f"Status: {resp.status_code}, Data: {resp.json()}")
    assert resp.status_code == 200
    assert resp.json()["email"] == email

    # 4. Create API Key
    print("\n4. Creating API Key...")
    resp = requests.post(f"{BASE_URL}/v1/auth/keys", headers=headers, json={
        "name": "V3 Key",
        "client_id": "v3_client"
    })
    print(f"Status: {resp.status_code}")
    assert resp.status_code == 200
    api_key = resp.json()["api_key"]
    
    # 5. Test /v1/auth/keys/me (API Key Verify)
    print("\n5. Testing /v1/auth/keys/me with X-API-KEY...")
    key_headers = {"X-API-KEY": api_key}
    resp = requests.get(f"{BASE_URL}/v1/auth/keys/me", headers=key_headers)
    print(f"Status: {resp.status_code}, Data: {resp.json()}")
    assert resp.status_code == 200
    assert resp.json()["client_id"] == "v3_client"

    # 6. Link External JWT
    print("\n6. Linking mock External JWT...")
    # Mock external token
    ext_sub = f"ext_{uuid.uuid4().hex[:6]}"
    external_payload = {
        "sub": ext_sub,
        "iss": "external-system",
        "exp": time.time() + 3600
    }
    # We use the same secret for simplicity in this test, 
    # but in reality external system would have its own.
    external_token = jwt.encode(external_payload, SECRET_KEY, algorithm=ALGORITHM)
    
    link_headers = {
        "Authorization": f"Bearer {token}",
        "X-EXTERNAL-JWT": external_token
    }
    resp = requests.post(f"{BASE_URL}/v1/auth/link/confirm", headers=link_headers)
    print(f"Status: {resp.status_code}, Response: {resp.json()}")
    assert resp.status_code == 200
    assert resp.json()["linked"] == True

    # 7. Test resolve_identity with External Bearer Token
    print("\n7. Testing resolve_identity with external token as Bearer...")
    ext_auth_headers = {"Authorization": f"Bearer {external_token}"}
    resp = requests.get(f"{BASE_URL}/v1/auth/me", headers=ext_auth_headers)
    print(f"Status: {resp.status_code}, Response: {resp.json()}")
    assert resp.status_code == 200
    assert resp.json()["user_id"] == user_id
    assert resp.json()["auth_method"] == "external"

    # 8. Delete Account
    print("\n8. Deleting account...")
    print(f"Sending request to POST /v1/auth/delete-account with headers keys: {list(headers.keys())}")
    resp = requests.post(f"{BASE_URL}/v1/auth/delete-account", headers=headers)
    print(f"Status: {resp.status_code}, Response: {resp.json()}")
    assert resp.status_code == 200

    # 9. Verify deletion
    print("\n9. Verifying deletion...")
    resp = requests.get(f"{BASE_URL}/v1/auth/me", headers=headers)
    print(f"Status: {resp.status_code} (Expected non-200)")
    assert resp.status_code != 200

    print("\n--- Verification v3 Successful ---")

if __name__ == "__main__":
    try:
        test_security_v3()
    except Exception as e:
        print(f"\nVerification FAILED: {str(e)}")
        exit(1)
