terraform {
  required_version = ">= 1.9.0"

  required_providers {
    k3d = {
      source  = "moio/k3d"
      version = "0.0.12"
    }
    kubectl = {
      source  = "gavinbunney/kubectl"
      version = "~> 1.19"
    }
  }
}
