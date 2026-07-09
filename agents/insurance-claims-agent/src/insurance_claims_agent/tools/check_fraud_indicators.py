"""Tool 4 : check_fraud_indicators

Vérifie les indicateurs de fraude (red flags) sur un sinistre.

Règles déterministes :
  1. claim_within_30_days : sinistre <30j après souscription de la police
  2. amount_3x_average : montant > 3x la moyenne des sinistres de ce type
  3. repeat_claims_6_months : ≥2 sinistres similaires en 6 mois
  4. no_police_report_high_amount : pas de rapport police pour sinistre > 10k€
  5. narrative_inconsistency : description incohérente (heuristique simple)

Input:  {"claim": {...}, "policy": {...}, "claim_history": {...}}
Output: {"red_flags": [...], "red_flag_count", "fraud_risk_level", "fraud_score"}

Pas de LLM : règles déterministes pures.
"""

from datetime import datetime


def check_fraud_indicators(
    claim: dict,
    policy: dict,
    claim_history: dict,
) -> dict:
    """Check fraud indicators for a claim.

    Args:
        claim: Parsed claim data (from parse_claim).
        policy: Policy data (from check_policy).
        claim_history: Claim history data (from check_claim_history).

    Returns:
        Dict with red flags, count, risk level, and fraud score.
    """
    red_flags = []

    # Rule 1: Claim within 30 days of policy start
    days_since_start = policy.get("days_since_start", 999)
    if days_since_start < 30:
        red_flags.append({
            "rule": "claim_within_30_days",
            "severity": "high",
            "detail": f"Claim filed only {days_since_start} days after policy start",
        })

    # Rule 2: Amount > 3x average for this claim type
    claim_amount = claim.get("claim_amount", 0)
    claim_type = claim.get("claim_type", "")
    history_claims = claim_history.get("claims", [])
    same_type_amounts = [c["claim_amount"] for c in history_claims if c["claim_type"] == claim_type]
    if same_type_amounts:
        avg_amount = sum(same_type_amounts) / len(same_type_amounts)
        if avg_amount > 0 and claim_amount > avg_amount * 3:
            red_flags.append({
                "rule": "amount_3x_average",
                "severity": "high",
                "detail": f"Claim amount {claim_amount} is >3x average ({avg_amount:.2f}) for {claim_type}",
            })

    # Rule 3: Repeat claims (≥2 similar in 6 months)
    if claim_history.get("has_repeat_claims", False):
        repeat_count = claim_history.get("total_claims", 0)
        red_flags.append({
            "rule": "repeat_claims_6_months",
            "severity": "medium",
            "detail": f"Customer has {repeat_count} previous claims with repeat types",
        })

    # Rule 4: No police report for high amount (>10k)
    if claim_amount > 10000 and not claim.get("police_report_filed", False):
        red_flags.append({
            "rule": "no_police_report_high_amount",
            "severity": "medium",
            "detail": f"Claim amount {claim_amount} > 10k but no police report filed",
        })

    # Rule 5: Narrative inconsistency (simple heuristic)
    description = claim.get("description", "").lower()
    claim_type_lower = claim_type.lower()
    inconsistencies = []
    if "fire" in claim_type_lower and "water" in description and "fire" not in description:
        inconsistencies.append("fire claim but description mentions water, not fire")
    if "theft" in claim_type_lower and "accident" in description:
        inconsistencies.append("theft claim but description mentions accident")
    if "collision" in claim_type_lower and "stolen" in description:
        inconsistencies.append("collision claim but description mentions theft")

    if inconsistencies:
        red_flags.append({
            "rule": "narrative_inconsistency",
            "severity": "high",
            "detail": "; ".join(inconsistencies),
        })

    # Also check: prior fraud in history
    if claim_history.get("has_fraud_history", False):
        red_flags.append({
            "rule": "prior_fraud_history",
            "severity": "high",
            "detail": "Customer has a prior claim marked as fraud",
        })

    # Calculate fraud score (0-100)
    high_count = sum(1 for f in red_flags if f["severity"] == "high")
    medium_count = sum(1 for f in red_flags if f["severity"] == "medium")
    fraud_score = min(100, high_count * 30 + medium_count * 15)

    # Risk level
    if fraud_score >= 60:
        risk_level = "HIGH"
    elif fraud_score >= 30:
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"

    return {
        "red_flags": red_flags,
        "red_flag_count": len(red_flags),
        "fraud_score": fraud_score,
        "fraud_risk_level": risk_level,
    }
