"""State 7: FRAUD_CHECK — compute supplier trust score.

Script only, no LLM.
"""

from ..tools.compute_trust_score import compute_trust_score


def handler(event: dict) -> dict:
    """Compute the trust score for the supplier.

    Input:  {"supplier_id": "SUP-001", "affected_orders": {...}, ...}
    Output: adds "trust_assessment" to the event
    """
    supplier_id = event["supplier_id"]
    trust = compute_trust_score(supplier_id)

    return {
        **event,
        "state": "FRAUD_CHECK",
        "trust_assessment": trust,
    }
