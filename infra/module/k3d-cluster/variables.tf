variable "cluster_name" {
  description = "Name of the k3d cluster"
  type        = string
  default     = "aipaas"
}

variable "kubeconfig_path" {
  description = "Path to kubeconfig file (written by k3d on cluster creation)"
  type        = string
  default     = "~/.kube/config"
}

variable "servers_count" {
  description = "Number of server (control-plane) nodes"
  type        = number
  default     = 1
}

variable "agents_count" {
  description = "Number of agent (worker) nodes"
  type        = number
  default     = 2
}

variable "kubernetes_version" {
  description = "K3s version tag (without the rancher/k3s: prefix)"
  type        = string
  default     = "1.31.5-k3s1"
}

variable "api_host_port" {
  description = "Host port for the Kubernetes API server"
  type        = number
  default     = 6550
}

variable "http_port" {
  description = "Host port for HTTP ingress (loadbalancer)"
  type        = number
  default     = 8080
}

variable "https_port" {
  description = "Host port for HTTPS ingress (loadbalancer)"
  type        = number
  default     = 8443
}

variable "registry_name" {
  description = "Name of the local Docker registry to create and connect"
  type        = string
  default     = "aipaas-registry"
}

variable "registry_port" {
  description = "Host port for the local registry"
  type        = number
  default     = 5001
}

variable "servers_memory" {
  description = "Memory limit for server nodes (Docker format, e.g. 512m, 2g)"
  type        = string
  default     = null
}

variable "agents_memory" {
  description = "Memory limit for agent nodes (Docker format, e.g. 2g, 4g)"
  type        = string
  default     = null
}

variable "server_node_labels" {
  description = "Kubernetes labels to apply to server (control-plane) nodes"
  type        = map(string)
  default     = {}
}

variable "server_node_taints" {
  description = "Taints to apply to server nodes (e.g. { Addons-Services = \"true:NoSchedule\" })"
  type        = map(string)
  default     = {}
}

variable "agent_node_labels" {
  description = "Kubernetes labels to apply to agent (worker) nodes"
  type        = map(string)
  default     = {}
}

variable "extra_ports" {
  description = "Additional port mappings to expose on the loadbalancer"
  type = list(object({
    host_port      = number
    container_port = number
    protocol       = optional(string, "tcp")
  }))
  default = []
}

# --- gVisor (runsc) sandboxing ---
# When enabled, mounts the runsc binary + containerd-shim-runsc-v1 into all
# k3d nodes, patches the containerd config to register runsc as a runtime,
# and creates a RuntimeClass "gvisor" so pods can opt into syscall isolation.
#
# Prerequisites: run infra/scripts/install-gvisor.sh on the host first.
variable "enable_gvisor" {
  description = "Enable gVisor (runsc) runtime isolation. Requires runsc + containerd-shim-runsc-v1 installed on the host (see infra/scripts/install-gvisor.sh)."
  type        = bool
  default     = false
}

variable "gvisor_runsc_path" {
  description = "Host path to the runsc binary (installed by infra/scripts/install-gvisor.sh)"
  type        = string
  default     = "/usr/local/bin/runsc"
}

variable "gvisor_shim_path" {
  description = "Host path to the containerd-shim-runsc-v1 binary (installed by infra/scripts/install-gvisor.sh)"
  type        = string
  default     = "/usr/local/bin/containerd-shim-runsc-v1"
}

variable "gvisor_install_script_path" {
  description = "Absolute path to the install-gvisor.sh script. Passed from terragrunt.hcl because path.module points to the terragrunt cache."
  type        = string
  default     = ""
}
