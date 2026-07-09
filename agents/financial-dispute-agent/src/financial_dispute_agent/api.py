"""FastAPI wrapper — exposes the Financial Dispute Resolution workflow as an HTTP API.

This runs the local orchestrator (not Step Functions) inside a Kubernetes pod
with gVisor isolation. It's the dev/local deployment of the agent.

Endpoints:
  GET  /health          → liveness/readiness probe
  POST /workflow         → run the workflow for a given invoice_id
  GET  /invoices         → list available invoices from the DuckDB
"""

import os
from contextlib import asynccontextmanager

import duckdb
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .orchestrator import run_workflow


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Pre-load the embedding model at startup to avoid blocking the event loop
    on the first RAG query (which would cause liveness probe failures).
    """
    provider = os.environ.get("RAG_PROVIDER", "faiss")
    if provider == "faiss":
        try:
            from .tools.rag_faiss import get_embedder
            get_embedder()  # Pre-load the model (~2s on CPU)
            print("[api] Embedding model pre-loaded")
        except Exception as e:
            print(f"[api] Warning: could not pre-load embedding model: {e}")
    yield


app = FastAPI(
    title="Financial Dispute Resolution Agent",
    description="B1+B2 — Step Functions workflow exposed as HTTP API (local orchestrator)",
    version="0.1.0",
    lifespan=lifespan,
)


class WorkflowRequest(BaseModel):
    invoice_id: str


class WorkflowResponse(BaseModel):
    final_decision: str
    actions_executed: list
    trace: list
    invoice_id: str


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/workflow", response_model=WorkflowResponse)
def workflow(req: WorkflowRequest):
    """Run the workflow in a thread pool (non-async) so the event loop
    stays free for health checks during LLM/RAG processing.
    """
    result = run_workflow(req.invoice_id, verbose=False)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return WorkflowResponse(
        final_decision=result.get("final_decision", "UNKNOWN"),
        actions_executed=result.get("actions_executed", []),
        trace=result.get("trace", []),
        invoice_id=req.invoice_id,
    )


@app.get("/invoices")
async def list_invoices():
    from .tools.db import get_db_path

    conn = duckdb.connect(str(get_db_path()), read_only=True)
    try:
        rows = conn.execute(
            "SELECT invoice_id, supplier_id, total_amount, expected_amount, "
            "variance_pct FROM invoices ORDER BY variance_pct DESC LIMIT 20"
        ).fetchall()
        return [
            {
                "invoice_id": r[0],
                "supplier_id": r[1],
                "total_amount": float(r[2]),
                "expected_amount": float(r[3]),
                "variance_pct": float(r[4]),
            }
            for r in rows
        ]
    finally:
        conn.close()
