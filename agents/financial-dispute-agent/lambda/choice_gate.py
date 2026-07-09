"""Lambda wrapper — State 4: CHOICE_GATE."""
from financial_dispute_agent.lambdas.state_4_choice_gate import handler


def lambda_handler(event, context):
    return handler(event)
