# Coder Setup — Guide d'installation et de gestion

Déploiement de [Coder](https://coder.com) (plateforme d'environnements de
développement à la demande) en conteneur Docker sur un VPS.

## Table of Contents

- [Installation](#installation)
- [Architecture des montages](#architecture-des-montages)
- [Commandes de gestion](#commandes-de-gestion)
- [Template custom (infra-template)](#template-custom-infra-template)
- [Outils gérés par mise](#outils-gérés-par-mise)
- [Mode 1 — Standalone (sans Coder)](#mode-1--standalone-sans-coder)
- [Mode 2 — Via Coder (workspace distant)](#mode-2--via-coder-workspace-distant)
- [mise.toml — sections](#misetoml--sections)
- [Reproductibilité](#reproductibilité)
- [Utilisateurs et accès Docker (DooD, pas DinD)](#utilisateurs-et-accès-docker-dood-pas-dind)

---

## Installation

```bash
# Mode test : tunnel gratuit *.try.coder.app (URL aléatoire, change à chaque redémarrage)
sudo bash setup-coder.sh

# Mode prod : URL stable avec votre domaine (DNS pointé vers le VPS + reverse proxy TLS)
sudo ACCESS_URL=https://coder.mondomaine.com bash setup-coder.sh
```

Le script est idempotent : il peut être relancé sans casser l'existant
(les données sont dans le volume Docker `coder_data`).

## Architecture des montages

| Montage | Type | Rôle |
|---|---|---|
| `coder_data:/home/coder/.config` | Volume géré par Docker | Config Coder + base PostgreSQL intégrée (persiste même si le conteneur est supprimé) |
| `/var/run/docker.sock:/var/run/docker.sock` | Bind mount | Permet à Coder de créer les conteneurs de workspaces sur l'hôte |

## Commandes de gestion

### Récupérer le lien d'accès (mode tunnel)

```bash
docker logs coder 2>&1 | grep -oE 'https://[a-z0-9.-]+\.try\.coder\.app' | tail -1
```

`tail -1` = l'URL la plus récente (elle change à chaque redémarrage du conteneur).

### Premier compte / utilisateurs

- Le **premier compte se crée dans l'UI web** : la première personne qui ouvre
  le lien devient **admin** (aucun identifiant par défaut). À faire rapidement
  après l'installation !
- Gestion des utilisateurs ensuite : **Deployment → Users** dans l'UI.

### CLI Coder (via docker exec)

```bash
docker exec coder coder login <URL>          # S'authentifier à la CLI
docker exec coder coder users list           # Lister les utilisateurs
docker exec coder coder templates list       # Lister les templates
docker exec coder coder list                 # Lister les workspaces
```

### Mise à jour de Coder

```bash
docker pull ghcr.io/coder/coder:latest       # Récupérer la nouvelle image
docker rm -f coder                           # Supprimer le conteneur (les données restent dans le volume)
sudo bash setup-coder.sh                     # Relancer le script
```

### Sauvegarde / inspection des données

```bash
docker volume inspect coder_data             # Localisation du volume sur l'hôte

# Backup du volume dans une archive tar :
docker run --rm -v coder_data:/data -v $(pwd):/backup alpine \
  tar czf /backup/coder-backup.tar.gz -C /data .
```

---

## Template custom (infra-template)

Le dossier `coder-env/infra-template/` contient un template Coder prêt à l'emploi
pour la plateforme AIPaaS. Il installe tous les outils nécessaires via **mise**
(gestionnaire de versions) + Docker.

### Structure

```
coder-env/infra-template/
├── mise.toml               # Source de vérité partagée (versions des outils)
├── standalone/             # Mode 1 : sans Coder (machine locale)
│   ├── install.sh          #   → installe mise, lit ../mise.toml, installe tout
│   └── install-docker.sh   #   → installe Docker si manquant
└── coder/                  # Mode 2 : via Coder (workspace distant)
    ├── main.tf             #   → coder_agent + docker_container
    └── variables.tf        #   → variables Coder (image, cpu, memory, git_repo)
```

**`mise.toml` est au centre** : les deux modes le lisent, les outils installés sont identiques.

### Publier le template (via la CLI dans le conteneur)

```bash
# 1. Copier le template dans le conteneur Coder
docker cp coder-env/infra-template coder:/tmp/aipaas-infra

# 2. Se connecter à la CLI (ouvre une URL de session à coller)
docker exec -it coder coder login http://localhost:7080

# 3. Pousser le template
docker exec -it coder coder templates push aipaas-infra -d /tmp/aipaas-infra
```

Alternative sans CLI : UI **Templates → New template**, et coller le contenu
de `main.tf` + le Dockerfile dans l'éditeur web.

### Itérer sur le template

```bash
# Après modification de main.tf ou du Dockerfile :
docker cp coder-env/infra-template coder:/tmp/aipaas-infra
docker exec -it coder coder templates push aipaas-infra -d /tmp/aipaas-infra
# Les workspaces existants proposent alors une mise à jour ("Update")
```

---

## Outils gérés par mise

| Outil | Version | Rôle |
|-------|---------|------|
| `terraform` | latest | Infrastructure as Code |
| `terragrunt` | latest | Wrapper Terraform (DRY, backend) |
| `k3d` | latest | Cluster Kubernetes local (Docker) |
| `kubectl` | latest | Client Kubernetes |
| `helm` | latest | Package manager K8s (ArgoCD, KEDA...) |
| `k9s` | latest | TUI Kubernetes |
| `aws-cli` | latest | AWS CLI (Bedrock, SQS, Step Functions) |
| `jq` | latest | JSON processing |
| `yq` | latest | YAML processing |
| `python` | 3.12 | Agents AWS Strands |
| `node` | 22 | Tooling JS (Backstage, etc.) |

Docker (Engine ou Desktop) est installé séparément car c'est un composant système.

---

## Mode 1 — Standalone (sans Coder)

Sur ta machine locale. Aucune dépendance Coder nécessaire.

```bash
cd coder-env/infra-template/standalone/
chmod +x install.sh install-docker.sh
./install.sh
```

Le script :
1. Installe **mise** (si absent)
2. Lit `../mise.toml` et installe tous les outils
3. Vérifie / installe **Docker**

Après installation :

```bash
# Recharger le shell
exec $SHELL

# Depuis la racine du template (là où mise.toml se trouve)
cd coder-env/infra-template
mise run verify        # vérifier les versions
mise run cluster-up    # créer le cluster k3d
mise run kubectl       # voir les nodes
mise run cluster-down  # détruire le cluster
```

---

## Mode 2 — Via Coder (workspace distant)

Pour un workspace distant provisionné par Coder.

```bash
# Pousser le template sur ton instance Coder
coder templates push aipaas-infra -d coder-env/infra-template/coder/

# Créer un workspace
coder create my-aipaas --template aipaas-infra

# Se connecter au workspace
coder ssh my-aipaas
```

Au démarrage du workspace, le `startup_script` du `coder_agent` :
1. Installe Docker dans le conteneur (socket de l'hôte monté)
2. Installe mise
3. Lit le `mise.toml` (monté via volume) et installe les outils
4. Clone le repo du projet si `git_repo_url` est défini

Le Docker socket de l'hôte est monté → k3d peut créer des conteneurs réels.

---

## mise.toml — sections

- **`[tools]`** : versions des outils. Changer `latest` en une version spécifique pour figer (ex: `terraform = "1.16.0"`).
- **`[env]`** : variables d'environnement injectées automatiquement quand tu `cd` dans ce dossier.
- **`[tasks.*]`** : raccourcis `mise run <task>` pour les commandes fréquentes.

---

## Reproductibilité

Pour figer les versions exactes (recommandé en production) :

```bash
cd coder-env/infra-template
mise lock    # génère mise.lock avec les versions exactes résolues
```

Le fichier `mise.lock` peut être commité pour garantir que tout le monde utilise les mêmes versions.

---

## Utilisateurs et accès Docker (DooD, pas DinD)

- Le conteneur Coder tourne avec l'utilisateur **`coder` (UID/GID 1000)**,
  pas root.
- Coder ne fait **pas de Docker-in-Docker (DinD)** : il n'y a pas de daemon
  Docker à l'intérieur du conteneur. On monte le **socket du daemon de
  l'hôte** (`/var/run/docker.sock`) : c'est du **Docker-out-of-Docker (DooD)**.
- Les workspaces créés par Coder sont donc des **conteneurs frères**
  (siblings) qui tournent directement sur l'hôte, au même niveau que le
  conteneur Coder lui-même.
- L'option `--group-add <GID du groupe docker de l'hôte>` donne à
  l'utilisateur `coder` le droit d'écrire sur le socket.
- **Sécurité** : l'accès au socket Docker équivaut à un accès root sur
  l'hôte. Ne montez ce socket que dans des conteneurs de confiance.
