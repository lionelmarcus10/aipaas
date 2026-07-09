"""RAG provider: FAISS — local vector search for k3d.

Uses sentence-transformers/all-MiniLM-L6-v2 (22.7M params, 88MB, 384 dims)
to generate embeddings, and FAISS (IndexFlatIP) for similarity search.

The FAISS index and metadata are persisted as files on the PVC alongside
the DuckDB database. The init container builds the index once at startup.

Files produced:
  {index_path}.faiss  — FAISS index (binary)
  {index_path}.meta   — pickled list of {policy_id, chunk_idx, text}

Usage:
  from .rag_faiss import build_index, retrieve

  # Indexing (one-time, in init container)
  build_index(policies, "/app/data/rag_index")

  # Retrieval (at runtime, in check_policy)
  chunks = retrieve("coverage limit for fire", "POL-0001", "/app/data/rag_index")
"""

import os
import pickle
from pathlib import Path
from typing import Dict, List, Optional

import faiss
import numpy as np

from .chunking import chunk_text, CHUNK_SIZE, CHUNK_OVERLAP

# all-MiniLM-L6-v2 produces 384-dimensional vectors
EMBED_DIM = 384
DEFAULT_TOP_K = 5

# Lazy-loaded embedding model (88MB, loaded once per process)
_embedder = None


def get_embedder():
    """Get or create the shared SentenceTransformer instance.

    The model is downloaded from Hugging Face on first use (~88MB) and
    cached in ~/.cache/huggingface/ for subsequent loads.
    """
    global _embedder
    if _embedder is None:
        from sentence_transformers import SentenceTransformer

        _embedder = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    return _embedder


def embed_texts(texts: List[str]) -> np.ndarray:
    """Embed a list of texts into normalized float32 vectors.

    Normalization enables cosine similarity via inner product (IndexFlatIP).
    """
    embedder = get_embedder()
    vectors = embedder.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return np.array(vectors, dtype=np.float32)


def embed_query(query: str) -> np.ndarray:
    """Embed a single query string into a normalized float32 vector."""
    return embed_texts([query])[0]


def build_index(policies: Dict[str, str], index_path: str) -> dict:
    """Build a FAISS index from policy documents.

    Args:
        policies: {policy_id: policy_text} for all policies.
        index_path: base path for the .faiss and .meta files
                    (e.g. "/app/data/rag_index").

    Returns:
        Dict with stats: {chunks, vectors, policies, dim}
    """
    print("  [rag_faiss] Building FAISS index...")

    all_chunks: List[str] = []
    metadata: List[dict] = []

    for policy_id, text in policies.items():
        chunks = chunk_text(text)
        for i, chunk in enumerate(chunks):
            all_chunks.append(chunk)
            metadata.append(
                {
                    "policy_id": policy_id,
                    "chunk_idx": i,
                    "text": chunk,
                }
            )

    if not all_chunks:
        raise ValueError("No chunks to index — policies dict is empty")

    print(f"  [rag_faiss] Embedding {len(all_chunks)} chunks...")
    vectors = embed_texts(all_chunks)

    # Build FAISS index: IndexFlatIP = inner product = cosine (normalized vectors)
    index = faiss.IndexFlatIP(EMBED_DIM)
    index.add(vectors)

    # Persist index + metadata
    faiss_path = f"{index_path}.faiss"
    meta_path = f"{index_path}.meta"

    # Ensure directory exists
    Path(index_path).parent.mkdir(parents=True, exist_ok=True)

    faiss.write_index(index, faiss_path)
    with open(meta_path, "wb") as f:
        pickle.dump(metadata, f)

    stats = {
        "chunks": len(all_chunks),
        "vectors": index.ntotal,
        "policies": len(policies),
        "dim": EMBED_DIM,
    }
    print(
        f"  [rag_faiss] Index saved: {stats['vectors']} vectors, "
        f"{stats['policies']} policies, dim={stats['dim']}"
    )
    return stats


# In-memory cache for the loaded index (avoid re-reading from PVC on every call)
_loaded_index: Optional[faiss.Index] = None
_loaded_metadata: Optional[List[dict]] = None
_loaded_path: Optional[str] = None


def _load_index(index_path: str):
    """Load FAISS index and metadata, with in-memory caching."""
    global _loaded_index, _loaded_metadata, _loaded_path

    if _loaded_path == index_path and _loaded_index is not None:
        return _loaded_index, _loaded_metadata

    faiss_path = f"{index_path}.faiss"
    meta_path = f"{index_path}.meta"

    if not os.path.exists(faiss_path):
        raise FileNotFoundError(f"FAISS index not found at {faiss_path}")

    _loaded_index = faiss.read_index(faiss_path)
    with open(meta_path, "rb") as f:
        _loaded_metadata = pickle.load(f)
    _loaded_path = index_path

    return _loaded_index, _loaded_metadata


def retrieve(
    query: str,
    policy_id: str,
    index_path: str,
    top_k: int = DEFAULT_TOP_K,
) -> List[str]:
    """Retrieve relevant policy chunks for a query.

    Args:
        query: natural language query (e.g. "coverage limit for fire damage").
        policy_id: filter results to this policy only.
        index_path: base path for the .faiss and .meta files.
        top_k: number of chunks to return.

    Returns:
        List of chunk text strings, most relevant first.
    """
    index, metadata = _load_index(index_path)

    # Embed the query
    query_vec = embed_query(query).reshape(1, -1)

    # Search ALL vectors, then filter by policy_id
    search_k = index.ntotal
    scores, indices = index.search(query_vec, search_k)

    # Filter by policy_id and take top_k
    results = []
    for idx, score in zip(indices[0], scores[0]):
        if idx < 0:
            continue
        meta = metadata[idx]
        if meta["policy_id"] == policy_id:
            results.append(meta["text"])
        if len(results) >= top_k:
            break

    return results
