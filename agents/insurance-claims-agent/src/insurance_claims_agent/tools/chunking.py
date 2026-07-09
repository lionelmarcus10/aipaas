"""Chunking — split policy text into overlapping chunks for RAG indexing.

Shared by all RAG providers (FAISS, S3 Vectors, mock). The chunking
parameters are tuned for insurance policy documents (~5-15k chars):

  CHUNK_SIZE   = 1000 chars  (~250 tokens, fits easily in 4096 context)
  CHUNK_OVERLAP = 200 chars  (preserves context across chunk boundaries)

This gives ~10-15 chunks per policy × N policies ≈ 200-300 vectors.
"""

from typing import List

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """Split text into overlapping chunks.

    Args:
        text: the input text (e.g. a policy document).
        size: max characters per chunk.
        overlap: number of characters shared between consecutive chunks.

    Returns:
        List of chunk strings. A 10 000-char policy yields ~13 chunks.
    """
    if not text:
        return []

    chunks = []
    step = size - overlap
    for i in range(0, len(text), step):
        chunk = text[i : i + size]
        chunks.append(chunk)
        if i + size >= len(text):
            break

    return chunks


def build_query_from_claim(claim: dict) -> str:
    """Build a natural-language query from claim fields for RAG retrieval.

    The query is what gets embedded and used for similarity search against
    policy chunks. It should contain the key terms that might match
    policy clauses: coverage type, claim type, amount, exclusions.

    Args:
        claim: the claim dict from the DuckDB /claims table.

    Returns:
        A query string like:
        "coverage auto collision claim amount 5000 deductible
         exclusion natural disaster policy limit"
    """
    parts = [
        "coverage",
        claim.get("claim_type", ""),
        f"claim amount {claim.get('claim_amount', '')}",
        f"policy {claim.get('policy_id', '')}",
    ]

    # Add claim description keywords
    description = claim.get("description", "")
    if description:
        # Take first 200 chars of description for query context
        parts.append(description[:200])

    # Common policy-related keywords to match clauses
    parts.extend(["deductible", "exclusion", "coverage limit", "policy conditions"])

    return " ".join(str(p) for p in parts if p)
