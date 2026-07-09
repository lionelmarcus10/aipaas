include "root" {
  path = find_in_parent_folders("terragrunt.hcl")
}

terraform {
  source = "../../module/argocd-config"
}

dependencies {
  paths = ["../007_aws_argocd_install"]
}

# ---------------------------------------------------------------------------
# 008 — Configurer ArgoCD sur EKS (projet, Helm repos, App-of-Apps)
# ---------------------------------------------------------------------------
# Réutilise le même module que 003_k3d_argocd_config mais avec le kubeconfig EKS.
#
# ⚠️ APP-OF-APPS EKS vs k3d:
# Le parent Application pointe vers apps/ mais utilise le filtre directory_include
# pour ne sélectionner que les application.yaml des apps qui ont un overlay EKS.
#
# 2 stratégies possibles:
#
#   Stratégie A (recommandée): un seul App-of-Apps qui scanne apps/*/application.yaml
#   Les application.yaml k3d pointent vers apps/<name>/ (base k3d).
#   Pour EKS, on crée des application-eks.yaml dans apps/<name>/eks/ qui pointent
#   vers le overlay EKS. Le parent EKS filtre sur "*/eks/application.yaml".
#
#   Stratégie B: 2 App-of-Apps séparés (un k3d, un EKS) qui pointent vers
#   des paths différents.
#
# Cette config utilise la stratégie A: le parent EKS scanne apps/*/eks/
# pour les apps qui ont un overlay, et apps/*/application.yaml pour les autres
# (apps sans patch EKS = identiques sur k3d et EKS).
#
# Prérequis:
#   1. terragrunt apply 007_aws_argocd_install
#   2. terragrunt apply 008_aws_argocd_config
# ---------------------------------------------------------------------------

inputs = {
  project_name        = "aipaas-eks"
  project_description = "AIPaaS platform — EKS GitOps managed applications"

  # Namespaces cibles sur EKS (ajout de kyverno-system et monitoring)
  target_namespaces = [
    "default", "aipaas", "agents", "keda-system", "argo-rollouts",
    "observability", "monitoring", "opencost", "kube-system",
    "argocd", "kyverno-system", "financial-dispute-agent"
  ]

  # App-of-Apps EKS — pointe vers apps/ avec filtre sur les overlays EKS
  #
  # Les apps qui ont un dossier eks/ (vllm, financial-dispute-agent, loki,
  # grafana, shared-storage) sont déployées via leur overlay EKS.
  # Les autres apps (keda, prometheus, kyverno, etc.) utilisent leur
  # application.yaml racine (identique k3d/EKS).
  #
  # Pour cela, on crée 2 parent Applications:
  #   1. "aipaas-eks-overlays" → scanne apps/*/eks/application.yaml (apps patchées)
  #   2. "aipaas-eks-base"     → scanne apps/*/application.yaml (apps sans patch)
  #
  # Les application.yaml des apps patchées (vllm, etc.) sont exclus du scan base
  # pour éviter les doublons. Voir le fichier application-eks.yaml dans chaque
  # dossier eks/ pour la définition ArgoCD de l'overlay.
  apps = [
    {
      name              = "aipaas-eks-base"
      path              = "apps"
      directory_recurse = true
      directory_include = "*/application.yaml"
      target_namespace  = "argocd"
    },
  ]
}
