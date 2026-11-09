import hashlib
import math
import os
import re
import time

import requests

BACKEND = os.getenv("EMBED_BACKEND", "ollama")      # "ollama" for real use, "hash" for tests
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")
BATCH = 32


class EmbeddingError(RuntimeError):
    pass


def _unit(vec):
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


def _hash_vector(text):
    """Test double: word-hash vectors, so tests need no model."""
    vec = [0.0] * 256
    for word in re.findall(r"[a-z0-9]+", text.lower()):
        vec[int(hashlib.md5(word.encode()).hexdigest(), 16) % 256] += 1.0
    return vec


def _ollama_batch(texts, tries):
    last = "unknown error"
    for attempt in range(1, tries + 1):
        try:
            r = requests.post(f"{OLLAMA_URL}/api/embed", timeout=120,
                              json={"model": EMBED_MODEL, "input": texts})
            if r.status_code == 200:
                return r.json()["embeddings"]
            last = f"HTTP {r.status_code}: {r.text[:100]}"
        except requests.RequestException as e:
            last = type(e).__name__
        if attempt < tries:
            time.sleep(attempt)
    raise EmbeddingError(f"Embedding service unavailable ({last}). "
                         f"Is Ollama running with the {EMBED_MODEL} model?")


def embed(texts, kind="document"):
    """One unit-length vector per text. kind is 'document' or 'query'."""
    if not texts:
        return []
    if BACKEND == "hash":
        return [_unit(_hash_vector(t)) for t in texts]
    prefix = f"search_{kind}: " if "nomic" in EMBED_MODEL else ""
    tries = 1 if kind == "query" else 3        # a question should fail fast
    out = []
    for i in range(0, len(texts), BATCH):
        batch = [prefix + t for t in texts[i:i + BATCH]]
        out.extend(_unit(v) for v in _ollama_batch(batch, tries))
    return out