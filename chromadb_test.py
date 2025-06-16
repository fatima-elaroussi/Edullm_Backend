import chromadb

client = chromadb.PersistentClient(path="./chroma_db")

collections = client.list_collections()

if not collections:
    print("⚠️ No collections found.")
else:
    for col in collections:
        collection = client.get_collection(col.name)
        docs = collection.get()
        print(f"📚 Collection '{col.name}' contains {len(docs['ids'])} document(s).")
