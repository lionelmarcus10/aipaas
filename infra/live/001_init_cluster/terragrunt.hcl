include "root" {
  path = find_in_parent_folders("terragrunt.hcl")
}

terraform {
  source = "../../module/k3d-cluster"
}

inputs = {
  cluster_name       = "aipaas"
  kubeconfig_path    = "~/.kube/config"
  servers_count      = 1
  agents_count       = 2
  kubernetes_version = "1.31.5-k3s1"
  api_host_port      = 6550
  http_port          = 8080
  https_port         = 8443
  registry_name      = "aipaas-registry"
  registry_port      = 5001

  # Labels appliques aux nodes server (control-plane)
  # Addons-Services=true => ArgoCD et autres addons schedulent uniquement sur les servers
  server_node_labels = {
    "Addons-Services" = "true"
  }

  # Taint sur les servers : seuls les pods avec la toleration Addons-Services=true
  # peuvent y tourner. Les apps (guestbook, agents, etc.) sont repoussees vers les agents.
  server_node_taints = {
    "Addons-Services" = "true:NoSchedule"
  }

  # Les agents (workers) n'ont pas le label Addons-Services
  # => les apps deployees par ArgoCD vont sur les agents
  # agent_node_labels = {}

  # Limits memoire — ajuster selon ta machine
  # servers_memory     = "512m"
  # agents_memory      = "2g"

  # Ports supplementaires exposes sur le loadbalancer
  # extra_ports = [
  #   { host_port = 30080, container_port = 30080 },
  # ]
}
