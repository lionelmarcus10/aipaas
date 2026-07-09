"""Lambda wrapper — State 1: PARSE_INVOICE."""
from financial_dispute_agent.lambdas.state_1_parse_invoice import handler


def lambda_handler(event, context):
    return handler(event)
