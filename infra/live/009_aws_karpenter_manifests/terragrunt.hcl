include "root" {
  path = find_in_parent_folders("terragrunt.hcl")
}

terraform {
  source = "../../module/karpenter-manifests"
}

dependencies {
  paths = ["../005_aws_eks"]
}

# ---------------------------------------------------------------------------
# 009 — Karpenter NodePool + EC2NodeClass manifests
# ---------------------------------------------------------------------------
# Le module EKS (005) crée l'infrastructure Karpenter (IAM, SQS, access entry)
# mais pas les manifests K8s (NodePool, EC2NodeClass). Ce live config les crée
# via le provider Kubernetes.
#
# Karpenter remplace les node groups managés par un autoscaling intelligent:
# - NodePool: définit quels pods Karpenter doit provisionner (taints, labels, resources)
# - EC2NodeClass: définit comment provisionner (AMI, security groups, subnet)
#
# Prérequis:
#   1. terragrunt apply 005_aws_eks (crée l'IAM Karpenter + SQS)
#   2. Installer le Helm chart Karpenter:
#      helm install karpenter oci://public.ecr.aws/karpenter/karpenter \
#        -n kube-system --create-namespace \
#        --set clusterSettings.clusterName=aipaas-eks \
#        --set clusterSettings.interruptionQueueName=aipaas-eks
#   3. terragrunt apply 009_aws_karpenter_manifests
# ---------------------------------------------------------------------------

dependency "eks" {
  config_path = "../005_aws_eks"

  mock_outputs = {
    cluster_name              = "aipaas-eks"
    cluster_endpoint          = "https://mock.eks.amazonaws.com"
    cluster_ca_certificate    = "mock"
  }

  mock_outputs_allowed_terraform_commands = ["init", "validate", "plan", "show", "graph"]
  mock_outputs_merge_strategy_with_state  = "shallow"
}

inputs = {
  cluster_name           = dependency.eks.outputs.cluster_name
  cluster_endpoint       = dependency.eks.outputs.cluster_endpoint
  cluster_ca_certificate = dependency.eks.outputs.cluster_ca_certificate

  # NodePool — provisionne des nodes à la demande
  # Karpenter crée des EC2 instances quand des pods sont en Pending
  node_pools = {
    # Pool CPU — pour les workloads standards (agents, observabilité)
    cpu = {
      labels = { role = "workload" }
      taints = {}
      capacity_types = ["on-demand", "spot"]
      instance_types = ["t4g.medium", "t4g.large"]
      min_size       = 0
      max_size       = 10
    }

    # Pool GPU — pour vLLM (taint nvidia.com/gpu = seuls les pods GPU schedulent)
    gpu = {
      labels = { role = "gpu" }
      taints = {
        gpu = {
          key    = "nvidia.com/gpu"
          value  = "true"
          effect = "NoSchedule"
        }
      }
      capacity_types = ["spot"]
      instance_types = ["g6.xlarge", "g5.xlarge"]
      min_size       = 0
      max_size       = 4
    }
  }
}
