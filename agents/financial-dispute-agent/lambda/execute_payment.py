"""Lambda wrapper — Terminal action: EXECUTE_PAYMENT.

Called by the Step Functions CHOICE_GATE when decision == "PAY".
Executes the payment mock and returns the final event.
"""

from financial_dispute_agent.tools.payment_mock import execute_payment


def lambda_handler(event, context):
    supplier_id = event["supplier_id"]
    amount = event["invoice"]["expected_amount"]
    result = execute_payment(supplier_id, amount)
    return {
        **event,
        "final_decision": "PAY",
        "actions_executed": [result],
        "state": "FINAL",
    }
