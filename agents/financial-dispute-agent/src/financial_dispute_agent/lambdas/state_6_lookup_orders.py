"""State 6: LOOKUP_AFFECTED_ORDERS — find customer orders linked to supplier.

Script only, no LLM.
"""

from ..tools.lookup_affected_orders import lookup_affected_orders


def handler(event: dict) -> dict:
    """Find orders affected by this supplier dispute.

    Input:  {"supplier_id": "SUP-001", "dispute_analysis": {...}, ...}
    Output: adds "affected_orders" to the event
    """
    supplier_id = event["supplier_id"]
    orders_result = lookup_affected_orders(supplier_id)

    return {
        **event,
        "state": "LOOKUP_AFFECTED_ORDERS",
        "affected_orders": orders_result,
    }
