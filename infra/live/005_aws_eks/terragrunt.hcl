include "root" {
  path = find_in_parent_folders("terragrunt.hcl")
}

terraform {
  source = "../../module/eks"
}

dependencies {
  paths = ["../004_aws_vpc"]
}

# ---------------------------------------------------------------------------
# Pull VPC outputs from the upstream VPC live config
# This avoids hardcoding VPC IDs — Terragrunt reads them from tfstate.
#
# mock_outputs_allowed_terraform_commands restricts the fake IDs to read-only
# commands. Without it, an `apply` run before the VPC exists would attempt to
# build an EKS cluster against vpc-mock00000000.
# ---------------------------------------------------------------------------
dependency "vpc" {
  config_path = "../004_aws_vpc"

  mock_outputs = {
    vpc_id             = "vpc-mock00000000"
    private_subnet_ids = ["subnet-mock00000001", "subnet-mock00000002"]
  }

  mock_outputs_allowed_terraform_commands = ["init", "validate", "plan", "show", "graph"]
  mock_outputs_merge_strategy_with_state  = "shallow"
}

inputs = {
  cluster_name       = "aipaas-eks"
  kubernetes_version = "1.31"

  # --- Networking (from VPC outputs) ---
  vpc_id     = dependency.vpc.outputs.vpc_id
  subnet_ids = dependency.vpc.outputs.private_subnet_ids

  # --- Endpoint access ---
  # Dev posture: public endpoint enabled but scoped. The module defaults to
  # private-only; this live config opts in explicitly so the intent is visible.
  #
  # TODO prod: replace with office/VPN CIDR, e.g. ["203.0.113.10/32"],
  # and drop allow_public_access_from_anywhere.
  endpoint_private_access           = true
  endpoint_public_access            = true
  allowed_public_access_cidrs       = ["0.0.0.0/0"]
  allow_public_access_from_anywhere = true

  # --- Logging (control plane logs → CloudWatch) ---
  cluster_log_types          = ["api", "audit", "authenticator", "controllerManager", "scheduler"]
  cluster_log_retention_days = 90

  # --- Encryption (null = module creates and rotates its own KMS key) ---
  kms_key_arn                     = null
  kms_key_deletion_window_in_days = 30

  # --- Prod safety: prevent accidental deletion ---
  deletion_protection = true

  # --- Managed addons (patched by AWS) ---
  # The module automatically wires:
  #   - NetworkPolicy enforcement into vpc-cni (pod-level firewalling)
  #   - a least-privilege Pod Identity IAM role into aws-ebs-csi-driver
  addons = {
    coredns    = {}
    kube-proxy = {}
    vpc-cni = {
      # Must exist before any node joins (pods need IPs + policy enforcement)
      before_compute = true
    }
    eks-pod-identity-agent = {
      # Must exist before any node joins (pods need AWS credentials at boot)
      before_compute = true
    }
    aws-ebs-csi-driver = {} # PersistentVolumes (EBS gp3) for stateful workloads
    metrics-server     = {} # kubectl top + HPA metrics
  }

  # --- Karpenter infrastructure (IAM + SQS + access entry) ---
  # The controller Helm chart + NodePool/EC2NodeClass manifests are GitOps-managed.
  enable_karpenter    = true
  karpenter_namespace = "kube-system"

  # --- Node groups ---
  # All attributes are optional in the module; specified here for explicitness.
  # Graviton (ARM64) instances: ~20% cheaper than x86 at equivalent performance.
  node_groups = {
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
    # GPU pool for AI inference (vLLM etc.). GPU instances are x86_64, so this
    # pool uses the NVIDIA-variant AMI with drivers preinstalled. desired_size=0
    # keeps cost at $0 until a GPU workload actually schedules; the taint
    # prevents CPU-only pods from wasting expensive capacity.
    gpu = {
      ami_type       = "AL2023_x86_64_NVIDIA"
      capacity_type  = "SPOT"
      desired_size   = 0
      disk_size      = 100
      instance_types = ["g6.xlarge", "g5.xlarge"]
      labels         = { role = "gpu" }
      max_size       = 2
      min_size       = 0
      taints = {
        gpu = {
          key    = "nvidia.com/gpu"
          value  = "true"
          effect = "NO_SCHEDULE"
        }
      }
    }
  }

}
