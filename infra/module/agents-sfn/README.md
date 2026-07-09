# agents-sfn module

Generic Terraform module for deploying Step Functions agents.

## What it does

Each agent in the `agents` map gets:
- **N Lambda functions** (via `terraform-aws-modules/lambda/aws` v8.8.0)
- **1 IAM role** for Step Functions to invoke those Lambdas (least-privilege)
- **1 `aws_sfn_state_machine`** with the ASL definition (ARNs injected via `templatestring()`)

The module is **agent-agnostic** — it doesn't know about financial disputes,
vulnerability patching, or any specific business logic. It takes a map of agents
and deploys them.

## ASL templating

The ASL definition uses `${lambda_arns["name"]}` placeholders. The module
replaces them with actual Lambda ARNs at apply time via `templatestring()`:

```json
{
  "PARSE_INVOICE": {
    "Type": "Task",
    "Resource": "${lambda_arns["parse_invoice"]}",
    "Next": "FETCH_CONTRACT"
  }
}
```

The ASL is stored in a separate JSON file (read via `file()`) to avoid HCL
interpolation of the `${...}` placeholders.

## Lambda packaging — Terraform-native (no external build script)

The module uses `source_path` with `commands` to build each Lambda ZIP:

1. Copy the handler wrapper from `source_dir`
2. Copy the agent package (`agent_src_dir/financial_dispute_agent`)
3. Copy the CAST library (`cast_dir/cast`)
4. Copy the DuckDB database (`duckdb_path` → `data/`)
5. `pip install` dependencies into the temp dir
6. `:zip` the temp dir

Terraform re-zips automatically when content changes (hash-based trigger).
No need for a separate `build-lambda-packages.sh` script.

## Inputs

| Variable | Type | Description |
|----------|------|-------------|
| `name_prefix` | string | Prefix for all resource names |
| `region` | string | AWS region (for SFN trust policy) |
| `agents` | map(agent) | Map of agents to deploy (see below) |
| `log_retention_days` | number | CloudWatch Logs retention (default: 30) |
| `tags` | map(string) | Additional tags |

### Agent object

| Field | Type | Description |
|-------|------|-------------|
| `lambdas` | map(lambda) | Map of Lambda functions |
| `state_machine_definition` | string | ASL JSON with `${lambda_arns}` placeholders |

### Lambda object

| Field | Type | Description |
|-------|------|-------------|
| `handler` | string | Lambda handler (e.g. `parse_invoice.lambda_handler`) |
| `runtime` | string | Lambda runtime (e.g. `python3.13`) |
| `memory_size` | number | Memory in MB |
| `timeout` | number | Timeout in seconds |
| `source_dir` | string | Directory containing the handler wrapper |
| `agent_src_dir` | string | Directory containing the agent package |
| `cast_dir` | string | Directory containing the CAST library |
| `duckdb_path` | string | Path to the DuckDB database file |
| `requirements_path` | string | Path to requirements.txt |
| `env_vars` | map(string) | Environment variables |
| `package_type` | string | `Zip` (default) or `Image` |
| `image_uri` | string | ECR URI (if `package_type = "Image"`) |

## Outputs

| Output | Description |
|--------|-------------|
| `state_machine_arns` | Map of `{ agent_name => arn }` |
| `state_machine_names` | Map of `{ agent_name => name }` |
| `lambda_arns` | Nested map of `{ agent_name => { lambda_name => arn } }` |
| `lambda_function_names` | Nested map of `{ agent_name => { lambda_name => name } }` |
| `sfn_role_arns` | Map of `{ agent_name => sfn_role_arn }` |
