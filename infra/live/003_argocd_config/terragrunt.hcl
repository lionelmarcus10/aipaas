include "root" {
  path = find_in_parent_folders("terragrunt.hcl")
}

terraform {
  source = "../../module/argocd-config"
}

dependencies {
  paths = ["../002_argocd_install"]
}

inputs = {
  argocd_namespace = "argocd"
  argocd_username  = "admin"
  kubeconfig_path  = "~/.kube/config"

  git_repo_url = "https://github.com/lionelmarcus10/aipaas.git"
  git_branch   = "master"

  project_name        = "aipaas"
  project_description = "AIPaaS platform — GitOps managed applications"

  target_namespaces = ["default", "aipaas", "agents", "keda-system", "argo-rollouts", "observability", "opencost"]

  # App-of-Apps: chaque entrée = une Application ArgoCD qui pointe vers un sous-dossier de apps/
  apps = [
    {
      name             = "test-nginx"
      path             = "apps/test-nginx"
      target_namespace = "default"
      auto_sync        = true
      self_heal        = true
      prune            = true
    },
    # --- Sprint 4 ---
    {
      name             = "keda"
      path             = "apps/keda"
      target_namespace = "keda-system"
      auto_sync        = true
      self_heal        = true
      prune            = true
    },
    {
      name             = "vllm"
      path             = "apps/vllm"
      target_namespace = "aipaas"
      auto_sync        = true
      self_heal        = true
      prune            = true
    },
    # --- Sprint 5 ---
    {
      name             = "argo-rollouts"
      path             = "apps/argo-rollouts"
      target_namespace = "argo-rollouts"
      auto_sync        = true
      self_heal        = true
      prune            = true
    },
    {
      name             = "grafana"
      path             = "apps/grafana"
      target_namespace = "observability"
      auto_sync        = true
      self_heal        = true
      prune            = true
    },
    {
      name             = "opencost"
      path             = "apps/opencost"
      target_namespace = "opencost"
      auto_sync        = true
      self_heal        = true
      prune            = true
    },
    {
      name             = "langfuse"
      path             = "apps/langfuse"
      target_namespace = "observability"
      auto_sync        = true
      self_heal        = true
      prune            = true
    },
  ]
}
