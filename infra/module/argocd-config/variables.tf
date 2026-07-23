variable "argocd_namespace" {
  description = "Namespace where ArgoCD is installed"
  type        = string
  default     = "argocd"
}

variable "argocd_username" {
  description = "ArgoCD admin username"
  type        = string
  default     = "admin"
}

variable "kubeconfig_path" {
  description = "Path to kubeconfig file for cluster access"
  type        = string
  default     = "~/.kube/config"
}

variable "git_repo_url" {
  description = "Git repository URL for GitOps sync"
  type        = string
}

variable "git_branch" {
  description = "Git branch to track"
  type        = string
  default     = "main"
}

variable "project_name" {
  description = "ArgoCD project name"
  type        = string
  default     = "aipaas"
}

variable "project_description" {
  description = "ArgoCD project description"
  type        = string
  default     = "AIPaaS platform — GitOps managed applications"
}

variable "target_namespaces" {
  description = "List of namespaces where apps can be deployed"
  type        = list(string)
  default     = ["default", "aipaas", "agents"]
}

variable "helm_repos" {
  description = "List of Helm repositories to register in ArgoCD"
  type = list(object({
    name = string
    url  = string
    type = optional(string, "helm")
  }))
  default = []
}

variable "apps" {
  description = "List of ArgoCD applications to create"
  type = list(object({
    name             = string
    path             = optional(string, "")
    target_namespace = string
    auto_sync        = optional(bool, true)
    self_heal        = optional(bool, true)
    prune            = optional(bool, true)
    # Helm chart mode (optional): if set, use upstream Helm chart instead of Git path
    helm_chart       = optional(string, "")
    helm_repo_url    = optional(string, "")
    helm_version     = optional(string, "")
    helm_values      = optional(string, "")
  }))
  default = []
}
