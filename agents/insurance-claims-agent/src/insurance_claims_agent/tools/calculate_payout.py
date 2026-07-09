"""Tool 5 : calculate_payout

Calcule l'indemnisation théorique : min(claim_amount, coverage_limit) - deductible - depreciation.

Input:  {"claim_amount": 45000, "coverage_limit": 50000, "deductible": 1000,
         "depreciation_pct": 10}
Output: {"payout_amount", "coverage_applied", "deductible_applied",
         "depreciation_amount", "is_within_limit"}

Pas de LLM : calcul mathématique pur.
"""


def calculate_payout(
    claim_amount: float,
    coverage_limit: float,
    deductible: float,
    depreciation_pct: float = 0.0,
) -> dict:
    """Calculate the theoretical payout for a claim.

    Formula: payout = min(claim_amount, coverage_limit) - deductible - depreciation
    where depreciation = min(claim_amount, coverage_limit) * depreciation_pct / 100

    Args:
        claim_amount: The claimed amount.
        coverage_limit: Maximum coverage from policy.
        deductible: Deductible amount from policy.
        depreciation_pct: Depreciation percentage (0-100).

    Returns:
        Dict with payout breakdown.
    """
    # Coverage is capped at the policy limit
    coverage_applied = min(claim_amount, coverage_limit)
    is_within_limit = claim_amount <= coverage_limit

    # Depreciation
    depreciation_amount = coverage_applied * (depreciation_pct / 100)

    # Payout = coverage - deductible - depreciation
    payout = coverage_applied - deductible - depreciation_amount

    # Payout can't be negative
    payout = max(0, payout)

    return {
        "payout_amount": round(payout, 2),
        "coverage_applied": round(coverage_applied, 2),
        "deductible_applied": deductible,
        "depreciation_amount": round(depreciation_amount, 2),
        "depreciation_pct": depreciation_pct,
        "is_within_limit": is_within_limit,
        "claim_amount": claim_amount,
        "coverage_limit": coverage_limit,
    }
