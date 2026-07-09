# ---------------------------------------------------------------------------
# Variables — alphabetical order, Type → Description → Default → Validation
# ---------------------------------------------------------------------------

variable "addons" {
  type = map(object({
    addon_version        = optional(string)
    before_compute       = optional(bool, false)
    configuration_values = optional(string)
    most_recent          = optional(bool, true)
    pod_identity_association = optional(list(object({
      role_arn        = string
      service_account = string
    })))
  }))
  description = <<-EOT
    Map of EKS managed addons to install. Managed addons are patched by AWS;
    without this, EKS installs vpc-cni/CoreDNS/kube-proxy as self-managed
    (you would have to upgrade them yourself).

    The wrapper injects two pieces of wiring automatically:
      - vpc-cni           : enableNetworkPolicy=true when
                            enable_vpc_cni_network_policy = true (unless you
                            supply your own configuration_values)
      - aws-ebs-csi-driver: a Pod Identity association with a least-privilege
                            IAM role created by the wrapper

    Default installs: coredns, kube-proxy, vpc-cni, eks-pod-identity-agent,
    aws-ebs-csi-driver, metrics-server.
    EOT
  default = {
    coredns                = {}
    kube-proxy             = {}
    vpc-cni                = {}
    eks-pod-identity-agent = {}
    aws-ebs-csi-driver     = {}
    metrics-server         = {}
  }
}

variable "allowed_public_access_cidrs" {
  type        = list(string)
  description = <<-EOT
    CIDR blocks allowed to reach the public API endpoint. Only used when
    `endpoint_public_access = true`.

    Secure by default: empty list. Set your office/VPN CIDR, e.g.
    ["203.0.113.10/32"]. Using 0.0.0.0/0 is rejected unless
    `allow_public_access_from_anywhere = true` is also set explicitly.
    EOT
  default     = []

  # Cross-variable validation (Terraform >= 1.9): refuse 0.0.0.0/0 unless the
  # operator opted in explicitly. Enforces AWS FSBP
  # `eks-cluster-endpoints-restrict-public-access`.
  validation {
    condition = !contains(var.allowed_public_access_cidrs, "0.0.0.0/0") || var.allow_public_access_from_anywhere
    error_message = join(" ", [
      "0.0.0.0/0 exposes the Kubernetes API server to the entire Internet.",
      "Restrict to your office/VPN CIDR, or set",
      "allow_public_access_from_anywhere = true to acknowledge the risk.",
    ])
  }

  validation {
    condition = alltrue([
      for c in var.allowed_public_access_cidrs : can(cidrhost(c, 0))
    ])
    error_message = "Each entry must be a valid CIDR block, e.g. 203.0.113.10/32."
  }
}

variable "allow_public_access_from_anywhere" {
  type        = bool
  description = <<-EOT
    Escape hatch to permit 0.0.0.0/0 in `allowed_public_access_cidrs`.
    Exposes the Kubernetes API server to the entire Internet and violates the
    AWS FSBP control `eks-cluster-endpoints-restrict-public-access`.
    Acceptable for throwaway dev clusters only — never for production.
    EOT
  default     = false
}

variable "cluster_log_retention_days" {
  type        = number
  description = "Number of days to retain EKS control plane logs in CloudWatch"
  default     = 90

  validation {
    condition     = var.cluster_log_retention_days >= 1
    error_message = "Log retention must be at least 1 day."
  }
}

variable "cluster_log_types" {
  type        = list(string)
  description = "CloudWatch log types to enable for the EKS control plane"
  default     = ["api", "audit", "authenticator", "controllerManager", "scheduler"]

  validation {
    condition = alltrue([
      for t in var.cluster_log_types :
      contains(["api", "audit", "authenticator", "controllerManager", "scheduler"], t)
    ])
    error_message = "Valid log types are: api, audit, authenticator, controllerManager, scheduler."
  }
}

variable "cluster_name" {
  type        = string
  description = "Name of the EKS cluster"
}

variable "deletion_protection" {
  type        = bool
  description = "Enable deletion protection on the EKS cluster. When enabled, the cluster cannot be deleted unless this is first set to false."
  default     = true
}

variable "ebs_csi_kms_key_arns" {
  type        = list(string)
  description = "KMS key ARNs the EBS CSI driver may use for encrypted volumes. Empty = only the AWS-managed aws/ebs key, which needs no explicit grant."
  default     = []
}

variable "enable_karpenter" {
  type        = bool
  description = <<-EOT
    Create the Karpenter infrastructure: controller IAM role (Pod Identity),
    SQS spot-interruption queue, EventBridge rules, node IAM role, instance
    profile and cluster access entry. The Karpenter controller itself (Helm
    chart) and its NodePool/EC2NodeClass manifests are deployed separately via
    GitOps.
    EOT
  default     = false
}

variable "enable_vpc_cni_network_policy" {
  type        = bool
  description = <<-EOT
    Enable Kubernetes NetworkPolicy enforcement in the VPC CNI addon
    (ENABLE_NETWORK_POLICY=true). Without this, every pod can talk to every
    pod in the cluster. Ignored if you pass your own configuration_values
    for the vpc-cni addon.
    EOT
  default     = true
}

variable "endpoint_private_access" {
  type        = bool
  description = "Enable private access to the cluster API server (from within the VPC)"
  default     = true
}

variable "endpoint_public_access" {
  type        = bool
  description = "Enable public access to the cluster API server. Secure by default (false) — private access via VPN/bastion/VPC is preferred."
  default     = false
}

variable "kms_key_arn" {
  type        = string
  description = "ARN of an existing KMS key for Kubernetes Secrets envelope encryption. If null, the module creates and manages its own key."
  nullable    = true
  default     = null
}

variable "kms_key_deletion_window_in_days" {
  type        = number
  description = "Waiting period before AWS deletes the KMS key created by this module. Ignored when `kms_key_arn` is set."
  default     = 30

  validation {
    condition     = var.kms_key_deletion_window_in_days >= 7 && var.kms_key_deletion_window_in_days <= 30
    error_message = "KMS deletion window must be between 7 and 30 days."
  }
}

variable "kubernetes_version" {
  type        = string
  description = "Kubernetes version for the EKS cluster (e.g. 1.31, 1.32). Check AWS docs for supported versions."
  default     = "1.31"
}

variable "karpenter_namespace" {
  type        = string
  description = "Namespace where the Karpenter controller will run (Pod Identity association target). Only used when enable_karpenter = true."
  default     = "kube-system"
}

variable "node_groups" {
  type = map(object({
    ami_type       = optional(string)
    capacity_type  = optional(string, "ON_DEMAND")
    desired_size   = optional(number, 1)
    disk_size      = optional(number, 20)
    instance_types = optional(list(string), ["t4g.medium"])
    labels         = optional(map(string), {})
    max_size       = optional(number, 3)
    min_size       = optional(number, 1)
    taints = optional(map(object({
      key    = string
      value  = optional(string)
      effect = string
    })), {})
  }))
  description = <<-EOT
    Map of managed node group definitions. Each key is the group name.
    All attributes are optional and fall back to the defaults shown below:
      ami_type       : EKS-optimized AMI family, e.g. AL2023_x86_64_NVIDIA
                       for GPU nodes                        (default: module default)
      capacity_type  : "ON_DEMAND" or "SPOT"          (default "ON_DEMAND")
      desired_size   : initial desired node count      (default 1)
      disk_size      : root EBS volume size in GB      (default 20)
      instance_types : list of EC2 instance types      (default ["t4g.medium"])
      labels         : Kubernetes node labels          (default {})
      max_size       : max nodes for cluster-autoscaler (default 3)
      min_size       : min nodes                       (default 1)
      taints         : map of taints (key, value, effect) (default {})

    Module default: 2 groups (system on Graviton Spot, workload on Graviton On-Demand).
    EOT
  default = {
    system = {
      capacity_type  = "SPOT"
      desired_size   = 1
      disk_size      = 20
      instance_types = ["t4g.small"]
      labels         = { role = "system" }
      max_size       = 2
      min_size       = 1
    }
    workload = {
      capacity_type  = "ON_DEMAND"
      desired_size   = 2
      disk_size      = 50
      instance_types = ["t4g.medium"]
      labels         = { role = "workload" }
      max_size       = 4
      min_size       = 1
    }
  }

  validation {
    condition = alltrue([
      for g in values(var.node_groups) :
      contains(["ON_DEMAND", "SPOT"], g.capacity_type)
    ])
    error_message = "capacity_type must be either ON_DEMAND or SPOT."
  }

  validation {
    condition = alltrue([
      for g in values(var.node_groups) :
      g.min_size <= g.desired_size && g.desired_size <= g.max_size
    ])
    error_message = "Each node group must satisfy min_size <= desired_size <= max_size."
  }
}

variable "subnet_ids" {
  type        = list(string)
  description = "List of subnet IDs for EKS nodes and control plane. Use private subnets for production."

  validation {
    condition     = length(var.subnet_ids) >= 2
    error_message = "EKS requires subnets in at least two Availability Zones."
  }
}

variable "tags" {
  type        = map(string)
  description = "Tags to apply to all EKS resources"
  default     = {}
}

variable "vpc_id" {
  type        = string
  description = "ID of the VPC where the EKS cluster will be deployed"
}
