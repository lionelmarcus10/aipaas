terraform {
  # >= 1.9 is required for cross-variable references inside `validation` blocks
  # (used by the endpoint_public_access CIDR guard in variables.tf).
  required_version = ">= 1.9.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.61"
    }
    tls = {
      source  = "hashicorp/tls"
      version = "~> 4.3"
    }
  }
}
