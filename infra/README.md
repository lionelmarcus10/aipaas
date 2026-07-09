# infra/

Infrastructure as Code et bootstrap du cluster k3d + ArgoCD.

## Structure
```
infra/
├── module/                       # Modules Terraform réutilisables
│   ├── k3d-cluster/              # Cluster k3d + labels/taints sur les nodes
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   ├── outputs.tf
│   │   └── versions.tf
│   ├── argocd-install/           # Install ArgoCD via Helm (wait=true)
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   ├── outputs.tf
│   │   └── versions.tf
│   └── argocd-config/            # Config ArgoCD (repo, project, apps) via provider oboukili/argocd
│       ├── main.tf
│       ├── variables.tf
│       ├── outputs.tf
│       └── versions.tf
└── live/                         # Configurations live gérées par Terragrunt
    ├── terragrunt.hcl            # Config racine (backend local)
    ├── 001_init_cluster/         # S1 : cluster k3d + registry locale + labels/taints
    │   └── terragrunt.hcl
    ├── 002_argocd_install/       # S1 : install ArgoCD via Helm
    │   └── terragrunt.hcl
    └── 003_argocd_config/        # S1 : config ArgoCD (repo, project, apps)
        └── terragrunt.hcl
```

## Providers

| Provider | Version | Usage |
|----------|---------|-------|
| [moio/k3d](https://registry.terraform.io/providers/moio/k3d/latest) | 0.0.12 | Création du cluster k3d |
| [gavinbunney/kubectl](https://registry.terraform.io/providers/gavinbunney/kubectl/latest) | ~> 1.14 | Labels & taints sur les nodes (server-side apply) |
| [hashicorp/kubernetes](https://registry.terraform.io/providers/hashicorp/kubernetes/latest) | ~> 2.27 | Namespace ArgoCD |
| [hashicorp/helm](https://registry.terraform.io/providers/hashicorp/helm/latest) | ~> 2.13 | Déploiement ArgoCD via Helm chart |
| [hashicorp/local](https://registry.terraform.io/providers/hashicorp/local/latest) | ~> 2.9 | Ephemeral resource pour récupérer le password ArgoCD |
| [oboukili/argocd](https://registry.terraform.io/providers/oboukili/argocd/latest) | 6.2.0 | Configuration ArgoCD (repo, project, apps) |

## Gestion du password ArgoCD

ArgoCD génère automatiquement son mot de passe admin au moment de l'installation
et le stocke dans le secret Kubernetes `argocd-initial-admin-secret`.

Le module `argocd-config` récupère ce password au runtime via une
**ephemeral resource** `local_command` qui exécute `kubectl get secret` :
- Le password **n'est jamais stocké** dans le tfstate ni dans les plan files
- Le password **n'est jamais saisi manuellement** dans les live configs
- L'ephemeral resource attend également que le pod `argocd-server` soit `Ready`
  avant de tenter de récupérer le secret

## Ordre de mise en place (S1)

```bash
# 001 — Créer le cluster k3d (two-step à cause du chicken-and-egg kubectl provider)
cd live/001_init_cluster
terragrunt apply -target k3d_cluster.this
terragrunt apply

# 002 — Installer ArgoCD (wait=true, bloquant jusqu'à ce que les pods soient prêts)
cd ../002_argocd_install
terragrunt apply

# 003 — Configurer ArgoCD (password récupéré au runtime via ephemeral, pas dans le state)
cd ../003_argocd_config
terragrunt apply
```
