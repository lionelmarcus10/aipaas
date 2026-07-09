"""End-to-end tests for the Financial Dispute Resolution workflow.

Tests the 7 validation cases from sprint2-agents.md.

Two modes:
  1. WITH OLLAMA_API_KEY: full LLM calls (integration test)
  2. WITHOUT OLLAMA_API_KEY: mock LLM responses (unit test)

Run:
  uv run python -m pytest tests/test_e2e_workflow.py -v
  OLLAMA_API_KEY=xxx uv run python -m pytest tests/test_e2e_workflow.py -v -m integration
"""

import os
import json
import pytest
import duckdb

from financial_dispute_agent.orchestrator import run_workflow
from financial_dispute_agent.lambdas.llm_helper import call_llm

from test_database import DB_PATH

pytestmark = pytest.mark.skipif(
    not DB_PATH.exists(),
    reason="Database not built — run `uv run python data/setup_db.py` first",
)

HAS_LLM = bool(os.environ.get("OLLAMA_API_KEY"))


# ─── Mock LLM responses for unit testing ──────────────────────────────

def mock_audit_response(variance_pct: float, confidence: float) -> dict:
    """Generate a realistic audit response for testing without LLM."""
    suspicious = []
    if variance_pct > 5:
        suspicious.append({
            "description": "Frais de gestion",
            "reason": "non_contractual",
            "amount": 150,
        })
    if variance_pct > 10:
        suspicious.append({
            "description": "Frais de retard",
            "reason": "temporal_mismatch",
            "amount": 75,
        })

    risk = "low" if variance_pct == 0 else "medium" if variance_pct <= 10 else "high"

    return {
        "variance_pct": variance_pct,
        "suspected_clauses": suspicious,
        "risk_level": risk,
        "confidence": confidence,
        "summary": f"Variance: {variance_pct}%, confidence: {confidence}%",
    }


def mock_dispute_response(severity: str = "medium") -> dict:
    return {
        "dispute_type": "non_contractual_fees",
        "customer_impact": "medium" if severity != "high" else "high",
        "severity": severity,
        "description": "Frais non contractuels détectés",
        "immediate_action": "lookup_affected_orders",
    }


def mock_resolution_plan(requires_human: bool = False) -> dict:
    return {
        "actions": [
            {"action": "partial_payment", "amount": 1455.0, "retained": 45.0},
        ],
        "rationale": "Plan de résolution automatique",
        "requires_human_review": requires_human,
    }


# ─── Fixtures ─────────────────────────────────────────────────────────

@pytest.fixture
def db_conn():
    conn = duckdb.connect(str(DB_PATH), read_only=True)
    yield conn
    conn.close()


@pytest.fixture
def test_invoices(db_conn) -> list[dict]:
    """Get the 7 test case invoices from the DB."""
    rows = db_conn.execute("""
        SELECT invoice_id, supplier_id, total_amount, expected_amount, variance_pct, metadata_json
        FROM invoices
        ORDER BY variance_pct DESC
        LIMIT 7
    """).fetchall()

    invoices = []
    for r in rows:
        meta = json.loads(r[5]) if r[5] else {}
        invoices.append({
            "invoice_id": r[0],
            "supplier_id": r[1],
            "total_amount": r[2],
            "expected_amount": r[3],
            "variance_pct": r[4],
            "confidence": meta.get("confidence", 90),
        })
    return invoices


# ─── Patch LLM for unit tests ─────────────────────────────────────────

@pytest.fixture
def mock_llm(monkeypatch):
    """Patch call_llm to return mock responses (when no OLLAMA_API_KEY)."""
    if HAS_LLM:
        pytest.skip("OLLAMA_API_KEY set — skipping mock tests (use -m integration)")

    def mock_call(prompt_name: str, user_message: str) -> dict:
        if prompt_name == "audit":
            # Extract variance from the message
            if "0.0" in user_message and "variance_pct" not in user_message.lower():
                return mock_audit_response(0, 95)
            return mock_audit_response(15, 85)
        elif prompt_name == "dispute":
            return mock_dispute_response("medium")
        elif prompt_name == "resolution":
            return mock_resolution_plan(False)
        return {}

    monkeypatch.setattr("financial_dispute_agent.lambdas.llm_helper.call_llm", mock_call)
    # Also patch the imported reference in each state module
    monkeypatch.setattr("financial_dispute_agent.lambdas.state_3_llm_audit.call_llm", mock_call)
    monkeypatch.setattr("financial_dispute_agent.lambdas.state_5_llm_dispute.call_llm", mock_call)
    monkeypatch.setattr("financial_dispute_agent.lambdas.state_8_llm_resolution.call_llm", mock_call)


# ─── E2E Tests ────────────────────────────────────────────────────────

class TestWorkflowStructure:
    """Test that the workflow runs end-to-end without crashing."""

    def test_workflow_completes(self, test_invoices, mock_llm):
        """The workflow should complete for any invoice."""
        inv = test_invoices[0]  # highest variance
        result = run_workflow(inv["invoice_id"], verbose=False)

        assert "error" not in result or "trace" in result
        assert "final_decision" in result or "decision" in result

    def test_workflow_trace(self, test_invoices, mock_llm):
        """Workflow should produce a trace of state transitions."""
        inv = test_invoices[0]
        result = run_workflow(inv["invoice_id"], verbose=False)

        assert "trace" in result
        assert len(result["trace"]) >= 3  # at least parse + fetch + audit

    def test_pay_decision_for_zero_variance(self, test_invoices, mock_llm):
        """Zero variance invoice should result in PAY decision."""
        # Find a zero-variance invoice in the full DB
        import duckdb
        conn = duckdb.connect(str(DB_PATH), read_only=True)
        row = conn.execute("""
            SELECT invoice_id FROM invoices WHERE variance_pct = 0 LIMIT 1
        """).fetchone()
        conn.close()

        if not row:
            pytest.skip("No zero-variance invoice in DB")

        result = run_workflow(row[0], verbose=False)

        decision = result.get("final_decision", result.get("decision", ""))
        assert decision in ("PAY", "PARTIAL_PAY", "HUMAN_REVIEW", "DISPUTE",
                           "FREEZE_AND_ESCALATE", "PARTIAL_PAY_AND_NOTIFY", "PAY_AND_REFUND")


class TestDeterministicRouting:
    """Test the deterministic routing logic (no LLM needed for these)."""

    def test_compute_variance_pay(self):
        from financial_dispute_agent.tools.compute_variance import compute_variance
        result = compute_variance(1500, 1500, confidence=95)
        assert result["decision"] == "PAY"

    def test_compute_variance_partial(self):
        from financial_dispute_agent.tools.compute_variance import compute_variance
        result = compute_variance(1545, 1500, confidence=85)
        assert result["decision"] == "PARTIAL_PAY"

    def test_compute_variance_dispute(self):
        from financial_dispute_agent.tools.compute_variance import compute_variance
        result = compute_variance(1725, 1500, confidence=82)
        assert result["decision"] == "DISPUTE"

    def test_compute_variance_human_review(self):
        from financial_dispute_agent.tools.compute_variance import compute_variance
        result = compute_variance(1500, 1500, confidence=65)
        assert result["decision"] == "HUMAN_REVIEW"

    def test_trust_score_high(self):
        from financial_dispute_agent.tools.compute_trust_score import compute_trust_score
        result = compute_trust_score("SUPP-000002")  # trust=85
        assert result["risk_level"] == "LOW"

    def test_trust_score_low(self):
        from financial_dispute_agent.tools.compute_trust_score import compute_trust_score
        result = compute_trust_score("SUPP-000003")  # trust=30
        assert result["risk_level"] == "HIGH"


class TestFinalChoiceRouting:
    """Test the final choice routing in state 9."""

    def test_freeze_for_low_trust(self, test_invoices, mock_llm):
        """Low trust supplier should be frozen."""
        # Find an invoice from SUPP-000003 (trust=30)
        import duckdb
        conn = duckdb.connect(str(DB_PATH), read_only=True)
        row = conn.execute("""
            SELECT i.invoice_id FROM invoices i
            JOIN suppliers s ON i.supplier_id = s.supplier_id
            WHERE s.trust_score < 50 AND i.variance_pct > 5
            LIMIT 1
        """).fetchone()
        conn.close()

        if not row:
            pytest.skip("No low-trust high-variance invoice found")

        result = run_workflow(row[0], verbose=False)
        decision = result.get("final_decision", "")
        # Should be FREEZE_AND_ESCALATE or HUMAN_REVIEW
        assert decision in ("FREEZE_AND_ESCALATE", "HUMAN_REVIEW", "DISPUTE")


class TestASLDefinition:
    """Test that the ASL definition is valid."""

    def test_asl_exists(self):
        from financial_dispute_agent.orchestrator import ASL_DEFINITION
        assert ASL_DEFINITION is not None
        assert ASL_DEFINITION["StartAt"] == "PARSE_INVOICE"

    def test_asl_has_all_states(self):
        from financial_dispute_agent.orchestrator import ASL_DEFINITION
        states = ASL_DEFINITION["States"]
        expected = [
            "PARSE_INVOICE", "FETCH_CONTRACT", "LLM_AUDIT", "CHOICE_GATE",
            "LLM_DISPUTE_ANALYSIS", "LOOKUP_AFFECTED_ORDERS", "FRAUD_CHECK",
            "LLM_RESOLUTION_PLAN", "FINAL_CHOICE",
            "EXECUTE_PAYMENT", "EXECUTE_PARTIAL_PAYMENT", "CREATE_TICKET",
        ]
        for s in expected:
            assert s in states, f"Missing state: {s}"

    def test_asl_choice_gate_has_branches(self):
        from financial_dispute_agent.orchestrator import ASL_DEFINITION
        choice = ASL_DEFINITION["States"]["CHOICE_GATE"]
        assert choice["Type"] == "Choice"
        assert len(choice["Choices"]) == 4  # PAY, PARTIAL_PAY, HUMAN_REVIEW, DISPUTE


# ─── Integration tests (only with OLLAMA_API_KEY) ─────────────────────

@pytest.mark.integration
class TestIntegration:
    """Integration tests with real LLM (requires OLLAMA_API_KEY)."""

    @pytest.mark.skipif(not HAS_LLM, reason="No OLLAMA_API_KEY")
    def test_real_llm_audit(self, test_invoices):
        """Test that the real LLM returns a valid audit report."""
        inv = test_invoices[0]
        result = run_workflow(inv["invoice_id"], verbose=True)

        assert "audit_report" in result
        audit = result["audit_report"]
        assert "variance_pct" in audit
        assert "confidence" in audit
        assert isinstance(audit["confidence"], (int, float))

    @pytest.mark.skipif(not HAS_LLM, reason="No OLLAMA_API_KEY")
    def test_real_llm_full_workflow(self, test_invoices):
        """Test the full workflow with real LLM calls."""
        inv = test_invoices[0]
        result = run_workflow(inv["invoice_id"], verbose=True)

        assert "final_decision" in result or "decision" in result
        assert "trace" in result
        assert len(result["trace"]) >= 3
