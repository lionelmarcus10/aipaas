# --- gVisor auto-install prerequisite ---
# When enable_gvisor = true, check if runsc + containerd-shim-runsc-v1 are
# installed on the host. If not, run install-gvisor.sh automatically.
# This runs BEFORE the cluster is created (depends_on below).
resource "null_resource" "gvisor_prereq" {
  count = var.enable_gvisor ? 1 : 0

  provisioner "local-exec" {
    # --check returns 0 if installed, 1 if missing
    # If --check fails → || triggers the full install
    command = "bash ${var.gvisor_install_script_path} --check || bash ${var.gvisor_install_script_path}"
    interpreter = ["bash", "-c"]
  }

  triggers = {
    always_rerun = timestamp()
  }
}

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
      host_port = var.registry_port
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

  # --- gVisor: mount runsc + shim + containerd config into all nodes ---
  # k3d v5.x node filter syntax: "server:0", "agent:0" (colon, not brackets)
  dynamic "volume" {
    for_each = var.enable_gvisor ? [1] : []
    content {
      source       = var.gvisor_runsc_path
      destination  = "/usr/local/bin/runsc"
      node_filters = ["server:0", "agent:0"]
    }
  }

  dynamic "volume" {
    for_each = var.enable_gvisor ? [1] : []
    content {
      source       = var.gvisor_shim_path
      destination  = "/usr/local/bin/containerd-shim-runsc-v1"
      node_filters = ["server:0", "agent:0"]
    }
  }

  dynamic "volume" {
    for_each = var.enable_gvisor ? [1] : []
    content {
      source       = "${abspath(path.module)}/files/containerd-config.toml.tmpl"
      destination  = "/var/lib/rancher/k3s/agent/etc/containerd/config.toml.tmpl"
      node_filters = ["server:0", "agent:0"]
    }
  }

  # gVisor must be installed on the host BEFORE the cluster is created
  depends_on = [null_resource.gvisor_prereq]
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

# --- gVisor RuntimeClass ---
# Registers the "gvisor" RuntimeClass so pods can opt into syscall isolation
# via spec.runtimeClassName: gvisor. The runsc binary is mounted into the nodes
# by the volume blocks above, and the containerd config registers it as a runtime.
resource "kubectl_manifest" "gvisor_runtimeclass" {
  count = var.enable_gvisor ? 1 : 0

  yaml_body = yamlencode({
    apiVersion = "node.k8s.io/v1"
    kind       = "RuntimeClass"
    metadata = {
      name = "gvisor"
    }
    handler = "runsc"
  })

  apply_only = true
  depends_on = [k3d_cluster.this]
}
