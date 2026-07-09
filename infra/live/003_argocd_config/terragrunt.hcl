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

  git_repo_url = "https://github.com/argoproj/argocd-example-apps.git"
  git_branch   = "master"

  project_name        = "aipaas"
  project_description = "AIPaaS platform — GitOps managed applications"

  target_namespaces = ["default", "aipaas", "agents"]

  # Apps à synchroniser depuis Git (chemins dans le repo)
  apps = [
    {
      name             = "guestbook"
      path             = "guestbook"
      target_namespace = "default"
      auto_sync        = true
      self_heal        = true
      prune            = true
    },
  ]
}
