"""Chunking — split contract text into overlapping chunks for RAG indexing.

Shared by all RAG providers (FAISS, S3 Vectors, mock). The chunking
parameters are tuned for CUAD contracts (~54k chars average):

  CHUNK_SIZE   = 1000 chars  (~250 tokens, fits easily in 4096 context)
  CHUNK_OVERLAP = 200 chars  (preserves context across chunk boundaries)

This gives ~55 chunks per contract × 510 contracts ≈ 28 000 vectors.
"""

from typing import List

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """Split text into overlapping chunks.

    Args:
        text: the input text (e.g. a contract).
        size: max characters per chunk.
        overlap: number of characters shared between consecutive chunks.

    Returns:
        List of chunk strings. A 54 000-char contract yields ~68 chunks.
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


def build_query_from_invoice(invoice: dict) -> str:
    """Build a natural-language query from invoice fields for RAG retrieval.

    The query is what gets embedded and used for similarity search against
    contract chunks. It should contain the key terms that might match
    contract clauses: payment amounts, dates, line item descriptions.

    Args:
        invoice: the invoice dict from the DuckDB /invoices table.

    Returns:
        A query string like:
        "payment terms total 1500.00 due 2024-03-15 late penalty fee
         management fee weekend surcharge"
    """
    parts = [
        "payment terms",
        f"total {invoice.get('total_amount', '')}",
        f"expected {invoice.get('expected_amount', '')}",
        f"due date {invoice.get('due_date', '')}",
        f"invoice date {invoice.get('invoice_date', '')}",
    ]

    # Extract line item descriptions if present in metadata
    metadata = invoice.get("metadata", {})
    if isinstance(metadata, dict):
        for key in ("description", "service", "item"):
            val = metadata.get(key)
            if val:
                parts.append(str(val))

    # Common fee-related keywords to match contract clauses
    parts.extend(["late penalty", "fee", "discount", "surcharge", "management fee"])

    return " ".join(str(p) for p in parts if p)
