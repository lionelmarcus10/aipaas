"""State 5: LLM_DISPUTE_ANALYSIS — categorize the dispute type.

LLM call via CAST. Only reached if decision == DISPUTE.
"""

import json

from .llm_helper import call_llm


def handler(event: dict) -> dict:
    """Analyze the dispute and categorize it.

    Input:  {"audit_report": {...}, "invoice": {...}, "decision": "DISPUTE", ...}
    Output: adds "dispute_analysis" to the event
    """
    audit = event.get("audit_report", {})
    invoice = event["invoice"]

    user_message = f"""## Audit Report
{json.dumps(audit, indent=2, ensure_ascii=False)}

## Invoice Summary
- Invoice ID: {invoice['invoice_id']}
- Supplier: {invoice['supplier_name']} ({invoice['supplier_id']})
- Total: {invoice['total_amount']}€ (expected: {invoice['expected_amount']}€)
- Variance: {event.get('variance_pct', 0)}%

## Task
Categorize this dispute and assess customer impact. Return JSON.
"""

    dispute_analysis = call_llm("dispute", user_message)

    return {
        **event,
        "state": "LLM_DISPUTE_ANALYSIS",
        "dispute_analysis": dispute_analysis,
    }
