"""Local orchestrator — simulates the Step Functions state machine.

This runs the full 9-state workflow locally without AWS Step Functions.
Used for development, testing, and demonstration.

In production, each state handler maps to a Lambda function, and the
state machine is defined in ASL (Amazon States Language) JSON.
"""

import json
import time
from typing import Any

from .lambdas.state_1_parse_invoice import handler as state_1
from .lambdas.state_2_fetch_contract import handler as state_2
from .lambdas.state_3_llm_audit import handler as state_3
from .lambdas.state_4_choice_gate import handler as state_4
from .lambdas.state_5_llm_dispute import handler as state_5
from .lambdas.state_6_lookup_orders import handler as state_6
from .lambdas.state_7_fraud_check import handler as state_7
from .lambdas.state_8_llm_resolution import handler as state_8
from .lambdas.state_9_final_choice import handler as state_9
from .tools.payment_mock import execute_payment, partial_payment


def run_workflow(invoice_id: str, verbose: bool = False) -> dict[str, Any]:
    """Run the full Financial Dispute Resolution workflow.

    Args:
        invoice_id: The invoice to process (e.g. "INV-1234").
        verbose: Print state transitions to stdout.

    Returns:
        Final event dict with all state results.
    """
    event: dict[str, Any] = {"invoice_id": invoice_id}
    trace: list[dict] = []

    def log(state_name: str, result: dict) -> None:
        if verbose:
            decision = result.get("decision", result.get("final_decision", ""))
            extra = f" → {decision}" if decision else ""
            print(f"  [{state_name}]{extra}")
        entry = {
            "state": state_name,
            "timestamp": time.time(),
            "decision": result.get("decision", result.get("final_decision", "")),
        }
        # Propagate RAG metadata for the FETCH_CONTRACT step
        if state_name == "FETCH_CONTRACT" and "rag_used" in result:
            entry["rag_used"] = result["rag_used"]
            contract = result.get("contract", {})
            if isinstance(contract, dict):
                entry["contract_length"] = contract.get("contract_length")
        trace.append(entry)

    # State 1: PARSE_INVOICE
    if verbose:
        print(f"\n{'='*60}")
        print(f"  Workflow: {invoice_id}")
        print(f"{'='*60}")
    event = state_1(event)
    log("PARSE_INVOICE", event)
    if "error" in event:
        return {"error": event["error"], "trace": trace}

    # State 2: FETCH_CONTRACT
    event = state_2(event)
    log("FETCH_CONTRACT", event)
    if "error" in event:
        return {"error": event["error"], "trace": trace}

    # State 3: LLM_AUDIT
    event = state_3(event)
    log("LLM_AUDIT", event)

    # State 4: CHOICE_GATE
    event = state_4(event)
    log("CHOICE_GATE", event)

    decision = event.get("decision", "")

    # Branch based on decision
    if decision == "PAY":
        # Direct payment, skip dispute states
        if verbose:
            print(f"  → PAY: executing payment directly")
        event["final_decision"] = "PAY"
        event["actions_executed"] = [
            execute_payment(event["supplier_id"], event["invoice"]["expected_amount"])
        ]
        event["state"] = "FINAL"

    elif decision == "PARTIAL_PAY":
        if verbose:
            print(f"  → PARTIAL_PAY: executing partial payment")
        retained = event.get("variance_abs", 0)
        pay_amount = event["invoice"]["total_amount"] - retained
        event["final_decision"] = "PARTIAL_PAY"
        event["actions_executed"] = [
            partial_payment(event["supplier_id"], pay_amount, retained)
        ]
        event["state"] = "FINAL"

    elif decision == "HUMAN_REVIEW":
        if verbose:
            print(f"  → HUMAN_REVIEW: escalating")
        event["final_decision"] = "HUMAN_REVIEW"
        event["actions_executed"] = [
            {"action": "create_ticket", "reason": event.get("decision_reason", "low confidence")}
        ]
        event["state"] = "FINAL"

    elif decision == "DISPUTE":
        # States 5-9: full dispute resolution
        if verbose:
            print(f"  → DISPUTE: running full resolution workflow")

        # State 5: LLM_DISPUTE_ANALYSIS
        event = state_5(event)
        log("LLM_DISPUTE_ANALYSIS", event)

        # State 6: LOOKUP_AFFECTED_ORDERS
        event = state_6(event)
        log("LOOKUP_AFFECTED_ORDERS", event)

        # State 7: FRAUD_CHECK
        event = state_7(event)
        log("FRAUD_CHECK", event)

        # State 8: LLM_RESOLUTION_PLAN
        event = state_8(event)
        log("LLM_RESOLUTION_PLAN", event)

        # State 9: FINAL_CHOICE
        event = state_9(event)
        log("FINAL_CHOICE", event)

    if verbose:
        print(f"\n  Final: {event.get('final_decision', 'UNKNOWN')}")
        print(f"  Actions: {len(event.get('actions_executed', []))}")
        print(f"{'='*60}\n")

    event["trace"] = trace
    return event


# ─── ASL definition (for AWS Step Functions deployment) ───────────────

ASL_DEFINITION = {
    "Comment": "Financial Dispute Resolution Agent — B1+B2 fusion",
    "StartAt": "PARSE_INVOICE",
    "States": {
        "PARSE_INVOICE": {
            "Type": "Task",
            "Resource": "arn:aws:lambda:REGION:ACCOUNT:function:financial-dispute-parse-invoice",
            "Next": "FETCH_CONTRACT",
        },
        "FETCH_CONTRACT": {
            "Type": "Task",
            "Resource": "arn:aws:lambda:REGION:ACCOUNT:function:financial-dispute-fetch-contract",
            "Next": "LLM_AUDIT",
        },
        "LLM_AUDIT": {
            "Type": "Task",
            "Resource": "arn:aws:lambda:REGION:ACCOUNT:function:financial-dispute-llm-audit",
            "Next": "CHOICE_GATE",
        },
        "CHOICE_GATE": {
            "Type": "Choice",
            "Choices": [
                {
                    "Variable": "$.decision",
                    "StringEquals": "PAY",
                    "Next": "EXECUTE_PAYMENT",
                },
                {
                    "Variable": "$.decision",
                    "StringEquals": "PARTIAL_PAY",
                    "Next": "EXECUTE_PARTIAL_PAYMENT",
                },
                {
                    "Variable": "$.decision",
                    "StringEquals": "HUMAN_REVIEW",
                    "Next": "CREATE_TICKET",
                },
                {
                    "Variable": "$.decision",
                    "StringEquals": "DISPUTE",
                    "Next": "LLM_DISPUTE_ANALYSIS",
                },
            ],
            "Default": "CREATE_TICKET",
        },
        "EXECUTE_PAYMENT": {
            "Type": "Task",
            "Resource": "arn:aws:lambda:REGION:ACCOUNT:function:financial-dispute-execute-payment",
            "End": True,
        },
        "EXECUTE_PARTIAL_PAYMENT": {
            "Type": "Task",
            "Resource": "arn:aws:lambda:REGION:ACCOUNT:function:financial-dispute-partial-payment",
            "End": True,
        },
        "CREATE_TICKET": {
            "Type": "Task",
            "Resource": "arn:aws:lambda:REGION:ACCOUNT:function:financial-dispute-create-ticket",
            "End": True,
        },
        "LLM_DISPUTE_ANALYSIS": {
            "Type": "Task",
            "Resource": "arn:aws:lambda:REGION:ACCOUNT:function:financial-dispute-llm-dispute",
            "Next": "LOOKUP_AFFECTED_ORDERS",
        },
        "LOOKUP_AFFECTED_ORDERS": {
            "Type": "Task",
            "Resource": "arn:aws:lambda:REGION:ACCOUNT:function:financial-dispute-lookup-orders",
            "Next": "FRAUD_CHECK",
        },
        "FRAUD_CHECK": {
            "Type": "Task",
            "Resource": "arn:aws:lambda:REGION:ACCOUNT:function:financial-dispute-fraud-check",
            "Next": "LLM_RESOLUTION_PLAN",
        },
        "LLM_RESOLUTION_PLAN": {
            "Type": "Task",
            "Resource": "arn:aws:lambda:REGION:ACCOUNT:function:financial-dispute-llm-resolution",
            "Next": "FINAL_CHOICE",
        },
        "FINAL_CHOICE": {
            "Type": "Task",
            "Resource": "arn:aws:lambda:REGION:ACCOUNT:function:financial-dispute-final-choice",
            "End": True,
        },
    },
}
