"""RAG factory — provider abstraction for policy document retrieval.

Selects the RAG provider based on the RAG_PROVIDER env var:

  "faiss"      → Local FAISS index on PVC (k3d, sentence-transformers)
  "s3vectors"  → AWS S3 Vectors (real AWS or Floci)
  "mock"       → Fallback: return first 8000 chars (backward compat)

This mirrors the LLM provider pattern in llm_helper.py: the agent code
calls retrieve_policy_chunks() without knowing which backend is active.

Env vars:
  RAG_PROVIDER           = faiss | s3vectors | mock  (default: faiss)
  RAG_INDEX_PATH         = path to FAISS index files  (faiss only)
  VECTOR_BUCKET_NAME     = S3 vector bucket name      (s3vectors only)
  VECTOR_INDEX_NAME      = S3 vector index name       (s3vectors only)
  RAG_EMBEDDING_PROVIDER = bedrock | local            (s3vectors only)
"""

import os
from typing import Dict, List, Optional


def get_provider() -> str:
    """Get the configured RAG provider."""
    return os.environ.get("RAG_PROVIDER", "faiss")


def build_index(policies: Dict[str, str], index_path: Optional[str] = None) -> dict:
    """Build the RAG index for all policy documents.

    Args:
        policies: {policy_id: policy_text}
        index_path: required for faiss provider (path on PVC)

    Returns:
        Dict with stats: {chunks, vectors, policies, dim}
    """
    provider = get_provider()

    if provider == "faiss":
        from .rag_faiss import build_index as _build
        if index_path is None:
            index_path = os.environ.get("RAG_INDEX_PATH", "/app/data/rag_index")
        return _build(policies, index_path)

    elif provider == "s3vectors":
        from .rag_s3vectors import build_index as _build
        return _build(policies)

    else:
        # mock: no indexing needed
        return {"chunks": 0, "vectors": 0, "policies": len(policies), "dim": 0}


def retrieve_policy_chunks(
    query: str,
    policy_id: str,
    top_k: int = 5,
) -> List[str]:
    """Retrieve relevant policy chunks for a query.

    This is the main entry point used by check_policy.py and the agent.
    It delegates to the configured provider.

    Args:
        query: natural language query (e.g. "coverage limit for fire damage")
        policy_id: filter to this policy's chunks
        top_k: number of chunks to retrieve

    Returns:
        List of chunk text strings, most relevant first.
    """
    provider = get_provider()

    if provider == "faiss":
        from .rag_faiss import retrieve as _retrieve
        index_path = os.environ.get("RAG_INDEX_PATH", "/app/data/rag_index")
        return _retrieve(query, policy_id, index_path, top_k)

    elif provider == "s3vectors":
        from .rag_s3vectors import retrieve as _retrieve
        return _retrieve(query, policy_id, top_k)

    else:
        # mock: return empty list
        return []


def index_exists() -> bool:
    """Check if the RAG index has been built.

    For faiss: checks if .faiss file exists.
    For s3vectors: always True (index is managed by AWS).
    For mock: always True.
    """
    provider = get_provider()

    if provider == "faiss":
        index_path = os.environ.get("RAG_INDEX_PATH", "/app/data/rag_index")
        return os.path.exists(f"{index_path}.faiss")

    return True
