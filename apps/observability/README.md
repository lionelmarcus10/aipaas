# apps/observability/

Stack d'observabilité déployée via GitOps.

## Contenu prévu (Sprint 5)

- `kube-prometheus-stack.yaml` — Grafana + Prometheus + AlertManager
- `langfuse.yaml` — Traces LLM (self-hosted)
- `opencost.yaml` — FinOps / coûts cluster

## Dashboards

- Grafana : métriques cluster (CPU, RAM, pods, network)
- Langfuse : traces des appels LLM (latence, tokens, coût par invocation)
- OpenCost : coût total cluster, coût par namespace, coût au repos
