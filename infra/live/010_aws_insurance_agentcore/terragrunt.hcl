include "root" {
  path = find_in_parent_folders("terragrunt.hcl")
}

terraform {
  source = "../../module/agents-agentcore"
}

# ---------------------------------------------------------------------------
# Agent A2 — Insurance Claims Triage (Bedrock AgentCore)
# ---------------------------------------------------------------------------
# Deploys A2 as a containerized runtime on Bedrock AgentCore.
# Unlike B1+B2 (financial-dispute) which uses Step Functions + Lambda,
# A2 uses AgentCore's managed container runtime for autonomous ReAct loops.
#
# Architecture:
#   - aws_bedrockagentcore_agent_runtime: registers the A2 container
#   - aws_bedrockagentcore_agent_runtime_endpoint: named endpoint for invocation
#   - IAM role: AgentCore assumes this to pull ECR + query S3 Vectors
#   - S3 Vectors: vector bucket + index for policy document RAG
#
# Testing with Floci:
#   source /root/projects/floci-test/env.floci
#   terragrunt -chdir=infra/live/010_aws_insurance_agentcore plan
#   terragrunt -chdir=infra/live/010_aws_insurance_agentcore apply
#
# Floci emulates:
#   - AgentCore control plane (CreateAgentRuntime, CreateEndpoint, etc.)
#   - AgentCore data plane (InvokeAgentRuntime → canned {"output":"yes"})
#   - S3 Vectors (PutVectors, QueryVectors, metadata filters)
#   - IAM (roles, policies)
#
# In production (real AWS):
#   - AgentCore pulls the container from ECR and runs it in a managed env
#   - The endpoint is a real HTTPS URL invocable via the SDK
#   - S3 Vectors stores real embeddings
# ---------------------------------------------------------------------------

inputs = {
  name_prefix = "aipaas"
  region      = "eu-west-3"

  # Agent runtime — name must match [a-zA-Z][a-zA-Z0-9_]{0,47} (no hyphens)
  agent_runtime_name        = "insuranceClaimsAgent"
  agent_runtime_description = "A2 — Insurance Claims Triage Agent (autonomous ReAct loop via Strands)"

  # Container image (ECR in production, dummy URI for Floci)
  container_uri = "123456789012.dkr.ecr.eu-west-3.amazonaws.com/insurance-claims-agent:latest"

  # Network mode: PUBLIC (internet-accessible endpoint)
  network_mode = "PUBLIC"

  # Environment variables injected into the container
  environment_variables = {
    DB_S3_BUCKET     = "aipaas-agent-data"
    DB_S3_KEY        = "insurance_claims.duckdb"
    BEDROCK_MODEL_ID = "global.anthropic.claude-sonnet-4-6"
    AWS_BEDROCK_REGION = "eu-west-3"
  }

  # Endpoint (qualifier) for invoking the agent
  endpoint_name = "prod"

  # RAG: S3 Vectors for policy document retrieval
  enable_rag              = true
  rag_vector_bucket_name  = "aipaas-rag-vectors"
  rag_vector_index_name   = "policy-chunks"
  rag_embedding_dimension = 384 # local MiniLM (384d); use 1024 for Bedrock Titan V2

  tags = {
    Agent    = "insurance-claims"
    Module   = "agents-agentcore"
    Project  = "aipaas"
  }
}
