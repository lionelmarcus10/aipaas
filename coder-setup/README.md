# Coder Setup — Guide d'installation et de gestion

Déploiement de [Coder](https://coder.com) (plateforme d'environnements de
développement à la demande) en conteneur Docker sur un VPS.

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

## Template custom : votre stack (Terraform / Terragrunt / Helm / Next.js)

Le dossier `template/` contient un template Coder prêt à l'emploi :

- `template/build/Dockerfile` : image de workspace avec Terraform, Terragrunt,
  Helm, kubectl, Node.js 22 + pnpm préinstallés
- `template/main.tf` : le template Terraform (agent Coder, code-server,
  volume home persistant, clone auto du repo passé en paramètre)

### Publier le template (via la CLI dans le conteneur)

```bash
# 1. Copier le template dans le conteneur Coder
docker cp template coder:/tmp/ma-stack

# 2. Se connecter à la CLI (ouvre une URL de session à coller)
docker exec -it coder coder login http://localhost:7080

# 3. Pousser le template
docker exec -it coder coder templates push ma-stack -d /tmp/ma-stack
```

Alternative sans CLI : UI **Templates → New template**, et coller le contenu
de `main.tf` + `build/Dockerfile` dans l'éditeur web.

### Itérer sur le template

```bash
# Après modification de main.tf ou du Dockerfile :
docker cp template coder:/tmp/ma-stack
docker exec -it coder coder templates push ma-stack -d /tmp/ma-stack
# Les workspaces existants proposent alors une mise à jour ("Update")
```

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
