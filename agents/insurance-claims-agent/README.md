# A2 — Insurance Claims Triage Agent

Autonomous ReAct agent for P&C (Property & Casualty) insurance claims triage.
Built with **AWS Strands SDK** + **cast** (Custom AWS Strands Toolkit).

## Overview

The Insurance Claims Triage Agent receives a **First Notification of Loss (FNOL)**
and autonomously investigates the claim to produce a structured triage decision:

```
FNOL JSON
  → Strands autonomous agent (ReAct loop)
  → parse_claim → check_policy → check_coverage
  → [conditionally] check_claim_history → check_fraud_indicators
  → [conditionally] assess_damage → calculate_payout
  → generate_triage_report
  → structured routing decision
```

### Routing outcomes

| Decision | Description |
|----------|-------------|
| `FAST_TRACK_APPROVE` | Simple claim, coverage confirmed, low fraud risk |
| `ADJUSTER_REVIEW` | Moderate complexity, needs human adjuster |
| `SIU_REFERRAL` | High fraud risk, refer to Special Investigations Unit |
| `DENY_COVERAGE` | Claim not covered by policy (exclusion or wrong type) |
| `REQUEST_INFORMATION` | Missing critical information |

### Autonomous behavior

Unlike B1+B2 (Financial Dispute Agent) which follows a fixed Step Functions workflow,
A2 is **genuinely autonomous** — the Strands agent decides which tools to call based
on what it finds at each step:

- **Simple claim** → 2-3 tool calls → `FAST_TRACK_APPROVE`
- **Complex claim** → 5-7 tool calls → `ADJUSTER_REVIEW`
- **Suspicious claim** → 6-8 tool calls → `SIU_REFERRAL`

## Architecture

```
                    ┌─────────────────────────────────────┐
                    │     Strands Agent (ReAct loop)      │
                    │  System prompt + 8 @tool functions  │
                    └──────────────┬──────────────────────┘
                                   │
                    ┌──────────────▼──────────────────────┐
                    │         cast.from_env()             │
                    │  (auto-detects LLM provider)        │
                    └──────────────┬──────────────────────┘
                                   │
          ┌────────────┬───────────┼───────────┬────────────┐
          ▼            ▼           ▼           ▼            ▼
     Ollama Cloud    vLLM      Bedrock    OpenRouter    Mock
     (gpt-oss)    (k3d/EKS)  (Lambda)   (GLM-5.2)   (no LLM)
```

## Project structure

```
agents/insurance-claims-agent/
├── pyproject.toml
├── data/
│   ├── setup_db.py                    # Build DuckDB from Faker data
│   ├── insurance_claims.duckdb        # Generated DB (not in git)
│   └── raw/                           # External datasets (optional)
├── src/insurance_claims_agent/
│   ├── __init__.py
│   ├── agent.py                       # Strands agent + ReAct loop
│   ├── claim_generator.py             # Faker + Pydantic FNOL generator
│   ├── llm_helper.py                  # cast AgentFactory wrapper
│   ├── prompts/
│   │   ├── assess_damage.md           # LLM prompt for damage assessment
│   │   └── triage_report.md           # LLM prompt for final triage
│   └── tools/
│       ├── db.py                      # DuckDB connection helper
│       ├── parse_claim.py             # Tool 1: Extract claim data
│       ├── check_policy.py            # Tool 2: Retrieve policy details
│       ├── check_claim_history.py     # Tool 3: Get customer claim history
│       ├── check_fraud_indicators.py  # Tool 4: Check fraud red flags
│       ├── check_coverage.py          # Tool 5: Verify coverage + exclusions
│       ├── calculate_payout.py        # Tool 6: Calculate payout amount
│       └── generate_triage_report.py  # Tool 7: Generate final triage
└── tests/
    ├── test_database.py               # DB integrity + referential joins
    ├── test_tools.py                  # Unit tests for all 7 tools
    └── test_e2e_triage.py             # End-to-end triage pipeline
```

## Quick start

### 1. Install dependencies

```bash
cd agents/insurance-claims-agent
uv sync
uv pip install -e ../../libs/custom-aws-strands-toolkit  # cast library
```

### 2. Build the database

```bash
uv run python data/setup_db.py
```

This generates:
- 20 policies (with coverage, deductibles, exclusions)
- 50 claims (5 controlled test cases + 45 random)
- 12 claim history entries (including fraud patterns for CUS-0003)
- 5 fraud rules (metadata table)

### 3. Run tests

```bash
# Deterministic tests (no LLM needed)
uv run pytest tests/ -v -k "not integration"

# Integration tests (requires OLLAMA_API_KEY)
OLLAMA_API_KEY=xxx uv run pytest tests/ -v -m integration
```

### 4. Run the agent

```bash
# With Ollama Cloud
export OLLAMA_API_KEY="your-key"
export OLLAMA_MODEL_ID="gpt-oss:120b-cloud"
export LLM_PROVIDER="ollama"
uv run python -c "
from insurance_claims_agent.agent import run_triage
result = run_triage('CLM-0001', verbose=True)
print(result['triage_decision'])
"

# Deterministic mode (no LLM, for testing)
uv run python -c "
from insurance_claims_agent.agent import run_triage_deterministic
result = run_triage_deterministic('CLM-0001', verbose=True)
print(result['triage_decision'])
"
```

## LLM providers

The agent uses `cast.from_env()` for provider auto-detection. Set environment
variables to choose a provider:

### Ollama Cloud (default for dev)

```bash
export OLLAMA_API_KEY="your-ollama-cloud-key"
export OLLAMA_MODEL_ID="gpt-oss:120b-cloud"  # free tier
# or: glm-4.7:cloud, gemma3:27b-cloud, gpt-oss:20b-cloud
export LLM_PROVIDER="ollama"
```

**Free tier models** (verified working):
- `gpt-oss:120b-cloud` — 120B params, supports tools
- `gpt-oss:20b-cloud` — 20B params, supports tools
- `gemma3:27b-cloud` — 27B params
- `glm-4.7:cloud` — GLM 4.7, supports tools

**Paid models** (require subscription):
- `glm-5.2:cloud` — GLM 5.2 (requires upgrade)
- `glm-5.3-flash:cloud` — GLM 5.3 Flash

### vLLM (k3d / EKS)

```bash
export VLLM_BASE_URL="http://vllm-svc.aipaas.svc.cluster.local:80/v1"
export VLLM_MODEL_ID="Qwen/Qwen2.5-1.5B-Instruct"
export LLM_PROVIDER="vllm"
```

### AWS Bedrock (Lambda / EKS)

```bash
export AWS_BEDROCK_REGION="us-west-2"
export BEDROCK_MODEL_ID="global.anthropic.claude-sonnet-4-6"
export LLM_PROVIDER="bedrock"
# IAM role provides auth — no API key needed
```

### Mock mode (no LLM)

If no provider is configured, the agent falls back to deterministic mode:
all tools run, but `assess_damage` and `generate_triage_report` use heuristic
fallbacks instead of LLM reasoning.

## Data sources

### Primary: Faker + Pydantic (synthetic)

The main data source is synthetic generation with Faker, providing full control
over test scenarios:

- 5 controlled test claims with known expected outcomes
- 45 random claims for bulk testing
- Claim history with fraud patterns (CUS-0003 has repeat claims + fraud flag)
- Policies with realistic coverage, deductibles, and exclusions

### Reference datasets (optional)

The following datasets were considered as reference for data distributions:

1. **Vehicle Insurance Fraud Detection** (Kaggle)
   - ~15,000 vehicle claims with fraud labels
   - URL: `https://www.kaggle.com/datasets/shivamb/vehicle-claim-fraud-detection`

2. **Synthetic Insurance Suite** (GitHub)
   - Policies, members, providers, coverages
   - URL: `https://github.com/Xaleed/synthetic_insurance_suite`

These are not currently downloaded — the Faker-generated data is sufficient
for the A2 use case and provides explicit ground truth for testing.

## DuckDB schema

```sql
-- policies
CREATE TABLE policies (
    policy_id VARCHAR PRIMARY KEY,
    customer_id VARCHAR,
    policy_type VARCHAR,        -- auto, home, health
    coverage_type VARCHAR,      -- collision, comprehensive, liability
    coverage_limit FLOAT,
    deductible FLOAT,
    premium_annual FLOAT,
    start_date VARCHAR,
    end_date VARCHAR,
    exclusions JSON,            -- list of exclusion strings
    status VARCHAR              -- active, expired, cancelled
);

-- claims (FNOL)
CREATE TABLE claims (
    claim_id VARCHAR PRIMARY KEY,
    policy_id VARCHAR,
    customer_id VARCHAR,
    claim_type VARCHAR,         -- auto_collision, home_fire, theft, water_damage
    incident_date VARCHAR,
    claim_date VARCHAR,
    claim_amount FLOAT,
    description TEXT,
    police_report_filed BOOLEAN,
    witnesses_count INTEGER,
    expected_triage VARCHAR,    -- ground truth for tests
    metadata_json JSON
);

-- claim_history (previous claims by customer)
CREATE TABLE claim_history (
    customer_id VARCHAR,
    claim_id VARCHAR,
    claim_date VARCHAR,
    claim_type VARCHAR,
    claim_amount FLOAT,
    fraud_found BOOLEAN
);

-- fraud_rules (metadata, not queried by tools)
CREATE TABLE fraud_rules (
    rule_id VARCHAR,
    description TEXT,
    severity VARCHAR
);
```

## Fraud detection rules

5 deterministic fraud rules:

| Rule | Severity | Description |
|------|----------|-------------|
| `claim_within_30_days` | high | Claim filed <30 days after policy start |
| `amount_3x_average` | high | Claim amount >3x average for this claim type |
| `repeat_claims_6_months` | medium | ≥2 similar claims in 6 months |
| `no_police_report_high_amount` | medium | No police report for claim >€10k |
| `narrative_inconsistency` | high | Description inconsistent with claim type |

Fraud score: `high_count * 30 + medium_count * 15` (capped at 100).

## Test scenarios

5 controlled claims with known expected outcomes:

| Claim | Scenario | Expected | Description |
|-------|----------|----------|-------------|
| CLM-0001 | Simple | `FAST_TRACK_APPROVE` | Minor damage, clear policy |
| CLM-0002 | Complex | `ADJUSTER_REVIEW` | Moderate damage, needs assessment |
| CLM-0003 | Fraud | `SIU_REFERRAL` | Recent policy, repeat claims, high amount |
| CLM-0004 | Exclusion | `DENY_COVERAGE` | Natural disaster excluded by policy |
| CLM-0005 | Missing info | `REQUEST_INFORMATION` | Incomplete claim data |

## SRE / Failure handling

- **Circuit breaker** (`CircuitBreakerHook`): After 3 consecutive tool failures,
  the tool is short-circuited for 60 seconds (Panne #3).
- **Sliding window** (`sliding_window`): Keeps last 20 messages in context,
  drops older ones to prevent context overflow (Panne #6).
- **Mock fallback**: If no LLM provider is configured, all tools still run
  with deterministic fallbacks for LLM-backed tools.

## Comparison with B1+B2 (Financial Dispute Agent)

| Aspect | B1+B2 Financial | A2 Insurance |
|--------|-----------------|--------------|
| Orchestration | Step Functions (fixed) | Strands ReAct (autonomous) |
| Tools | 9 deterministic states | 7 tools + LLM reasoning |
| LLM states | 3 (audit, dispute, resolution) | 2 (assess_damage, triage_report) |
| Data | MessyOps (real) + Faker | Faker (synthetic) |
| Provider | cast.from_env() | cast.from_env() (same) |
| Routing | Fixed workflow | Dynamic (agent decides) |

## Deployment (AgentCore — future)

Future deployment via AWS AgentCore:

```bash
# Package
agentcore package --entry-point src/insurance_claims_agent/agent.py

# Deploy
agentcore deploy --name insurance-triage-agent
```

The agent is designed to be deployment-agnostic — the same code runs locally
with Ollama Cloud, on k3d with vLLM, and on AWS Lambda/EKS with Bedrock.
