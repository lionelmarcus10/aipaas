"""Lambda wrapper — State 3: LLM_AUDIT."""
from financial_dispute_agent.lambdas.state_3_llm_audit import handler


def lambda_handler(event, context):
    return handler(event)
