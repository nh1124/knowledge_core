"""
Knowledge Core - Client Usage Sample
=====================================
This script demonstrates how to interact with the Knowledge Core API 
from external applications using different authentication methods.

Authentication Methods:
1. JWT Token (for UI/User sessions) - Login with email/password
2. API Key (for M2M/Automation) - Use X-API-KEY header

API Endpoints:
- POST /v1/auth/login     - Get JWT token
- POST /v1/auth/register  - Create new user
- POST /v1/auth/keys      - Create API key
- GET  /v1/auth/me        - Get current user profile
- POST /v1/ingest         - AI-powered memory extraction
- GET  /v1/ingest/{id}    - Check ingestion status
- GET  /v1/memories       - Search memories
- POST /v1/memories       - Create memory directly
- GET  /v1/memories/{id}  - Get single memory
- PATCH /v1/memories/{id} - Update memory
- DELETE /v1/memories/{id}- Delete memory
- POST /v1/context        - RAG context synthesis
"""
import httpx
import time
import json
from typing import Optional

# ============================================================================
# Configuration
# ============================================================================
BASE_URL = "http://localhost:8200"  # Change to your server URL

# For development/testing with legacy key (if enabled in .env)
# LEGACY_API_KEY = "cortex_secret_key_2025"


# ============================================================================
# Client Class
# ============================================================================
class KnowledgeCoreClient:
    """Client for interacting with Knowledge Core API."""
    
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.token: Optional[str] = None
        self.api_key: Optional[str] = None
    
    def _get_headers(self) -> dict:
        """Build request headers with appropriate auth."""
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        elif self.api_key:
            headers["X-API-KEY"] = self.api_key
        return headers
    
    def _request(self, method: str, endpoint: str, **kwargs) -> dict:
        """Make an HTTP request."""
        with httpx.Client(base_url=self.base_url, timeout=30.0) as client:
            resp = client.request(method, endpoint, headers=self._get_headers(), **kwargs)
            resp.raise_for_status()
            return resp.json()
    
    # --- Authentication ---
    
    def register(self, email: str, password: str, gemini_api_key: str, name: str = None) -> dict:
        """Register a new user account (requires Gemini API key)."""
        return self._request("POST", "/v1/auth/register", json={
            "email": email,
            "password": password,
            "gemini_api_key": gemini_api_key,
            "name": name or "API User"
        })
    
    def login(self, email: str, password: str) -> str:
        """Login and get JWT token."""
        data = self._request("POST", "/v1/auth/login", json={
            "email": email,
            "password": password
        })
        self.token = data["access_token"]
        return self.token
    
    def use_api_key(self, api_key: str):
        """Set API key for authentication."""
        self.api_key = api_key
        self.token = None  # Clear JWT if using API key
    
    def create_api_key(self, name: str, scopes: list = None) -> dict:
        """Create a new API key (requires JWT auth)."""
        payload = {"name": name}
        if scopes:
            payload["scopes"] = scopes
        return self._request("POST", "/v1/auth/keys", json=payload)
    
    def get_profile(self) -> dict:
        """Get current user profile."""
        return self._request("GET", "/v1/auth/me")
    
    def update_settings(self, gemini_api_key: str = None) -> dict:
        """Update user settings (e.g., Gemini API key)."""
        payload = {}
        if gemini_api_key is not None:
            payload["gemini_api_key"] = gemini_api_key
        return self._request("PATCH", "/v1/auth/settings", json=payload)
    
    # --- Memory Operations ---
    
    def ingest(self, text: str, source: str = "api", scope: str = "global") -> str:
        """Submit text for AI-powered memory extraction. Returns job ID."""
        data = self._request("POST", "/v1/ingest", json={
            "text": text,
            "source": source,
            "scope": scope
        })
        return data["ingest_id"]
    
    def get_ingest_status(self, job_id: str) -> dict:
        """Check status of an ingestion job."""
        return self._request("GET", f"/v1/ingest/{job_id}")
    
    def wait_for_ingest(self, job_id: str, timeout: int = 60) -> dict:
        """Wait for ingestion to complete."""
        start = time.time()
        while time.time() - start < timeout:
            status = self.get_ingest_status(job_id)
            if status["status"] in ["completed", "failed"]:
                return status
            time.sleep(2)
        raise TimeoutError(f"Ingestion job {job_id} did not complete in {timeout}s")
    
    def search_memories(self, query: str = None, limit: int = 10, 
                        memory_type: str = None, tags: str = None) -> list:
        """Search memories using semantic similarity."""
        params = {"limit": limit}
        if query:
            params["q"] = query
        if memory_type:
            params["memory_type"] = memory_type
        if tags:
            params["tags"] = tags
        data = self._request("GET", "/v1/memories", params=params)
        return data["memories"]
    
    def create_memory(self, content: str, memory_type: str = "fact", 
                     importance: int = 3, tags: list = None) -> dict:
        """Create a memory directly (bypass AI extraction)."""
        return self._request("POST", "/v1/memories", json={
            "content": content,
            "memory_type": memory_type,
            "importance": importance,
            "tags": tags or [],
            "confidence": 1.0
        })
    
    def get_memory(self, memory_id: str) -> dict:
        """Get a single memory by ID."""
        return self._request("GET", f"/v1/memories/{memory_id}")
    
    def update_memory(self, memory_id: str, content: str = None, 
                     tags: list = None, importance: int = None) -> dict:
        """Update a memory."""
        payload = {}
        if content is not None:
            payload["content"] = content
        if tags is not None:
            payload["tags"] = tags
        if importance is not None:
            payload["importance"] = importance
        return self._request("PATCH", f"/v1/memories/{memory_id}", json=payload)
    
    def delete_memory(self, memory_id: str, hard: bool = False) -> dict:
        """Delete a memory (soft delete by default)."""
        return self._request("DELETE", f"/v1/memories/{memory_id}", params={"hard": hard})
    
    # --- Context (RAG) ---
    
    def synthesize_context(self, query: str, k: int = 10, 
                           return_evidence: bool = True) -> dict:
        """Retrieve and synthesize context for RAG applications."""
        return self._request("POST", "/v1/context", json={
            "query": query,
            "k": k,
            "return_evidence": return_evidence
        })


# ============================================================================
# Example Usage
# ============================================================================
def print_json(title: str, data):
    """Pretty print JSON data."""
    print(f"\n{'='*60}")
    print(f" {title}")
    print('='*60)
    print(json.dumps(data, indent=2, ensure_ascii=False))


def example_with_jwt(gemini_key: str = None):
    """Example: Using JWT authentication (for user sessions)."""
    print("\n" + "="*60)
    print(" EXAMPLE: JWT Authentication")
    print("="*60)
    
    client = KnowledgeCoreClient()
    
    # Register a new user (skip if already exists)
    # Note: Registration now requires a Gemini API key
    try:
        if not gemini_key:
            print("⚠️  Gemini API key required for registration.")
            print("   Set GEMINI_API_KEY environment variable or pass it to this function.")
            print("   Attempting login with existing user...")
        else:
            client.register("sample@example.com", "password123", 
                          gemini_api_key=gemini_key, name="Sample User")
            print("✓ User registered with Gemini key")
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 400:
            print("✓ User already exists")
        elif e.response.status_code == 422:
            print("⚠️  Registration failed - Gemini API key is required")
        else:
            raise
    
    # Login
    token = client.login("sample@example.com", "password123")
    print(f"✓ Logged in. Token: {token[:20]}...")
    
    # Get profile
    profile = client.get_profile()
    print_json("User Profile", profile)
    
    return client


def example_with_api_key(client: KnowledgeCoreClient):
    """Example: Creating and using an API key."""
    print("\n" + "="*60)
    print(" EXAMPLE: API Key Authentication")
    print("="*60)
    
    # Create API key (requires JWT) with full scopes
    key_data = client.create_api_key(
        "Sample Integration", 
        scopes=["ingest", "context", "memories:read", "memories:write"]
    )
    api_key = key_data["api_key"]
    print(f"✓ Created API Key: {api_key[:15]}...")
    print("  (Save this key! It won't be shown again)")
    
    # Switch to API key auth
    client.use_api_key(api_key)
    print("✓ Switched to API key authentication")
    
    return api_key


def example_update_settings(client: KnowledgeCoreClient, gemini_key: str = None):
    """Example: Updating user settings via API."""
    print("\n" + "="*60)
    print(" EXAMPLE: Update Settings via API")
    print("="*60)
    
    if gemini_key:
        result = client.update_settings(gemini_api_key=gemini_key)
        print(f"✓ Updated Gemini API key via PATCH /v1/auth/settings")
        print(f"  Response: {result}")
    else:
        print("⏭  Skipped (provide gemini_key to demo settings update)")


def example_memory_operations(client: KnowledgeCoreClient):
    """Example: Memory CRUD operations."""
    print("\n" + "="*60)
    print(" EXAMPLE: Memory Operations")
    print("="*60)
    
    # 1. AI Ingest
    print("\n--- AI-Powered Ingestion ---")
    text = """
    私は東京に住んでいる研究者です。
    光工学とAI技術の融合について研究しています。
    最近はGemini APIを使った記憶管理システムを開発しています。
    昨日は論文の締め切りがあり、徹夜で作業しました。
    """
    job_id = client.ingest(text, source="sample_script")
    print(f"✓ Ingestion started: {job_id}")
    
    result = client.wait_for_ingest(job_id)
    print(f"✓ Ingestion complete: {result['created_count']} memories created")
    
    # 2. Search memories
    print("\n--- List Memories ---")
    results = client.search_memories(limit=5)
    print(f"✓ Found {len(results)} memories")
    for mem in results[:3]:
        print(f"  - [{mem['memory_type']}] {mem['content'][:50]}...")


def example_rag_context(client: KnowledgeCoreClient):
    """Example: RAG context synthesis."""
    print("\n" + "="*60)
    print(" EXAMPLE: RAG Context Synthesis")
    print("="*60)
    
    query = "ユーザーの研究分野と最近の活動について教えてください"
    print(f"Query: {query}")
    
    context = client.synthesize_context(query, k=10, return_evidence=True)
    
    print(f"\n--- Summary ---")
    print(context["context"].get("summary", "N/A"))
    
    print(f"\n--- Key Points ---")
    for bullet in context["context"].get("bullets", []):
        print(f"  • {bullet}")
    
    if context.get("evidence"):
        print(f"\n--- Evidence ({len(context['evidence'])} memories) ---")
        for ev in context["evidence"][:3]:
            print(f"  [{ev['similarity']:.2%}] {ev['content'][:60]}...")


# ============================================================================
# Main
# ============================================================================
def main():
    import os
    
    print("="*60)
    print(" Knowledge Core - Client Sample")
    print("="*60)
    print(f"Connecting to: {BASE_URL}")
    
    # Get Gemini API key from environment (required for full demo)
    gemini_key = "AIzaSyDdShdAJLcNb1_fd7lGsZNE0we_k3PdmqI"#os.environ.get("GEMINI_API_KEY")
    if not gemini_key:
        print("\n⚠️  GEMINI_API_KEY environment variable not set.")
        print("   Some features will be limited.")
        print("   Set it with: set GEMINI_API_KEY=your_key_here")
    
    # Run examples
    client = example_with_jwt(gemini_key)
    example_update_settings(client, gemini_key)  # Must be before API key switch (requires JWT)
    example_with_api_key(client)
    example_memory_operations(client)
    example_rag_context(client)
    
    print("\n" + "="*60)
    print(" All examples completed!")
    print("="*60)


if __name__ == "__main__":
    main()
