"""Tool 7 : generate_triage_report

Génère le rapport de triage final à partir de tous les findings.
C'est un tool LLM — il utilise cast pour appeler le modèle.

Mais en mode mock (pas de LLM), il génère un rapport déterministe
basé sur les règles de routing.

Input:  {"claim": {...}, "policy": {...}, "coverage": {...},
         "fraud": {...}, "payout": {...}, "claim_history": {...}}
Output: {"triage_decision", "reasoning", "risk_score", "recommendation",
         "payout_amount", "tool_calls_summary"}

LLM via cast (ou mock fallback déterministe).
"""

import json
from typing import Any


def _deterministic_triage(
    claim: dict,
    policy: dict,
    coverage: dict,
    fraud: dict,
    payout: dict,
    claim_history: dict,
) -> dict:
    """Deterministic fallback triage (no LLM).

    Routing rules:
      - Not covered → DENY_COVERAGE
      - Fraud score >= 60 → SIU_REFERRAL
      - High severity (bodily injury or amount > 25k) → ADJUSTER_REVIEW
      - Amount < deductible → FAST_TRACK_APPROVE (payout = 0)
      - Otherwise → FAST_TRACK_APPROVE
    """
    # Missing information (amount = 0 or description is incomplete)
    claim_amount = claim.get("claim_amount", 0)
    description = claim.get("description", "")
    if claim_amount == 0 or "incomplete" in description.lower():
        return {
            "triage_decision": "REQUEST_INFORMATION",
            "reasoning": "Claim is missing critical information (amount or description incomplete)",
            "risk_score": fraud.get("fraud_score", 0),
            "recommendation": "Request additional information from claimant before proceeding",
            "payout_amount": 0,
            "tool_calls_summary": "parse_claim → check_policy → REQUEST_INFO",
        }

    # Coverage denied
    if not coverage.get("is_covered", True):
        return {
            "triage_decision": "DENY_COVERAGE",
            "reasoning": f"Claim not covered: {coverage.get('reason', 'exclusion hit')}",
            "risk_score": fraud.get("fraud_score", 0),
            "recommendation": "Deny claim — policy exclusion applies",
            "payout_amount": 0,
            "tool_calls_summary": "parse_claim → check_policy → check_coverage → DENY",
        }

    # High fraud risk → SIU
    if fraud.get("fraud_score", 0) >= 60:
        return {
            "triage_decision": "SIU_REFERRAL",
            "reasoning": f"High fraud risk (score={fraud['fraud_score']}, {fraud['red_flag_count']} red flags)",
            "risk_score": fraud["fraud_score"],
            "recommendation": "Refer to Special Investigations Unit for fraud investigation",
            "payout_amount": 0,
            "tool_calls_summary": "parse_claim → check_policy → check_fraud_indicators → SIU",
        }

    # High severity → adjuster
    claim_type = claim.get("claim_type", "")
    claim_amount = claim.get("claim_amount", 0)
    if claim_type == "bodily_injury" or claim_amount > 25000:
        return {
            "triage_decision": "ADJUSTER_REVIEW",
            "reasoning": f"High severity claim (type={claim_type}, amount={claim_amount})",
            "risk_score": fraud.get("fraud_score", 0),
            "recommendation": "Assign to human adjuster for detailed review",
            "payout_amount": payout.get("payout_amount", 0),
            "tool_calls_summary": "parse_claim → check_policy → calculate_payout → ADJUSTER",
        }

    # Amount under deductible → approve but no payout
    if claim_amount <= policy.get("deductible", 0):
        return {
            "triage_decision": "FAST_TRACK_APPROVE",
            "reasoning": f"Claim amount ({claim_amount}) under deductible ({policy['deductible']}), no payout",
            "risk_score": fraud.get("fraud_score", 0),
            "recommendation": "Approve claim — fast track, no payout needed",
            "payout_amount": 0,
            "tool_calls_summary": "parse_claim → check_policy → FAST_TRACK",
        }

    # Default → fast track approve
    return {
        "triage_decision": "FAST_TRACK_APPROVE",
        "reasoning": f"Simple claim, coverage confirmed, low fraud risk (score={fraud.get('fraud_score', 0)})",
        "risk_score": fraud.get("fraud_score", 0),
        "recommendation": "Approve claim — fast track processing",
        "payout_amount": payout.get("payout_amount", 0),
        "tool_calls_summary": "parse_claim → check_policy → check_fraud_indicators → FAST_TRACK",
    }


def generate_triage_report(
    claim: dict,
    policy: dict,
    coverage: dict,
    fraud: dict,
    payout: dict,
    claim_history: dict,
    use_llm: bool = True,
) -> dict:
    """Generate the final triage report.

    Args:
        claim: Parsed claim data.
        policy: Policy data.
        coverage: Coverage assessment.
        fraud: Fraud indicators.
        payout: Payout calculation.
        claim_history: Claim history.
        use_llm: If True, try to use LLM via cast. If False or LLM unavailable,
                 use deterministic fallback.

    Returns:
        Dict with triage decision, reasoning, risk score, recommendation.
    """
    if use_llm:
        try:
            from ..llm_helper import call_llm

            context = json.dumps({
                "claim": claim,
                "policy": policy,
                "coverage": coverage,
                "fraud_indicators": fraud,
                "payout_calculation": payout,
                "claim_history": {
                    "total_claims": claim_history.get("total_claims", 0),
                    "has_fraud_history": claim_history.get("has_fraud_history", False),
                    "has_repeat_claims": claim_history.get("has_repeat_claims", False),
                },
            }, indent=2)

            result = call_llm("triage_report", context)
            if "error" not in result:
                return result
        except Exception:
            pass  # Fall through to deterministic

    # Deterministic fallback
    return _deterministic_triage(claim, policy, coverage, fraud, payout, claim_history)
