# AIPaaS — AI Platform-as-a-Service

> Internal Developer Platform (IDP) pour déployer et opérer des agents IA en production.


## Angle du projet
Prouver la maîtrise simultanée de deux mondes : servir un LLM (IA) avec de
l'autoscaling événementiel et du contrôle de coûts (Infra / FinOps).

## Stack (cœur)
| Domaine | Techno |
|---|---|
| GitOps | ArgoCD |
| Cluster | Kubernetes (k3d local) & AWS EKS ( prod ) |
| Inférence | vLLM (CPU) |
| Autoscaling | KEDA (Scale-to-Zero via SQS) |
| Agents | AWS Strands SDK + Amazon Bedrock |
| Orchestration | Bedrock Agent Runtime (Cas A) + Step Functions (Cas B) |
| Observabilité | Grafana + Langfuse + OpenCost |

## Structure du repo
```
aipaas-platform/
├── infra/        # Terraform + manifests cluster (k3d, ArgoCD)
├── apps/         # Manifests applicatifs déployés via GitOps
├── agents/       # Code Python des agents AWS Strands
├── docs/         # Architecture, métriques, périmètre CŒUR/BONUS
```