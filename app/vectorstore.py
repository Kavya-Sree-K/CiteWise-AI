import os
from pathlib import Path

import chromadb

BASE = Path(__file__).resolve().parent.parent
CHROMA_PATH = os.getenv("CHROMA_PATH", str(BASE / "data" / "chroma"))
_client = None


def _col():
    global _client
    if _client is None:
        Path(CHROMA_PATH).mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(path=CHROMA_PATH)
    return _client.get_or_create_collection("chunks", metadata={"hnsw:space": "cosine"})


def add(ids, vectors, metadatas, documents):
    col = _col()
    for i in range(0, len(ids), 200):
        col.add(ids=[str(x) for x in ids[i:i + 200]],
                embeddings=vectors[i:i + 200],
                metadatas=metadatas[i:i + 200],
                documents=documents[i:i + 200])


def delete_document(doc_id):
    _col().delete(where={"document_id": doc_id})


def reset():
    _col()
    _client.delete_collection("chunks")


def count():
    return _col().count()


def query(vector, doc_ids, n=15):
    """Nearest chunks, searched ONLY inside the allowed documents."""
    if not doc_ids:
        return []
    res = _col().query(query_embeddings=[vector], n_results=n,
                       where={"document_id": {"$in": list(doc_ids)}})
    return [(int(i), 1.0 - float(d)) for i, d in zip(res["ids"][0], res["distances"][0])]


def embeddings_for(ids):
    if not ids:
        return {}
    res = _col().get(ids=[str(i) for i in ids], include=["embeddings"])
    return {int(i): [float(x) for x in e] for i, e in zip(res["ids"], res["embeddings"])}