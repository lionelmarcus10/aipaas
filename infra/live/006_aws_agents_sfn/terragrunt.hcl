include "root" {
  path = find_in_parent_folders("terragrunt.hcl")
}

terraform {
  source = "../../module/agents-sfn"
}

# ---------------------------------------------------------------------------
# Agent B1+B2 — Financial Dispute Resolution
# ---------------------------------------------------------------------------
# 12 Lambda functions (9 states + 3 terminal actions) + 1 Step Functions
# state machine. The ASL definition uses ${lambda_arns["name"]} placeholders
# that the agents-sfn module replaces with actual Lambda ARNs at apply time.
#
# Packaging is handled entirely by Terraform (no external build script):
#   - source_path uses commands to copy handler + agent package + CAST
#   - pip install runs inside the commands (into a temp build dir)
#   - :zip tells the lambda module what to zip
#   - Terraform re-zips automatically when content changes (hash-based)
#
# DuckDB is NOT bundled in the ZIP — it's uploaded to S3 and each Lambda
# downloads it to /tmp at cold start. This keeps the ZIP under 100 MB.
#
# ── LLM Provider switching ─────────────────────────────────────────────────
# Change `llm_provider` below to switch the LLM backend for all Lambdas.
# The selected provider's env vars are injected into every Lambda function.
#
#   llm_provider = "bedrock"     → Amazon Bedrock (Claude Sonnet 4)
#                                    Auth: IAM execution role (no API key)
#                                    Set: AWS_BEDROCK_REGION, BEDROCK_MODEL_ID
#
#   llm_provider = "ollama"      → Ollama Cloud (GLM 5.2 Cloud)
#                                    Auth: OLLAMA_API_KEY (bearer token)
#                                    Set: OLLAMA_API_KEY, OLLAMA_MODEL_ID
#
#   llm_provider = "vllm"        → vLLM (OpenAI-compatible, k3d internal)
#                                    Auth: none (dummy key, internal endpoint)
#                                    Set: VLLM_BASE_URL, VLLM_MODEL_ID
#
#   llm_provider = "openrouter"  → OpenRouter (GLM 5.2, OpenAI-compatible)
#                                    Auth: OPENROUTER_API_KEY
#                                    Set: OPENROUTER_API_KEY, SCENARIO_MODEL_ID
#
#   llm_provider = "openai"      → OpenAI (GPT-4o)
#                                    Auth: OPENAI_API_KEY
#                                    Set: OPENAI_API_KEY, OPENAI_MODEL_ID
#
# Secrets (API keys) should be passed via TF_VAR_ env vars or a secrets
# manager, never committed to the repo.
#
# Testing with floci:
#   source /root/projects/floci-test/env.floci
#   terragrunt plan    # should show 12 Lambdas + 1 SFN + S3 bucket + IAM roles
#   terragrunt apply   # deploy to floci
# ---------------------------------------------------------------------------

locals {
  agent_dir    = "${get_parent_terragrunt_dir()}/../../agents/financial-dispute-agent"
  project_root = "${get_parent_terragrunt_dir()}/../.."
  lambda_dir   = "${local.agent_dir}/lambda"
  src_dir      = "${local.agent_dir}/src"
  cast_dir     = "${get_parent_terragrunt_dir()}/../../libs/custom-aws-strands-toolkit/src"
  duckdb_path  = "${local.agent_dir}/data/financial_dispute.duckdb"
  requirements = "${local.lambda_dir}/requirements.txt"

  # ── LLM Provider selection ──────────────────────────────────────────────
  # Change this one line to switch the LLM backend for all Lambdas.
  # Options: "bedrock" | "ollama" | "vllm" | "openrouter" | "openai"
  # ── Tested & working ──────────────────────────────────────────────────────
  # "bedrock"  → Floci stub (no real LLM, but workflow runs end-to-end)
  # "ollama"   → Ollama Cloud gpt-oss:20b (REAL LLM, requires OLLAMA_API_KEY)
  # "vllm"     → vLLM Qwen2.5-0.5B-Instruct on k3d CPU (REAL local LLM)
  # ── To switch ─────────────────────────────────────────────────────────────
  # 1. Change llm_provider below
  # 2. For "ollama": export OLLAMA_API_KEY="your-key" before terragrunt apply
  # 3. For "vllm": deploy vLLM on k3d + start the socat proxy (if want to use on floci lambda):
  #      kubectl apply -f apps/vllm/deployment.yaml
  #      docker run -d --name vllm-proxy --network floci-test_default \
  #        alpine/socat TCP-LISTEN:8000,fork,reuseaddr TCP:172.18.0.2:30080
  #      docker network connect k3d-aipaas vllm-proxy
  # 4. terragrunt apply (twice if "inconsistent plan" error on first run)
  # ──────────────────────────────────────────────────────────────────────────
  llm_provider = "ollama"

  # Provider-specific env vars — only the selected provider's vars are injected
  llm_env_vars = local.llm_provider == "bedrock" ? {
    LLM_PROVIDER       = "bedrock"
    AWS_BEDROCK_REGION = "eu-west-3"
    BEDROCK_MODEL_ID   = "global.anthropic.claude-sonnet-4-6"
  } : local.llm_provider == "ollama" ? {
    LLM_PROVIDER   = "ollama"
    OLLAMA_API_KEY = get_env("OLLAMA_API_KEY", "")
    OLLAMA_MODEL_ID = "gpt-oss:20b"
  } : local.llm_provider == "vllm" ? {
    LLM_PROVIDER   = "vllm"
    # Floci Lambda containers reach vLLM via a socat proxy container that bridges
    # the floci-test_default and k3d-aipaas Docker networks.
    # The proxy is started with: docker run -d --name vllm-proxy --network floci-test_default
    #   alpine/socat TCP-LISTEN:8000,fork,reuseaddr TCP:172.18.0.2:30080
    # In real k3d/EKS, use the in-cluster Service URL: http://vllm-svc.aipaas.svc.cluster.local:80/v1
    VLLM_BASE_URL  = "http://vllm-proxy:8000/v1"
    VLLM_MODEL_ID  = "Qwen/Qwen2.5-0.5B-Instruct"
    VLLM_API_KEY   = "dummy"
  } : local.llm_provider == "openrouter" ? {
    LLM_PROVIDER      = "openrouter"
    OPENROUTER_API_KEY = get_env("OPENROUTER_API_KEY", "")
    SCENARIO_MODEL_ID  = "z-ai/glm-5.2"
  } : local.llm_provider == "openai" ? {
    LLM_PROVIDER   = "openai"
    OPENAI_API_KEY = get_env("OPENAI_API_KEY", "")
    OPENAI_MODEL_ID = "gpt-4o"
  } : {}
}

inputs = {
  name_prefix = "aipaas"
  region      = "eu-west-3"

  # S3 bucket for the DuckDB (too large for Lambda ZIP)
  data_bucket_name   = "aipaas-agent-data"
  duckdb_source_path = local.duckdb_path

  # Common config merged into every lambda (avoids repetition)
  common_lambda_config = {
    source_dir        = local.lambda_dir
    agent_src_dir     = local.src_dir
    cast_dir          = local.cast_dir
    requirements_path = local.requirements
  }

  agents = {
    financial-dispute = {
      lambdas = {
        # 9 workflow states — 512 MB / 120s pour cold start + S3 download + deps
        # LLM env vars are injected via env_vars (see local.llm_env_vars above)
        parse_invoice    = { handler = "parse_invoice.lambda_handler",   runtime = "python3.13", memory_size = 512, timeout = 120, env_vars = local.llm_env_vars }
        fetch_contract   = { handler = "fetch_contract.lambda_handler",  runtime = "python3.13", memory_size = 512, timeout = 120, env_vars = local.llm_env_vars }
        llm_audit        = { handler = "llm_audit.lambda_handler",       runtime = "python3.13", memory_size = 512, timeout = 120, env_vars = local.llm_env_vars }
        choice_gate      = { handler = "choice_gate.lambda_handler",     runtime = "python3.13", memory_size = 512, timeout = 120, env_vars = local.llm_env_vars }
        llm_dispute      = { handler = "llm_dispute.lambda_handler",     runtime = "python3.13", memory_size = 512, timeout = 120, env_vars = local.llm_env_vars }
        lookup_orders    = { handler = "lookup_orders.lambda_handler",   runtime = "python3.13", memory_size = 512, timeout = 120, env_vars = local.llm_env_vars }
        fraud_check      = { handler = "fraud_check.lambda_handler",     runtime = "python3.13", memory_size = 512, timeout = 120, env_vars = local.llm_env_vars }
        llm_resolution   = { handler = "llm_resolution.lambda_handler",  runtime = "python3.13", memory_size = 512, timeout = 120, env_vars = local.llm_env_vars }
        final_choice     = { handler = "final_choice.lambda_handler",    runtime = "python3.13", memory_size = 512, timeout = 120, env_vars = local.llm_env_vars }
        # 3 terminal actions
        execute_payment  = { handler = "execute_payment.lambda_handler", runtime = "python3.13", memory_size = 512, timeout = 120, env_vars = local.llm_env_vars }
        partial_payment  = { handler = "partial_payment.lambda_handler", runtime = "python3.13", memory_size = 512, timeout = 120, env_vars = local.llm_env_vars }
        create_ticket    = { handler = "create_ticket.lambda_handler",   runtime = "python3.13", memory_size = 512, timeout = 120, env_vars = local.llm_env_vars }
      }

      state_machine_definition = file("${get_parent_terragrunt_dir()}/006_aws_agents_sfn/financial-dispute-asl.json")
    }
  }

  # ── RAG / S3 Vectors ──────────────────────────────────────────────────────
  # Enable RAG for contract retrieval via S3 Vectors.
  # Floci supports S3 Vectors (PutVectors, QueryVectors, metadata filters).
  # Use "local" embeddings (384 dims) for Floci, "bedrock" (1024 dims) for real AWS.
  enable_rag              = true
  rag_embedding_provider  = "local"
  rag_vector_bucket_name  = "aipaas-rag-vectors"
  rag_vector_index_name   = "contract-chunks"

  log_retention_days = 30

  tags = {
    Agent = "financial-dispute"
  }
}
