"""Tool 1 : parse_invoice

État 1 du Step Functions.
Extrait les données structurées d'une facture depuis la DuckDB.

Input:  {"invoice_id": "INV-1234"}
Output: {"invoice_id", "supplier_id", "supplier_name", "invoice_date",
         "due_date", "total_amount", "expected_amount", "lines", "metadata"}

Pas de LLM : parsing structuré pur via Pydantic.
"""

from pydantic import BaseModel, Field

from .db import get_connection


class InvoiceLine(BaseModel):
    description: str
    quantity: int = 1
    unit_price: float
    amount: float


class ParsedInvoice(BaseModel):
    invoice_id: str
    supplier_id: str
    supplier_name: str
    invoice_date: str
    due_date: str
    total_amount: float
    expected_amount: float
    variance_pct: float
    lines: list[InvoiceLine]
    metadata: dict = Field(default_factory=dict)


def parse_invoice(invoice_id: str) -> dict:
    """Parse an invoice from the database into structured data.

    Args:
        invoice_id: The invoice identifier (e.g. "INV-1234").

    Returns:
        Dict with structured invoice data, or {"error": "..."} if not found.
    """
    import json

    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM invoices WHERE invoice_id = ?",
            [invoice_id],
        ).fetchone()

        if row is None:
            return {"error": f"Invoice {invoice_id} not found"}

        (
            inv_id, sup_id, sup_name, inv_date, due_date,
            total, expected, variance, lines_json, metadata_json,
        ) = row

        lines = [InvoiceLine(**l) for l in json.loads(lines_json)]
        metadata = json.loads(metadata_json) if metadata_json else {}

        invoice = ParsedInvoice(
            invoice_id=inv_id,
            supplier_id=sup_id,
            supplier_name=sup_name,
            invoice_date=inv_date,
            due_date=due_date,
            total_amount=total,
            expected_amount=expected,
            variance_pct=variance,
            lines=lines,
            metadata=metadata,
        )

        return invoice.model_dump()
    finally:
        conn.close()
