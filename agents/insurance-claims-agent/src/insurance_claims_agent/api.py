"""FastAPI wrapper — exposes the Insurance Claims Triage Agent as an HTTP API.

This runs the local orchestrator inside a Kubernetes pod (k3d or EKS).
It's the dev/local deployment of the agent — same code, different LLM provider
based on environment variables.

On k3d:  LLM_PROVIDER=ollama (Ollama Cloud) or LLM_PROVIDER=vllm (vLLM endpoint)
On EKS:  LLM_PROVIDER=bedrock (AWS Bedrock, IAM-based auth)

Endpoints:
  GET  /health          → liveness/readiness probe
  GET  /                → API info + available endpoints
  POST /triage          → run triage for a claim_id (autonomous ReAct agent)
  POST /triage/det      → run deterministic triage (no LLM, for testing)
  GET  /claims          → list available claims from the DuckDB
  GET  /claims/{id}     → get a specific claim details
  GET  /policies/{id}   → get a specific policy details
  GET  /history/{cid}   → get claim history for a customer
  GET  /fraud-rules     → list the 5 fraud detection rules
  GET  /stats           → database statistics (table counts, sizes)
"""

import os
from typing import Any

import duckdb
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .orchestrator import run_workflow
from .tools.db import get_db_path


app = FastAPI(
    title="Insurance Claims Triage Agent",
    description="A2 — Autonomous ReAct agent for P&C insurance claims triage (Strands + cast)",
    version="0.1.0",
)


# ─── Request/Response models ─────────────────────────────────────────

class TriageRequest(BaseModel):
    claim_id: str
    use_llm: bool = True


class TriageResponse(BaseModel):
    claim_id: str
    triage_decision: str
    reasoning: str = ""
    risk_score: int = 0
    recommendation: str = ""
    payout_amount: float = 0
    duration_sec: float = 0
    trace: list[dict[str, Any]] = []


# ─── Health & info ───────────────────────────────────────────────────

@app.get("/health")
async def health():
    """Liveness/readiness probe."""
    return {"status": "ok"}


@app.get("/")
async def root():
    """API info + available endpoints."""
    return {
        "agent": "Insurance Claims Triage Agent (A2)",
        "version": "0.1.0",
        "description": "Autonomous ReAct agent for P&C insurance claims triage",
        "endpoints": {
            "GET  /health": "Liveness probe",
            "POST /triage": "Run triage (autonomous ReAct agent with LLM)",
            "POST /triage/det": "Run deterministic triage (no LLM, for testing)",
            "GET  /claims": "List available claims",
            "GET  /claims/{claim_id}": "Get claim details",
            "GET  /policies/{policy_id}": "Get policy details",
            "GET  /history/{customer_id}": "Get claim history for a customer",
            "GET  /fraud-rules": "List the 5 fraud detection rules",
            "GET  /stats": "Database statistics",
        },
        "provider": os.environ.get("LLM_PROVIDER", "auto-detect"),
        "model": os.environ.get("OLLAMA_MODEL_ID", os.environ.get("VLLM_MODEL_ID", os.environ.get("BEDROCK_MODEL_ID", "auto"))),
    }


# ─── Triage endpoints ────────────────────────────────────────────────

@app.post("/triage", response_model=TriageResponse)
def triage(req: TriageRequest):
    """Run the autonomous ReAct agent for a claim.

    Uses Strands + cast.from_env() to auto-detect the LLM provider:
      - Ollama Cloud (OLLAMA_API_KEY)
      - vLLM (VLLM_BASE_URL)
      - Bedrock (AWS_BEDROCK_REGION / AWS_LAMBDA_FUNCTION_NAME)

    The agent decides which tools to call based on the claim context.
    Simple claims → 2-3 tool calls. Complex/suspicious → 6-8 tool calls.
    """
    result = run_workflow(req.claim_id, verbose=False, use_llm=req.use_llm)
    if "error" in result and result.get("triage_decision") == "ERROR":
        raise HTTPException(status_code=400, detail=result["error"])
    return TriageResponse(
        claim_id=result.get("claim_id", req.claim_id),
        triage_decision=result.get("triage_decision", "UNKNOWN"),
        reasoning=result.get("reasoning", ""),
        risk_score=result.get("risk_score", 0),
        recommendation=result.get("recommendation", ""),
        payout_amount=result.get("payout_amount", 0),
        duration_sec=result.get("duration_sec", 0),
        trace=result.get("trace", []),
    )


@app.post("/triage/det", response_model=TriageResponse)
def triage_deterministic(claim_id: str):
    """Run deterministic triage (no LLM, uses heuristic fallbacks).

    This calls all tools in sequence and uses the deterministic router
    for the triage decision. Useful for testing without an LLM provider.
    """
    result = run_workflow(claim_id, verbose=False, use_llm=False)
    return TriageResponse(
        claim_id=result.get("claim_id", claim_id),
        triage_decision=result.get("triage_decision", "UNKNOWN"),
        reasoning=result.get("reasoning", ""),
        risk_score=result.get("risk_score", 0),
        recommendation=result.get("recommendation", ""),
        payout_amount=result.get("payout_amount", 0),
        duration_sec=result.get("duration_sec", 0),
        trace=result.get("trace", []),
    )


# ─── Data endpoints ──────────────────────────────────────────────────

@app.get("/claims")
async def list_claims(limit: int = 20, offset: int = 0):
    """List available claims from the DuckDB."""
    conn = duckdb.connect(str(get_db_path()), read_only=True)
    try:
        rows = conn.execute(
            "SELECT claim_id, policy_id, customer_id, claim_type, claim_amount, "
            "expected_triage FROM claims ORDER BY claim_id LIMIT ? OFFSET ?",
            [limit, offset],
        ).fetchall()
        return [
            {
                "claim_id": r[0],
                "policy_id": r[1],
                "customer_id": r[2],
                "claim_type": r[3],
                "claim_amount": float(r[4]),
                "expected_triage": r[5],
            }
            for r in rows
        ]
    finally:
        conn.close()


@app.get("/claims/{claim_id}")
async def get_claim(claim_id: str):
    """Get details for a specific claim."""
    from .tools.parse_claim import parse_claim
    result = parse_claim(claim_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@app.get("/policies/{policy_id}")
async def get_policy(policy_id: str):
    """Get details for a specific policy."""
    from .tools.check_policy import check_policy
    result = check_policy(policy_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@app.get("/history/{customer_id}")
async def get_history(customer_id: str):
    """Get claim history for a customer."""
    from .tools.check_claim_history import check_claim_history
    return check_claim_history(customer_id)


@app.get("/fraud-rules")
async def get_fraud_rules():
    """List the 5 fraud detection rules."""
    conn = duckdb.connect(str(get_db_path()), read_only=True)
    try:
        rows = conn.execute(
            "SELECT rule_id, description, severity FROM fraud_rules ORDER BY severity DESC"
        ).fetchall()
        return [
            {"rule_id": r[0], "description": r[1], "severity": r[2]}
            for r in rows
        ]
    finally:
        conn.close()


@app.get("/stats")
async def stats():
    """Database statistics — table counts and sizes."""
    conn = duckdb.connect(str(get_db_path()), read_only=True)
    try:
        tables = ["policies", "claims", "claim_history", "fraud_rules"]
        result = {}
        for table in tables:
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            result[table] = count

        # Claims by type
        type_counts = conn.execute(
            "SELECT claim_type, COUNT(*) FROM claims GROUP BY claim_type ORDER BY COUNT(*) DESC"
        ).fetchall()
        result["claims_by_type"] = {r[0]: r[1] for r in type_counts}

        # Claims by expected triage
        triage_counts = conn.execute(
            "SELECT expected_triage, COUNT(*) FROM claims "
            "WHERE expected_triage != '' GROUP BY expected_triage"
        ).fetchall()
        result["claims_by_triage"] = {r[0]: r[1] for r in triage_counts}

        # DB file size
        db_path = get_db_path()
        result["db_size_kb"] = round(db_path.stat().st_size / 1024, 1)
        result["db_path"] = str(db_path)

        return result
    finally:
        conn.close()
