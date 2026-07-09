# ---------------------------------------------------------------------------
# EKS Cluster — using terraform-aws-modules/eks/aws v21.25.0
# ---------------------------------------------------------------------------
# Production-oriented EKS cluster with:
#   - Managed node groups (Graviton ARM64 by default, cost-optimized)
#   - IRSA (IAM Roles for Service Accounts) via OIDC provider
#   - EKS Pod Identity for addon IAM (EBS CSI) — successor to IRSA, no OIDC
#     trust policy per role
#   - Managed addons patched by AWS: vpc-cni, coredns, kube-proxy,
#     eks-pod-identity-agent, aws-ebs-csi-driver, metrics-server
#   - VPC CNI NetworkPolicy enforcement (pod-level firewalling)
#   - Control plane logging to CloudWatch with explicit retention
#   - Kubernetes Secrets envelope encryption via KMS (rotation enabled)
#   - Cluster creator granted admin permissions via EKS access entries
#   - Private API endpoint by default; public access is opt-in and CIDR-scoped
#   - Deletion protection enabled by default
#   - Optional Karpenter infrastructure (IAM, SQS interruption queue,
#     access entry) — the controller itself is deployed via GitOps
#
# Consumes VPC outputs (vpc_id, subnet_ids) from the upstream VPC module.
# Pass them via Terragrunt dependency or inputs.
# ---------------------------------------------------------------------------

locals {
  cluster_tags = merge(var.tags, {
    Module = "eks"
  })

  # The module creates and manages its own KMS key unless the caller supplies one.
  create_kms_key = var.kms_key_arn == null

  # `provider_key_arn` is optional upstream and is ignored entirely when
  # create_kms_key = true (see eks/main.tf: key_arn = var.create_kms_key ?
  # module.kms.key_arn : encryption_config.value.provider_key_arn).
  # Passing var.kms_key_arn unconditionally is therefore both type-safe and
  # correct in both branches. Never pass encryption_config = null: upstream
  # treats null as "disable Secrets encryption entirely".
  encryption_config = {
    provider_key_arn = var.kms_key_arn
    resources        = ["secrets"]
  }

  ebs_csi_enabled = contains(keys(var.addons), "aws-ebs-csi-driver")

  # Rewrites two addons before handing them to the upstream module:
  #   vpc-cni           -> inject enableNetworkPolicy=true unless the caller
  #                        supplied their own configuration_values
  #   aws-ebs-csi-driver -> inject a Pod Identity association backed by the
  #                        least-privilege role created below, unless the
  #                        caller wired their own
  addons = {
    for name, cfg in var.addons : name => {
      addon_version  = cfg.addon_version
      before_compute = cfg.before_compute
      most_recent    = cfg.most_recent
      configuration_values = name == "vpc-cni" && cfg.configuration_values == null && var.enable_vpc_cni_network_policy ? jsonencode({
        enableNetworkPolicy = "true"
      }) : cfg.configuration_values
      pod_identity_association = name == "aws-ebs-csi-driver" && cfg.pod_identity_association == null ? [{
        role_arn        = module.ebs_csi_pod_identity[0].iam_role_arn
        service_account = "ebs-csi-controller-sa"
      }] : cfg.pod_identity_association
    }
  }

  # Karpenter discovers the subnets/security groups it may use through this tag
  karpenter_discovery_tags = var.enable_karpenter ? {
    "karpenter.sh/discovery" = var.cluster_name
  } : {}
}

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "21.25.0"

  name               = var.cluster_name
  kubernetes_version = var.kubernetes_version

  # --- Networking ---
  vpc_id                   = var.vpc_id
  subnet_ids               = var.subnet_ids
  control_plane_subnet_ids = var.subnet_ids

  # --- Endpoint access ---
  # Private-only by default. Public access requires an explicit opt-in plus a
  # non-empty CIDR allow-list (enforced by variable validation).
  endpoint_private_access      = var.endpoint_private_access
  endpoint_public_access       = var.endpoint_public_access
  endpoint_public_access_cidrs = var.allowed_public_access_cidrs

  # --- Managed addons (AWS patches them; NetworkPolicy + Pod Identity wired) ---
  addons = local.addons

  # --- Logging (control plane logs → CloudWatch) ---
  enabled_log_types                      = var.cluster_log_types
  cloudwatch_log_group_retention_in_days = var.cluster_log_retention_days

  # --- Kubernetes Secrets envelope encryption ---
  create_kms_key                  = local.create_kms_key
  enable_kms_key_rotation         = local.create_kms_key
  kms_key_deletion_window_in_days = var.kms_key_deletion_window_in_days
  encryption_config               = local.encryption_config

  # --- Prod safety: prevent accidental cluster deletion ---
  deletion_protection = var.deletion_protection

  # --- IAM: IRSA (IAM Roles for Service Accounts) ---
  # Kept alongside Pod Identity: IRSA remains the portable OIDC-based option
  # for workloads that need cross-account or non-EKS-compatible identity.
  enable_irsa = true

  # --- Access: grant cluster creator admin permissions ---
  enable_cluster_creator_admin_permissions = true

  # --- Managed node groups (inline in v21.x) ---
  eks_managed_node_groups = var.node_groups

  # --- Karpenter discovery tags on the shared node security group ---
  node_security_group_tags = local.karpenter_discovery_tags

  # --- Tags ---
  cluster_tags = local.cluster_tags
  tags         = local.cluster_tags
}

# ---------------------------------------------------------------------------
# IAM role for the EBS CSI controller (EKS Pod Identity)
# ---------------------------------------------------------------------------
# The EBS CSI driver provisions/attaches/resizes EBS volumes and therefore
# needs EC2 permissions. The association itself is created by the eks module's
# addon block (local.addons above); this module only creates the role + policy.
# ---------------------------------------------------------------------------
module "ebs_csi_pod_identity" {
  source  = "terraform-aws-modules/eks-pod-identity/aws"
  version = "~> 2.8"

  count = local.ebs_csi_enabled ? 1 : 0

  name = "${var.cluster_name}-ebs-csi"

  attach_aws_ebs_csi_policy = true
  aws_ebs_csi_kms_arns      = var.ebs_csi_kms_key_arns

  tags = local.cluster_tags
}

# ---------------------------------------------------------------------------
# Karpenter infrastructure (optional)
# ---------------------------------------------------------------------------
# Creates everything Karpenter needs EXCEPT the controller: IAM role (Pod
# Identity), SQS queue + EventBridge rules for spot interruption handling,
# node IAM role, instance profile, and the access entry that lets
# Karpenter-provisioned nodes join the cluster.
#
# The controller Helm chart and the NodePool/EC2NodeClass manifests are
# deployed via GitOps (ArgoCD), not here: they are Kubernetes resources, and
# mixing them into the Terraform layer would recreate the provider
# chicken-and-egg problem (provider needs the cluster to exist).
# ---------------------------------------------------------------------------
module "karpenter" {
  source  = "terraform-aws-modules/eks/aws//modules/karpenter"
  version = "21.25.0"

  count = var.enable_karpenter ? 1 : 0

  cluster_name = module.eks.cluster_name
  namespace    = var.karpenter_namespace

  create_pod_identity_association = true

  tags = local.cluster_tags
}
