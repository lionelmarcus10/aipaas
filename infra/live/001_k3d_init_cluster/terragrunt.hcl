include "root" {
  path = find_in_parent_folders("terragrunt.hcl")
}

terraform {
  source = "../../module/k3d-cluster"
}

inputs = {
  cluster_name       = "aipaas"
  servers_count      = 1
  agents_count       = 1
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
  # Agent: 12g pour accommoder vLLM (Qwen2.5-0.5B = ~1 GB) + l'agent pod + headroom
  servers_memory = "3g"
  agents_memory  = "12g"

  # Ports supplementaires exposes sur le loadbalancer
  # extra_ports = [
  #   { host_port = 30080, container_port = 30080 },
  # ]

  # --- gVisor (runsc) sandboxing ---
  # Active l'isolation syscall pour les pods avec runtimeClassName: gvisor.
  # Prerequis : bash infra/scripts/install-gvisor.sh sur le host avant de creer le cluster.
  # Si runsc n'est pas installe, mettre a false.
  enable_gvisor = true

  # Chemin absolu vers le script d'install gVisor (passé au module car
  # path.module dans Terraform pointe vers le cache Terragrunt, pas le repo)
  gvisor_install_script_path = "${get_repo_root()}/infra/scripts/install-gvisor.sh"
}
