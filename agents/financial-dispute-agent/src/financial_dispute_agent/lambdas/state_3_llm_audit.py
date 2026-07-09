"""State 3: LLM_AUDIT — compare invoice vs contract using LLM.

LLM call via CAST. The LLM detects semantic anomalies that scripts can't.
"""

import json

from .llm_helper import call_llm


def handler(event: dict) -> dict:
    """Run LLM audit on the invoice against the contract.

    Input:  {"invoice": {...}, "contract": {...}, ...}
    Output: adds "audit_report" to the event
    """
    invoice = event["invoice"]
    contract = event["contract"]

    # Build the context for the LLM
    user_message = f"""## Invoice
{json.dumps(invoice, indent=2, ensure_ascii=False)}

## Contract
Supplier: {contract['supplier_name']}
Trust Score: {contract['trust_score']}

Contract text:
{contract['contract_text']}

## Task
Analyze this invoice against the contract and return the audit report as JSON.
"""

    audit_report = call_llm("audit", user_message)

    return {
        **event,
        "state": "LLM_AUDIT",
        "audit_report": audit_report,
    }
