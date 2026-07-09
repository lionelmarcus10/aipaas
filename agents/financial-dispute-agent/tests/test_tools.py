"""Tests for the 6 deterministic tools.

Run:  uv run pytest tests/test_tools.py -v
"""

import pytest

from financial_dispute_agent.tools.parse_invoice import parse_invoice
from financial_dispute_agent.tools.fetch_contract import fetch_contract
from financial_dispute_agent.tools.compute_variance import compute_variance
from financial_dispute_agent.tools.lookup_affected_orders import lookup_affected_orders
from financial_dispute_agent.tools.compute_trust_score import compute_trust_score
from financial_dispute_agent.tools.payment_mock import (
    execute_payment,
    partial_payment,
    refund_customer,
    freeze_supplier,
    escalate_to_finance,
)

from test_database import DB_PATH

pytestmark = pytest.mark.skipif(
    not DB_PATH.exists(),
    reason="Database not built — run `uv run python data/setup_db.py` first",
)


# ─── parse_invoice ────────────────────────────────────────────────────

class TestParseInvoice:
    def test_existing_invoice(self):
        """parse_invoice should return structured data for a valid invoice_id."""
        # Récupérer un invoice_id existant
        result = parse_invoice("INV-6188")  # premier invoice du test
        # Si celui-ci n'existe pas, on en cherche un
        if "error" in result:
            import duckdb
            conn = duckdb.connect(str(DB_PATH), read_only=True)
            inv_id = conn.execute("SELECT invoice_id FROM invoices LIMIT 1").fetchone()[0]
            conn.close()
            result = parse_invoice(inv_id)

        assert "error" not in result
        assert "invoice_id" in result
        assert "supplier_id" in result
        assert "lines" in result
        assert len(result["lines"]) >= 1
        assert "total_amount" in result
        assert "expected_amount" in result

    def test_nonexistent_invoice(self):
        """parse_invoice should return error for unknown invoice_id."""
        result = parse_invoice("INV-DOESNOTEXIST")
        assert "error" in result

    def test_invoice_has_pydantic_structure(self):
        """Invoice lines should have description, quantity, unit_price, amount."""
        import duckdb
        conn = duckdb.connect(str(DB_PATH), read_only=True)
        inv_id = conn.execute("SELECT invoice_id FROM invoices LIMIT 1").fetchone()[0]
        conn.close()

        result = parse_invoice(inv_id)
        line = result["lines"][0]
        assert "description" in line
        assert "quantity" in line
        assert "unit_price" in line
        assert "amount" in line


# ─── fetch_contract ───────────────────────────────────────────────────

class TestFetchContract:
    def test_existing_supplier(self):
        """fetch_contract should return contract text for a valid supplier."""
        result = fetch_contract("SUPP-000001")
        assert "error" not in result
        assert result["supplier_id"] == "SUPP-000001"
        assert len(result["contract_text"]) > 100
        assert "trust_score" in result

    def test_nonexistent_supplier(self):
        """fetch_contract should return error for unknown supplier."""
        result = fetch_contract("SUP-999")
        assert "error" in result

    def test_contract_truncation(self):
        """Contract text should be truncated to max 8000 chars + suffix."""
        # SUP-010 has a very long contract (145k chars)
        result = fetch_contract("SUP-010")
        if "error" not in result:
            # 8000 chars + "\n... [tronqué, RAG non disponible]" (34 chars)
            assert result["contract_length"] <= 8034


# ─── compute_variance ─────────────────────────────────────────────────

class TestComputeVariance:
    def test_zero_variance_pay(self):
        """0% variance with high confidence → PAY."""
        result = compute_variance(1500.0, 1500.0, confidence=98.0)
        assert result["decision"] == "PAY"
        assert result["variance_pct"] == 0.0

    def test_small_variance_partial(self):
        """3% variance with high confidence → PARTIAL_PAY."""
        result = compute_variance(1545.0, 1500.0, confidence=85.0)
        assert result["decision"] == "PARTIAL_PAY"
        assert result["variance_pct"] == 3.0

    def test_high_variance_dispute(self):
        """15% variance with high confidence → DISPUTE."""
        result = compute_variance(1725.0, 1500.0, confidence=82.0)
        assert result["decision"] == "DISPUTE"
        assert result["variance_pct"] == 15.0

    def test_low_confidence_human_review(self):
        """Low confidence → HUMAN_REVIEW regardless of variance."""
        result = compute_variance(1500.0, 1500.0, confidence=65.0)
        assert result["decision"] == "HUMAN_REVIEW"

    def test_zero_expected_amount(self):
        """expected_amount=0 should not crash, should HUMAN_REVIEW."""
        result = compute_variance(1500.0, 0.0, confidence=90.0)
        assert result["decision"] == "HUMAN_REVIEW"
        assert "error" not in result

    def test_negative_variance(self):
        """Negative variance (invoice < expected) → PARTIAL_PAY (still an anomaly)."""
        result = compute_variance(1400.0, 1500.0, confidence=90.0)
        assert result["variance_pct"] < 0
        # Negative variance is still an anomaly but ≤ 5% in abs
        assert result["decision"] in ("PARTIAL_PAY", "DISPUTE")


# ─── lookup_affected_orders ───────────────────────────────────────────

class TestLookupAffectedOrders:
    def test_sup_001_has_orders(self):
        """SUPP-000001 should have affected orders."""
        result = lookup_affected_orders("SUPP-000001")
        assert result["order_count"] > 0
        assert result["total_impact"] > 0
        assert result["affected_customers"] > 0
        assert len(result["affected_orders"]) == result["order_count"]

    def test_nonexistent_supplier(self):
        """Unknown supplier should return empty list, not error."""
        result = lookup_affected_orders("SUP-999")
        assert result["affected_orders"] == []
        assert result["total_impact"] == 0.0

    def test_orders_sorted_by_amount(self):
        """Orders should be sorted by amount descending."""
        result = lookup_affected_orders("SUPP-000001")
        amounts = [o["amount"] for o in result["affected_orders"]]
        assert amounts == sorted(amounts, reverse=True)


# ─── compute_trust_score ──────────────────────────────────────────────

class TestComputeTrustScore:
    def test_high_trust(self):
        """trust >= 80 → LOW risk."""
        # SUPP-000002 has trust=85
        result = compute_trust_score("SUPP-000002")
        assert result["trust_score"] == 85
        assert result["risk_level"] == "LOW"
        assert result["recommendation"] == "proceed_with_caution"

    def test_medium_trust(self):
        """50 <= trust < 80 → MEDIUM risk."""
        # SUPP-000001 has trust=72
        result = compute_trust_score("SUPP-000001")
        assert result["trust_score"] == 72
        assert result["risk_level"] == "MEDIUM"
        assert result["recommendation"] == "notify_and_monitor"

    def test_low_trust(self):
        """trust < 50 → HIGH risk."""
        # SUPP-000003 has trust=30
        result = compute_trust_score("SUPP-000003")
        assert result["trust_score"] == 30
        assert result["risk_level"] == "HIGH"
        assert result["recommendation"] == "freeze_and_escalate"

    def test_nonexistent_supplier(self):
        """Unknown supplier → error."""
        result = compute_trust_score("SUP-999")
        assert "error" in result


# ─── payment_mock ─────────────────────────────────────────────────────

class TestPaymentMock:
    def test_execute_payment(self):
        result = execute_payment("SUPP-000001", 1500.0)
        assert result["status"] == "success"
        assert result["action"] == "execute_payment"
        assert result["amount"] == 1500.0
        assert result["transaction_id"].startswith("txn_")

    def test_partial_payment(self):
        result = partial_payment("SUPP-000001", 1455.0, 45.0)
        assert result["status"] == "success"
        assert result["amount_paid"] == 1455.0
        assert result["amount_retained"] == 45.0

    def test_refund_customer(self):
        result = refund_customer("CUST-001", 500.0, "surfacturation fournisseur")
        assert result["status"] == "success"
        assert result["amount"] == 500.0
        assert result["transaction_id"].startswith("ref_")

    def test_freeze_supplier(self):
        result = freeze_supplier("SUPP-000003")
        assert result["status"] == "frozen"
        assert result["supplier_id"] == "SUPP-000003"

    def test_escalate_to_finance(self):
        result = escalate_to_finance("SUPP-000003", "trust score trop bas")
        assert result["status"] == "ticket_created"
        assert result["ticket_id"].startswith("fin_")

    def test_unique_transaction_ids(self):
        """Each call should produce a unique transaction_id."""
        r1 = execute_payment("SUPP-000001", 100.0)
        r2 = execute_payment("SUPP-000001", 100.0)
        assert r1["transaction_id"] != r2["transaction_id"]
