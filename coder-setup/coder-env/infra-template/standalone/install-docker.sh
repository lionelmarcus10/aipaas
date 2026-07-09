#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# install-docker.sh — Docker Desktop / Docker Engine installer
# Used by the AIPaaS infra template (codeur/setup/infra-template)
# ============================================================

OS="$(uname -s)"
ARCH="$(uname -m)"

echo "=========================================="
echo "  Docker Installer — AIPaaS Platform"
echo "  OS: ${OS} / ARCH: ${ARCH}"
echo "=========================================="

if command -v docker &>/dev/null; then
  echo "[OK] Docker already installed: $(docker --version)"
  docker info &>/dev/null && echo "[OK] Docker daemon is running." || echo "[WARN] Docker daemon is NOT running — start Docker Desktop or: sudo systemctl start docker"
  exit 0
fi

case "${OS}" in
  Linux)
    echo "[INFO] Installing Docker Engine on Linux..."
    if command -v dnf &>/dev/null; then
      # RHEL / CentOS / Fedora / Rocky / Alma
      sudo dnf install -y dnf-plugins-core
      sudo dnf config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
      sudo dnf install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    elif command -v apt &>/dev/null; then
      # Debian / Ubuntu
      sudo apt-get update
      sudo apt-get install -y ca-certificates curl gnupg
      sudo install -m 0755 -d /etc/apt/keyrings
      curl -fsSL https://download.docker.com/linux/$(. /etc/os-release; echo "$ID")/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
      sudo chmod a+r /etc/apt/keyrings/docker.gpg
      echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/$(. /etc/os-release; echo "$ID") $(. /etc/os-release; echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list
      sudo apt-get update
      sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    else
      echo "[ERROR] Unsupported Linux package manager. Install Docker manually: https://docs.docker.com/engine/install/"
      exit 1
    fi
    sudo systemctl enable --now docker
    sudo usermod -aG docker "$USER" 2>/dev/null || true
    echo "[OK] Docker Engine installed and started."
    echo "[HINT] You may need to log out/in for the docker group to take effect, or use: newgrp docker"
    ;;

  Darwin)
    echo "[INFO] Installing Docker Desktop on macOS..."
    if command -v brew &>/dev/null; then
      brew install --cask docker
      echo "[OK] Docker Desktop installed via Homebrew."
      echo "[HINT] Launch Docker Desktop from Applications, then wait for the whale icon in the menu bar."
    else
      ARCH_SUFFIX="amd64"
      [[ "${ARCH}" == "arm64" ]] && ARCH_SUFFIX="arm64"
      echo "[INFO] Downloading Docker Desktop for macOS (${ARCH_SUFFIX})..."
      curl -L "https://desktop.docker.com/mac/main/${ARCH_SUFFIX}/Docker.dmg" -o /tmp/Docker.dmg
      hdiutil attach /tmp/Docker.dmg
      cp -R /Volumes/Docker/Docker.app /Applications/
      hdiutil detach /Volumes/Docker
      rm /tmp/Docker.dmg
      echo "[OK] Docker Desktop copied to /Applications."
      echo "[HINT] Launch Docker Desktop from Applications."
    fi
    ;;

  *)
    echo "[ERROR] Unsupported OS: ${OS}"
    echo "Install Docker manually: https://docs.docker.com/get-docker/"
    exit 1
    ;;
esac

echo ""
echo "=========================================="
echo "  Docker installation complete!"
echo "=========================================="
docker --version 2>/dev/null || echo "[WARN] Docker not yet in PATH — restart your shell or start Docker Desktop."
