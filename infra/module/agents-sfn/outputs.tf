output "state_machine_arns" {
  description = "Map of { agent_name => state_machine_arn }"
  value       = { for k, v in aws_sfn_state_machine.this : k => v.arn }
}

output "state_machine_names" {
  description = "Map of { agent_name => state_machine_name }"
  value       = { for k, v in aws_sfn_state_machine.this : k => v.name }
}

output "lambda_arns" {
  description = "Nested map of { agent_name => { lambda_name => arn } }"
  value       = local.lambda_arns_nested
}

output "lambda_function_names" {
  description = "Nested map of { agent_name => { lambda_name => function_name } }"
  value       = local.lambda_names_nested
}

output "sfn_role_arns" {
  description = "Map of { agent_name => step_functions_execution_role_arn }"
  value       = { for k, v in aws_iam_role.sfn_execution : k => v.arn }
}

output "sfn_log_group_arns" {
  description = "Map of { agent_name => CloudWatch log group ARN for Step Functions execution logs }"
  value       = { for k, v in aws_cloudwatch_log_group.sfn_execution : k => v.arn }
}

output "sfn_log_group_names" {
  description = "Map of { agent_name => CloudWatch log group name for Step Functions execution logs }"
  value       = { for k, v in aws_cloudwatch_log_group.sfn_execution : k => v.name }
}
