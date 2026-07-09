"""Lambda wrapper — State 5: LLM_DISPUTE_ANALYSIS."""
from financial_dispute_agent.lambdas.state_5_llm_dispute import handler


def lambda_handler(event, context):
    return handler(event)
