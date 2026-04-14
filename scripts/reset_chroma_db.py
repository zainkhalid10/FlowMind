"""
Wipe all ChromaDB collections under FlowMind/chroma_db.
Run from repo:  python scripts/reset_chroma_db.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROMA_PATH = os.path.join(ROOT, "chroma_db")


def main() -> None:
    try:
        import chromadb
        from chromadb.config import Settings
    except ImportError as e:
        print("chromadb is required:", e)
        sys.exit(1)

    os.environ.setdefault("ANONYMIZED_TELEMETRY", "false")
    client = chromadb.PersistentClient(
        path=CHROMA_PATH,
        settings=Settings(anonymized_telemetry=False),
    )
    for col in client.list_collections():
        try:
            client.delete_collection(col.name)
            print(f"Deleted collection: {col.name}")
        except Exception as ex:
            print(f"Failed to delete {col.name}: {ex}")
    print(f"ChromaDB at {CHROMA_PATH} is wiped. Collections will be recreated on next server run.")


if __name__ == "__main__":
    main()
