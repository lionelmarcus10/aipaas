"""State 8: LLM_RESOLUTION_PLAN — propose a resolution plan.

LLM call via CAST. Takes all context: dispute, orders, trust.
"""

import json

from .llm_helper import call_llm


def handler(event: dict) -> dict:
    """Generate a resolution plan based on all context.

    Input:  {"dispute_analysis": {...}, "affected_orders": {...},
             "trust_assessment": {...}, "invoice": {...}, ...}
    Output: adds "resolution_plan" to the event
    """
    dispute = event.get("dispute_analysis", {})
    orders = event.get("affected_orders", {})
    trust = event.get("trust_assessment", {})
    invoice = event["invoice"]

    # Summarize orders for the LLM (don't send all 1000)
    order_summary = {
        "order_count": orders.get("order_count", 0),
        "total_impact": orders.get("total_impact", 0),
        "affected_customers": orders.get("affected_customers", 0),
        "top_5_orders": orders.get("affected_orders", [])[:5],
    }

    user_message = f"""## Dispute Analysis
{json.dumps(dispute, indent=2, ensure_ascii=False)}

## Affected Orders Summary
{json.dumps(order_summary, indent=2, ensure_ascii=False)}

## Trust Assessment
{json.dumps(trust, indent=2, ensure_ascii=False)}

## Invoice
- ID: {invoice['invoice_id']}
- Supplier: {invoice['supplier_name']} ({invoice['supplier_id']})
- Total: {invoice['total_amount']}€ (expected: {invoice['expected_amount']}€)
- Variance: {event.get('variance_pct', 0)}%

## Task
Propose a resolution plan. Return JSON with actions, rationale, and requires_human_review.
"""

    resolution_plan = call_llm("resolution", user_message)

    return {
        **event,
        "state": "LLM_RESOLUTION_PLAN",
        "resolution_plan": resolution_plan,
    }
