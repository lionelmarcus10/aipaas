"""Insurance Claims Triage Agent — autonomous ReAct agent.

Uses Strands SDK + cast for the LLM provider. The agent receives a FNOL
(First Notification of Loss) claim, investigates it autonomously using
the 7 deterministic tools, and produces a structured triage decision.

The agent decides which tools to call based on the claim context:
  - Simple claim → 2-3 tool calls → FAST_TRACK_APPROVE
  - Complex claim → 5-7 tool calls → ADJUSTER_REVIEW
  - Suspicious claim → 6-8 tool calls → SIU_REFERRAL

Provider auto-detection (via cast.from_env()):
  1. AWS Bedrock (Lambda/EKS) — IAM-based, no API key
  2. vLLM (k3d) — OpenAI-compatible endpoint
  3. Ollama Cloud — Bearer token auth
  4. OpenRouter / OpenAI — API key
  5. Mock — deterministic fallback (no LLM)
"""

import json
import logging
from typing import Any

from strands import tool

from .tools.parse_claim import parse_claim
from .tools.check_policy import check_policy
from .tools.check_claim_history import check_claim_history
from .tools.check_fraud_indicators import check_fraud_indicators
from .tools.check_coverage import check_coverage
from .tools.calculate_payout import calculate_payout
from .tools.generate_triage_report import generate_triage_report
from .llm_helper import assess_damage_llm

logger = logging.getLogger(__name__)


# ─── Strands @tool wrappers ──────────────────────────────────────────

@tool
def tool_parse_claim(claim_id: str) -> dict:
    """Parse a claim from the database into structured data.

    Args:
        claim_id: The claim identifier (e.g. "CLM-0001").
    """
    return parse_claim(claim_id)


@tool
def tool_check_policy(policy_id: str) -> dict:
    """Retrieve insurance policy details including coverage, limits, and exclusions.

    Args:
        policy_id: The policy identifier (e.g. "POL-0042").
    """
    return check_policy(policy_id)


@tool
def tool_check_claim_history(customer_id: str) -> dict:
    """Retrieve the claim history for a customer (previous claims, fraud flags).

    Args:
        customer_id: The customer identifier (e.g. "CUS-0099").
    """
    return check_claim_history(customer_id)


@tool
def tool_check_fraud_indicators(claim_json: str, policy_json: str, history_json: str) -> dict:
    """Check fraud indicators (red flags) for a claim based on policy and history.

    Args:
        claim_json: JSON string of the parsed claim.
        policy_json: JSON string of the policy details.
        history_json: JSON string of the claim history.
    """
    claim = json.loads(claim_json)
    policy = json.loads(policy_json)
    history = json.loads(history_json)
    return check_fraud_indicators(claim, policy, history)


@tool
def tool_check_coverage(policy_json: str, claim_type: str, description: str) -> dict:
    """Check if the policy covers the claim type and no exclusions apply.

    Args:
        policy_json: JSON string of the policy details.
        claim_type: The type of claim (e.g. "home_fire").
        description: The claim description (for exclusion keyword matching).
    """
    policy = json.loads(policy_json)
    return check_coverage(policy, claim_type, description)


@tool
def tool_calculate_payout(claim_amount: float, coverage_limit: float, deductible: float, depreciation_pct: float = 0.0) -> dict:
    """Calculate the theoretical payout for a claim.

    Args:
        claim_amount: The claimed amount.
        coverage_limit: Maximum coverage from policy.
        deductible: Deductible amount from policy.
        depreciation_pct: Depreciation percentage (0-100, default 0).
    """
    return calculate_payout(claim_amount, coverage_limit, deductible, depreciation_pct)


@tool
def tool_assess_damage(claim_description: str, claim_type: str) -> dict:
    """Assess the severity of damage from a claim description using LLM analysis.

    Args:
        claim_description: The narrative description of the incident.
        claim_type: The type of claim (auto_collision, home_fire, etc.).
    """
    return assess_damage_llm(claim_description, claim_type)


@tool
def tool_generate_triage_report(
    claim_json: str,
    policy_json: str,
    coverage_json: str,
    fraud_json: str,
    payout_json: str,
    history_json: str,
) -> dict:
    """Generate the final triage report with decision, reasoning, and recommendation.

    Args:
        claim_json: JSON string of the parsed claim.
        policy_json: JSON string of the policy.
        coverage_json: JSON string of the coverage assessment.
        fraud_json: JSON string of the fraud indicators.
        payout_json: JSON string of the payout calculation.
        history_json: JSON string of the claim history.
    """
    claim = json.loads(claim_json)
    policy = json.loads(policy_json)
    coverage = json.loads(coverage_json)
    fraud = json.loads(fraud_json)
    payout = json.loads(payout_json)
    history = json.loads(history_json)
    return generate_triage_report(claim, policy, coverage, fraud, payout, history)


# ─── Agent creation ──────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an expert Insurance Claims Triage Agent for a P&C (Property & Casualty) insurance company.

Your job is to investigate insurance claims (First Notification of Loss) and produce a triage decision.

## Available Tools

You have 8 tools available:
1. tool_parse_claim — Extract structured data from a claim by ID
2. tool_check_policy — Retrieve policy details (coverage, limits, exclusions)
3. tool_check_claim_history — Get previous claims for a customer
4. tool_check_fraud_indicators — Check for fraud red flags
5. tool_check_coverage — Verify if the policy covers the claim type
6. tool_calculate_payout — Calculate the theoretical payout amount
7. tool_assess_damage — Assess damage severity from the claim description (LLM)
8. tool_generate_triage_report — Generate the final triage decision

## Investigation Strategy

You decide which tools to call based on what you find at each step:

**Simple claim** (minor damage, clear policy):
1. tool_parse_claim → get claim data
2. tool_check_policy → verify coverage
3. tool_generate_triage_report → FAST_TRACK_APPROVE

**Complex claim** (moderate damage, needs assessment):
1. tool_parse_claim → get claim data
2. tool_check_policy → verify coverage
3. tool_check_claim_history → check for repeat claims
4. tool_assess_damage → estimate severity
5. tool_calculate_payout → compute payout
6. tool_generate_triage_report → ADJUSTER_REVIEW

**Suspicious claim** (fraud indicators):
1. tool_parse_claim → get claim data
2. tool_check_policy → verify coverage
3. tool_check_claim_history → check for repeat claims
4. tool_check_fraud_indicators → identify red flags
5. tool_assess_damage → check if description matches damage
6. tool_calculate_payout → compute theoretical payout
7. tool_generate_triage_report → SIU_REFERRAL

## Rules

- ALWAYS start with tool_parse_claim to get the claim data
- ALWAYS check the policy with tool_check_policy
- If the claim amount is high (>10k) or the type is bodily_injury, check claim history
- If anything seems suspicious (recent policy, high amount, no police report), check fraud indicators
- NEVER deny a claim based solely on fraud suspicion — always refer to SIU instead
- ALWAYS generate a triage report at the end
- Pass JSON strings to tools that accept JSON (use json.dumps)
"""


def create_triage_agent():
    """Create the Strands triage agent with all tools.

    Auto-detects the LLM provider via cast.from_env().
    Includes CircuitBreakerHook for Panne #3 and sliding window for Panne #6.
    """
    from cast import AgentFactory, CircuitBreakerHook, sliding_window

    try:
        from cast import from_env
        model = from_env()
    except ValueError:
        model = None  # mock mode

    factory = AgentFactory(
        model=model,
        streaming=True,
        prompts_dir=str(__import__("pathlib").Path(__file__).parent / "prompts"),
    )

    all_tools = [
        tool_parse_claim,
        tool_check_policy,
        tool_check_claim_history,
        tool_check_fraud_indicators,
        tool_check_coverage,
        tool_calculate_payout,
        tool_assess_damage,
        tool_generate_triage_report,
    ]

    agent = factory.create_agent(
        system_prompt=SYSTEM_PROMPT,
        tools=all_tools,
        hooks=[CircuitBreakerHook(failure_threshold=3, reset_timeout=60)],
        conversation_manager=sliding_window(window_size=20, pin_first=True),
    )

    return agent


# ─── Convenience: run triage for a claim ─────────────────────────────

def run_triage(claim_id: str, verbose: bool = False) -> dict[str, Any]:
    """Run the full triage investigation for a claim.

    This is a convenience function that creates the agent and runs it.
    For more control, use create_triage_agent() directly.

    Args:
        claim_id: The claim ID to investigate (e.g. "CLM-0001").
        verbose: If True, print progress.

    Returns:
        Dict with the triage decision and investigation trace.
    """
    if verbose:
        print(f"  [triage] Starting investigation for claim {claim_id}...")

    agent = create_triage_agent()
    response = agent(f"Investigate claim {claim_id} and produce a triage decision.")

    text = str(response)

    # Try to extract JSON from the response
    text = text.strip()
    if "```json" in text:
        json_text = text.split("```json")[1].split("```")[0].strip()
        try:
            return json.loads(json_text)
        except json.JSONDecodeError:
            pass

    # Try to find a JSON block in the full text
    first = text.find("{")
    last = text.rfind("}")
    if first != -1 and last != -1:
        try:
            return json.loads(text[first : last + 1])
        except json.JSONDecodeError:
            pass

    # Fallback: extract triage decision from markdown text
    import re
    decision_patterns = [
        r"(?:Triage Decision|triage_decision|Decision)[:\s]*\**([A-Z_]+)\**",
        r"\b(FAST_TRACK_APPROVE|ADJUSTER_REVIEW|SIU_REFERRAL|DENY_COVERAGE|REQUEST_INFORMATION)\b",
    ]
    for pattern in decision_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            decision = match.group(1).upper()
            return {
                "triage_decision": decision,
                "reasoning": text[:500],
                "raw_response": text[:1000],
            }

    return {
        "triage_decision": "UNKNOWN",
        "raw_response": text[:1000],
    }


# ─── Deterministic runner (no LLM, for tests) ────────────────────────

def run_triage_deterministic(claim_id: str, verbose: bool = False) -> dict[str, Any]:
    """Run the full triage investigation deterministically (no LLM).

    This calls all tools in sequence and uses the deterministic fallback
    for the triage report. Used for tests that don't need LLM reasoning.

    Args:
        claim_id: The claim ID to investigate.
        verbose: If True, print each step.

    Returns:
        Dict with the triage decision and all tool outputs.
    """
    trace = []

    def log(msg):
        trace.append(msg)
        if verbose:
            print(f"  [triage] {msg}")

    # Step 1: Parse claim
    log(f"parse_claim({claim_id})")
    claim = parse_claim(claim_id)
    if "error" in claim:
        return {"error": claim["error"], "trace": trace}
    log(f"  → claim_type={claim['claim_type']}, amount={claim['claim_amount']}")

    # Step 2: Check policy
    log(f"check_policy({claim['policy_id']})")
    policy = check_policy(claim["policy_id"])
    if "error" in policy:
        return {"error": policy["error"], "trace": trace}
    log(f"  → policy_type={policy['policy_type']}, active={policy['is_active']}, days={policy['days_since_start']}")

    # Step 3: Check coverage
    log(f"check_coverage(policy, {claim['claim_type']})")
    coverage = check_coverage(policy, claim["claim_type"], claim["description"])
    log(f"  → covered={coverage['is_covered']}, reason={coverage['reason']}")

    if not coverage["is_covered"]:
        # Short circuit: coverage denied
        report = generate_triage_report(claim, policy, coverage, {"fraud_score": 0}, {"payout_amount": 0}, {"total_claims": 0}, use_llm=False)
        log(f"generate_triage_report() → {report['triage_decision']}")
        return {**report, "trace": trace, "claim": claim, "policy": policy, "coverage": coverage}

    # Step 4: Check claim history
    log(f"check_claim_history({claim['customer_id']})")
    history = check_claim_history(claim["customer_id"])
    log(f"  → total_claims={history['total_claims']}, repeat={history['has_repeat_claims']}, fraud={history['has_fraud_history']}")

    # Step 5: Check fraud indicators
    log("check_fraud_indicators(claim, policy, history)")
    fraud = check_fraud_indicators(claim, policy, history)
    log(f"  → red_flags={fraud['red_flag_count']}, score={fraud['fraud_score']}, level={fraud['fraud_risk_level']}")

    # Step 6: Calculate payout
    log("calculate_payout(...)")
    payout = calculate_payout(
        claim_amount=claim["claim_amount"],
        coverage_limit=policy["coverage_limit"],
        deductible=policy["deductible"],
    )
    log(f"  → payout={payout['payout_amount']}")

    # Step 7: Generate triage report (deterministic)
    log("generate_triage_report() [deterministic]")
    report = generate_triage_report(claim, policy, coverage, fraud, payout, history, use_llm=False)
    log(f"  → decision={report['triage_decision']}")

    return {
        **report,
        "trace": trace,
        "claim": claim,
        "policy": policy,
        "coverage": coverage,
        "fraud": fraud,
        "payout": payout,
        "history": {
            "total_claims": history["total_claims"],
            "has_fraud_history": history["has_fraud_history"],
            "has_repeat_claims": history["has_repeat_claims"],
        },
    }
