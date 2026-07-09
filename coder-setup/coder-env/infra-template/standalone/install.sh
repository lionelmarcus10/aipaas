#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# install.sh — Bootstrap script for AIPaaS infra template
#
#  1. Installs mise (dev tool manager)
#  2. mise reads mise.toml and installs ALL tools:
#     terraform, terragrunt, k3d, kubectl, helm, k9s, etc.
#  3. Checks Docker is available (installs if missing)
#
#  After this script, your environment is ready to run:
#     mise run cluster-up    (creates the k3d cluster)
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
OS="$(uname -s)"
ARCH="$(uname -m)"

echo "=========================================="
echo "  AIPaaS — Environment Setup"
echo "  OS: ${OS} / ARCH: ${ARCH}"
echo "  Dir: ${SCRIPT_DIR}"
echo "=========================================="
echo ""

# ------------------------------------------
# Step 1 — Install mise
# ------------------------------------------
echo "[1/3] Installing mise..."

if command -v mise &>/dev/null; then
  echo "  [OK] mise already installed: $(mise --version)"
else
  case "${OS}" in
    Linux)
      # Universal installer from mise.run
      curl -fsSL https://mise.run | sh
      export MISE_INSTALL_PATH="${HOME}/.local/bin/mise"
      ;;
    Darwin)
      if command -v brew &>/dev/null; then
        brew install mise
      else
        curl -fsSL https://mise.run | sh
      fi
      ;;
    *)
      echo "  [ERROR] Unsupported OS: ${OS}"
      exit 1
      ;;
  esac
fi

# Activate mise in current shell
eval "$(mise activate bash 2>/dev/null || true)"

# Add mise activation to shell rc if not already present
SHELL_RC="${HOME}/.bashrc"
[[ "$(echo $SHELL)" == *zsh* ]] && SHELL_RC="${HOME}/.zshrc"

if ! grep -q 'mise activate' "${SHELL_RC}" 2>/dev/null; then
  echo 'eval "$(mise activate bash)"' >> "${SHELL_RC}"
  echo "  [OK] Added mise activation to ${SHELL_RC}"
fi

echo "  [OK] mise is ready: $(mise --version)"
echo ""

# ------------------------------------------
# Step 2 — Install all tools via mise.toml
# ------------------------------------------
echo "[2/3] Installing tools from mise.toml..."
echo "  Tools: terraform, terragrunt, k3d, kubectl, helm, k9s,"
echo "         jq, yq, aws-cli, python, node"
echo ""

cd "${TEMPLATE_ROOT}"
mise trust
mise install

echo ""
echo "  [OK] All tools installed."
echo ""

# Show versions
echo "  --- Installed versions ---"
mise ls 2>/dev/null | grep -E 'terraform|terragrunt|k3d|kubectl|helm|k9s|jq|yq|aws-cli|python|node' || true
echo ""

# ------------------------------------------
# Step 3 — Check / install Docker
# ------------------------------------------
echo "[3/3] Checking Docker..."

if command -v docker &>/dev/null && docker info &>/dev/null 2>&1; then
  echo "  [OK] Docker is installed and running: $(docker --version)"
else
  echo "  [WARN] Docker is not available or not running."
  echo "  Running install-docker.sh..."
  bash "${SCRIPT_DIR}/install-docker.sh"
  echo ""
  echo "  [NOTE] You may need to restart your shell or start Docker Desktop"
  echo "         for the docker daemon to be accessible."
fi

echo ""
echo "=========================================="
echo "  Setup complete!"
echo "=========================================="
echo ""
echo "  Next steps:"
echo "    1. Restart your shell (or run: eval \"\$(mise activate bash)\")"
echo "    2. Verify tools:        mise run verify"
echo "    3. Create the cluster:  mise run cluster-up"
echo "    4. Check nodes:         mise run kubectl"
echo ""
echo "  Or manually:"
echo "    cd <project-root>/infra/live/001_init_cluster"
echo "    terragrunt apply"
echo ""
