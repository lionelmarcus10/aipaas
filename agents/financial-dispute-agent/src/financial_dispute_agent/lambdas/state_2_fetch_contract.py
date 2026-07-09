"""State 2: FETCH_CONTRACT — retrieve supplier contract from CUAD.

Script only, no LLM.
"""

from ..tools.fetch_contract import fetch_contract


def handler(event: dict) -> dict:
    """Fetch the contract for the invoice's supplier.

    Uses RAG to retrieve only relevant contract chunks when available.
    The invoice is passed to fetch_contract to build the RAG query.

    Input:  {"supplier_id": "SUP-001", "invoice": {...}, ...}
    Output: adds "contract" to the event
    """
    supplier_id = event["supplier_id"]
    invoice = event.get("invoice", {})
    contract = fetch_contract(supplier_id, invoice=invoice)

    if "error" in contract:
        return {**event, "error": contract["error"], "state": "FETCH_CONTRACT"}

    return {
        **event,
        "state": "FETCH_CONTRACT",
        "contract": contract,
        "trust_score": contract["trust_score"],
        "rag_used": contract.get("rag_used", False),
    }
