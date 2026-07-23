include "root" {
  path = find_in_parent_folders("terragrunt.hcl")
}

terraform {
  source = "../../module/argocd-config"
}

dependencies {
  paths = ["../002_argocd_install"]
}

inputs = {
  argocd_namespace = "argocd"
  argocd_username  = "admin"
  kubeconfig_path  = "~/.kube/config"

  git_repo_url = "https://github.com/lionelmarcus10/aipaas.git"
  git_branch   = "master"

  project_name        = "aipaas"
  project_description = "AIPaaS platform — GitOps managed applications"

  target_namespaces = ["default", "aipaas", "agents", "keda-system", "argo-rollouts", "observability", "opencost"]

  # Helm repositories for upstream charts
  helm_repos = [
    { name = "kedacore",      url = "https://kedacore.github.io/charts" },
    { name = "argoproj",      url = "https://argoproj.github.io/argo-helm" },
    { name = "grafana",       url = "https://grafana.github.io/helm-charts" },
    { name = "opencost",      url = "https://opencost.github.io/opencost-helm-chart" },
    { name = "langfuse",      url = "https://langfuse.github.io/langfuse-k8s" },
  ]

  # App-of-Apps: Git path mode = raw manifests in our repo; Helm chart mode = upstream chart + inline values
  apps = [
    # --- Sprint 1 (Git path) ---
    {
      name             = "test-nginx"
      path             = "apps/test-nginx"
      target_namespace = "default"
    },
    # --- Sprint 4 ---
    # KEDA — Helm chart mode
    {
      name             = "keda"
      target_namespace = "keda-system"
      helm_chart       = "keda"
      helm_repo_url    = "https://kedacore.github.io/charts"
      helm_version     = "2.20.1"
      helm_values      = <<-EOT
watchNamespace: ""
operator:
  logLevel: debug
  resources:
    limits:
      cpu: 500m
      memory: 256Mi
    requests:
      cpu: 100m
      memory: 128Mi
EOT
    },
    # vLLM — Git path mode (raw manifests, chart not published to registry)
    {
      name             = "vllm"
      path             = "apps/vllm"
      target_namespace = "aipaas"
    },
    # --- Sprint 5 ---
    # Argo Rollouts — Helm chart mode
    {
      name             = "argo-rollouts"
      target_namespace = "argo-rollouts"
      helm_chart       = "argo-rollouts"
      helm_repo_url    = "https://argoproj.github.io/argo-helm"
      helm_version     = "2.41.1"
      helm_values      = <<-EOT
controller:
  resources:
    limits:
      cpu: 500m
      memory: 256Mi
    requests:
      cpu: 100m
      memory: 128Mi
dashboard:
  enabled: true
EOT
    },
    # Grafana — Helm chart mode
    {
      name             = "grafana"
      target_namespace = "observability"
      helm_chart       = "grafana"
      helm_repo_url    = "https://grafana.github.io/helm-charts"
      helm_version     = "10.5.15"
      helm_values      = <<-EOT
adminUser: admin
adminPassword: aipaas-dev
resources:
  limits:
    cpu: 500m
    memory: 256Mi
  requests:
    cpu: 100m
    memory: 128Mi
persistence:
  enabled: true
  size: 1Gi
  accessModes:
    - ReadWriteOnce
datasources:
  datasources.yaml:
    apiVersion: 1
    datasources:
      - name: Prometheus
        type: prometheus
        access: proxy
        url: http://prometheus-server.observability.svc.cluster.local:80
        isDefault: true
service:
  type: ClusterIP
  port: 80
EOT
    },
    # OpenCost — Helm chart mode
    {
      name             = "opencost"
      target_namespace = "opencost"
      helm_chart       = "opencost"
      helm_repo_url    = "https://opencost.github.io/opencost-helm-chart"
      helm_version     = "2.5.28"
      helm_values      = <<-EOT
opencost:
  exporter:
    defaultClusterName: aipaas-k3d
    resources:
      limits:
        cpu: 500m
        memory: 512Mi
      requests:
        cpu: 100m
        memory: 256Mi
  cloudProvider: ""
  prometheus:
    enabled: true
    internal:
      enabled: true
      address: http://prometheus-server.observability.svc.cluster.local:80
  ui:
    enabled: true
EOT
    },
    # Langfuse — Helm chart mode
    {
      name             = "langfuse"
      target_namespace = "observability"
      helm_chart       = "langfuse"
      helm_repo_url    = "https://langfuse.github.io/langfuse-k8s"
      helm_version     = "1.5.40"
      helm_values      = <<-EOT
langfuse:
  resources:
    limits:
      cpu: 500m
      memory: 512Mi
    requests:
      cpu: 100m
      memory: 256Mi
  salt:
    value: "aipaas-langfuse-dev-salt-change-me"
  nextauth:
    url: http://localhost:3000
    secret:
      value: "aipaas-langfuse-dev-secret-change-me"
  encryptionKey:
    value: "aipaas-langfuse-dev-encryption-key-change-me-64chars"
postgresql:
  deploy: true
  auth:
    password: "aipaas-langfuse-pg-dev"
  primary:
    persistence:
      size: 2Gi
service:
  type: ClusterIP
  port: 80
EOT
    },
  ]
}
