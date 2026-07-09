include "root" {
  path = find_in_parent_folders("terragrunt.hcl")
}

terraform {
  source = "../../module/argocd-config"
}

dependencies {
  paths = ["../002_k3d_argocd_install"]
}

inputs = {
  project_name        = "aipaas"
  project_description = "AIPaaS platform — GitOps managed applications"

  target_namespaces = ["default", "aipaas", "agents", "keda-system", "argo-rollouts", "observability", "opencost", "kube-system", "argocd", "financial-dispute-agent", "insurance-claims-agent"]

  # Single App-of-Apps — all app configs live in apps/*/application.yaml
  apps = [
    {
      name              = "aipaas-apps"
      path              = "apps"
      directory_recurse = true
      directory_include = "*/application.yaml"
      target_namespace  = "argocd"
    },
  ]
}
