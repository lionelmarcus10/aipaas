# Lambda handler wrappers for the Financial Dispute Resolution Agent.

Each file in this directory is a thin wrapper that adapts the existing
state handler (signature: `handler(event: dict) -> dict`) to the AWS Lambda
signature (`lambda_handler(event, context) -> dict`).

## Packaging

Lambda ZIPs are built **entirely by Terraform** — no external build script.

The `agents-sfn` module (`infra/module/agents-sfn/`) uses `source_path` with
`commands` to assemble each ZIP at `terragrunt plan/apply` time:

1. Copy the handler wrapper (e.g., `parse_invoice.py`) from this directory
2. Copy the `financial_dispute_agent` package from `src/`
3. Copy the CAST library from `libs/custom-aws-strands-toolkit/src/cast/`
4. Copy the DuckDB database into `data/`
5. `pip install` dependencies from `requirements.txt`
6. Zip the result

Terraform re-zips automatically when content changes (hash-based trigger).

## Files

| File | State | Type |
|------|-------|------|
| `parse_invoice.py` | 1 — PARSE_INVOICE | script |
| `fetch_contract.py` | 2 — FETCH_CONTRACT | script |
| `llm_audit.py` | 3 — LLM_AUDIT | LLM |
| `choice_gate.py` | 4 — CHOICE_GATE | script (routing) |
| `llm_dispute.py` | 5 — LLM_DISPUTE_ANALYSIS | LLM |
| `lookup_orders.py` | 6 — LOOKUP_AFFECTED_ORDERS | script |
| `fraud_check.py` | 7 — FRAUD_CHECK | script |
| `llm_resolution.py` | 8 — LLM_RESOLUTION_PLAN | LLM |
| `final_choice.py` | 9 — FINAL_CHOICE | script |
| `execute_payment.py` | terminal — PAY | action |
| `partial_payment.py` | terminal — PARTIAL_PAY | action |
| `create_ticket.py` | terminal — HUMAN_REVIEW | action |
