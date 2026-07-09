# ---------------------------------------------------------------------------
# agents-agentcore — Module for deploying AI agents on Bedrock AgentCore
# ---------------------------------------------------------------------------
# Deploys an AI agent as a containerized runtime on AWS Bedrock AgentCore.
# Unlike agents-sfn (Step Functions + Lambda), this module uses the
# AgentCore control plane to register a container runtime + endpoint.
#
# Resources created:
#   - IAM role for Bedrock AgentCore to assume (with ECR pull permissions)
#   - aws_bedrockagentcore_agent_runtime (the containerized agent)
#   - aws_bedrockagentcore_agent_runtime_endpoint (network endpoint)
#   - (optional) S3 Vectors bucket + index for RAG
#
# Testing with Floci:
#   source /root/projects/floci-test/env.floci
#   terragrunt -chdir=infra/live/010_aws_insurance_agentcore plan
#   terragrunt -chdir=infra/live/010_aws_insurance_agentcore apply
#
# The AWS provider routes to Floci via AWS_ENDPOINT_URL (set in root
# terragrunt.hcl). Floci emulates the AgentCore control plane + data plane.
# ---------------------------------------------------------------------------

# --- IAM role for Bedrock AgentCore ---
# AgentCore assumes this role to pull the container image from ECR and
# access any AWS services the agent needs (S3, Bedrock, etc.)

data "aws_iam_policy_document" "assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["bedrock-agentcore.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "agent_runtime" {
  name               = "${var.name_prefix}-${var.agent_runtime_name}-runtime-role"
  assume_role_policy = data.aws_iam_policy_document.assume_role.json
  tags               = var.tags
}

# ECR pull permissions (container_uri must be in ECR)
data "aws_iam_policy_document" "ecr_permissions" {
  statement {
    actions   = ["ecr:GetAuthorizationToken"]
    effect    = "Allow"
    resources = ["*"]
  }

  statement {
    actions = [
      "ecr:BatchGetImage",
      "ecr:GetDownloadUrlForLayer",
    ]
    effect    = "Allow"
    resources = ["*"] # Floci: no real ECR ARN to scope
  }
}

resource "aws_iam_role_policy" "ecr_pull" {
  name   = "${var.name_prefix}-${var.agent_runtime_name}-ecr-pull"
  role   = aws_iam_role.agent_runtime.id
  policy = data.aws_iam_policy_document.ecr_permissions.json
}

# --- RAG: S3 Vectors (optional) ---
# Same pattern as agents-sfn: vector bucket + index for policy/contract chunks.
# NOTE: The vector bucket name must be globally unique. If it already exists
# (e.g. created by agents-sfn), Terraform will fail with ConflictException.
# In that case, either use a different bucket name or import the existing one.

resource "aws_s3vectors_vector_bucket" "agent_vectors" {
  count              = var.enable_rag ? 1 : 0
  vector_bucket_name = var.rag_vector_bucket_name
}

resource "aws_s3vectors_index" "policy_chunks" {
  count              = var.enable_rag ? 1 : 0
  vector_bucket_name = aws_s3vectors_vector_bucket.agent_vectors[0].vector_bucket_name
  index_name         = var.rag_vector_index_name
  dimension          = var.rag_embedding_dimension
  distance_metric    = "cosine"
  data_type          = "float32"
}

# IAM permissions for the agent runtime to query S3 Vectors
data "aws_iam_policy_document" "s3vectors_query" {
  count = var.enable_rag ? 1 : 0
  statement {
    effect = "Allow"
    actions = [
      "s3vectors:QueryVectors",
      "s3vectors:PutVectors",
      "s3vectors:GetVectors",
      "s3vectors:DeleteVectors",
      "s3vectors:ListVectors",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "s3vectors" {
  count  = var.enable_rag ? 1 : 0
  name   = "${var.name_prefix}-${var.agent_runtime_name}-s3vectors"
  role   = aws_iam_role.agent_runtime.id
  policy = data.aws_iam_policy_document.s3vectors_query[0].json
}

# --- Bedrock AgentCore Agent Runtime ---
# The containerized agent. AgentCore pulls the image from ECR and runs it
# in a managed container environment with automatic scaling.

resource "aws_bedrockagentcore_agent_runtime" "this" {
  agent_runtime_name = var.agent_runtime_name
  description        = var.agent_runtime_description
  role_arn           = aws_iam_role.agent_runtime.arn

  agent_runtime_artifact {
    container_configuration {
      container_uri = var.container_uri
    }
  }

  environment_variables = merge(
    {
      LLM_PROVIDER = "bedrock"
      RAG_PROVIDER = var.enable_rag ? "s3vectors" : "mock"
    },
    var.enable_rag ? {
      RAG_EMBEDDING_PROVIDER = "local"
      VECTOR_BUCKET_NAME     = var.rag_vector_bucket_name
      VECTOR_INDEX_NAME      = var.rag_vector_index_name
    } : {},
    var.environment_variables
  )

  network_configuration {
    network_mode = var.network_mode
  }

  # NOTE: tags omitted — Floci returns ValidationException on ListTagsForResource
  # for AgentCore resources. In real AWS, uncomment: tags = var.tags
}

# --- Bedrock AgentCore Agent Runtime Endpoint ---
# A named endpoint (qualifier) that targets a specific runtime version.
# External systems invoke the agent via this endpoint.

resource "aws_bedrockagentcore_agent_runtime_endpoint" "this" {
  name             = var.endpoint_name
  agent_runtime_id = aws_bedrockagentcore_agent_runtime.this.agent_runtime_id
  description      = "Endpoint for ${var.agent_runtime_name}"
  # NOTE: tags omitted — Floci does not support tagging on AgentCore endpoints.
  # In real AWS, uncomment: tags = var.tags
}
