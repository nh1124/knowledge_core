"""
Knowledge Core Test Client

A command-line test script to verify all API endpoints.
Run with: python test_client.py

Requires the server to be running on http://localhost:8000
"""
import httpx
import json
import asyncio
from datetime import datetime

BASE_URL = "http://localhost:8000"
API_KEY = "cortex_secret_key_2025"  # Must match .env
HEADERS = {"X-API-KEY": API_KEY}


async def test_health():
    """Test health endpoints."""
    print("\n" + "="*60)
    print("Testing Health Endpoints")
    print("="*60)
    
    async with httpx.AsyncClient() as client:
        # Root endpoint
        response = await client.get(f"{BASE_URL}/", headers=HEADERS)
        print(f"\n✓ GET / : {response.status_code}")
        print(f"  Response: {response.json()}")
        
        # Health check
        response = await client.get(f"{BASE_URL}/health", headers=HEADERS)
        print(f"\n✓ GET /health : {response.status_code}")
        print(f"  Response: {response.json()}")


async def test_ingest():
    """Test text ingestion with AI extraction (Async with Polling)."""
    print("\n" + "="*60)
    print("Testing POST /v1/ingest (AI Text Analysis - ASYNC)")
    print("="*60)
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        # Test with sample text
        payload = {
            "text": "私はJohnといいます。東京大学で光工学を研究しています。最近、腰が痛くて困っています。昨日、指導教官の田中先生と論文について相談しました。",
            "source": "test_client",
            "scope": "global",
        }
        
        print(f"\n→ Sending text: {payload['text'][:50]}...")
        response = await client.post(f"{BASE_URL}/v1/ingest", json=payload, headers=HEADERS)
        print(f"\n✓ POST /v1/ingest : {response.status_code}")
        
        if response.status_code != 202:
            print(f"  Error: {response.text}")
            return []
            
        result = response.json()
        job_id = result.get("ingest_id")
        print(f"  Job ID: {job_id}")
        
        # Polling for completion
        print("  Polling for results...")
        max_attempts = 30
        for i in range(max_attempts):
            await asyncio.sleep(2)
            poll_resp = await client.get(f"{BASE_URL}/v1/ingest/{job_id}", headers=HEADERS)
            job_data = poll_resp.json()
            status = job_data.get("status")
            print(f"    - Attempt {i+1}: Status = {status}")
            
            if status == "completed":
                print(f"\n  ✅ Ingestion Completed!")
                print(f"    Created: {job_data.get('created_count', 0)}")
                print(f"    Updated: {job_data.get('updated_count', 0)}")
                print(f"    Skipped: {job_data.get('skipped_count', 0)}")
                print(f"    Memory IDs: {job_data.get('memory_ids', [])}")
                return job_data.get('memory_ids', [])
            elif status == "failed":
                print(f"  ❌ Job Failed: {job_data.get('errors')}")
                return []
        
        print("  ❌ Polling timed out")
        return []


async def test_force_create():
    """Test direct memory creation (bypass AI)."""
    print("\n" + "="*60)
    print("Testing POST /v1/memories (Force Create)")
    print("="*60)
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        payload = {
            "content": f"ユーザーのAPIキー (Test {datetime.now().strftime('%H%M%S')}): test_key_12345",
            "memory_type": "fact",
            "tags": ["credentials", "api"],
            "scope": "global",
            "importance": 5,
            "confidence": 1.0,
            "source": "test_client_force",
        }
        
        print(f"\n→ Creating FACT: {payload['content']}")
        response = await client.post(f"{BASE_URL}/v1/memories", json=payload, headers=HEADERS)
        print(f"\n✓ POST /v1/memories : {response.status_code}")
        result = response.json()
        print(f"  Created memory ID: {result.get('id')}")
        print(f"  Type: {result.get('memory_type')}")
        print(f"  Tags: {result.get('tags')}")
        
        return result.get('id')


async def test_search(query: str = None):
    """Test memory search."""
    print("\n" + "="*60)
    print("Testing GET /v1/memories (Search)")
    print("="*60)
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        params = {"limit": 10}
        if query:
            params["q"] = query
        
        print(f"\n→ Searching with params: {params}")
        response = await client.get(f"{BASE_URL}/v1/memories", params=params, headers=HEADERS)
        print(f"\n✓ GET /v1/memories : {response.status_code}")
        result = response.json()
        print(f"  Total memories: {result.get('total', 0)}")
        
        for mem in result.get('memories', [])[:5]:
            print(f"\n  [{mem['memory_type']}] {mem['content'][:60]}...")
            print(f"    ID: {mem['id']}")
            print(f"    Tags: {mem['tags']}")
            if 'similarity' in mem:
                print(f"    Similarity: {mem['similarity']:.3f}")
        
        return result.get('memories', [])


async def test_context(query: str):
    """Test RAG context synthesis."""
    print("\n" + "="*60)
    print("Testing POST /v1/context (RAG Synthesis)")
    print("="*60)
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        payload = {
            "query": query,
            "k": 5,
            "return_evidence": True,
        }
        
        print(f"\n→ Query: {query}")
        response = await client.post(f"{BASE_URL}/v1/context", json=payload, headers=HEADERS)
        print(f"\n✓ POST /v1/context : {response.status_code}")
        result = response.json()
        
        context = result.get('context', {})
        print(f"\n  Summary: {context.get('summary', 'N/A')}")
        print(f"  Bullets:")
        for bullet in context.get('bullets', []):
            print(f"    • {bullet}")
        
        if result.get('evidence'):
            print(f"\n  Evidence ({len(result['evidence'])} memories):")
            for ev in result['evidence'][:3]:
                print(f"    - {ev['content'][:50]}... (score: {ev['score']:.3f})")
        
        return result


async def test_update(memory_id: str):
    """Test memory update."""
    print("\n" + "="*60)
    print("Testing PATCH /v1/memories/{id} (Update)")
    print("="*60)
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        payload = {
            "tags": ["updated", "test"],
            "importance": 4,
        }
        
        print(f"\n→ Updating memory: {memory_id}")
        response = await client.patch(f"{BASE_URL}/v1/memories/{memory_id}", json=payload, headers=HEADERS)
        print(f"\n✓ PATCH /v1/memories/{memory_id} : {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"  Updated tags: {result.get('tags')}")
            print(f"  Updated importance: {result.get('importance')}")
        else:
            print(f"  Error: {response.text}")


async def test_delete(memory_id: str):
    """Test memory deletion."""
    print("\n" + "="*60)
    print("Testing DELETE /v1/memories/{id} (Delete)")
    print("="*60)
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        print(f"\n→ Deleting memory: {memory_id}")
        response = await client.delete(f"{BASE_URL}/v1/memories/{memory_id}", headers=HEADERS)
        print(f"\n✓ DELETE /v1/memories/{memory_id} : {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"  Status: {result.get('status')}")
        else:
            print(f"  Error: {response.text}")


async def run_all_tests():
    """Run all tests."""
    print("\n" + "#"*60)
    print("  KNOWLEDGE CORE API TEST SUITE")
    print(f"  Started: {datetime.now().isoformat()}")
    print("#"*60)
    
    try:
        # 1. Health checks
        await test_health()
        
        # 2. AI-powered ingestion
        memory_ids = await test_ingest()
        
        # 3. Force create
        force_id = await test_force_create()
        
        # 4. Search (all)
        await test_search()
        
        # 5. Semantic search
        await test_search("光工学の研究について")
        
        # 6. RAG context
        await test_context("ユーザーの健康状態について教えてください")
        
        # 7. Update
        if force_id:
            await test_update(force_id)
        
        # 8. Delete (the force-created one)
        # if force_id:
        #     #await test_delete(force_id)
            

        print("\n" + "="*60)
        print("✅ ALL TESTS COMPLETED SUCCESSFULLY")
        print("="*60 + "\n")
        
    except httpx.ConnectError:
        print("\n❌ ERROR: Could not connect to server at", BASE_URL)
        print("   Make sure the server is running: start_service.bat")
    except Exception as e:
        print(f"\n❌ ERROR: {type(e).__name__}: {e}")


if __name__ == "__main__":
    asyncio.run(run_all_tests())
