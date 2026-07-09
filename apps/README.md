# apps/

Manifests applicatifs déployés **via GitOps** (ArgoCD surveille ce dossier).

## Contenu prévu
- `vllm/` — déploiement vLLM CPU (Sprint 4)
- `keda/` — ScaledObject + trigger SQS (Sprint 4)
- `observability/` — Grafana, Langfuse, OpenCost (Sprint 5)

## Règle
Tout ce qui est ici doit être appliqué **uniquement** par ArgoCD.
Ne jamais faire de `kubectl apply` manuel sur ces ressources.
