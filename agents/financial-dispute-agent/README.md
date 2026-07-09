# Financial Dispute Resolution Agent

> B1+B2 fusion — Step Functions agent for invoice audit + dispute resolution.

## Overview

This agent processes supplier invoices and resolves disputes by combining:
- **3 LLM calls** (semantic audit, dispute categorization, resolution plan)
- **6 deterministic tools** (parsing, calculation, routing, payment mock)
- **9 Step Functions states** with Choice gates for auditable routing

The pattern is **"Cerveau LLM + Bras Déterministe"**: the LLM handles
semantic understanding and reasoning, the scripts handle exact calculations
and routing. Neither could do the job alone.

## Architecture

```
[Invoice received]
       │
  ┌────▼──────┐
  │ State 1   │  PARSE_INVOICE      (script — Pydantic)
  │ State 2   │  FETCH_CONTRACT     (script — DuckDB/CUAD)
  │ State 3   │  LLM_AUDIT          (LLM — semantic clause comparison)
  │ State 4   │  CHOICE_GATE        (script — deterministic routing)
  └────┬──────┘
       │
       ├── PAY → execute_payment
       ├── PARTIAL_PAY → partial_payment
       ├── HUMAN_REVIEW → create_ticket
       │
       └── DISPUTE →
            │ State 5   │  LLM_DISPUTE_ANALYSIS  (LLM — categorize dispute)
            │ State 6   │  LOOKUP_AFFECTED_ORDERS (script — DuckDB/MessyOps)
            │ State 7   │  FRAUD_CHECK           (script — trust scoring)
            │ State 8   │  LLM_RESOLUTION_PLAN   (LLM — propose plan)
            │ State 9   │  FINAL_CHOICE          (script — execute plan)
            └── PAY_AND_REFUND | PARTIAL_PAY_AND_NOTIFY | FREEZE_AND_ESCALATE | HUMAN_REVIEW
```

## Quick Start

### Prerequisites

- Python 3.10+
- [UV](https://docs.astral.sh/uv/) package manager
- Optional: `OLLAMA_API_KEY` for real LLM calls (without it, tests use mocks)

### Setup

```bash
cd agents/financial-dispute-agent

# Install dependencies
uv sync

# Build the database (downloads CUAD + MessyOps, generates invoices)
uv run python data/setup_db.py

# Run tests
uv run python -m pytest tests/ -v
```

### Run the workflow

```python
from financial_dispute_agent.orchestrator import run_workflow

# Process an invoice
result = run_workflow("INV-6188", verbose=True)

print(result["final_decision"])    # PAY, DISPUTE, FREEZE_AND_ESCALATE, etc.
print(result["actions_executed"])  # list of payment/refund/freeze actions
print(result["trace"])             # state transition trace
```

### Run with real LLM (Ollama Cloud)

```bash
export OLLAMA_API_KEY="your-key"
export OLLAMA_MODEL_ID="gpt-oss:120b"

uv run python -m pytest tests/test_e2e_workflow.py -v -m integration
```

## Project Structure

```
agents/financial-dispute-agent/
├── pyproject.toml              # UV config (CAST, Strands, Faker, DuckDB)
├── Dockerfile                  # Container image for k3d deployment (non-root, gVisor)
├── data/
│   ├── setup_db.py             # One-shot: download + build DuckDB
│   ├── financial_dispute.duckdb# Generated DB (not in git)
│   └── raw/                    # Downloaded datasets (not in git)
│       ├── CUAD_v1/            # 510 contracts (Zenodo, 106 MB)
│       └── messyops/           # 17 B2B tables, 650k rows (Kaggle, 50 MB)
├── lambda/                     # AWS Lambda wrappers (thin adapters for Step Functions)
│   ├── requirements.txt        # Lambda pip dependencies
│   ├── parse_invoice.py        # Wraps state_1_parse_invoice.handler
│   ├── fetch_contract.py       # Wraps state_2_fetch_contract.handler
│   ├── llm_audit.py            # Wraps state_3_llm_audit.handler
│   ├── choice_gate.py          # Wraps state_4_choice_gate.handler
│   ├── llm_dispute.py          # Wraps state_5_llm_dispute.handler
│   ├── lookup_orders.py        # Wraps state_6_lookup_orders.handler
│   ├── fraud_check.py          # Wraps state_7_fraud_check.handler
│   ├── llm_resolution.py       # Wraps state_8_llm_resolution.handler
│   ├── final_choice.py         # Wraps state_9_final_choice.handler
│   ├── execute_payment.py      # Terminal action: PAY
│   ├── partial_payment.py      # Terminal action: PARTIAL_PAY
│   └── create_ticket.py        # Terminal action: HUMAN_REVIEW
├── src/financial_dispute_agent/
│   ├── orchestrator.py         # Local Step Functions simulator + ASL
│   ├── api.py                  # FastAPI HTTP wrapper (for k3d deployment)
│   ├── invoice_generator.py    # Faker + Pydantic invoice generator
│   ├── tools/                  # 6 deterministic tools
│   │   ├── parse_invoice.py    # State 1
│   │   ├── fetch_contract.py   # State 2
│   │   ├── compute_variance.py # State 4 (routing logic)
│   │   ├── lookup_affected_orders.py  # State 6
│   │   ├── compute_trust_score.py     # State 7
│   │   └── payment_mock.py     # States 4a/4b/9 (API mock)
│   ├── lambdas/                # 9 state handlers (1 per Step Functions state)
│   │   ├── llm_helper.py       # Shared CAST agent factory
│   │   ├── state_1_parse_invoice.py
│   │   ├── state_2_fetch_contract.py
│   │   ├── state_3_llm_audit.py        # LLM
│   │   ├── state_4_choice_gate.py
│   │   ├── state_5_llm_dispute.py      # LLM
│   │   ├── state_6_lookup_orders.py
│   │   ├── state_7_fraud_check.py
│   │   ├── state_8_llm_resolution.py   # LLM
│   │   └── state_9_final_choice.py
│   └── prompts/                # 3 LLM prompt templates
│       ├── audit.md
│       ├── dispute.md
│       └── resolution.md
└── tests/
    ├── test_database.py        # 12 tests — DB integrity
    ├── test_tools.py           # 25 tests — each tool
    └── test_e2e_workflow.py    # 15 tests — full workflow + ASL
```

## The 3 LLM States

### State 3: LLM_AUDIT

Compares invoice line items against contract clauses semantically.
Detects anomalies that scripts can't:

```
Contract: "Pénalité de retard applicable après 30 jours"
Invoice:  "Frais de retard: 45€ (retard 22 jours)"
→ LLM: "22 days < 30 days = fee UNJUSTIFIED"
```

Output: `{variance_pct, suspected_clauses, risk_level, confidence}`

### State 5: LLM_DISPUTE_ANALYSIS

Categorizes the dispute type and assesses customer impact.

Output: `{dispute_type, customer_impact, severity, immediate_action}`

### State 8: LLM_RESOLUTION_PLAN

Proposes a coherent multi-actor resolution plan (supplier + customers + finance).

Output: `{actions: [...], rationale, requires_human_review}`

## The 6 Deterministic Tools

| Tool | State | What it does |
|------|-------|-------------|
| `parse_invoice` | 1 | Extract invoice from DB via Pydantic |
| `fetch_contract` | 2 | Query supplier contract from CUAD (DuckDB) |
| `compute_variance` | 4 | Calculate variance + route (PAY/PARTIAL/DISPUTE/HUMAN) |
| `lookup_affected_orders` | 6 | Find customer orders linked to supplier (DuckDB) |
| `compute_trust_score` | 7 | Score supplier trust → risk level (LOW/MEDIUM/HIGH) |
| `payment_mock` | 9 | Mock API: pay, partial pay, refund, freeze, escalate |

## Routing Logic (deterministic)

### State 4: Choice Gate

| Condition | Decision |
|-----------|----------|
| confidence < 80% | HUMAN_REVIEW |
| variance == 0% | PAY |
| 0% < variance ≤ 5% | PARTIAL_PAY |
| variance > 5% | DISPUTE |

### State 9: Final Choice

| Condition | Decision |
|-----------|----------|
| severity == high or human review requested | HUMAN_REVIEW |
| trust < 50 (HIGH risk) | FREEZE_AND_ESCALATE |
| 50 ≤ trust < 80 (MEDIUM risk) | PARTIAL_PAY_AND_NOTIFY |
| trust ≥ 80 (LOW risk) | PAY_AND_REFUND |

## Datasets

| Dataset | Source | Size | Usage |
|---------|--------|------|-------|
| CUAD v1 | [Zenodo](https://zenodo.org/records/4595826) | 106 MB | 510 commercial contracts (contract text for RAG audit) |
| MessyOps | [Kaggle](https://www.kaggle.com/datasets/fares279/messyops) | 50 MB | 17 B2B tables, 650k rows (procure-to-pay + order-to-cash) |
| Faker | Generated locally | — | 57 synthetic invoices (7 test + 50 random, controlled variance) |

All linked by `supplier_id` in a single DuckDB database.
CUAD contract[i] → MessyOps supplier[i] (1:1 mapping, natural B2B alignment).

## Database Schema

```
suppliers (N rows — CUAD + MessyOps merged 1:1)
  supplier_id | supplier_name | contract_text | trust_score | reliability_tier | country

purchase_orders (MessyOps — real B2B POs)
  purchase_order_id | supplier_id | order_date | total_amount | po_status

supplier_invoices (MessyOps — real supplier invoices)
  supplier_invoice_id | purchase_order_id | supplier_id | invoice_amount | invoice_status

products (MessyOps — products with primary_supplier_id)
  product_id | product_name | category | primary_supplier_id | unit_cost | list_price

sales_orders (MessyOps — real customer orders)
  sales_order_id | customer_id | order_date | order_status | total_amount

sales_order_lines (MessyOps — order line items)
  sales_order_line_id | sales_order_id | product_id | quantity | unit_price | line_total

customers (MessyOps — B2B customers)
  customer_id | company_name | customer_segment | country | credit_limit

orders (backward compat — simplified sales_orders for existing tools)
  order_id | supplier_id | customer | amount | status | date

invoices (Faker — controlled test cases)
  invoice_id | supplier_id | total_amount | expected_amount | variance_pct | lines_json
```

The procurement chain: supplier → products → sales_order_lines → sales_orders → customers.
The audit chain: invoice (Faker) → contract (CUAD) → purchase_orders (MessyOps) → variance.

## Deployment

The agent has **two deployment targets** that share the same 9 state handlers:

### 1. AWS — Step Functions + Lambda (production / floci testing)

- **Module**: `infra/module/agents-sfn/` (generic, agent-agnostic)
- **Live config**: `infra/live/006_aws_agents_sfn/`
- **ASL definition**: `infra/live/006_aws_agents_sfn/financial-dispute-asl.json`
- **Lambda wrappers**: `lambda/` (12 thin wrappers adapting handlers to AWS signature)
- **Packaging**: Terraform-native (no external build script). The `agents-sfn` module
  uses `source_path` with `commands` to copy the handler + agent package + CAST + DuckDB
  into a temp dir, runs `pip install`, and zips it. Re-zips automatically on content change.

```bash
# Deploy to floci (local AWS emulator)
source /root/projects/floci-test/env.floci
cd infra/live/006_aws_agents_sfn
terragrunt plan    # 87 resources: 12 Lambdas + 1 SFN + IAM roles
terragrunt apply

# Start an execution
aws stepfunctions start-execution \
  --state-machine-arn $(terragrunt output -raw state_machine_arns | jq -r '."financial-dispute"') \
  --input '{"invoice_id":"INV-6188"}' \
  --endpoint-url $AWS_ENDPOINT_URL
```

### 2. k3d — FastAPI pod with gVisor isolation (local dev / demo)

- **API**: `src/financial_dispute_agent/api.py` (FastAPI wrapper around `orchestrator.py`)
- **Dockerfile**: `Dockerfile` (non-root, python:3.13-slim)
- **K8s manifests**: `apps/financial-dispute-agent/` (Deployment + Service + NetworkPolicy)
- **Isolation**: `runtimeClassName: gvisor` (syscall isolation via runsc)
- **Security**: Pod Security Standard `restricted` (non-root, read-only rootfs, no capabilities)

```bash
# Build and push to k3d local registry
docker build -t localhost:5001/financial-dispute-agent:latest .
docker push localhost:5001/financial-dispute-agent:latest

# Deploy via ArgoCD (or kubectl apply)
kubectl apply -f apps/financial-dispute-agent/

# Test the API
kubectl port-forward -n financial-dispute-agent svc/financial-dispute-agent 8080:80
curl http://localhost:8080/health
curl -X POST http://localhost:8080/workflow -H "Content-Type: application/json" -d '{"invoice_id":"INV-6188"}'
```

### Key difference

| | AWS (Step Functions) | k3d (FastAPI pod) |
|---|---|---|
| **Orchestration** | AWS Step Functions (declarative ASL) | `orchestrator.py` (Python) |
| **Execution** | 12 Lambda functions (serverless) | 1 pod (long-running) |
| **State transitions** | Managed by AWS (auditable) | Managed by Python code |
| **Isolation** | Lambda microVMs (Firecracker) | gVisor (runsc) |
| **Trigger** | `aws stepfunctions start-execution` | `POST /workflow` (HTTP) |

Both use the **same 9 state handlers** (`lambdas/state_*.py`). The logic is identical;
only the orchestration layer differs.

## RAG (Retrieval-Augmented Generation)

CUAD contracts are ~54k characters, but the local Qwen 0.5B model has a ~4096 token context
window. Truncating to 8000 chars loses relevant clauses. RAG retrieves only the semantically
relevant chunks instead.

### Architecture

```
fetch_contract(supplier_id, invoice)
  │
  ├─ build_query_from_invoice → "payment terms late penalty fee..."
  │
  ├─ RAG_PROVIDER=faiss (k3d)
  │   ├─ FAISS index on PVC (33635 chunks, 510 suppliers, dim=384)
  │   ├─ sentence-transformers/all-MiniLM-L6-v2 embeddings
  │   └─ search ALL vectors → filter by supplier_id → top_k=5
  │
  ├─ RAG_PROVIDER=s3vectors (AWS/Floci)
  │   ├─ S3 Vectors bucket + index (serverless)
  │   ├─ Embeddings: local (384d) or Amazon Titan V2 (1024d)
  │   └─ query_vectors(filter={supplier_id: {$eq: "SUP-001"}})
  │
  └─ Fallback (no RAG) → truncate to 8000 chars
```

### Chunking

- Chunk size: 1000 characters
- Overlap: 200 characters (avoids cutting clauses mid-sentence)

### Configuration

| Env var | Values | Description |
|---------|--------|-------------|
| `RAG_PROVIDER` | `faiss` \| `s3vectors` \| `mock` | Provider selection (default: `faiss`) |
| `RAG_INDEX_PATH` | path | FAISS index base path (faiss only) |
| `VECTOR_BUCKET_NAME` | string | S3 vector bucket name (s3vectors only) |
| `VECTOR_INDEX_NAME` | string | S3 vector index name (s3vectors only) |
| `RAG_EMBEDDING_PROVIDER` | `local` \| `bedrock` | Embedding model (s3vectors only) |
| `HF_HOME` | path | HuggingFace cache (writable, non-root) |

### Terraform (AWS/Floci)

Set `enable_rag = true` in `terragrunt.hcl` to create:
- `aws_s3vectors_vector_bucket` + `aws_s3vectors_index`
- IAM permissions `s3vectors:QueryVectors/PutVectors/GetVectors` on Lambdas
- Env vars `RAG_PROVIDER=s3vectors` injected into all 12 Lambdas

Set `enable_rag = false` to disable RAG — `fetch_contract` falls back to truncation.

### Validated

- **k3d (FAISS)**: workflow end-to-end, `rag_used=True`, `PAY_AND_REFUND`, 4 actions
- **Floci (S3 Vectors)**: Terraform apply (103 resources), 33635 chunks indexed, multi-supplier retrieval
- **Fallback**: `enable_rag=false` or missing index → truncation (backward compatible)

## Testing

```bash
# All tests (50 pass, 2 skip without LLM)
uv run python -m pytest tests/ -v

# Only database tests
uv run python -m pytest tests/test_database.py -v

# Only tool tests
uv run python -m pytest tests/test_tools.py -v

# E2E workflow tests
uv run python -m pytest tests/test_e2e_workflow.py -v

# Integration tests (requires OLLAMA_API_KEY)
OLLAMA_API_KEY=xxx uv run python -m pytest tests/test_e2e_workflow.py -v -m integration
```

## Dependencies

- `strands-agents[ollama,openai]` — AWS Strands agent SDK
- `cast` — Custom AWS Strands Toolkit (local library)
- `faker` — Synthetic invoice generation
- `pydantic` — Structured data validation
- `duckdb` — Embedded analytical database
- `datasets` — HuggingFace dataset loader (for CUAD)
- `pandas` — CSV processing (MessyOps)
