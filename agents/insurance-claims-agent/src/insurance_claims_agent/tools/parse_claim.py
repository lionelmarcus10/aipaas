"""Tool 1 : parse_claim

Extrait les données structurées d'une déclaration de sinistre (FNOL) depuis la DuckDB.

Input:  {"claim_id": "CLM-0001"}
Output: {"claim_id", "policy_id", "customer_id", "claim_type", "incident_date",
         "claim_date", "claim_amount", "description", "police_report_filed",
         "witnesses_count", "metadata"}

Pas de LLM : parsing structuré pur via Pydantic.
"""

import json

from pydantic import BaseModel, Field

from .db import get_connection


class ParsedClaim(BaseModel):
    claim_id: str
    policy_id: str
    customer_id: str
    claim_type: str
    incident_date: str
    claim_date: str
    claim_amount: float
    description: str
    police_report_filed: bool
    witnesses_count: int
    metadata: dict = Field(default_factory=dict)


def parse_claim(claim_id: str) -> dict:
    """Parse a claim from the database into structured data.

    Args:
        claim_id: The claim identifier (e.g. "CLM-0001").

    Returns:
        Dict with structured claim data, or {"error": "..."} if not found.
    """
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM claims WHERE claim_id = ?",
            [claim_id],
        ).fetchone()

        if row is None:
            return {"error": f"Claim {claim_id} not found"}

        (
            cid, pid, cust_id, ctype, inc_date, clm_date,
            amount, desc, police, witnesses, expected, meta_json,
        ) = row

        metadata = json.loads(meta_json) if meta_json else {}

        claim = ParsedClaim(
            claim_id=cid,
            policy_id=pid,
            customer_id=cust_id,
            claim_type=ctype,
            incident_date=inc_date,
            claim_date=clm_date,
            claim_amount=amount,
            description=desc,
            police_report_filed=police,
            witnesses_count=witnesses,
            metadata=metadata,
        )

        return claim.model_dump()
    finally:
        conn.close()
