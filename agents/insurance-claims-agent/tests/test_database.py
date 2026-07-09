"""Test the insurance_claims.duckdb database.

Run:  uv run pytest tests/test_database.py -v
"""

from pathlib import Path

import duckdb
import pytest

DB_PATH = Path(__file__).parent.parent / "data" / "insurance_claims.duckdb"

pytestmark = pytest.mark.skipif(
    not DB_PATH.exists(),
    reason="Database not built — run `uv run python data/setup_db.py` first",
)


@pytest.fixture
def conn():
    c = duckdb.connect(str(DB_PATH), read_only=True)
    yield c
    c.close()


# ─── Table existence ─────────────────────────────────────────────────

def test_policies_exist(conn):
    """Policies table should have data."""
    count = conn.execute("SELECT COUNT(*) FROM policies").fetchone()[0]
    assert count >= 5, f"Expected >=5 policies, got {count}"


def test_claims_exist(conn):
    """Claims table should have data."""
    count = conn.execute("SELECT COUNT(*) FROM claims").fetchone()[0]
    assert count >= 5, f"Expected >=5 claims, got {count}"


def test_claim_history_exists(conn):
    """Claim history table should have data."""
    count = conn.execute("SELECT COUNT(*) FROM claim_history").fetchone()[0]
    assert count >= 1, f"Expected >=1 history entries, got {count}"


def test_fraud_rules_exist(conn):
    """Fraud rules table should have the 5 rules."""
    count = conn.execute("SELECT COUNT(*) FROM fraud_rules").fetchone()[0]
    assert count == 5, f"Expected 5 fraud rules, got {count}"


# ─── Data integrity ──────────────────────────────────────────────────

def test_claims_link_to_policies(conn):
    """All claims should link to a valid policy."""
    df = conn.execute("""
        SELECT COUNT(*) as orphan_count
        FROM claims c
        LEFT JOIN policies p ON c.policy_id = p.policy_id
        WHERE p.policy_id IS NULL
    """).fetchdf()
    assert df["orphan_count"][0] == 0, "Orphan claims found (no matching policy)"


def test_history_links_to_customers(conn):
    """All claim history entries should link to a valid customer (via policies)."""
    df = conn.execute("""
        SELECT COUNT(*) as orphan_count
        FROM claim_history h
        LEFT JOIN policies p ON h.customer_id = p.customer_id
        WHERE p.customer_id IS NULL
    """).fetchdf()
    assert df["orphan_count"][0] == 0, "Orphan history entries found"


# ─── Test claims with expected triage ────────────────────────────────

def test_test_claims_have_expected_triage(conn):
    """The 5 controlled test claims should have expected_triage set."""
    df = conn.execute("""
        SELECT claim_id, expected_triage FROM claims
        WHERE expected_triage != ''
        ORDER BY claim_id
    """).fetchdf()
    assert len(df) >= 5, f"Expected >=5 test claims, got {len(df)}"

    expected = {
        "CLM-0001": "FAST_TRACK_APPROVE",
        "CLM-0002": "ADJUSTER_REVIEW",
        "CLM-0003": "SIU_REFERRAL",
        "CLM-0004": "DENY_COVERAGE",
        "CLM-0005": "REQUEST_INFORMATION",
    }
    for _, row in df.iterrows():
        if row["claim_id"] in expected:
            assert row["expected_triage"] == expected[row["claim_id"]], \
                f"{row['claim_id']}: expected {expected[row['claim_id']]}, got {row['expected_triage']}"


# ─── Fraud pattern in history ────────────────────────────────────────

def test_customer_003_has_repeat_claims(conn):
    """CUS-0003 should have repeat claims in history (fraud pattern)."""
    count = conn.execute(
        "SELECT COUNT(*) FROM claim_history WHERE customer_id = 'CUS-0003'"
    ).fetchone()[0]
    assert count >= 2, f"CUS-0003 should have >=2 history entries, got {count}"


def test_customer_003_has_fraud_flag(conn):
    """CUS-0003 should have at least one fraud-flagged claim in history."""
    count = conn.execute(
        "SELECT COUNT(*) FROM claim_history WHERE customer_id = 'CUS-0003' AND fraud_found = true"
    ).fetchone()[0]
    assert count >= 1, "CUS-0003 should have at least 1 fraud-flagged claim"


# ─── Policy data ─────────────────────────────────────────────────────

def test_policies_have_exclusions(conn):
    """Policies should have exclusions (JSON array)."""
    df = conn.execute("SELECT policy_id, exclusions FROM policies LIMIT 5").fetchdf()
    for _, row in df.iterrows():
        import json
        exclusions = json.loads(row["exclusions"])
        assert len(exclusions) > 0, f"Policy {row['policy_id']} has no exclusions"


def test_policy_3_is_recent(conn):
    """Policy 3 (POL-0003) should be recent (for fraud test — claim within 30 days)."""
    row = conn.execute("SELECT start_date FROM policies WHERE policy_id = 'POL-0003'").fetchone()
    assert row is not None, "POL-0003 not found"
    from datetime import datetime
    start = datetime.strptime(row[0], "%Y-%m-%d")
    days = (datetime.now() - start).days
    assert days < 30, f"POL-0003 should be <30 days old, got {days} days"


def test_policy_4_has_natural_disaster_exclusion(conn):
    """Policy 4 (POL-0004) should have 'natural_disaster' exclusion (for coverage denial test)."""
    row = conn.execute("SELECT exclusions FROM policies WHERE policy_id = 'POL-0004'").fetchone()
    assert row is not None, "POL-0004 not found"
    import json
    exclusions = json.loads(row[0])
    assert "natural_disaster" in exclusions, f"POL-0004 should have 'natural_disaster' exclusion, got {exclusions}"


# ─── Join tests ──────────────────────────────────────────────────────

def test_join_claim_policy(conn):
    """Join claim + policy should work."""
    df = conn.execute("""
        SELECT c.claim_id, c.claim_type, c.claim_amount,
               p.policy_type, p.coverage_limit, p.deductible
        FROM claims c
        JOIN policies p ON c.policy_id = p.policy_id
        LIMIT 5
    """).fetchdf()
    assert len(df) >= 1
    assert all(df["claim_amount"] >= 0)


def test_join_claim_history_customer(conn):
    """Join claim_history + policies should work."""
    df = conn.execute("""
        SELECT h.customer_id, h.claim_id, h.claim_amount, h.fraud_found,
               p.policy_type
        FROM claim_history h
        JOIN policies p ON h.customer_id = p.customer_id
        LIMIT 5
    """).fetchdf()
    assert len(df) >= 1
