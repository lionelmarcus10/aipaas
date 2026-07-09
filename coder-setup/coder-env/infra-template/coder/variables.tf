variable "git_repo_url" {
  description = "Git repository URL to clone into the workspace"
  type        = string
  default     = "https://github.com/your-username/aipaas-platform.git"
}

variable "docker_image" {
  description = "Base image for the workspace"
  type        = string
  default     = "ubuntu:24.04"
}

variable "docker_mode" {
  description = "Docker mode: 'dood' (socket mount from host) or 'dind' (privileged, daemon inside container)"
  type        = string
  default     = "dood"

  validation {
    condition     = contains(["dood", "dind"], var.docker_mode)
    error_message = "docker_mode must be 'dood' or 'dind'."
  }
}

variable "cpu_count" {
  description = "CPU cores allocated to the workspace"
  type        = number
  default     = 4
}

variable "memory" {
  description = "Memory allocated to the workspace (GB)"
  type        = number
  default     = 8
}

variable "disk_size" {
  description = "Disk size in GB"
  type        = number
  default     = 20
}
