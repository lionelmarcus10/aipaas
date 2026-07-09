#!/usr/bin/env bash
#
# ==============================================================================
# setup-coder.sh — Installation complète de Docker + Coder sur un VPS
# ==============================================================================
#
# Ce script reproduit le setup suivant :
#   1. Installation de Docker CE depuis le dépôt officiel (Rocky/RHEL/CentOS 9)
#   2. Démarrage et activation de Docker au boot
#   3. Déploiement de Coder (https://coder.com) en conteneur Docker :
#      - PostgreSQL intégré (données persistées dans un volume Docker)
#      - Socket Docker monté -> Coder peut provisionner des workspaces
#        Docker pour les développeurs directement sur cette machine
#      - Redémarrage automatique du conteneur
#   4. Exposition :
#      - Par défaut : tunnel gratuit *.try.coder.app (aucun port à ouvrir,
#        URL aléatoire qui CHANGE à chaque redémarrage -> pour tester)
#      - Optionnel : passer un domaine en variable d'env ACCESS_URL pour
#        une URL stable (prod), ex: ACCESS_URL=https://coder.mondomaine.com
#
# Usage :
#   sudo bash setup-coder.sh                                   # mode tunnel
#   sudo ACCESS_URL=https://coder.mondomaine.com bash setup-coder.sh  # mode prod
#
# Prérequis : Rocky Linux / RHEL / CentOS / AlmaLinux 9 (x86_64), accès root.
# Pour Debian/Ubuntu, adapter la section "Installation de Docker" (apt).
# ==============================================================================

set -euo pipefail   # Arrêt immédiat en cas d'erreur, variable non définie, ou
                    # échec dans un pipe -> évite les états à moitié installés

# ------------------------------------------------------------------------------
# Variables configurables
# ------------------------------------------------------------------------------
CODER_PORT="${CODER_PORT:-7080}"        # Port HTTP local de Coder
ACCESS_URL="${ACCESS_URL:-}"            # Vide = tunnel automatique try.coder.app
CONTAINER_NAME="coder"                  # Nom du conteneur
VOLUME_NAME="coder_data"                # Volume Docker (config + PostgreSQL)
CODER_IMAGE="ghcr.io/coder/coder:latest"

# ------------------------------------------------------------------------------
# 0. Vérifications préliminaires
# ------------------------------------------------------------------------------
if [[ $EUID -ne 0 ]]; then
  echo "ERREUR : ce script doit être exécuté en root (ou via sudo)." >&2
  exit 1
fi

echo "==> [1/5] Installation de Docker CE..."

# ------------------------------------------------------------------------------
# 1. Installation de Docker (dépôt officiel Docker pour RHEL/CentOS/Rocky)
# ------------------------------------------------------------------------------
if command -v docker &>/dev/null; then
  echo "    Docker déjà installé ($(docker --version)) — étape ignorée."
else
  # Ajout du dépôt officiel Docker (le dépôt 'centos' couvre Rocky/Alma/RHEL)
  dnf config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo

  # Installation du moteur, du CLI, de containerd et du plugin compose
  dnf install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
fi

echo "==> [2/5] Démarrage et activation de Docker au boot..."

# Active Docker maintenant ET à chaque démarrage de la machine
systemctl enable --now docker

# Vérification que le daemon répond
docker info --format '    Docker Server version : {{.ServerVersion}}'

echo "==> [3/5] Préparation du volume de données Coder..."

# ------------------------------------------------------------------------------
# 2. Volume de persistance
# ------------------------------------------------------------------------------
# Le conteneur Coder tourne avec l'utilisateur 'coder' (UID/GID 1000).
# Un volume Docker fraîchement créé appartient à root -> Coder ne pourrait
# pas écrire dedans ("mkdir permission denied"). On corrige la propriété
# du volume AVANT de lancer Coder, via un conteneur alpine jetable.
docker volume create "${VOLUME_NAME}" >/dev/null
docker run --rm -v "${VOLUME_NAME}":/data alpine chown -R 1000:1000 /data

echo "==> [4/5] Déploiement du conteneur Coder..."

# ------------------------------------------------------------------------------
# 3. Lancement de Coder
# ------------------------------------------------------------------------------
# Supprime un éventuel ancien conteneur du même nom (idempotence du script)
docker rm -f "${CONTAINER_NAME}" 2>/dev/null || true

# Récupère le GID du groupe 'docker' de l'hôte : on l'ajoute au conteneur
# pour que le process Coder ait le droit de parler au socket Docker monté.
DOCKER_GID="$(getent group docker | cut -d: -f3)"

# Construction des options d'environnement :
# - CODER_HTTP_ADDRESS : écoute sur toutes les interfaces du conteneur
# - CODER_ACCESS_URL   : si fourni -> URL stable (prod) ;
#                        si absent -> Coder ouvre un tunnel *.try.coder.app
ENV_OPTS=(-e "CODER_HTTP_ADDRESS=0.0.0.0:${CODER_PORT}")
if [[ -n "${ACCESS_URL}" ]]; then
  ENV_OPTS+=(-e "CODER_ACCESS_URL=${ACCESS_URL}")
fi

docker run -d \
  --name "${CONTAINER_NAME}" \
  --restart unless-stopped \
  -p "${CODER_PORT}:${CODER_PORT}" \
  "${ENV_OPTS[@]}" \
  --group-add "${DOCKER_GID}" \
  -v "${VOLUME_NAME}":/home/coder/.config \
  -v /var/run/docker.sock:/var/run/docker.sock \
  "${CODER_IMAGE}"

echo "==> [5/5] Attente du démarrage de Coder..."

# ------------------------------------------------------------------------------
# 4. Vérification de santé + récupération de l'URL d'accès
# ------------------------------------------------------------------------------
# On interroge /healthz jusqu'à obtenir un HTTP 200 (max ~90s)
for i in $(seq 1 30); do
  if curl -sf -o /dev/null "http://localhost:${CODER_PORT}/healthz"; then
    break
  fi
  sleep 3
done

if ! curl -sf -o /dev/null "http://localhost:${CODER_PORT}/healthz"; then
  echo "ERREUR : Coder ne répond pas. Consultez : docker logs ${CONTAINER_NAME}" >&2
  exit 1
fi

echo ""
echo "=============================================================="
echo " Coder est opérationnel !"
echo "=============================================================="

if [[ -n "${ACCESS_URL}" ]]; then
  # Mode production : URL stable fournie par l'utilisateur
  echo " URL d'accès : ${ACCESS_URL}"
  echo " (Assurez-vous que le DNS pointe vers ce serveur et qu'un"
  echo "  reverse proxy TLS relaie vers le port ${CODER_PORT}.)"
else
  # Mode tunnel : l'URL aléatoire est affichée dans les logs du conteneur,
  # on l'extrait avec grep (motif https://xxxx.try.coder.app)
  TUNNEL_URL="$(docker logs "${CONTAINER_NAME}" 2>&1 \
    | grep -oE 'https://[a-z0-9.-]+\.try\.coder\.app' | head -1)"
  echo " URL d'accès (tunnel)  : ${TUNNEL_URL:-voir 'docker logs coder'}"
  echo " URL locale            : http://localhost:${CODER_PORT}"
  echo ""
  echo " NOTE : cette URL tunnel change à chaque redémarrage du"
  echo " conteneur. Pour une URL stable, relancez ce script avec :"
  echo "   ACCESS_URL=https://coder.votredomaine.com bash $(basename "$0")"
fi

echo ""
echo " Prochaines étapes :"
echo "  1. Ouvrez l'URL et créez le compte administrateur"
echo "  2. Templates -> Starter Templates -> 'Docker Containers'"
echo "  3. Vos développeurs créent leurs workspaces à la demande"
echo "=============================================================="
