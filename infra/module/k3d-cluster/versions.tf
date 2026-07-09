terraform {
  required_version = ">= 1.3.0"
  backend "local" {}

  required_providers {
    k3d = {
      source  = "moio/k3d"
      version = "0.0.12"
    }
    kubectl = {
      source  = "gavinbunney/kubectl"
      version = "~> 1.14"
    }
  }
}
