output "argocd_namespace" {
  description = "Namespace where ArgoCD is installed"
  value       = var.namespace
}

output "chart_version" {
  description = "ArgoCD Helm chart version deployed"
  value       = var.chart_version
}

output "release_name" {
  description = "Helm release name"
  value       = helm_release.argocd.name
}

output "release_status" {
  description = "Helm release status"
  value       = helm_release.argocd.status
}
