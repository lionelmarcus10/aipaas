# apps/

Manifests applicatifs déployés **via GitOps** (ArgoCD surveille ce dossier).

## Structure

```
apps/
├── test-nginx/        # App de test — valide la boucle GitOps (Sprint 1)
├── vllm/              # Déploiement vLLM CPU (Sprint 4)
├── keda/              # ScaledObject + trigger SQS (Sprint 4)
└── observability/     # Grafana, Langfuse, OpenCost (Sprint 5)
```

## App-of-Apps

Chaque sous-dossier est référencé par une `Application` ArgoCD déclarée dans le module `infra/module/argocd-config/`. La configuration Terragrunt (`infra/live/003_argocd_config/terragrunt.hcl`) liste les apps à synchroniser.

## Règle

Tout ce qui est ici doit être appliqué **uniquement** par ArgoCD.
Ne jamais faire de `kubectl apply` manuel sur ces ressources.
