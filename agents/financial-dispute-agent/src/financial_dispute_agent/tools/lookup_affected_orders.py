"""Tool 4 : lookup_affected_orders

État 6 du Step Functions.
Recherche les commandes clients liées à un fournisseur en litige.

Input:  {"supplier_id": "SUP-001"}
Output: {"supplier_id", "affected_orders": [...], "total_impact": float,
         "affected_customers": int}

Pas de LLM : requête DuckDB pure.
"""

from .db import get_connection


def lookup_affected_orders(supplier_id: str) -> dict:
    """Find all customer orders linked to a supplier.

    Used when a supplier dispute is detected, to identify which
    customer orders might be impacted.

    Args:
        supplier_id: The supplier in dispute.

    Returns:
        Dict with affected_orders list, total_impact, affected_customers count.
    """
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT order_id, customer, amount, status, date
            FROM orders
            WHERE supplier_id = ?
            ORDER BY amount DESC
            """,
            [supplier_id],
        ).fetchall()

        if not rows:
            return {
                "supplier_id": supplier_id,
                "affected_orders": [],
                "total_impact": 0.0,
                "affected_customers": 0,
            }

        orders = [
            {
                "order_id": r[0],
                "customer": r[1],
                "amount": r[2],
                "status": r[3],
                "date": r[4],
            }
            for r in rows
        ]

        total_impact = round(sum(o["amount"] for o in orders), 2)
        unique_customers = len({o["customer"] for o in orders})

        return {
            "supplier_id": supplier_id,
            "affected_orders": orders,
            "total_impact": total_impact,
            "affected_customers": unique_customers,
            "order_count": len(orders),
        }
    finally:
        conn.close()
