"""Tool 6 : payment_mock

États 4a/4b/9a/9b du Step Functions.
Simule les appels API de paiement et remboursement (Stripe sandbox mock).

Input:  {"action": "execute_payment", "supplier_id": "SUP-001", "amount": 1500.0}
Output: {"action", "status", "transaction_id", "amount", "timestamp"}

Pas de LLM, pas de vrai API : mock qui logge et retourne un faux transaction_id.
"""

import uuid
from datetime import datetime, timezone


def execute_payment(supplier_id: str, amount: float) -> dict:
    """Mock: execute a payment to a supplier.

    Args:
        supplier_id: The supplier to pay.
        amount: The payment amount.
    """
    return {
        "action": "execute_payment",
        "supplier_id": supplier_id,
        "status": "success",
        "transaction_id": f"txn_{uuid.uuid4().hex[:12]}",
        "amount": amount,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def partial_payment(supplier_id: str, amount: float, retained: float) -> dict:
    """Mock: execute a partial payment, retaining the disputed portion.

    Args:
        supplier_id: The supplier to pay.
        amount: The amount to pay.
        retained: The amount retained (disputed).
    """
    return {
        "action": "partial_payment",
        "supplier_id": supplier_id,
        "status": "success",
        "transaction_id": f"txn_{uuid.uuid4().hex[:12]}",
        "amount_paid": amount,
        "amount_retained": retained,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def refund_customer(customer_id: str, amount: float, reason: str) -> dict:
    """Mock: refund a customer.

    Args:
        customer_id: The customer to refund.
        amount: The refund amount.
        reason: The refund reason.
    """
    return {
        "action": "refund_customer",
        "customer_id": customer_id,
        "status": "success",
        "transaction_id": f"ref_{uuid.uuid4().hex[:12]}",
        "amount": amount,
        "reason": reason,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def freeze_supplier(supplier_id: str) -> dict:
    """Mock: freeze a supplier account (escalation).

    Args:
        supplier_id: The supplier to freeze.
    """
    return {
        "action": "freeze_supplier",
        "supplier_id": supplier_id,
        "status": "frozen",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def escalate_to_finance(supplier_id: str, reason: str) -> dict:
    """Mock: escalate to finance team.

    Args:
        supplier_id: The supplier concerned.
        reason: The escalation reason.
    """
    return {
        "action": "escalate_to_finance",
        "supplier_id": supplier_id,
        "status": "ticket_created",
        "ticket_id": f"fin_{uuid.uuid4().hex[:8]}",
        "reason": reason,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
