from chromadb import PersistentClient

# Path to your ChromaDB folder
client = PersistentClient(path="./chroma_db")

# List all collections
collections = client.list_collections()
print("Collections found:")
for col in collections:
    print("-", col.name)

# Get a specific collection (replace with the actual collection name)
collection_name = "documents"
collection = client.get_collection(name=collection_name)

# Fetch all data
data = collection.get()

# Print the documents
print("\n--- DOCUMENTS ---")
for doc_id, doc in zip(data["ids"], data["documents"]):
    print(f"{doc_id}: {doc}")

# Print metadata
print("\n--- METADATA ---")
for meta in data.get("metadatas", []):
    print(meta)
