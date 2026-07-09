"""State 9: FINAL_CHOICE — execute the resolution plan.

Script only. Routes based on trust score + resolution plan + severity.
Executes the appropriate payment_mock actions.
"""

from ..tools.payment_mock import (
    execute_payment,
    partial_payment,
    refund_customer,
    freeze_supplier,
    escalate_to_finance,
)


def handler(event: dict) -> dict:
    """Execute the final resolution based on trust score and plan.

    Input:  {"trust_assessment": {...}, "resolution_plan": {...},
             "invoice": {...}, "affected_orders": {...}, ...}
    Output: {"final_decision", "actions_executed", ...}
    """
    trust = event.get("trust_assessment", {})
    plan = event.get("resolution_plan", {})
    invoice = event["invoice"]
    orders = event.get("affected_orders", {})
    dispute = event.get("dispute_analysis", {})

    trust_score = trust.get("trust_score", 50)
    risk_level = trust.get("risk_level", "MEDIUM")
    severity = dispute.get("severity", "medium")
    requires_human = plan.get("requires_human_review", False)

    actions_executed = []
    final_decision = ""

    # Deterministic routing based on trust + severity
    if requires_human or severity == "high":
        final_decision = "HUMAN_REVIEW"
        actions_executed.append({"action": "create_ticket", "reason": "severity high or human review requested"})

    elif risk_level == "HIGH" or trust_score < 50:
        final_decision = "FREEZE_AND_ESCALATE"
        actions_executed.append(freeze_supplier(invoice["supplier_id"]))
        actions_executed.append(escalate_to_finance(
            invoice["supplier_id"],
            f"Trust score {trust_score} — freeze required. Variance: {event.get('variance_pct', 0)}%",
        ))

    elif risk_level == "MEDIUM" or 50 <= trust_score < 80:
        final_decision = "PARTIAL_PAY_AND_NOTIFY"
        retained = event.get("variance_abs", 0)
        pay_amount = invoice["total_amount"] - retained
        actions_executed.append(partial_payment(
            invoice["supplier_id"],
            pay_amount,
            retained,
        ))
        # Notify affected customers
        for order in orders.get("affected_orders", [])[:3]:  # top 3
            actions_executed.append({
                "action": "notify_customer",
                "customer": order["customer"],
                "message": f"Litige fournisseur en cours. Commande {order['order_id'][:8]}... suivie.",
            })

    else:  # LOW risk, trust >= 80
        final_decision = "PAY_AND_REFUND"
        actions_executed.append(execute_payment(
            invoice["supplier_id"],
            invoice["expected_amount"],  # pay expected, not total
        ))
        # Refund affected customers if any
        for order in orders.get("affected_orders", [])[:3]:
            actions_executed.append(refund_customer(
                order["customer"],
                order["amount"],
                f"Surfacturation fournisseur {invoice['supplier_id']}",
            ))

    return {
        **event,
        "state": "FINAL_CHOICE",
        "final_decision": final_decision,
        "actions_executed": actions_executed,
        "trust_score": trust_score,
        "risk_level": risk_level,
    }
