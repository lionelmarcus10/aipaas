"""Lambda wrapper — State 9: FINAL_CHOICE."""
from financial_dispute_agent.lambdas.state_9_final_choice import handler


def lambda_handler(event, context):
    return handler(event)
