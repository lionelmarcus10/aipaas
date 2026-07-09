terraform {
  required_version = ">= 1.3.0"

  required_providers {
    coder = {
      source  = "coder/coder"
      version = "~> 2.0"
    }
    docker = {
      source  = "kreuzwerker/docker"
      version = "~> 3.0"
    }
  }
}

# --- Coder data sources ---

data "coder_workspace" "me" {}
data "coder_workspace_owner" "me" {}

# --- Coder agent ---

resource "coder_agent" "main" {
  os   = "linux"
  arch = "amd64"

  startup_script_timeout = 600
  startup_script = <<-EOT
    set -e

    # ========================================
    # AIPaaS workspace bootstrap
    # Docker: DooD mode (socket mount from host)
    # No dockerd needed — the workspace talks
    # to the host's Docker daemon via the socket.
    # ========================================

    # 1 — Install Docker CLI (always needed)
    if ! command -v docker &>/dev/null; then
      apt-get update && apt-get install -y ca-certificates curl gnupg
      install -m 0755 -d /etc/apt/keyrings
      curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
      chmod a+r /etc/apt/keyrings/docker.gpg
      echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" > /etc/apt/sources.list.d/docker.list
      apt-get update
      apt-get install -y docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    fi

    # Docker mode: DooD (socket mount) or DinD (privileged, local daemon)
    DOCKER_MODE="${DOCKER_MODE:-dood}"

    if [ "$DOCKER_MODE" = "dind" ]; then
      # DinD: start dockerd inside the container (requires --privileged)
      if ! docker info &>/dev/null 2>&1; then
        apt-get install -y docker-ce
        usermod -aG docker coder 2>/dev/null || true
        dockerd &>/tmp/dockerd.log &
        sleep 5
      fi
      docker ps &>/dev/null && echo "[OK] Docker daemon running (DinD)" || echo "[ERROR] dockerd failed to start — check /tmp/dockerd.log"
    else
      # DooD: socket is mounted from host, just verify connectivity
      docker ps &>/dev/null && echo "[OK] Docker daemon reachable via socket (DooD)" || echo "[WARN] Docker socket not accessible — check host Docker daemon"
    fi

    # 2 — Install mise
    if ! command -v mise &>/dev/null; then
      curl -fsSL https://mise.run | sh
      echo 'eval "$(mise activate bash)"' >> /home/coder/.bashrc
    fi
    export PATH="$HOME/.local/bin:$PATH"
    eval "$(mise activate bash 2>/dev/null || true)"

    # 3 — Install all tools from mise.toml
    cd /home/coder/project
    mise trust -a
    mise install

    # 4 — Clone the project if not present and repo URL is set
    if [ ! -d /home/coder/project/aipaas-platform ] && [ -n "${var.git_repo_url}" ]; then
      git clone ${var.git_repo_url} /home/coder/project/aipaas-platform 2>/dev/null || true
    fi

    echo "=== AIPaaS workspace ready ==="
    mise run verify
  EOT

  env = {
    GIT_REPOSITORY = var.git_repo_url
    DEBIAN_FRONTEND = "noninteractive"
  }
}

# --- Docker container (workspace) ---

resource "docker_volume" "workspace" {
  name = "coder-${data.coder_workspace_owner.me.name}-${data.coder_workspace.me.name}-home"
}

resource "docker_container" "workspace" {
  count = data.coder_workspace.me.start_count
  name  = "coder-${data.coder_workspace_owner.me.name}-${data.coder_workspace.me.name}"
  image = var.docker_image

  # Privileged mode only for DinD (daemon runs inside the container)
  privileged = var.docker_mode == "dind"

  # Host DNS for Docker socket
  host {
    host = "host.docker.internal"
    ip   = "host-gateway"
  }

  # DooD: mount host Docker socket so the workspace can use the host daemon
  # DinD: no socket mount — dockerd runs inside the container (privileged)
  dynamic "volumes" {
    for_each = var.docker_mode == "dood" ? [1] : []
    content {
      container_path = "/var/run/docker.sock"
      host_path       = "/var/run/docker.sock"
    }
  }

  # Persistent home
  volumes {
    container_path = "/home/coder"
    volume_name     = docker_volume.workspace.name
  }

  # Project dir — mount template root (parent of coder/) so mise.toml is accessible
  volumes {
    container_path = "/home/coder/project"
    host_path       = abspath("${path.module}/..")
  }

  env = [
    "CODER_AGENT_TOKEN=${coder_agent.main.token}",
    "DEBIAN_FRONTEND=noninteractive",
    "DOCKER_MODE=${var.docker_mode}",
  ]

  command = ["sh", "-c", coder_agent.main.init_script]

  memory     = var.memory * 1024
  cpu_shares = var.cpu_count * 1024
}

# --- Metadata ---

resource "coder_metadata" "workspace_info" {
  count       = data.coder_workspace.me.start_count
  resource_id = docker_container.workspace[0].id

  item {
    key   = "image"
    value = var.docker_image
  }
  item {
    key   = "cpu"
    value = "${var.cpu_count} cores"
  }
  item {
    key   = "memory"
    value = "${var.memory} GB"
  }
  item {
    key   = "disk"
    value = "${var.disk_size} GB"
  }
  item {
    key   = "tools"
    value = "mise-managed (terraform, terragrunt, k3d, kubectl, helm, aws-cli, python, node)"
  }
  item {
    key   = "docker"
    value = var.docker_mode == "dind" ? "DinD (privileged, isolated)" : "DooD (host socket mount)"
  }
}
