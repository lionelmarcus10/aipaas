"""Tool 2 : fetch_contract

État 2 du Step Functions.
Récupère le contrat fournisseur depuis la DuckDB (source CUAD).

Input:  {"supplier_id": "SUP-001"}
Output: {"supplier_id", "supplier_name", "contract_text", "trust_score",
         "expected_amount", "rag_used": bool}

Avec RAG: au lieu de passer le contrat complet (~54k chars) au LLM,
on récupère seulement les chunks pertinents via similarity search.
Si RAG n'est pas disponible (mock provider), on fallback sur truncation.
"""

from .db import get_connection


def fetch_contract(supplier_id: str, invoice: dict | None = None) -> dict:
    """Fetch the contract and trust score for a given supplier.

    Uses RAG to retrieve only the relevant contract chunks when available.
    Falls back to truncation (8000 chars) if RAG is not configured.

    Args:
        supplier_id: The supplier identifier (e.g. "SUP-001").
        invoice: Optional invoice dict for building the RAG query.

    Returns:
        Dict with contract_text (RAG chunks or truncated), trust_score,
        supplier_name, or {"error": "..."}.
    """
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT supplier_id, supplier_name, contract_text, trust_score
            FROM suppliers
            WHERE supplier_id = ?
            """,
            [supplier_id],
        ).fetchone()

        if row is None:
            return {"error": f"Supplier {supplier_id} not found"}

        supplier_id, supplier_name, contract_text, trust_score = row

        # Try RAG retrieval first
        rag_used = False
        try:
            from .rag_factory import retrieve_contract_chunks, index_exists
            from .chunking import build_query_from_invoice

            if index_exists():
                query = build_query_from_invoice(invoice or {})
                chunks = retrieve_contract_chunks(query, supplier_id)

                if chunks:
                    contract_text = "\n\n---\n\n".join(chunks)
                    rag_used = True
        except Exception:
            # RAG not available — fall back to truncation
            pass

        # Fallback: truncate if RAG was not used
        if not rag_used:
            max_chars = 8000
            if len(contract_text) > max_chars:
                contract_text = contract_text[:max_chars] + "\n... [tronqué, RAG non disponible]"

        return {
            "supplier_id": supplier_id,
            "supplier_name": supplier_name,
            "contract_text": contract_text,
            "trust_score": trust_score,
            "contract_length": len(contract_text),
            "rag_used": rag_used,
        }
    finally:
        conn.close()
