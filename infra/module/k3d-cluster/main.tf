resource "k3d_cluster" "this" {
  name    = var.cluster_name
  servers = var.servers_count
  agents  = var.agents_count
  image   = "rancher/k3s:v${var.kubernetes_version}"

  kube_api {
    host_ip   = "0.0.0.0"
    host_port = var.api_host_port
  }

  port {
    host_port      = var.http_port
    container_port = 80
    node_filters   = ["loadbalancer"]
  }

  port {
    host_port      = var.https_port
    container_port = 443
    node_filters   = ["loadbalancer"]
  }

  dynamic "port" {
    for_each = var.extra_ports
    content {
      host_port      = port.value.host_port
      container_port = port.value.container_port
      protocol       = port.value.protocol
      node_filters   = ["loadbalancer"]
    }
  }

  registries {
    create {
      name      = var.registry_name
      host      = "localhost"
      host_port = "${var.registry_port}"
    }
  }

  k3d {
    disable_load_balancer = false
    disable_image_volume  = false
  }

  kubeconfig {
    update_default_kubeconfig = true
    switch_current_context    = true
  }

  dynamic "runtime" {
    for_each = var.servers_memory != null || var.agents_memory != null ? [1] : []
    content {
      servers_memory = var.servers_memory
      agents_memory  = var.agents_memory
    }
  }
}

provider "kubectl" {
  config_path = var.kubeconfig_path
}

# --- Server node labels ---
resource "kubectl_manifest" "server_labels" {
  for_each = { for k, v in var.server_node_labels : k => v }

  yaml_body = yamlencode({
    apiVersion = "v1"
    kind       = "Node"
    metadata = {
      name   = "k3d-${var.cluster_name}-server-0"
      labels = { (each.key) = each.value }
    }
  })

  apply_only = true
  depends_on = [k3d_cluster.this]
}

# --- Server node taints ---
resource "kubectl_manifest" "server_taints" {
  for_each = { for k, v in var.server_node_taints : k => v }

  yaml_body = yamlencode({
    apiVersion = "v1"
    kind       = "Node"
    metadata = {
      name = "k3d-${var.cluster_name}-server-0"
    }
    spec = {
      taints = [
        {
          key    = each.key
          value  = split(":", each.value)[0]
          effect = split(":", each.value)[1]
        }
      ]
    }
  })

  apply_only = true
  depends_on = [k3d_cluster.this]
}

# --- Agent node labels ---
resource "kubectl_manifest" "agent_labels" {
  for_each = { for k, v in var.agent_node_labels : k => v }

  yaml_body = yamlencode({
    apiVersion = "v1"
    kind       = "Node"
    metadata = {
      name   = "k3d-${var.cluster_name}-agent-0"
      labels = { (each.key) = each.value }
    }
  })

  apply_only = true
  depends_on = [k3d_cluster.this]
}
