"""RAG provider: FAISS — local vector search for k3d.

Uses sentence-transformers/all-MiniLM-L6-v2 (22.7M params, 88MB, 384 dims)
to generate embeddings, and FAISS (IndexFlatIP) for similarity search.

The FAISS index and metadata are persisted as files on the PVC alongside
the DuckDB database. The init container builds the index once at startup.

Files produced:
  {index_path}.faiss  — FAISS index (binary)
  {index_path}.meta   — pickled list of {supplier_id, chunk_idx, text}

Usage:
  from .rag_faiss import build_index, retrieve

  # Indexing (one-time, in init container)
  build_index(contracts, "/app/data/rag_index")

  # Retrieval (at runtime, in fetch_contract)
  chunks = retrieve("late payment penalty", "SUP-001", "/app/data/rag_index")
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


def build_index(contracts: Dict[str, str], index_path: str) -> dict:
    """Build a FAISS index from supplier contracts.

    Args:
        contracts: {supplier_id: contract_text} for all suppliers.
        index_path: base path for the .faiss and .meta files
                    (e.g. "/app/data/rag_index").

    Returns:
        Dict with stats: {chunks, vectors, suppliers, dim}
    """
    print("  [rag_faiss] Building FAISS index...")

    all_chunks: List[str] = []
    metadata: List[dict] = []

    for supplier_id, text in contracts.items():
        chunks = chunk_text(text)
        for i, chunk in enumerate(chunks):
            all_chunks.append(chunk)
            metadata.append(
                {
                    "supplier_id": supplier_id,
                    "chunk_idx": i,
                    "text": chunk,
                }
            )

    if not all_chunks:
        raise ValueError("No chunks to index — contracts dict is empty")

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
        "suppliers": len(contracts),
        "dim": EMBED_DIM,
    }
    print(
        f"  [rag_faiss] Index saved: {stats['vectors']} vectors, "
        f"{stats['suppliers']} suppliers, dim={stats['dim']}"
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
    supplier_id: str,
    index_path: str,
    top_k: int = DEFAULT_TOP_K,
) -> List[str]:
    """Retrieve relevant contract chunks for a query.

    Args:
        query: natural language query (e.g. "late payment penalty terms").
        supplier_id: filter results to this supplier only.
        index_path: base path for the .faiss and .meta files.
        top_k: number of chunks to return.

    Returns:
        List of chunk text strings, most relevant first.
    """
    index, metadata = _load_index(index_path)

    # Embed the query
    query_vec = embed_query(query).reshape(1, -1)

    # Search ALL vectors, then filter by supplier_id.
    # With 33k vectors, IndexFlatIP search is still <100ms on CPU.
    # This ensures we don't miss relevant chunks from the target supplier
    # just because other suppliers have higher-scoring chunks.
    search_k = index.ntotal
    scores, indices = index.search(query_vec, search_k)

    # Filter by supplier_id and take top_k
    results = []
    for idx, score in zip(indices[0], scores[0]):
        if idx < 0:
            continue
        meta = metadata[idx]
        if meta["supplier_id"] == supplier_id:
            results.append(meta["text"])
        if len(results) >= top_k:
            break

    return results
