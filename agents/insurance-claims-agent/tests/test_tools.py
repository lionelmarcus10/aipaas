"""Test the 7 deterministic tools.

Run:  uv run pytest tests/test_tools.py -v
"""

import json
from pathlib import Path

import pytest

DB_PATH = Path(__file__).parent.parent / "data" / "insurance_claims.duckdb"

pytestmark = pytest.mark.skipif(
    not DB_PATH.exists(),
    reason="Database not built — run `uv run python data/setup_db.py` first",
)

from insurance_claims_agent.tools.parse_claim import parse_claim
from insurance_claims_agent.tools.check_policy import check_policy
from insurance_claims_agent.tools.check_claim_history import check_claim_history
from insurance_claims_agent.tools.check_fraud_indicators import check_fraud_indicators
from insurance_claims_agent.tools.check_coverage import check_coverage
from insurance_claims_agent.tools.calculate_payout import calculate_payout
from insurance_claims_agent.tools.generate_triage_report import generate_triage_report


# ─── parse_claim ─────────────────────────────────────────────────────

class TestParseClaim:
    def test_existing_claim(self):
        """parse_claim should return structured data for CLM-0001."""
        result = parse_claim("CLM-0001")
        assert "error" not in result
        assert result["claim_id"] == "CLM-0001"
        assert result["claim_amount"] > 0
        assert len(result["description"]) > 10

    def test_nonexistent_claim(self):
        """parse_claim should return error for unknown claim."""
        result = parse_claim("CLM-9999")
        assert "error" in result

    def test_claim_has_policy_id(self):
        """Parsed claim should have a policy_id."""
        result = parse_claim("CLM-0001")
        assert result["policy_id"].startswith("POL-")


# ─── check_policy ────────────────────────────────────────────────────

class TestCheckPolicy:
    def test_existing_policy(self):
        """check_policy should return policy details for POL-0001."""
        result = check_policy("POL-0001")
        assert "error" not in result
        assert result["policy_id"] == "POL-0001"
        assert result["coverage_limit"] > 0
        assert result["deductible"] >= 0
        assert len(result["exclusions"]) > 0

    def test_nonexistent_policy(self):
        """check_policy should return error for unknown policy."""
        result = check_policy("POL-9999")
        assert "error" in result

    def test_policy_has_days_since_start(self):
        """Policy should have days_since_start calculated."""
        result = check_policy("POL-0001")
        assert "days_since_start" in result
        assert result["days_since_start"] >= 0


# ─── check_claim_history ─────────────────────────────────────────────

class TestCheckClaimHistory:
    def test_customer_with_history(self):
        """CUS-0003 should have claim history."""
        result = check_claim_history("CUS-0003")
        assert result["total_claims"] >= 2
        assert result["has_repeat_claims"] == True

    def test_customer_without_history(self):
        """A customer with no history should return empty."""
        result = check_claim_history("CUS-9999")
        assert result["total_claims"] == 0
        assert result["has_fraud_history"] == False

    def test_customer_003_has_fraud(self):
        """CUS-0003 should have fraud history."""
        result = check_claim_history("CUS-0003")
        assert result["has_fraud_history"] == True


# ─── check_fraud_indicators ──────────────────────────────────────────

class TestCheckFraudIndicators:
    def test_no_red_flags_for_simple_claim(self):
        """A simple claim should have few or no red flags."""
        claim = {"claim_amount": 500, "claim_type": "auto_collision", "description": "minor scratch", "police_report_filed": True}
        policy = {"days_since_start": 365, "coverage_limit": 50000, "deductible": 500}
        history = {"claims": [], "has_repeat_claims": False, "has_fraud_history": False, "total_claims": 0}
        result = check_fraud_indicators(claim, policy, history)
        assert result["red_flag_count"] <= 1
        assert result["fraud_risk_level"] == "LOW"

    def test_red_flags_for_suspicious_claim(self):
        """A suspicious claim should trigger multiple red flags."""
        claim = {"claim_amount": 45000, "claim_type": "home_fire", "description": "fire reported", "police_report_filed": False}
        policy = {"days_since_start": 3, "coverage_limit": 200000, "deductible": 1000}
        history = {
            "claims": [
                {"claim_type": "home_fire", "claim_amount": 10000, "fraud_found": True},
                {"claim_type": "home_fire", "claim_amount": 12000, "fraud_found": False},
            ],
            "has_repeat_claims": True,
            "has_fraud_history": True,
            "total_claims": 2,
        }
        result = check_fraud_indicators(claim, policy, history)
        assert result["red_flag_count"] >= 3
        assert result["fraud_risk_level"] == "HIGH"
        assert result["fraud_score"] >= 60

    def test_claim_within_30_days(self):
        """Claim within 30 days of policy start should be flagged."""
        claim = {"claim_amount": 5000, "claim_type": "auto_collision", "description": "accident", "police_report_filed": True}
        policy = {"days_since_start": 5, "coverage_limit": 50000, "deductible": 500}
        history = {"claims": [], "has_repeat_claims": False, "has_fraud_history": False, "total_claims": 0}
        result = check_fraud_indicators(claim, policy, history)
        rules = [f["rule"] for f in result["red_flags"]]
        assert "claim_within_30_days" in rules

    def test_no_police_report_high_amount(self):
        """No police report for >10k should be flagged."""
        claim = {"claim_amount": 15000, "claim_type": "theft", "description": "stolen items", "police_report_filed": False}
        policy = {"days_since_start": 365, "coverage_limit": 30000, "deductible": 250}
        history = {"claims": [], "has_repeat_claims": False, "has_fraud_history": False, "total_claims": 0}
        result = check_fraud_indicators(claim, policy, history)
        rules = [f["rule"] for f in result["red_flags"]]
        assert "no_police_report_high_amount" in rules


# ─── check_coverage ──────────────────────────────────────────────────

class TestCheckCoverage:
    def test_covered_claim(self):
        """A matching claim type should be covered."""
        policy = {"policy_type": "auto", "is_active": True, "exclusions": ["racing"], "coverage_limit": 50000, "deductible": 500}
        result = check_coverage(policy, "auto_collision", "minor accident")
        assert result["is_covered"] == True

    def test_wrong_policy_type(self):
        """A mismatched claim type should not be covered."""
        policy = {"policy_type": "home", "is_active": True, "exclusions": [], "coverage_limit": 200000, "deductible": 1000}
        result = check_coverage(policy, "auto_collision", "car accident")
        assert result["is_covered"] == False
        assert "requires auto policy" in result["reason"]

    def test_inactive_policy(self):
        """An inactive policy should not cover claims."""
        policy = {"policy_type": "auto", "is_active": False, "status": "expired", "exclusions": [], "coverage_limit": 50000, "deductible": 500}
        result = check_coverage(policy, "auto_collision", "accident")
        assert result["is_covered"] == False

    def test_exclusion_hit(self):
        """An exclusion matching the description should deny coverage."""
        policy = {"policy_type": "home", "is_active": True, "exclusions": ["natural_disaster"], "coverage_limit": 200000, "deductible": 1000}
        result = check_coverage(policy, "water_damage", "Home flooded during severe storm. City declared natural disaster zone.")
        assert result["is_covered"] == False
        assert result["exclusion_hit"] == "natural_disaster"


# ─── calculate_payout ────────────────────────────────────────────────

class TestCalculatePayout:
    def test_simple_payout(self):
        """Payout = claim - deductible (no depreciation)."""
        result = calculate_payout(claim_amount=5000, coverage_limit=50000, deductible=500)
        assert result["payout_amount"] == 4500
        assert result["is_within_limit"] == True

    def test_capped_at_coverage_limit(self):
        """Payout should be capped at coverage limit."""
        result = calculate_payout(claim_amount=60000, coverage_limit=50000, deductible=500)
        assert result["coverage_applied"] == 50000
        assert result["is_within_limit"] == False
        assert result["payout_amount"] == 49500

    def test_with_depreciation(self):
        """Payout should subtract depreciation."""
        result = calculate_payout(claim_amount=10000, coverage_limit=50000, deductible=500, depreciation_pct=10)
        # 10000 - 500 - (10000 * 0.10) = 10000 - 500 - 1000 = 8500
        assert result["payout_amount"] == 8500
        assert result["depreciation_amount"] == 1000

    def test_zero_payout_when_under_deductible(self):
        """Payout should be 0 when claim < deductible."""
        result = calculate_payout(claim_amount=300, coverage_limit=50000, deductible=500)
        assert result["payout_amount"] == 0  # max(0, 300 - 500) = 0


# ─── generate_triage_report (deterministic) ──────────────────────────

class TestGenerateTriageReport:
    def test_fast_track_approve(self):
        """Simple claim with low fraud → FAST_TRACK_APPROVE."""
        claim = {"claim_amount": 500, "claim_type": "auto_collision", "description": "minor scratch"}
        policy = {"deductible": 500, "is_active": True, "status": "active"}
        coverage = {"is_covered": True, "reason": "Coverage confirmed"}
        fraud = {"fraud_score": 0, "red_flag_count": 0, "fraud_risk_level": "LOW"}
        payout = {"payout_amount": 0}
        history = {"total_claims": 0, "has_fraud_history": False}
        result = generate_triage_report(claim, policy, coverage, fraud, payout, history, use_llm=False)
        assert result["triage_decision"] == "FAST_TRACK_APPROVE"

    def test_siu_referral(self):
        """High fraud score → SIU_REFERRAL."""
        claim = {"claim_amount": 45000, "claim_type": "home_fire", "description": "fire"}
        policy = {"deductible": 1000, "is_active": True, "status": "active"}
        coverage = {"is_covered": True, "reason": "Coverage confirmed"}
        fraud = {"fraud_score": 90, "red_flag_count": 3, "fraud_risk_level": "HIGH"}
        payout = {"payout_amount": 44000}
        history = {"total_claims": 3, "has_fraud_history": True}
        result = generate_triage_report(claim, policy, coverage, fraud, payout, history, use_llm=False)
        assert result["triage_decision"] == "SIU_REFERRAL"

    def test_deny_coverage(self):
        """Not covered → DENY_COVERAGE."""
        claim = {"claim_amount": 30000, "claim_type": "water_damage", "description": "flood"}
        policy = {"deductible": 500, "is_active": True, "status": "active"}
        coverage = {"is_covered": False, "reason": "Claim excluded by policy exclusion: 'natural_disaster'"}
        fraud = {"fraud_score": 0, "red_flag_count": 0, "fraud_risk_level": "LOW"}
        payout = {"payout_amount": 0}
        history = {"total_claims": 0, "has_fraud_history": False}
        result = generate_triage_report(claim, policy, coverage, fraud, payout, history, use_llm=False)
        assert result["triage_decision"] == "DENY_COVERAGE"

    def test_adjuster_review(self):
        """High severity → ADJUSTER_REVIEW."""
        claim = {"claim_amount": 30000, "claim_type": "auto_collision", "description": "major accident"}
        policy = {"deductible": 500, "is_active": True, "status": "active"}
        coverage = {"is_covered": True, "reason": "Coverage confirmed"}
        fraud = {"fraud_score": 10, "red_flag_count": 0, "fraud_risk_level": "LOW"}
        payout = {"payout_amount": 29500}
        history = {"total_claims": 0, "has_fraud_history": False}
        result = generate_triage_report(claim, policy, coverage, fraud, payout, history, use_llm=False)
        assert result["triage_decision"] == "ADJUSTER_REVIEW"
