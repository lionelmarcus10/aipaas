output "cluster_arn" {
  description = "EKS cluster ARN"
  value       = module.eks.cluster_arn
}

output "cluster_ca_certificate" {
  description = "Base64-encoded CA certificate for kubectl"
  value       = module.eks.cluster_certificate_authority_data
  sensitive   = true
}

output "cluster_endpoint" {
  description = "EKS cluster API server endpoint"
  value       = module.eks.cluster_endpoint
  sensitive   = true
}

output "cluster_name" {
  description = "EKS cluster name"
  value       = module.eks.cluster_name
}

output "cluster_oidc_issuer_url" {
  description = "OIDC issuer URL for IRSA (IAM Roles for Service Accounts)"
  value       = module.eks.oidc_provider
}

output "cluster_primary_security_group_id" {
  description = "Security group ID created by EKS for the cluster (control plane)"
  value       = module.eks.cluster_primary_security_group_id
}

output "cluster_security_group_id" {
  description = "Security group ID attached to the cluster control plane"
  value       = module.eks.cluster_security_group_id
}

output "cluster_version" {
  description = "Actual Kubernetes version of the cluster"
  value       = module.eks.cluster_version
}

output "eks_managed_node_groups" {
  description = "Map of EKS managed node groups created"
  value       = module.eks.eks_managed_node_groups
}

output "karpenter_iam_role_arn" {
  description = "IAM role ARN assumed by the Karpenter controller via Pod Identity (null when Karpenter is disabled)"
  value       = var.enable_karpenter ? module.karpenter[0].iam_role_arn : null
}

output "karpenter_instance_profile_name" {
  description = "Instance profile name for Karpenter-provisioned nodes — referenced by the EC2NodeClass (null when Karpenter is disabled)"
  value       = var.enable_karpenter ? module.karpenter[0].instance_profile_name : null
}

output "karpenter_node_iam_role_name" {
  description = "IAM role name attached to Karpenter-provisioned nodes — referenced by the EC2NodeClass (null when Karpenter is disabled)"
  value       = var.enable_karpenter ? module.karpenter[0].node_iam_role_name : null
}

output "karpenter_queue_name" {
  description = "SQS queue name receiving spot interruption and rebalance events for Karpenter (null when Karpenter is disabled)"
  value       = var.enable_karpenter ? module.karpenter[0].queue_name : null
}

output "kms_key_arn" {
  description = "ARN of the KMS key used for secret encryption"
  value       = module.eks.kms_key_arn
}

output "node_security_group_id" {
  description = "Security group ID attached to worker nodes"
  value       = module.eks.node_security_group_id
}
