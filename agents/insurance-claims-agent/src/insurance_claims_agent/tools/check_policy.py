"""Tool 2 : check_policy

Récupère la police d'assurance + garanties + plafonds + franchise + exclusions.

Input:  {"policy_id": "POL-0042"}
Output: {"policy_id", "customer_id", "policy_type", "coverage_type",
         "coverage_limit", "deductible", "premium_annual", "start_date",
         "end_date", "exclusions", "status", "is_active", "days_since_start"}

Pas de LLM : requête DuckDB pure.
"""

import json
from datetime import datetime

from .db import get_connection


def check_policy(policy_id: str) -> dict:
    """Retrieve policy details from the database.

    Args:
        policy_id: The policy identifier (e.g. "POL-0042").

    Returns:
        Dict with policy details, or {"error": "..."} if not found.
    """
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM policies WHERE policy_id = ?",
            [policy_id],
        ).fetchone()

        if row is None:
            return {"error": f"Policy {policy_id} not found"}

        (
            pid, cust_id, ptype, ctype, limit, deductible,
            premium, start, end, exclusions_json, status,
        ) = row

        exclusions = json.loads(exclusions_json) if exclusions_json else []

        # Calculate days since policy start
        try:
            start_date = datetime.strptime(start, "%Y-%m-%d")
            days_since_start = (datetime.now() - start_date).days
        except (ValueError, TypeError):
            days_since_start = 0

        is_active = status == "active"

        return {
            "policy_id": pid,
            "customer_id": cust_id,
            "policy_type": ptype,
            "coverage_type": ctype,
            "coverage_limit": limit,
            "deductible": deductible,
            "premium_annual": premium,
            "start_date": start,
            "end_date": end,
            "exclusions": exclusions,
            "status": status,
            "is_active": is_active,
            "days_since_start": days_since_start,
        }
    finally:
        conn.close()
