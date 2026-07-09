"""Tool 5 : compute_trust_score

État 7 du Step Functions.
Évalue le trust score d'un fournisseur basé sur son historique.

Input:  {"supplier_id": "SUP-001"}
Output: {"supplier_id", "trust_score", "risk_level", "recommendation"}

Pas de LLM : règle déterministe de scoring.

Le trust_score est stocké dans la DB (0-100).
Le risk_level est dérivé du score :
  - trust >= 80 → LOW risk (fiable)
  - 50 <= trust < 80 → MEDIUM risk (à surveiller)
  - trust < 50 → HIGH risk (dangereux)
"""

from .db import get_connection


def compute_trust_score(supplier_id: str) -> dict:
    """Compute the trust score and risk level for a supplier.

    Args:
        supplier_id: The supplier identifier.

    Returns:
        Dict with trust_score, risk_level, recommendation.
    """
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT trust_score FROM suppliers WHERE supplier_id = ?",
            [supplier_id],
        ).fetchone()

        if row is None:
            return {"error": f"Supplier {supplier_id} not found"}

        trust_score = row[0]

        # Routing déterministe
        if trust_score >= 80:
            risk_level = "LOW"
            recommendation = "proceed_with_caution"
        elif trust_score >= 50:
            risk_level = "MEDIUM"
            recommendation = "notify_and_monitor"
        else:
            risk_level = "HIGH"
            recommendation = "freeze_and_escalate"

        return {
            "supplier_id": supplier_id,
            "trust_score": trust_score,
            "risk_level": risk_level,
            "recommendation": recommendation,
        }
    finally:
        conn.close()
