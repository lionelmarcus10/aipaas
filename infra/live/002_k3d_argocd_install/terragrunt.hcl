include "root" {
  path = find_in_parent_folders("terragrunt.hcl")
}

terraform {
  source = "../../module/argocd-install"
}

dependencies {
  paths = ["../001_k3d_init_cluster"]
}

inputs = {
  values_yaml           = <<-EOT
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
