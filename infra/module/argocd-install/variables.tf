variable "kubeconfig_path" {
  description = "Path to kubeconfig file for cluster access"
  type        = string
  default     = "~/.kube/config"
}

variable "namespace" {
  description = "Kubernetes namespace for ArgoCD"
  type        = string
  default     = "argocd"
}

variable "chart_version" {
  description = "Version of the ArgoCD Helm chart"
  type        = string
  default     = "7.3.11"
}

variable "hostname" {
  description = "Hostname for ArgoCD UI (leave empty for local/no ingress)"
  type        = string
  default     = ""
}

variable "redis_ha_enabled" {
  description = "Enable Redis High Availability"
  type        = bool
  default     = false
}

variable "autoscaling_enabled" {
  description = "Enable ArgoCD server autoscaling"
  type        = bool
  default     = false
}

variable "notifications_enabled" {
  description = "Enable ArgoCD notifications"
  type        = bool
  default     = false
}

variable "values_yaml" {
  description = "Custom Helm values YAML to override defaults"
  type        = string
  default     = ""
}

