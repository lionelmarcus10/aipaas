"""Local orchestrator — runs the Insurance Claims Triage Agent locally.

This runs the Strands agent (or deterministic fallback) locally without
needing AWS infrastructure. Used for development, testing, and k3d deployment.

In production on AWS, the agent is deployed via AgentCore Runtime or Lambda,
and the same tools/agent.py code runs unchanged — only the LLM provider
changes (Bedrock instead of Ollama Cloud/vLLM).

Two modes:
  1. LLM mode (default)     — uses Strands agent with cast.from_env() provider
  2. Deterministic mode     — no LLM, uses heuristic fallbacks (for CI/tests)

Usage:
  from insurance_claims_agent.orchestrator import run_triage
  result = run_triage("CLM-0001", verbose=True)
"""

import json
import time
from typing import Any

from .agent import run_triage, run_triage_deterministic


def run_workflow(claim_id: str, verbose: bool = False, use_llm: bool = True) -> dict[str, Any]:
    """Run the full Insurance Claims Triage workflow.

    This is the equivalent of the Financial Dispute Agent's run_workflow(),
    but for the autonomous ReAct agent instead of a fixed Step Functions pipeline.

    Args:
        claim_id: The claim ID to investigate (e.g. "CLM-0001").
        verbose: Print investigation steps to stdout.
        use_llm: If True, use Strands agent with LLM. If False, deterministic fallback.

    Returns:
        Dict with triage_decision, reasoning, risk_score, trace, etc.
    """
    start_time = time.time()
    trace: list[dict] = []

    def log(step: str, detail: str = "") -> None:
        if verbose:
            extra = f" → {detail}" if detail else ""
            print(f"  [{step}]{extra}")
        trace.append({
            "step": step,
            "timestamp": time.time(),
            "detail": detail,
        })

    if verbose:
        print(f"\n{'='*60}")
        print(f"  Triage Workflow: {claim_id} ({'LLM' if use_llm else 'deterministic'})")
        print(f"{'='*60}")

    log("START", f"claim_id={claim_id}, use_llm={use_llm}")

    try:
        if use_llm:
            log("AGENT_INIT", "creating Strands agent with cast.from_env()")
            result = run_triage(claim_id, verbose=verbose)
        else:
            log("DETERMINISTIC", "running without LLM")
            result = run_triage_deterministic(claim_id, verbose=verbose)

        log("DONE", result.get("triage_decision", "UNKNOWN"))

    except Exception as e:
        log("ERROR", str(e))
        return {
            "claim_id": claim_id,
            "triage_decision": "ERROR",
            "error": str(e),
            "trace": trace,
            "duration_sec": round(time.time() - start_time, 2),
        }

    if verbose:
        print(f"\n  Final: {result.get('triage_decision', 'UNKNOWN')}")
        print(f"  Duration: {time.time() - start_time:.2f}s")
        print(f"{'='*60}\n")

    result["claim_id"] = claim_id
    result["trace"] = trace
    result["duration_sec"] = round(time.time() - start_time, 2)
    return result


# ─── AgentCore Runtime handler (for AWS deployment) ──────────────────

def agentcore_handler(event: dict, context: Any = None) -> dict:
    """AWS AgentCore Runtime / Lambda handler.

    This is the entry point for AWS deployment (AgentCore Runtime or Lambda).
    The same code runs locally with Ollama Cloud and on AWS with Bedrock —
    only the environment variables change.

    Event format:
        {"claim_id": "CLM-0001"}
        or
        {"claim_id": "CLM-0001", "use_llm": false}

    Returns:
        Triage decision dict.
    """
    claim_id = event.get("claim_id", "")
    use_llm = event.get("use_llm", True)

    if not claim_id:
        return {"error": "claim_id is required"}

    result = run_workflow(claim_id, verbose=False, use_llm=use_llm)

    # AgentCore Runtime expects a serializable dict
    return {
        "claim_id": claim_id,
        "triage_decision": result.get("triage_decision", "UNKNOWN"),
        "reasoning": result.get("reasoning", ""),
        "risk_score": result.get("risk_score", 0),
        "recommendation": result.get("recommendation", ""),
        "payout_amount": result.get("payout_amount", 0),
        "duration_sec": result.get("duration_sec", 0),
    }
