"""Lambda wrapper — State 7: FRAUD_CHECK."""
from financial_dispute_agent.lambdas.state_7_fraud_check import handler


def lambda_handler(event, context):
    return handler(event)
