include "root" {
  path = find_in_parent_folders("terragrunt.hcl")
}

terraform {
  source = "../../module/argocd-install"
}

dependencies {
  paths = ["../001_init_cluster"]
}

inputs = {
  kubeconfig_path     = "~/.kube/config"
  namespace            = "argocd"
  chart_version        = "7.3.11"
  hostname             = ""
  redis_ha_enabled     = false
  autoscaling_enabled  = false
  notifications_enabled = false
  values_yaml          = <<-EOT
server:
  ingress:
    enabled: false
  service:
    type: LoadBalancer
dex:
  enabled: false

# Force tous les pods ArgoCD sur les nodes avec Addons-Services=true (server nodes)
# + toleration pour passer le taint NoSchedule
global:
  nodeSelector:
    Addons-Services: "true"
  tolerations:
    - key: "Addons-Services"
      operator: "Equal"
      value: "true"
      effect: "NoSchedule"
EOT
}
