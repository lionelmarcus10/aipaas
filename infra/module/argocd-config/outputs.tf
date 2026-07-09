output "project_name" {
  description = "ArgoCD project name"
  value       = argocd_project.this.metadata[0].name
}

output "repository_name" {
  description = "Connected Git repository name"
  value       = argocd_repository.main.name
}

output "repository_connection_state" {
  description = "Connection state of the Git repository"
  value       = argocd_repository.main.connection_state_status
}

output "application_names" {
  description = "List of created ArgoCD application names"
  value       = [for app in argocd_application.apps : app.metadata[0].name]
}
