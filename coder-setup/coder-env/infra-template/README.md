---
display_name: "AIPaaS Infra Environment"
description: "Workspace avec terraform, terragrunt, k3d, kubectl, helm, aws-cli — gérés par mise"
icon: "📦"
verified: false
tags: ["docker", "kubernetes", "terraform", "k3d", "mise", "aipaas"]
---

# infra-template

Template d'environnement pour la plateforme AIPaaS.
Installe tous les outils nécessaires via **mise** (gestionnaire de versions) + Docker.

## Structure

```
coder-env/infra-template/
├── mise.toml               # Source de vérité partagée (versions des outils)
├── README.md               # Ce fichier
├── standalone/             # Mode 1 : sans Coder (machine locale)
│   ├── install.sh          #   → installe mise, lit ../mise.toml, installe tout
│   └── install-docker.sh   #   → installe Docker si manquant
└── coder/                  # Mode 2 : via Coder (workspace distant)
    ├── main.tf             #   → coder_agent + docker_container
    └── variables.tf        #   → variables Coder (image, cpu, memory, git_repo)
```

**`mise.toml` est au centre** : les deux modes le lisent, les outils installés sont identiques.

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
cd standalone/
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
mise run verify        # vérifier les versions
mise run cluster-up    # créer le cluster k3d
mise run kubectl       # voir les nodes
mise run cluster-down  # détruire le cluster
```

---

## Mode 2 — Via Coder

Pour un workspace distant provisionné par Coder.

```bash
# Pousser le template sur ton instance Coder
coder templates push aipaas-infra -d coder/

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

## Reproductibilité

Pour figer les versions exactes (recommandé en production) :

```bash
mise lock    # génère mise.lock avec les versions exactes résolues
```

Le fichier `mise.lock` peut être commité pour garantir que tout le monde utilise les mêmes versions.
