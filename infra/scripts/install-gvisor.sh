#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# install-gvisor.sh — Install gVisor (runsc) + containerd-shim-runsc-v1 on the host
# ---------------------------------------------------------------------------
# gVisor provides userspace kernel isolation for Kubernetes pods. It intercepts
# syscalls from the container and handles them in userspace, isolating the
# container from the host kernel. This is critical for running untrusted code
# (e.g., AI agents that generate and execute code).
#
# Prerequisites:
#   - Linux x86_64 host
#   - Docker installed (k3d runs k3s in Docker containers)
#   - sudo access (to move binaries to /usr/local/bin/)
#
# After running this script:
#   1. Recreate the k3d cluster with enable_gvisor = true
#   2. The RuntimeClass "gvisor" will be created by the k3d-cluster Terraform module
#   3. Pods with runtimeClassName: gvisor will run under runsc isolation
#
# Usage:
#   bash infra/scripts/install-gvisor.sh          # install
#   bash infra/scripts/install-gvisor.sh --check   # verify installation only
# ---------------------------------------------------------------------------
set -euo pipefail

GVISOR_RELEASE="release/latest"
ARCH="x86_64"
INSTALL_DIR="/usr/local/bin"
BINARIES=("runsc" "containerd-shim-runsc-v1")
GVISOR_BASE_URL="https://storage.googleapis.com/gvisor/releases/${GVISOR_RELEASE}/${ARCH}"

# --- Colors ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[gVisor]${NC} $*"; }
warn() { echo -e "${YELLOW}[gVisor]${NC} $*"; }
err()  { echo -e "${RED}[gVisor]${NC} $*" >&2; }

# --- Check mode ---
if [[ "${1:-}" == "--check" ]]; then
  log "Checking gVisor installation..."
  all_ok=true
  for bin in "${BINARIES[@]}"; do
    if [[ -x "${INSTALL_DIR}/${bin}" ]]; then
      log "  ${bin}: ${GREEN}OK${NC} ($(${INSTALL_DIR}/${bin} --version 2>&1 || echo 'version unknown'))"
    else
      err "  ${bin}: ${RED}MISSING${NC}"
      all_ok=false
    fi
  done
  if $all_ok; then
    log "All gVisor binaries are installed."
    exit 0
  else
    err "gVisor is not fully installed. Run this script without --check to install."
    exit 1
  fi
fi

# --- Install mode ---
log "Installing gVisor (runsc + containerd-shim-runsc-v1)..."

# Check architecture
HOST_ARCH=$(uname -m)
if [[ "$HOST_ARCH" != "x86_64" ]]; then
  err "Unsupported architecture: ${HOST_ARCH}. gVisor runsc only supports x86_64."
  exit 1
fi

# Check if already installed
already_installed=true
for bin in "${BINARIES[@]}"; do
  if [[ ! -x "${INSTALL_DIR}/${bin}" ]]; then
    already_installed=false
    break
  fi
done

if $already_installed; then
  log "gVisor binaries already present in ${INSTALL_DIR}/. Use --check to verify."
  log "To reinstall, remove them first: sudo rm ${INSTALL_DIR}/runsc ${INSTALL_DIR}/containerd-shim-runsc-v1"
  exit 0
fi

# Download binaries to a temp directory
TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT

log "Downloading gVisor binaries from ${GVISOR_BASE_URL}..."
for bin in "${BINARIES[@]}"; do
  log "  Downloading ${bin}..."
  curl -fsSL "${GVISOR_BASE_URL}/${bin}" -o "${TMP_DIR}/${bin}"
  chmod +x "${TMP_DIR}/${bin}"
done

# Move to /usr/local/bin (requires sudo)
log "Installing binaries to ${INSTALL_DIR}/ (requires sudo)..."
if [[ $EUID -eq 0 ]]; then
  for bin in "${BINARIES[@]}"; do
    mv "${TMP_DIR}/${bin}" "${INSTALL_DIR}/${bin}"
  done
else
  for bin in "${BINARIES[@]}"; do
    sudo mv "${TMP_DIR}/${bin}" "${INSTALL_DIR}/${bin}"
  done
fi

# Verify installation
log "Verifying installation..."
for bin in "${BINARIES[@]}"; do
  if [[ -x "${INSTALL_DIR}/${bin}" ]]; then
    log "  ${bin}: ${GREEN}OK${NC}"
  else
    err "  ${bin}: ${RED}FAILED${NC}"
    exit 1
  fi
done

log ""
log "gVisor installed successfully!"
log ""
log "Next steps:"
log "  1. Recreate the k3d cluster with gVisor enabled:"
log "     cd infra/live/001_k3d_init_cluster"
log "     terragrunt destroy -auto-approve  # destroy existing cluster"
log "     terragrunt apply -auto-approve    # recreate with gVisor mounts"
log ""
log "  2. Verify the RuntimeClass exists:"
log "     kubectl get runtimeclass gvisor"
log ""
log "  3. Deploy a test pod with gVisor:"
log "     kubectl run gvisor-test --image=alpine --runtime-class=gvisor --rm -it -- sh"
