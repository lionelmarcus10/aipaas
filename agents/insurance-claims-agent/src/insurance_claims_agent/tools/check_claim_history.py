"""Tool 3 : check_claim_history

Récupère l'historique des sinistres d'un client (12 derniers mois).

Input:  {"customer_id": "CUS-0099"}
Output: {"customer_id", "total_claims", "claims": [...], "has_repeat_claims",
         "has_fraud_history", "total_claimed_amount"}

Pas de LLM : requête DuckDB pure.
"""

from .db import get_connection


def check_claim_history(customer_id: str) -> dict:
    """Retrieve claim history for a customer.

    Args:
        customer_id: The customer identifier (e.g. "CUS-0099").

    Returns:
        Dict with claim history summary, or {"error": "..."} if not found.
    """
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT customer_id, claim_id, claim_date, claim_type,
                      claim_amount, fraud_found
               FROM claim_history
               WHERE customer_id = ?
               ORDER BY claim_date DESC""",
            [customer_id],
        ).fetchall()

        if not rows:
            return {
                "customer_id": customer_id,
                "total_claims": 0,
                "claims": [],
                "has_repeat_claims": False,
                "has_fraud_history": False,
                "total_claimed_amount": 0.0,
            }

        claims = []
        total_amount = 0.0
        has_fraud = False
        claim_types = []

        for row in rows:
            cid, claim_id, claim_date, claim_type, amount, fraud = row
            claims.append({
                "claim_id": claim_id,
                "claim_date": claim_date,
                "claim_type": claim_type,
                "claim_amount": amount,
                "fraud_found": fraud,
            })
            total_amount += amount
            if fraud:
                has_fraud = True
            claim_types.append(claim_type)

        # Check for repeat claims (same type, 2+ in history)
        from collections import Counter
        type_counts = Counter(claim_types)
        has_repeat = any(count >= 2 for count in type_counts.values())

        return {
            "customer_id": customer_id,
            "total_claims": len(claims),
            "claims": claims,
            "has_repeat_claims": has_repeat,
            "has_fraud_history": has_fraud,
            "total_claimed_amount": round(total_amount, 2),
        }
    finally:
        conn.close()
