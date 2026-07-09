terraform {
  required_version = ">= 1.3.0"
  backend "local" {}

  required_providers {
    argocd = {
      source  = "oboukili/argocd"
      version = "6.2.0"
    }
    local = {
      source  = "hashicorp/local"
      version = "~> 2.9"
    }
  }
}
