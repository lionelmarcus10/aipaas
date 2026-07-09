# ---------------------------------------------------------------------------
# agents-sfn variables
# ---------------------------------------------------------------------------

variable "name_prefix" {
  description = "Prefix for all resource names (Lambda functions, state machines, IAM roles)"
  type        = string
  default     = "aipaas"
}

variable "region" {
  description = "AWS region (used for the Step Functions trust policy)"
  type        = string
}

variable "agents" {
  description = <<-EOT
    Map of Step Functions agents to deploy. Each agent has:
      - lambdas: map of { lambda_name => { handler, runtime, memory_size, timeout, ... } }
      - state_machine_definition: ASL JSON template with $$lambda_arns["name"] placeholders

    The state_machine_definition is processed by templatestring() at apply time.
    Use the placeholder syntax $$lambda_arns["lambda_name"] where Lambda ARNs
    should be injected. The module replaces them with actual ARNs.

    Common packaging fields (source_dir, agent_src_dir, cast_dir, requirements_path)
    can be set once in `common_lambda_config` and will be merged into each lambda.
    Per-lambda values override the common ones.

    Example:
      agents = {
        financial-dispute = {
          lambdas = {
            parse_invoice = {
              handler     = "parse_invoice.lambda_handler"
              runtime     = "python3.13"
              memory_size = 256
              timeout     = 30
            }
          }
          state_machine_definition = jsonencode({
            StartAt = "PARSE_INVOICE"
            States = {
              PARSE_INVOICE = {
                Type     = "Task"
                Resource = "$$lambda_arns[\"parse_invoice\"]"
                Next     = "FETCH_CONTRACT"
              }
            }
          })
        }
      }
      common_lambda_config = {
        source_dir        = "agents/financial-dispute-agent/lambda"
        agent_src_dir     = "agents/financial-dispute-agent/src"
        cast_dir          = "libs/custom-aws-strands-toolkit/src"
        requirements_path = "agents/financial-dispute-agent/lambda/requirements.txt"
      }
  EOT
  type = map(object({
    lambdas = map(object({
      handler     = string
      runtime     = string
      memory_size = number
      timeout     = number
      # Packaging — Terraform-native ZIP (no external build script)
      source_dir = optional(string, null)
      # Extra paths needed in the ZIP (copied via commands before zipping)
      agent_src_dir     = optional(string, null)
      cast_dir          = optional(string, null)
      duckdb_path       = optional(string, null)
      requirements_path = optional(string, null)
      env_vars          = optional(map(string), {})
      package_type      = optional(string, "Zip")
      image_uri         = optional(string, null)
    }))
    state_machine_definition = string
  }))
}

variable "common_lambda_config" {
  description = <<-EOT
    Common config merged into every lambda. Per-lambda values override these.
    Set source_dir, agent_src_dir, cast_dir, requirements_path here to avoid
    repeating them in every lambda entry.
  EOT
  type = object({
    source_dir        = optional(string, null)
    agent_src_dir     = optional(string, null)
    cast_dir          = optional(string, null)
    duckdb_path       = optional(string, null)
    requirements_path = optional(string, null)
  })
  default = {
    source_dir        = null
    agent_src_dir     = null
    cast_dir          = null
    duckdb_path       = null
    requirements_path = null
  }
}

variable "log_retention_days" {
  description = "CloudWatch Logs retention in days for Lambda log groups"
  type        = number
  default     = 30
}

variable "sfn_log_level" {
  description = <<-EOT
    Step Functions execution logging level.
      "ALL"            — log every state transition (input + output). Full audit trail.
      "ERROR"          — log only failures.
      "OFF"            — disable logging.
    Defaults to "ALL" for auditability (financial flows require traceability).
  EOT
  type        = string
  default     = "ALL"
  validation {
    condition     = contains(["ALL", "ERROR", "OFF"], var.sfn_log_level)
    error_message = "sfn_log_level must be 'ALL', 'ERROR', or 'OFF'."
  }
}

variable "tags" {
  description = "Additional tags to apply to all resources"
  type        = map(string)
  default     = {}
}

variable "data_bucket_name" {
  description = <<-EOT
    Name of the S3 bucket to store shared data (DuckDB database).
    If set, the module creates the bucket and uploads the DuckDB.
    Each Lambda gets DB_S3_BUCKET + DB_S3_KEY env vars and S3 read permissions.
    Set to null to disable (e.g., for testing without S3).
  EOT
  type        = string
  default     = null
}

variable "duckdb_source_path" {
  description = "Local path to the DuckDB database file to upload to S3."
  type        = string
  default     = null
}

# ---------------------------------------------------------------------------
# RAG / S3 Vectors variables
# ---------------------------------------------------------------------------

variable "enable_rag" {
  description = <<-EOT
    Enable RAG (Retrieval-Augmented Generation) for contract retrieval.
    When true, creates an S3 vector bucket + index for semantic search
    over contract chunks, and grants Lambdas permission to query it.
    Set to false for environments without S3 Vectors (e.g., pure k3d).
  EOT
  type        = bool
  default     = false
}

variable "rag_embedding_provider" {
  description = <<-EOT
    Embedding model provider for RAG:
      "bedrock" — Amazon Titan Text Embeddings V2 (1024 dims, real AWS)
      "local"   — sentence-transformers/all-MiniLM-L6-v2 (384 dims, Floci)
    The S3 vector index dimension must match this provider.
  EOT
  type        = string
  default     = "local"
  validation {
    condition     = contains(["bedrock", "local"], var.rag_embedding_provider)
    error_message = "rag_embedding_provider must be 'bedrock' or 'local'."
  }
}

variable "rag_vector_bucket_name" {
  description = "Name of the S3 vector bucket for RAG. Required if enable_rag=true."
  type        = string
  default     = null
}

variable "rag_vector_index_name" {
  description = "Name of the S3 vector index for contract chunks."
  type        = string
  default     = "contract-chunks"
}
