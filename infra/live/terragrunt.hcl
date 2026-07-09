# ---------------------------------------------------------------------------
# Root Terragrunt configuration
# ---------------------------------------------------------------------------
# `generate` makes Terragrunt write the backend block into the module copy in
# .terragrunt-cache instead of passing -backend-config on the CLI. This lets the
# reusable modules under infra/module/ stay backend-agnostic, which is the
# expected shape for a reusable module (the backend is a root-module concern).
# ---------------------------------------------------------------------------

# Generate an AWS provider with S3 path-style (required for floci/localstack).
# When AWS_ENDPOINT_URL is set (floci), s3_use_path_style avoids DNS resolution
# errors like `bucket.localhost:4566` which doesn't exist.
generate "provider" {
  path      = "provider.tf"
  if_exists = "overwrite_terragrunt"
  contents  = <<-EOT
    provider "aws" {
      region = var.aws_region

      # Floci / LocalStack: use path-style S3 (bucket.localhost → localhost/bucket)
      s3_use_path_style = true

      # When AWS_ENDPOINT_URL is set, all AWS calls go to floci
      endpoints {
        s3             = var.aws_endpoint_url
        lambda         = var.aws_endpoint_url
        iam            = var.aws_endpoint_url
        sqs            = var.aws_endpoint_url
        dynamodb       = var.aws_endpoint_url
        stepfunctions  = var.aws_endpoint_url
      }

      # Floci credentials (test/test) — ignored by real AWS
      access_key = var.aws_access_key
      secret_key = var.aws_secret_key
      token      = var.aws_session_token

      skip_credentials_validation = true
      skip_metadata_api_check     = true
      skip_requesting_account_id  = true
    }

    variable "aws_region" {
      type    = string
      default = "eu-west-3"
    }

    variable "aws_endpoint_url" {
      type    = string
      default = null
    }

    variable "aws_access_key" {
      type    = string
      default = "test"
    }

    variable "aws_secret_key" {
      type    = string
      default = "test"
    }

    variable "aws_session_token" {
      type    = string
      default = null
    }
  EOT
}

# ---------------------------------------------------------------------------
# Common inputs — inherited by all live configs via `include "root"`.
# Each live config can override any of these (deep merge: child wins key by key).
# Modules that don't declare a matching `variable` will emit a harmless
# "Value for undeclared variable" warning — Terraform ignores the value.
# ---------------------------------------------------------------------------
inputs = {
  # --- k3d + ArgoCD (001, 002, 003, 007, 008) ---
  kubeconfig_path = "~/.kube/config"

  # --- ArgoCD install (002, 007) ---
  namespace             = "argocd"
  chart_version         = "7.3.11"
  hostname              = ""
  redis_ha_enabled      = false
  autoscaling_enabled   = false
  notifications_enabled = false

  # --- ArgoCD config (003, 008) ---
  argocd_namespace = "argocd"
  argocd_username  = "admin"
  git_repo_url     = "https://github.com/lionelmarcus10/aipaas.git"
  git_branch       = "master"  # TEMP: was "master", changed for A2 testing
  helm_repos = [
    { name = "kedacore",   url = "https://kedacore.github.io/charts" },
    { name = "argoproj",   url = "https://argoproj.github.io/argo-helm" },
    { name = "grafana",    url = "https://grafana.github.io/helm-charts" },
    { name = "opencost",   url = "https://opencost.github.io/opencost-helm-chart" },
    { name = "langfuse",   url = "https://langfuse.github.io/langfuse-k8s" },
    { name = "prometheus", url = "https://prometheus-community.github.io/helm-charts" },
  ]

  # --- AWS modules (004, 005, 006) ---
  tags = {
    Project     = "aipaas"
    Environment = "dev"
    ManagedBy   = "terragrunt"
  }
}

remote_state {
  backend = "local"

  config = {
    path = "${get_parent_terragrunt_dir()}/${path_relative_to_include()}/terraform.tfstate"
  }

  generate = {
    path      = "backend.tf"
    if_exists = "overwrite_terragrunt"
  }
}
