"""Tool 3 : compute_variance

État 4 (Choice gate) du Step Functions.
Calcule l'écart exact entre le montant facturé et le montant attendu.

Input:  {"total_amount": 1725.0, "expected_amount": 1500.0}
Output: {"variance_pct": 15.0, "variance_abs": 225.0, "decision": "DISPUTE"}

Pas de LLM : calcul mathématique pur + routing déterministe.
"""

from dataclasses import dataclass


# Seuils de routing (configurable)
VARIANCE_OK_THRESHOLD = 0.0       # écart == 0% → PAY
VARIANCE_PARTIAL_THRESHOLD = 5.0  # écart ≤ 5% → PARTIAL_PAY
CONFIDENCE_THRESHOLD = 80.0       # confiance < 80% → HUMAN_REVIEW


@dataclass
class VarianceResult:
    variance_pct: float
    variance_abs: float
    decision: str  # PAY | PARTIAL_PAY | DISPUTE | HUMAN_REVIEW


def compute_variance(
    total_amount: float,
    expected_amount: float,
    confidence: float = 100.0,
) -> dict:
    """Compute the variance between invoiced and expected amounts.

    The routing logic is deterministic:
    - confidence < 80%           → HUMAN_REVIEW (regardless of variance)
    - variance == 0%             → PAY
    - 0% < variance ≤ 5%         → PARTIAL_PAY
    - variance > 5%              → DISPUTE

    Args:
        total_amount: The total amount on the invoice.
        expected_amount: The expected amount from the contract.
        confidence: LLM confidence score (0-100). Defaults to 100.

    Returns:
        Dict with variance_pct, variance_abs, and decision.
    """
    if expected_amount == 0:
        return {
            "variance_pct": 0.0,
            "variance_abs": total_amount,
            "decision": "HUMAN_REVIEW",
            "reason": "expected_amount is zero — cannot compute variance",
        }

    variance_abs = round(total_amount - expected_amount, 2)
    variance_pct = round((variance_abs / expected_amount) * 100, 2)

    # Routing déterministe
    if confidence < CONFIDENCE_THRESHOLD:
        decision = "HUMAN_REVIEW"
        reason = f"confidence {confidence}% < {CONFIDENCE_THRESHOLD}%"
    elif variance_pct == VARIANCE_OK_THRESHOLD:
        decision = "PAY"
        reason = "variance is zero"
    elif variance_pct <= VARIANCE_PARTIAL_THRESHOLD:
        decision = "PARTIAL_PAY"
        reason = f"variance {variance_pct}% ≤ {VARIANCE_PARTIAL_THRESHOLD}%"
    else:
        decision = "DISPUTE"
        reason = f"variance {variance_pct}% > {VARIANCE_PARTIAL_THRESHOLD}%"

    return {
        "variance_pct": variance_pct,
        "variance_abs": variance_abs,
        "decision": decision,
        "reason": reason,
    }
