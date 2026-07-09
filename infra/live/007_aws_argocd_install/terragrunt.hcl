include "root" {
  path = find_in_parent_folders("terragrunt.hcl")
}

terraform {
  source = "../../module/argocd-install"
}

dependencies {
  paths = ["../005_aws_eks"]
}

# ---------------------------------------------------------------------------
# 007 — Installer ArgoCD sur EKS
# ---------------------------------------------------------------------------
# Réutilise le même module que 002_k3d_argocd_install mais avec le kubeconfig
# EKS généré par `aws eks update-kubeconfig`.
#
# Prérequis:
#   1. terragrunt apply 004_aws_vpc
#   2. terragrunt apply 005_aws_eks
#   3. aws eks update-kubeconfig --name aipaas-eks --region eu-west-3
#      (génère ~/.kube/config avec le contexte EKS)
#   4. terragrunt apply 007_aws_argocd_install
#
# Différences avec k3d (002):
#   - Pas de nodeSelector Addons-Services (EKS n'a pas de taint sur les nodes)
#   - service.type: LoadBalancer → crée un NLB/ALB sur AWS
#   - hostname: "" (mettre un domaine si TLS voulu + cert-manager)
# ---------------------------------------------------------------------------

inputs = {
  values_yaml           = <<-EOT
server:
  ingress:
    enabled: false
  service:
    type: LoadBalancer
dex:
  enabled: false

# Sur EKS, pas de taint Addons-Services — ArgoCD peut tourner sur n'importe quel node.
# On garde un nodeSelector sur le node group "system" pour éviter les nodes workload/gpu.
global:
  nodeSelector:
    role: system
  EOT
}
