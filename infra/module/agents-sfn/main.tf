# ---------------------------------------------------------------------------
# agents-sfn — Generic module for deploying Step Functions agents
# ---------------------------------------------------------------------------
# Deploys any agent that follows the "Lambda handlers + Step Functions state
# machine" pattern. Each agent in the `agents` map gets:
#   - N Lambda functions (via terraform-aws-modules/lambda/aws)
#   - 1 IAM role for Step Functions to invoke those Lambdas
#   - 1 aws_sfn_state_machine with the ASL definition (ARNs injected via templatestring)
#
# The module is agent-agnostic: it doesn't know about financial disputes,
# vulnerability patching, or any specific business logic. It just takes a map
# of agents, each with their lambdas and ASL definition, and deploys them.
#
# ASL templating:
#   The state_machine_definition field is a Terraform template string. Use
#   ${lambda_arns["<lambda_name>"]} placeholders where Lambda ARNs should be
#   injected. The module replaces them with the actual ARNs at plan time.
#
# Packaging:
#   - ZIP (default): set source_dir + agent_src_dir + cast_dir + duckdb_path +
#     requirements_path. The module copies everything into a temp dir, runs
#     pip install, and zips it — all via Terraform (no external build script).
#   - Container image: set package_type = "Image" and image_uri to an ECR URI.
#
# Testing with floci:
#   source /root/projects/floci-test/env.floci
#   terragrunt -chdir=infra/live/006_aws_agents_sfn plan
#   terragrunt -chdir=infra/live/006_aws_agents_sfn apply
# ---------------------------------------------------------------------------

locals {
  # Flatten the agents map into a list of {agent_name, lambda_name, config} tuples
  # for the for_each over the lambda module.
  # Common config is merged into each lambda — per-lambda values override.
  lambda_entries = flatten([
    for agent_name, agent in var.agents : [
      for lambda_name, lambda_cfg in agent.lambdas : {
        agent_name  = agent_name
        lambda_name = lambda_name
        config = {
          handler           = lambda_cfg.handler
          runtime           = lambda_cfg.runtime
          memory_size       = lambda_cfg.memory_size
          timeout           = lambda_cfg.timeout
          source_dir        = coalesce(lambda_cfg.source_dir, var.common_lambda_config.source_dir)
          agent_src_dir     = coalesce(lambda_cfg.agent_src_dir, var.common_lambda_config.agent_src_dir)
          cast_dir          = coalesce(lambda_cfg.cast_dir, var.common_lambda_config.cast_dir)
          duckdb_path       = coalesce(lambda_cfg.duckdb_path, var.common_lambda_config.duckdb_path, "unused")
          requirements_path = coalesce(lambda_cfg.requirements_path, var.common_lambda_config.requirements_path)
          env_vars          = lambda_cfg.env_vars
          package_type      = lambda_cfg.package_type
          image_uri         = lambda_cfg.image_uri
        }
      }
    ]
  ])

  # Map keyed by "agent_name/lambda_name" for the for_each
  lambda_map = {
    for entry in local.lambda_entries :
    "${entry.agent_name}/${entry.lambda_name}" => entry
  }

  # Build nested maps: { agent_name => { lambda_name => arn } }
  # These are used for ASL templating and IAM policy scoping.
  lambda_arns_nested = {
    for agent_name in keys(var.agents) :
    agent_name => {
      for key, entry in local.lambda_map :
      entry.lambda_name => module.lambda_functions["${entry.agent_name}/${entry.lambda_name}"].lambda_function_arn
      if entry.agent_name == agent_name
    }
  }

  lambda_names_nested = {
    for agent_name in keys(var.agents) :
    agent_name => {
      for key, entry in local.lambda_map :
      entry.lambda_name => module.lambda_functions["${entry.agent_name}/${entry.lambda_name}"].lambda_function_name
      if entry.agent_name == agent_name
    }
  }

  common_tags = merge(var.tags, {
    Module    = "agents-sfn"
    ManagedBy = "terragrunt"
  })
}

# ---------------------------------------------------------------------------
# S3 bucket for shared data (DuckDB database)
# ---------------------------------------------------------------------------
# The DuckDB is too large to bundle in each Lambda ZIP (>100 MB with deps).
# Instead, we upload it to S3 and each Lambda downloads it to /tmp at cold start.
# This is the AWS-recommended pattern for large read-only data in Lambda.
# ---------------------------------------------------------------------------
resource "aws_s3_bucket" "agent_data" {
  count  = var.data_bucket_name != null ? 1 : 0
  bucket = var.data_bucket_name
  tags   = local.common_tags
}

resource "aws_s3_object" "duckdb" {
  count  = var.duckdb_source_path != null ? 1 : 0
  bucket = aws_s3_bucket.agent_data[0].id
  key    = "financial_dispute.duckdb"
  source = var.duckdb_source_path
  etag   = filemd5(var.duckdb_source_path)
  tags   = local.common_tags
}

# ---------------------------------------------------------------------------
# S3 Vectors — vector bucket + index for RAG
# ---------------------------------------------------------------------------
# When enable_rag=true, we create an S3 vector bucket and index to store
# contract chunk embeddings. The Lambdas use this for semantic retrieval
# instead of passing the full contract text to the LLM.
#
# The index dimension depends on the embedding provider:
#   - "bedrock" → 1024 (Amazon Titan Text Embeddings V2)
#   - "local"   → 384  (sentence-transformers/all-MiniLM-L6-v2, for Floci)
#
# Floci supports S3 Vectors (PutVectors, QueryVectors, metadata filters).
# Floci's Bedrock InvokeModel returns stub responses, so use "local" for
# Floci testing and "bedrock" for real AWS.
# ---------------------------------------------------------------------------
locals {
  rag_embedding_dim = var.rag_embedding_provider == "bedrock" ? 1024 : 384
}

resource "aws_s3vectors_vector_bucket" "agent_vectors" {
  count              = var.enable_rag ? 1 : 0
  vector_bucket_name = var.rag_vector_bucket_name
  tags               = local.common_tags
}

resource "aws_s3vectors_index" "contracts" {
  count              = var.enable_rag ? 1 : 0
  vector_bucket_name = aws_s3vectors_vector_bucket.agent_vectors[0].vector_bucket_name
  index_name         = var.rag_vector_index_name
  dimension          = local.rag_embedding_dim
  distance_metric    = "cosine"
  data_type          = "float32"
  tags               = local.common_tags
}

# ---------------------------------------------------------------------------
# Lambda functions — one module instance per (agent, lambda) pair
# ---------------------------------------------------------------------------
# terraform-aws-modules/lambda/aws creates a single Lambda function per module
# call. We use for_each over the flattened lambda_map to create one instance
# per (agent_name, lambda_name) pair.
#
# The module handles:
#   - ZIP packaging (create_package = true, source_path = source_dir)
#   - IAM role creation (create_role = true)
#   - CloudWatch Logs log group
#   - Environment variables
#   - Container image packaging (package_type = "Image", image_uri)
# ---------------------------------------------------------------------------
module "lambda_functions" {
  source  = "terraform-aws-modules/lambda/aws"
  version = "8.8.0"

  for_each = local.lambda_map

  function_name = "${var.name_prefix}-${each.value.agent_name}-${each.value.lambda_name}"
  description   = "Lambda for agent ${each.value.agent_name} — state ${each.value.lambda_name}"
  handler       = each.value.config.handler
  runtime       = each.value.config.runtime
  memory_size   = each.value.config.memory_size
  timeout       = each.value.config.timeout

  # Packaging — Terraform-native ZIP creation (no external build script)
  #
  # The DuckDB is NOT bundled in the ZIP — it's uploaded to S3 and downloaded
  # at cold start (see aws_s3_bucket + aws_s3_object above). This keeps the ZIP
  # under the 100 MB limit and is the AWS-recommended pattern for large data.
  #
  # We build in a temp dir to avoid polluting the source directory:
  #   1. Copy the handler wrapper from the lambda dir
  #   2. Copy the agent package (financial_dispute_agent)
  #   3. Copy the CAST library
  #   4. pip install dependencies into the temp dir
  #   5. :zip the temp dir
  #
  # Terraform re-zips automatically when content changes (hash-based trigger).
  create_package = each.value.config.package_type == "Zip"
  source_path = each.value.config.package_type == "Zip" ? [{
    path = each.value.config.source_dir
    commands = [
      "rm -rf /tmp/lambda_build_${each.value.lambda_name} && mkdir -p /tmp/lambda_build_${each.value.lambda_name}",
      "cp ${each.value.config.source_dir}/${each.value.lambda_name}.py /tmp/lambda_build_${each.value.lambda_name}/",
      "cp -r ${each.value.config.agent_src_dir}/financial_dispute_agent /tmp/lambda_build_${each.value.lambda_name}/",
      "cp -r ${each.value.config.cast_dir}/cast /tmp/lambda_build_${each.value.lambda_name}/",
      "/usr/bin/python3 -m pip install --target /tmp/lambda_build_${each.value.lambda_name} --no-compile -r ${each.value.config.requirements_path} 2>&1 | tail -1",
      "find /tmp/lambda_build_${each.value.lambda_name} -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true",
      ":zip /tmp/lambda_build_${each.value.lambda_name}",
    ]
  }] : null
  package_type = each.value.config.package_type
  image_uri    = each.value.config.image_uri

  # Environment variables — add DB_S3_BUCKET so the Lambda can download the DB
  # Also add RAG env vars when enable_rag=true
  environment_variables = merge(
    each.value.config.env_vars,
    var.data_bucket_name != null ? {
      DB_S3_BUCKET = var.data_bucket_name
      DB_S3_KEY    = "financial_dispute.duckdb"
    } : {},
    var.enable_rag ? {
      RAG_PROVIDER           = "s3vectors"
      RAG_EMBEDDING_PROVIDER = var.rag_embedding_provider
      VECTOR_BUCKET_NAME     = var.rag_vector_bucket_name
      VECTOR_INDEX_NAME      = var.rag_vector_index_name
    } : {}
  )

  # IAM — add S3 read permissions for the DuckDB
  # Also add S3 Vectors permissions for RAG when enable_rag=true
  create_role = true
  role_tags   = local.common_tags

  # Attach a policy to read the DuckDB from S3 + query S3 Vectors
  attach_policy_statements = var.data_bucket_name != null || var.enable_rag
  policy_statements = merge(
    var.data_bucket_name != null ? {
      s3_read_duckdb = {
        effect    = "Allow"
        actions   = ["s3:GetObject"]
        resources = ["${aws_s3_bucket.agent_data[0].arn}/financial_dispute.duckdb"]
      }
    } : {},
    var.enable_rag ? {
      s3vectors_query = {
        effect = "Allow"
        actions = [
          "s3vectors:QueryVectors",
          "s3vectors:GetVectors",
          "s3vectors:PutVectors",
        ]
        resources = [aws_s3vectors_index.contracts[0].index_arn]
      }
    } : {}
  )

  # CloudWatch Logs
  cloudwatch_logs_retention_in_days = var.log_retention_days

  tags = merge(local.common_tags, {
    Agent = each.value.agent_name
    State = each.value.lambda_name
  })
}

# ---------------------------------------------------------------------------
# IAM role for Step Functions — one per agent
# ---------------------------------------------------------------------------
# Step Functions needs permission to invoke all the Lambda functions of an agent.
# We create one role per agent with a policy scoped to that agent's Lambda ARNs.
# ---------------------------------------------------------------------------
data "aws_iam_policy_document" "sfn_assume_role" {
  for_each = var.agents

  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["states.${var.region}.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "sfn_execution" {
  for_each = var.agents

  name               = "${var.name_prefix}-${each.key}-sfn-role"
  assume_role_policy = data.aws_iam_policy_document.sfn_assume_role[each.key].json
  tags               = merge(local.common_tags, { Agent = each.key })
}

data "aws_iam_policy_document" "sfn_invoke_lambdas" {
  for_each = var.agents

  statement {
    effect    = "Allow"
    actions   = ["lambda:InvokeFunction"]
    resources = values(local.lambda_arns_nested[each.key])
  }

  # CloudWatch Logs — Step Functions needs permission to write execution logs
  # when logging_configuration is enabled (level != OFF).
  statement {
    effect = "Allow"
    actions = [
      "logs:CreateLogDelivery",
      "logs:GetLogDelivery",
      "logs:UpdateLogDelivery",
      "logs:DeleteLogDelivery",
      "logs:ListLogDeliveries",
      "logs:PutLogEvents",
      "logs:PutResourcePolicy",
      "logs:DescribeResourcePolicies",
      "logs:DescribeLogGroups",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "sfn_invoke_lambdas" {
  for_each = var.agents

  name   = "invoke-agent-lambdas"
  role   = aws_iam_role.sfn_execution[each.key].id
  policy = data.aws_iam_policy_document.sfn_invoke_lambdas[each.key].json
}

# ---------------------------------------------------------------------------
# CloudWatch Logs — one log group per agent for Step Functions execution logs
# ---------------------------------------------------------------------------
# Step Functions can log every state transition (input/output) to CloudWatch.
# This is critical for auditability: financial flows require a traceable record
# of each state's input, output, and timestamp.
#
# Level "ALL" logs every transition. Level "ERROR" logs only failures.
# The log group name follows the AWS convention: /aws/vendedlogs/states/<name>
# ---------------------------------------------------------------------------
resource "aws_cloudwatch_log_group" "sfn_execution" {
  for_each = var.agents

  name              = "/aws/vendedlogs/states/${var.name_prefix}-${each.key}"
  retention_in_days = var.log_retention_days
  tags              = merge(local.common_tags, { Agent = each.key })
}

# ---------------------------------------------------------------------------
# Step Functions state machines — one per agent
# ---------------------------------------------------------------------------
# The ASL definition is a template string. The module injects Lambda ARNs
# via templatestring(), replacing ${lambda_arns["name"]} with actual ARNs.
#
# This is the key abstraction: the agent author writes ASL with placeholders,
# and the module handles the ARN wiring. No hardcoded ARNs in the ASL.
# ---------------------------------------------------------------------------
resource "aws_sfn_state_machine" "this" {
  for_each = var.agents

  name     = "${var.name_prefix}-${each.key}"
  role_arn = aws_iam_role.sfn_execution[each.key].arn

  # Inject Lambda ARNs into the ASL template
  definition = templatestring(each.value.state_machine_definition, {
    lambda_arns = local.lambda_arns_nested[each.key]
  })

  type = "STANDARD"

  # Execution logging — every state transition (input/output) is written to
  # CloudWatch Logs. This provides an auditable trail for financial flows.
  # Level "ALL" captures every transition; "ERROR" only failures.
  dynamic "logging_configuration" {
    for_each = var.sfn_log_level != "OFF" ? [1] : []
    content {
      log_destination        = aws_cloudwatch_log_group.sfn_execution[each.key].arn
      include_execution_data = true
      level                  = var.sfn_log_level
    }
  }

  tags = merge(local.common_tags, { Agent = each.key })
}
