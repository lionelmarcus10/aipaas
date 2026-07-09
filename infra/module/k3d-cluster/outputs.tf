output "cluster_name" {
  description = "Name of the created k3d cluster"
  value       = k3d_cluster.this.name
}

output "cluster_id" {
  description = "ID of the created k3d cluster"
  value       = k3d_cluster.this.id
}

output "api_server_port" {
  description = "Host port exposing the Kubernetes API"
  value       = var.api_host_port
}

output "http_port" {
  description = "Host port for HTTP ingress"
  value       = var.http_port
}

output "https_port" {
  description = "Host port for HTTPS ingress"
  value       = var.https_port
}

output "registry_name" {
  description = "Name of the local registry"
  value       = var.registry_name
}

output "registry_url" {
  description = "URL of the local registry"
  value       = "localhost:${var.registry_port}"
}

output "kubeconfig_context" {
  description = "kubectl context to interact with the cluster"
  value       = "k3d-${var.cluster_name}"
}

output "kubeconfig_raw" {
  description = "Raw kubeconfig for the cluster"
  value       = k3d_cluster.this.credentials[0].raw
  sensitive   = true
}
