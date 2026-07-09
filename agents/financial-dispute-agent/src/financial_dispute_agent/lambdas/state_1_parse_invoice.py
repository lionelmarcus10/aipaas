"""State 1: PARSE_INVOICE — extract structured invoice data.

Script only, no LLM.
"""

from ..tools.parse_invoice import parse_invoice


def handler(event: dict) -> dict:
    """Parse an invoice from the database.

    Input:  {"invoice_id": "INV-1234"}
    Output: {"invoice": {...}, "supplier_id": "SUP-001", ...}
    """
    invoice_id = event["invoice_id"]
    invoice = parse_invoice(invoice_id)

    if "error" in invoice:
        return {"error": invoice["error"], "state": "PARSE_INVOICE"}

    return {
        "state": "PARSE_INVOICE",
        "invoice": invoice,
        "supplier_id": invoice["supplier_id"],
        "total_amount": invoice["total_amount"],
        "expected_amount": invoice["expected_amount"],
    }
