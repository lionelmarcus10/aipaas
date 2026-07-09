"""Test the financial_dispute.duckdb database.

Run:  uv run pytest tests/test_database.py -v
"""

import os
from pathlib import Path

import duckdb
import pytest

DB_PATH = Path(__file__).parent.parent / "data" / "financial_dispute.duckdb"

pytestmark = pytest.mark.skipif(
    not DB_PATH.exists(),
    reason="Database not built — run `uv run python data/setup_db.py` first",
)


@pytest.fixture
def conn():
    c = duckdb.connect(str(DB_PATH), read_only=True)
    yield c
    c.close()


def test_suppliers_exist(conn):
    """Suppliers should exist (CUAD + MessyOps merged 1:1)."""
    count = conn.execute("SELECT COUNT(*) FROM suppliers").fetchone()[0]
    assert count >= 1, f"Expected >=1 suppliers, got {count}"


def test_suppliers_have_contracts(conn):
    """Each supplier should have a non-empty contract_text (from CUAD)."""
    df = conn.execute("SELECT supplier_id, LENGTH(contract_text) as len FROM suppliers").fetchdf()
    assert all(df["len"] > 100), "All contracts should be > 100 chars"
    assert all(df["len"] > 0), "No empty contracts"


def test_suppliers_have_trust_scores(conn):
    """Each supplier should have a trust_score between 0 and 100."""
    df = conn.execute("SELECT trust_score FROM suppliers").fetchdf()
    assert all(0 <= s <= 100 for s in df["trust_score"]), "Trust scores out of range"


def test_suppliers_have_messyops_tier(conn):
    """Each supplier should have a reliability_tier from MessyOps."""
    df = conn.execute("SELECT reliability_tier FROM suppliers").fetchdf()
    valid_tiers = {"Reliable", "Average", "Unreliable"}
    actual = set(df["reliability_tier"].unique())
    assert actual.issubset(valid_tiers), f"Unexpected tiers: {actual - valid_tiers}"


def test_invoices_exist(conn):
    """Faker invoices should exist (7 test + N random per supplier)."""
    count = conn.execute("SELECT COUNT(*) FROM invoices").fetchone()[0]
    assert count >= 7, f"Expected >=7 invoices (test cases), got {count}"


def test_invoices_have_variance(conn):
    """Invoices should have variance_pct values."""
    df = conn.execute("SELECT variance_pct FROM invoices").fetchdf()
    assert all(v >= 0 for v in df["variance_pct"]), "Negative variance"


def test_purchase_orders_exist(conn):
    """Purchase orders from MessyOps should exist."""
    count = conn.execute("SELECT COUNT(*) FROM purchase_orders").fetchone()[0]
    assert count >= 1, f"Expected >=1 purchase orders, got {count}"


def test_supplier_invoices_exist(conn):
    """Supplier invoices from MessyOps should exist."""
    count = conn.execute("SELECT COUNT(*) FROM supplier_invoices").fetchone()[0]
    assert count >= 1, f"Expected >=1 supplier invoices, got {count}"


def test_orders_exist(conn):
    """Sales orders from MessyOps should exist (backward compat table)."""
    count = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    assert count >= 1, f"Expected >=1 orders, got {count}"


def test_orders_link_to_suppliers(conn):
    """All orders should link to a valid supplier."""
    df = conn.execute("""
        SELECT COUNT(*) as orphan_count
        FROM orders o
        LEFT JOIN suppliers s ON o.supplier_id = s.supplier_id
        WHERE s.supplier_id IS NULL
    """).fetchdf()
    assert df["orphan_count"][0] == 0, "Orphan orders found (no matching supplier)"


def test_invoices_link_to_suppliers(conn):
    """All Faker invoices should link to a valid supplier."""
    df = conn.execute("""
        SELECT COUNT(*) as orphan_count
        FROM invoices i
        LEFT JOIN suppliers s ON i.supplier_id = s.supplier_id
        WHERE s.supplier_id IS NULL
    """).fetchdf()
    assert df["orphan_count"][0] == 0, "Orphan invoices found (no matching supplier)"


def test_purchase_orders_link_to_suppliers(conn):
    """All purchase orders should link to a valid supplier."""
    df = conn.execute("""
        SELECT COUNT(*) as orphan_count
        FROM purchase_orders po
        LEFT JOIN suppliers s ON po.supplier_id = s.supplier_id
        WHERE s.supplier_id IS NULL
    """).fetchdf()
    assert df["orphan_count"][0] == 0, "Orphan purchase orders found"


def test_products_link_to_suppliers(conn):
    """All products should link to a valid supplier via primary_supplier_id."""
    df = conn.execute("""
        SELECT COUNT(*) as orphan_count
        FROM products p
        LEFT JOIN suppliers s ON p.primary_supplier_id = s.supplier_id
        WHERE s.supplier_id IS NULL
    """).fetchdf()
    assert df["orphan_count"][0] == 0, "Orphan products found (no matching supplier)"


def test_test_case_1_zero_variance(conn):
    """Cas 1 : au moins une facture avec variance 0%."""
    df = conn.execute("SELECT COUNT(*) as c FROM invoices WHERE variance_pct = 0").fetchdf()
    assert df["c"][0] >= 1, "No zero-variance invoice found"


def test_test_case_3_high_variance(conn):
    """Cas 3 : au moins une facture avec variance > 10%."""
    df = conn.execute("SELECT COUNT(*) as c FROM invoices WHERE variance_pct > 10").fetchdf()
    assert df["c"][0] >= 1, "No high-variance invoice found"


def test_join_invoice_contract(conn):
    """Join invoice + contract should work (this is what the LLM audit uses)."""
    df = conn.execute("""
        SELECT i.invoice_id, i.total_amount, i.variance_pct,
               s.supplier_name, LENGTH(s.contract_text) as contract_len
        FROM invoices i
        JOIN suppliers s ON i.supplier_id = s.supplier_id
        LIMIT 5
    """).fetchdf()
    assert len(df) >= 1
    assert all(df["contract_len"] > 0)


def test_join_orders_supplier(conn):
    """Join orders + supplier should work (this is what lookup_affected_orders uses)."""
    # Get the first supplier_id from the DB (MessyOps uses SUPP-000001 format)
    first_supplier = conn.execute("SELECT supplier_id, trust_score FROM suppliers LIMIT 1").fetchone()
    sid = first_supplier[0]
    trust = first_supplier[1]

    df = conn.execute("""
        SELECT o.order_id, o.amount, s.supplier_name, s.trust_score
        FROM orders o
        JOIN suppliers s ON o.supplier_id = s.supplier_id
        WHERE o.supplier_id = ?
        LIMIT 5
    """, [sid]).fetchdf()
    assert len(df) >= 1
    assert all(df["trust_score"] == trust)


def test_join_po_supplier_invoice(conn):
    """Join purchase_order + supplier + supplier_invoice (procure-to-pay chain)."""
    df = conn.execute("""
        SELECT po.purchase_order_id, po.total_amount as po_amount,
               si.invoice_amount, si.invoice_status,
               s.supplier_name, s.reliability_tier
        FROM purchase_orders po
        JOIN suppliers s ON po.supplier_id = s.supplier_id
        LEFT JOIN supplier_invoices si ON po.purchase_order_id = si.purchase_order_id
        LIMIT 5
    """).fetchdf()
    assert len(df) >= 1
    assert all(df["reliability_tier"].notna())
