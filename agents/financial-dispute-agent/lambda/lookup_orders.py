"""Lambda wrapper — State 6: LOOKUP_AFFECTED_ORDERS."""
from financial_dispute_agent.lambdas.state_6_lookup_orders import handler


def lambda_handler(event, context):
    return handler(event)
