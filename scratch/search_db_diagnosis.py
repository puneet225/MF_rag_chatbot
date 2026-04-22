import chromadb
import sys
from pathlib import Path

# Setup paths
ROOT_DIR = Path("/Users/puneetmall/RAG_mutual_fund_chatbot")
sys.path.insert(0, str(ROOT_DIR))

def search_date():
    persist_dir = str(ROOT_DIR / "chroma_db")
    client = chromadb.PersistentClient(path=persist_dir)
    try:
        collection = client.get_collection(name="hdfc_funds")
    except Exception as e:
        print(f"Error getting collection: {e}")
        return

    # Fetch all docs and check for the specific date
    all_docs = collection.get()
    
    found = False
    for i in range(len(all_docs['documents'])):
        doc = all_docs['documents'][i]
        if "2026-04-16" in doc:
            print(f"--- MATCH FOUND ---")
            print(f"ID: {all_docs['ids'][i]}")
            print(f"Metadata: {all_docs['metadatas'][i]}")
            print(f"Content: {doc}")
            found = True
            
    if not found:
        print("Date '2026-04-16' NOT found in any document in the vector store.")

if __name__ == "__main__":
    search_date()
