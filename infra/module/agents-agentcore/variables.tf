/**
 * variables.tf — agents-agentcore module
 * Variables for deploying an AI agent as a Bedrock AgentCore runtime.
 */

variable "name_prefix" {
  description = "Prefix for resource names (e.g. aipaas)"
  type        = string
}

variable "region" {
  description = "AWS region"
  type        = string
  default     = "eu-west-3"
}

variable "agent_runtime_name" {
  description = "Name of the AgentCore runtime (must match [a-zA-Z][a-zA-Z0-9_]{0,47}, no hyphens)"
  type        = string
  validation {
    condition     = can(regex("^[a-zA-Z][a-zA-Z0-9_]{0,47}$", var.agent_runtime_name))
    error_message = "agent_runtime_name must match [a-zA-Z][a-zA-Z0-9_]{0,47} (no hyphens)."
  }
}

variable "agent_runtime_description" {
  description = "Description of the agent runtime"
  type        = string
  default     = "AI agent deployed via Bedrock AgentCore"
}

variable "container_uri" {
  description = "ECR URI of the container image (e.g. 123456789012.dkr.ecr.eu-west-3.amazonaws.com/agent:latest)"
  type        = string
}

variable "network_mode" {
  description = "Network mode for the runtime: PUBLIC or PRIVATE"
  type        = string
  default     = "PUBLIC"
  validation {
    condition     = contains(["PUBLIC", "PRIVATE"], var.network_mode)
    error_message = "network_mode must be PUBLIC or PRIVATE."
  }
}

variable "environment_variables" {
  description = "Map of environment variables passed to the container"
  type        = map(string)
  default     = {}
}

variable "endpoint_name" {
  description = "Name of the agent runtime endpoint (qualifier)"
  type        = string
  default     = "prod"
}

variable "enable_rag" {
  description = "Enable S3 Vectors RAG (vector bucket + index)"
  type        = bool
  default     = false
}

variable "rag_vector_bucket_name" {
  description = "S3 Vectors bucket name for RAG"
  type        = string
  default     = "aipaas-rag-vectors"
}

variable "rag_vector_index_name" {
  description = "S3 Vectors index name for RAG"
  type        = string
  default     = "policy-chunks"
}

variable "rag_embedding_dimension" {
  description = "Embedding dimension (384 for local MiniLM, 1024 for Bedrock Titan V2)"
  type        = number
  default     = 384
}

variable "tags" {
  description = "Tags applied to all resources"
  type        = map(string)
  default     = {}
}
