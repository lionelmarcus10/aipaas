output "agent_runtime_id" {
  description = "ID of the Bedrock AgentCore runtime"
  value       = aws_bedrockagentcore_agent_runtime.this.agent_runtime_id
}

output "agent_runtime_arn" {
  description = "ARN of the Bedrock AgentCore runtime"
  value       = aws_bedrockagentcore_agent_runtime.this.agent_runtime_arn
}

output "agent_runtime_endpoint_arn" {
  description = "ARN of the Bedrock AgentCore runtime endpoint"
  value       = aws_bedrockagentcore_agent_runtime_endpoint.this.agent_runtime_endpoint_arn
}

output "agent_runtime_endpoint_name" {
  description = "Name of the Bedrock AgentCore runtime endpoint"
  value       = aws_bedrockagentcore_agent_runtime_endpoint.this.name
}

output "iam_role_arn" {
  description = "ARN of the IAM role assumed by AgentCore"
  value       = aws_iam_role.agent_runtime.arn
}

output "rag_vector_bucket_name" {
  description = "Name of the S3 Vectors bucket (if RAG enabled)"
  value       = var.enable_rag ? aws_s3vectors_vector_bucket.agent_vectors[0].vector_bucket_name : null
}

output "rag_vector_index_name" {
  description = "Name of the S3 Vectors index (if RAG enabled)"
  value       = var.enable_rag ? aws_s3vectors_index.policy_chunks[0].index_name : null
}
