"""Lambda wrapper — Terminal action: EXECUTE_PARTIAL_PAYMENT.

Called by the Step Functions CHOICE_GATE when decision == "PARTIAL_PAY".
Pays the expected amount, retains the variance.
"""

from financial_dispute_agent.tools.payment_mock import partial_payment


def lambda_handler(event, context):
    supplier_id = event["supplier_id"]
    retained = event.get("variance_abs", 0)
    pay_amount = event["invoice"]["total_amount"] - retained
    result = partial_payment(supplier_id, pay_amount, retained)
    return {
        **event,
        "final_decision": "PARTIAL_PAY",
        "actions_executed": [result],
        "state": "FINAL",
    }
