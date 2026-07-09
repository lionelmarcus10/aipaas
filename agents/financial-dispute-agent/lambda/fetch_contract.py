"""Lambda wrapper — State 2: FETCH_CONTRACT."""
from financial_dispute_agent.lambdas.state_2_fetch_contract import handler


def lambda_handler(event, context):
    return handler(event)
