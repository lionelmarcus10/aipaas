"""Lambda wrapper — State 8: LLM_RESOLUTION_PLAN."""
from financial_dispute_agent.lambdas.state_8_llm_resolution import handler


def lambda_handler(event, context):
    return handler(event)
