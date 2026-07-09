"""State 4: CHOICE_GATE — deterministic routing based on audit results.

Script only, no LLM. Uses compute_variance for the routing logic.
"""

from ..tools.compute_variance import compute_variance


def handler(event: dict) -> dict:
    """Route based on variance and confidence.

    Input:  {"audit_report": {...}, "invoice": {...}, ...}
    Output: adds "decision" and routes to next state
    """
    audit = event.get("audit_report", {})
    invoice = event["invoice"]

    # Use the LLM's variance if available, otherwise compute it
    variance_pct = audit.get("variance_pct", invoice.get("variance_pct", 0))
    confidence = audit.get("confidence", 100)

    # Compute the deterministic decision
    result = compute_variance(
        total_amount=invoice["total_amount"],
        expected_amount=invoice["expected_amount"],
        confidence=confidence,
    )

    return {
        **event,
        "state": "CHOICE_GATE",
        "decision": result["decision"],
        "variance_pct": result["variance_pct"],
        "variance_abs": result["variance_abs"],
        "decision_reason": result["reason"],
    }
