
import os
import sys

# Add the parent directory to sys.path so we can import the sdk
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from knowledge_core_sdk import KnowledgeCoreClient

def main():
    # Simply provide your API Key or Login credentials
    API_KEY = os.environ.get("KC_API_KEY", "your_api_key_here")
    
    client = KnowledgeCoreClient(base_url="http://localhost:8200")
    client.set_api_key(API_KEY)

    try:
        # Search for memories
        print("Searching memories...")
        results = client.list_memories(query="research", limit=3)
        
        for mem in results.memories:
            print(f"- {mem.content}")

        # Get context for a query
        print("\nGetting context for RAG...")
        response = client.get_context("What has the user been working on recently?")
        print(f"AI Summary: {response.context.get('summary')}")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    main()
