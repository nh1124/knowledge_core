"""
Antigravity Cortex - Client Usage Sample
This script demonstrates how to interact with the Knowledge Core API.
"""
import httpx
import time
import json

# Configuration
API_BASE = "http://localhost:8000"
API_KEY = "cortex_secret_key_2025"  # From .env
HEADERS = {
    "X-API-KEY": API_KEY,
    "Content-Type": "application/json"
}

def print_result(title, data):
    print(f"\n=== {title} ===")
    print(json.dumps(data, indent=2, ensure_ascii=False))

def main():
    with httpx.Client(base_url=API_BASE, headers=HEADERS, timeout=30.0) as client:
        # 1. Health Check (Public)
        print("Checking service health...")
        health = client.get("/health").json()
        print(f"Status: {health['status']}")

        # 2. Asynchronous Ingestion
        # AI will extract memories from this text
        print("\nIngesting text asynchronously...")
        ingest_text = "私は東京に住んでいる研究者です。最近はGeminiを使ったAI開発に熱中しています。昨日は素晴らしいコードを書きました。"
        ingest_resp = client.post("/v1/ingest", json={
            "text": ingest_text,
            "source": "sample_client",
            "scope": "global"
        }).json()
        
        job_id = ingest_resp["ingest_id"]
        print(f"Ingestion started. Job ID: {job_id}")

        # Poll for completion
        while True:
            job_status = client.get(f"/v1/ingest/{job_id}").json()
            print(f"Job Status: {job_status['status']}")
            if job_status["status"] in ["completed", "failed"]:
                print_result("Ingestion Result", job_status)
                break
            time.sleep(2)

        # 3. Semantic Search
        # Uses pgvector to find relevant memories
        print("\nSearching for relevant memories...")
        search_query = "AI開発について教えて"
        search_results = client.get("/v1/memories", params={
            "q": search_query,
            "limit": 5
        }).json()
        print_result(f"Search Results for: '{search_query}'", search_results)

        # 4. Context Synthesis (RAG)
        # Synthesizes a context block based on retrieved memories
        print("\nSynthesizing context for RAG...")
        context_resp = client.post("/v1/context", json={
            "query": "ユーザーはどのような活動をしていますか？",
            "k": 10
        }).json()
        print_result("Synthesized Context", context_resp["context"])

if __name__ == "__main__":
    main()
