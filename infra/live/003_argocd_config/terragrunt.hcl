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
  git_branch   = "main"

  project_name        = "aipaas"
  project_description = "AIPaaS platform — GitOps managed applications"

  target_namespaces = ["default", "aipaas", "agents"]

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
    # Les apps suivantes seront activées dans les sprints ultérieurs
    # {
    #   name             = "vllm"
    #   path             = "apps/vllm"
    #   target_namespace = "aipaas"
    #   auto_sync        = true
    #   self_heal        = true
    #   prune            = true
    # },
    # {
    #   name             = "keda"
    #   path             = "apps/keda"
    #   target_namespace = "aipaas"
    #   auto_sync        = true
    #   self_heal        = true
    #   prune            = true
    # },
    # {
    #   name             = "observability"
    #   path             = "apps/observability"
    #   target_namespace = "aipaas"
    #   auto_sync        = true
    #   self_heal        = true
    #   prune            = true
    # },
  ]
}
