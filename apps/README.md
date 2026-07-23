# apps/

Manifests applicatifs déployés **via GitOps** (ArgoCD surveille ce dossier).

## Structure

```
apps/
├── test-nginx/        # App de test — valide la boucle GitOps (Sprint 1) ✅
├── keda/              # KEDA — Scale-to-Zero autoscaling (Sprint 4)
├── vllm/              # vLLM — LLM inference CPU k3d / GPU AWS (Sprint 4)
├── argo-rollouts/     # Argo Rollouts — Canary + rollback auto (Sprint 5)
├── grafana/           # Grafana — Dashboard unifié (Sprint 5)
├── opencost/          # OpenCost — FinOps cluster cost tracking (Sprint 5)
├── langfuse/          # Langfuse — LLM tracing & observability (Sprint 5)
└── README.md
```

## App-of-Apps

Chaque sous-dossier contient:
- `application.yaml` — ArgoCD Application CRD
- `Chart.yaml` — Helm chart dependency (upstream charts)
- `values.yaml` — Helm values (defaults k3d, overrides AWS)

La configuration Terragrunt (`infra/live/003_argocd_config/terragrunt.hcl`) liste les apps à synchroniser via le module `infra/module/argocd-config/`.

## k3d vs AWS switch

Chaque `values.yaml` a des defaults pour k3d (CPU, pas de cloud provider). Pour déployer sur AWS EKS, override via Terragrunt ou un values file séparé.

## Règle

Tout ce qui est ici doit être appliqué **uniquement** par ArgoCD.
Ne jamais faire de `kubectl apply` manuel sur ces ressources.
