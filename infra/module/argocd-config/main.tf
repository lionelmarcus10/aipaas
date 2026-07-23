ephemeral "local_command" "argocd_password" {
  command = "bash"
  arguments = [
    "-c",
    "kubectl wait --for=condition=Ready pod -l app.kubernetes.io/name=argocd-server -n ${var.argocd_namespace} --timeout=120s --kubeconfig ${pathexpand(var.kubeconfig_path)} >&2 && kubectl get secret argocd-initial-admin-secret -n ${var.argocd_namespace} -o jsonpath={.data.password} --kubeconfig ${pathexpand(var.kubeconfig_path)}",
  ]
}

provider "argocd" {
  port_forward_with_namespace = var.argocd_namespace
  username                    = var.argocd_username
  password                    = base64decode(trimspace(ephemeral.local_command.argocd_password.stdout))
  insecure                    = true
}

# --- Git repository connection ---

resource "argocd_repository" "main" {
  repo = var.git_repo_url
  name = var.project_name
  type = "git"
}

# --- Helm repositories ---

resource "argocd_repository" "helm" {
  for_each = { for repo in var.helm_repos : repo.name => repo }

  repo = each.value.url
  name = each.value.name
  type = each.value.type

  depends_on = [argocd_repository.main]
}

# --- ArgoCD project ---

resource "argocd_project" "this" {
  metadata {
    name      = var.project_name
    namespace = var.argocd_namespace
    labels = {
      "app.kubernetes.io/managed-by" = "terraform"
    }
  }

  spec {
    description       = var.project_description
    source_repos      = concat([var.git_repo_url], [for repo in var.helm_repos : repo.url])
    source_namespaces = [var.argocd_namespace]

    dynamic "destination" {
      for_each = toset(var.target_namespaces)
      content {
        server    = "https://kubernetes.default.svc"
        namespace = destination.value
      }
    }

    # Allow Namespace cluster-scoped resources (needed by Helm charts that create namespaces)
    cluster_resource_whitelist {
      group = ""
      kind  = "Namespace"
    }
  }
}

# --- ArgoCD applications ---

resource "argocd_application" "apps" {
  for_each = { for app in var.apps : app.name => app }

  metadata {
    name      = each.value.name
    namespace = var.argocd_namespace
    labels = {
      "app.kubernetes.io/managed-by" = "terraform"
      "argocd.argoproj.io/project"   = var.project_name
    }
  }

  spec {
    project = argocd_project.this.metadata[0].name

    destination {
      server    = "https://kubernetes.default.svc"
      namespace = each.value.target_namespace
    }

    # Git path mode (raw manifests or kustomize)
    dynamic "source" {
      for_each = each.value.helm_chart == "" ? [1] : []
      content {
        repo_url        = var.git_repo_url
        path            = each.value.path
        target_revision = var.git_branch
      }
    }

    # Helm chart mode (upstream chart + inline values)
    dynamic "source" {
      for_each = each.value.helm_chart != "" ? [1] : []
      content {
        repo_url        = each.value.helm_repo_url
        chart           = each.value.helm_chart
        target_revision = each.value.helm_version

        helm {
          values = each.value.helm_values
        }
      }
    }

    sync_policy {
      dynamic "automated" {
        for_each = each.value.auto_sync ? [1] : []
        content {
          prune     = each.value.prune
          self_heal = each.value.self_heal
        }
      }

      sync_options = ["CreateNamespace=true"]

      retry {
        limit = "5"
        backoff {
          duration     = "30s"
          max_duration = "2m"
          factor       = "2"
        }
      }
    }
  }

  wait = false

  depends_on = [argocd_repository.main]
}
