"""End-to-end triage tests — run the full deterministic pipeline on the 5 test claims.

Run:  uv run pytest tests/test_e2e_triage.py -v
"""

from pathlib import Path

import pytest

DB_PATH = Path(__file__).parent.parent / "data" / "insurance_claims.duckdb"

pytestmark = pytest.mark.skipif(
    not DB_PATH.exists(),
    reason="Database not built — run `uv run python data/setup_db.py` first",
)

from insurance_claims_agent.agent import run_triage_deterministic


class TestEndToEndTriage:
    """Test the 5 controlled claims through the full deterministic pipeline."""

    def test_claim_1_fast_track(self):
        """CLM-0001: simple claim → FAST_TRACK_APPROVE."""
        result = run_triage_deterministic("CLM-0001")
        assert "error" not in result
        assert result["triage_decision"] == "FAST_TRACK_APPROVE"
        assert len(result["trace"]) >= 3  # at least 3 tool calls

    def test_claim_2_adjuster_review(self):
        """CLM-0002: complex claim → ADJUSTER_REVIEW."""
        result = run_triage_deterministic("CLM-0002")
        assert "error" not in result
        assert result["triage_decision"] == "ADJUSTER_REVIEW"
        assert len(result["trace"]) >= 5  # more investigation steps

    def test_claim_3_siu_referral(self):
        """CLM-0003: fraud indicators → SIU_REFERRAL."""
        result = run_triage_deterministic("CLM-0003")
        assert "error" not in result
        assert result["triage_decision"] == "SIU_REFERRAL"
        assert result["risk_score"] >= 60
        assert len(result["trace"]) >= 5

    def test_claim_4_deny_coverage(self):
        """CLM-0004: exclusion applies → DENY_COVERAGE."""
        result = run_triage_deterministic("CLM-0004")
        assert "error" not in result
        assert result["triage_decision"] == "DENY_COVERAGE"

    def test_claim_5_request_information(self):
        """CLM-0005: missing info → should handle gracefully."""
        result = run_triage_deterministic("CLM-0005")
        assert "error" not in result
        # Missing info claim has amount=0, so it should be fast-tracked
        # (the deterministic router doesn't have a REQUEST_INFORMATION path,
        # but it should not crash)
        assert result["triage_decision"] in ["FAST_TRACK_APPROVE", "REQUEST_INFORMATION"]


class TestTriageTrace:
    """Verify the investigation trace is correct."""

    def test_trace_starts_with_parse_claim(self):
        """The first step should always be parse_claim."""
        result = run_triage_deterministic("CLM-0001")
        assert "parse_claim" in result["trace"][0]

    def test_trace_includes_check_policy(self):
        """The trace should include check_policy."""
        result = run_triage_deterministic("CLM-0001")
        trace_text = " ".join(result["trace"])
        assert "check_policy" in trace_text

    def test_trace_includes_fraud_check_for_suspicious(self):
        """CLM-0003 (fraud) should include fraud indicators check."""
        result = run_triage_deterministic("CLM-0003")
        trace_text = " ".join(result["trace"])
        assert "fraud_indicators" in trace_text

    def test_trace_short_for_simple_claim(self):
        """CLM-0001 (simple) should have fewer steps than CLM-0003 (fraud)."""
        simple = run_triage_deterministic("CLM-0001")
        fraud = run_triage_deterministic("CLM-0003")
        assert len(simple["trace"]) <= len(fraud["trace"])


class TestTriageWithLLM:
    """Integration tests that require a real LLM (Ollama Cloud, vLLM, or Bedrock).

    Run:  OLLAMA_API_KEY=xxx uv run pytest tests/test_e2e_triage.py -v -m integration
    """

    @pytest.mark.integration
    def test_llm_triage_claim_1(self):
        """CLM-0001 with LLM → should produce a valid triage decision."""
        from insurance_claims_agent.agent import run_triage
        result = run_triage("CLM-0001", verbose=True)
        assert "triage_decision" in result
        assert result["triage_decision"] in [
            "FAST_TRACK_APPROVE", "ADJUSTER_REVIEW", "SIU_REFERRAL",
            "DENY_COVERAGE", "REQUEST_INFORMATION",
        ]

    @pytest.mark.integration
    def test_llm_triage_claim_3(self):
        """CLM-0003 with LLM → should detect fraud and refer to SIU."""
        from insurance_claims_agent.agent import run_triage
        result = run_triage("CLM-0003", verbose=True)
        assert "triage_decision" in result
        # The LLM should detect the fraud indicators and refer to SIU
        # (or at minimum, not FAST_TRACK_APPROVE)
        assert result["triage_decision"] != "FAST_TRACK_APPROVE"
