terraform {
  required_version = ">= 1.9.0"

  required_providers {
    argocd = {
      source  = "oboukili/argocd"
      version = "~> 6.2"
    }
    local = {
      source  = "hashicorp/local"
      version = "~> 2.9"
    }
  }
}
