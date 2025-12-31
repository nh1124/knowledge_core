
import os
import sys
import uuid
import json
from datetime import datetime

# Add the parent directory to sys.path so we can import the sdk
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from knowledge_core_sdk import KnowledgeCoreClient, AuthenticationError

def print_section(title):
    print("\n" + "="*80)
    print(f" {title}")
    print("="*80)

def main():
    # Configuration
    BASE_URL = os.environ.get("KC_BASE_URL", "http://localhost:8200")
    EMAIL = os.environ.get("KC_EMAIL", "demo@example.com")
    PASSWORD = os.environ.get("KC_PASSWORD", "password123")
    GEMINI_KEY = os.environ.get("GEMINI_API_KEY")

    if not GEMINI_KEY:
        print("WARNING: GEMINI_API_KEY not set. Some AI features will fail.")

    client = KnowledgeCoreClient(base_url=BASE_URL)

    try:
        # --- Auth Flow ---
        print_section("AUTHENTICATION & USER MANAGEMENT")
        
        # 1. Register (if needed)
        try:
            print(f"Attempting to register {EMAIL}...")
            client.register(EMAIL, PASSWORD, gemini_api_key=GEMINI_KEY or "dummy_key")
            print("✓ Registered successfully.")
        except Exception as e:
            print(f"Note: Registration skipped or failed (likely already exists): {e}")

        # 2. Login
        print(f"Logging in as {EMAIL}...")
        token_res = client.login(EMAIL, PASSWORD)
        print(f"✓ Logged in. User ID: {token_res.user_id}")

        # 3. Get Profile
        profile = client.get_my_profile()
        print(f"✓ Profile retrieved: {profile.name} ({profile.email})")

        # 4. API Key Management
        print("Creating an API key...")
        new_key = client.create_api_key(name="Demo Script Key", scopes=["memories:read", "memories:write", "context", "ingest"])
        api_key = new_key.api_key
        print(f"✓ API Key created: {api_key[:10]}...")

        # Switch to API Key Auth
        print("Switching authentication to API Key...")
        client.set_api_key(api_key)
        
        # Verify API Key
        key_info = client.get_my_key_info()
        print(f"✓ API Key verified. Name: {key_info.name}")

        # --- Ingestion ---
        print_section("AI-POWERED INGESTION")
        text = "I am a researcher working on outdoor lighting systems. I live in Tokyo and I'm currently finishing my master's thesis."
        print(f"Submitting text for ingestion: {text}")
        ingest_res = client.ingest_text(text, source="demo_script")
        print(f"✓ Ingestion job started: {ingest_res.ingest_id}")

        print("Waiting for ingestion to complete...")
        status = client.wait_for_ingestion(ingest_res.ingest_id)
        print(f"✓ Ingestion complete. Created: {status.get('created_count')}, Warnings: {status.get('warnings')}")

        # --- Memory CRUD ---
        print_section("MEMORY OPERATIONS")
        
        # 1. Create a manual memory
        print("Creating a manual memory...")
        manual_mem = client.create_memory(
            content="Water boils at 100 degrees Celsius at sea level.",
            memory_type="fact",
            tags=["science", "physics"]
        )
        print(f"✓ Manual memory created. ID: {manual_mem.id}")

        # 2. Search memories
        print("Searching for 'lighting'...")
        search_res = client.list_memories(query="lighting", limit=5)
        print(f"✓ Found {search_res.total} relevant memories.")
        for mem in search_res.memories:
            print(f"  - [{mem.memory_type}] {mem.content[:50]}...")

        # 3. Update memory
        print(f"Updating memory {manual_mem.id}...")
        updated_mem = client.update_memory(manual_mem.id, importance=5, tags=["science", "essential"])
        print(f"✓ Memory updated. New tags: {updated_mem.tags}")

        # --- Context synthesis ---
        print_section("CONTEXT SYNTHESIS (RAG)")
        query = "What is the user's research topic?"
        print(f"Synthesizing context for query: '{query}'")
        ctx_res = client.get_context(query=query)
        print("✓ Context synthesized:")
        print(f"  Summary: {ctx_res.context.get('summary')}")
        if ctx_res.evidence:
            print(f"  Evidence: {len(ctx_res.evidence)} memories found.")

        # --- Cleanup ---
        print_section("CLEANUP")
        print(f"Deleting memory {manual_mem.id}...")
        client.delete_memory(manual_mem.id, hard=True)
        print("✓ Memory deleted.")

        print(f"Revoking API Key {new_key.details.id}...")
        client.revoke_api_key(new_key.details.id)
        print("✓ API Key revoked.")

    except AuthenticationError as e:
        print(f"Auth Error: {e.message} (Status: {e.status_code})")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    main()
