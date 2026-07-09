# AIPaaS — Notes de projet

## Branche active

- **Branche de travail :** `sprint-1-and-2`
- **Branche stable :** `master`
- **Remote :** `https://github.com/lionelmarcus10/aipaas`

## Commandes utiles

```bash
# k3d — recréer le cluster from scratch
cd infra/live/001_k3d_init_cluster && rm -f terraform.tfstate* && rm -rf .terragrunt-cache && terragrunt apply -auto-approve
cd ../002_k3d_argocd_install && rm -rf .terragrunt-cache && terragrunt apply -auto-approve
cd ../003_k3d_argocd_config && rm -rf .terragrunt-cache && terragrunt apply -auto-approve

# Build + push image agent
docker build -t aipaas-registry:5000/insurance-claims-agent:latest -f agents/insurance-claims-agent/Dockerfile .
docker tag aipaas-registry:5000/insurance-claims-agent:latest localhost:5001/insurance-claims-agent:latest
docker push localhost:5001/insurance-claims-agent:latest

# Floci — tester AgentCore
source /root/projects/floci-test/env.floci
cd infra/live/010_aws_insurance_agentcore && rm -rf .terragrunt-cache && terragrunt apply -auto-approve

# Tests agent A2 (depuis le pod)
kubectl exec -n insurance-claims-agent deploy/insurance-claims-agent -- python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/health').read())"
```

## Modifications temporaires sur la branche (à remettre sur master)

| Fichier | Modification | Statut |
|---------|-------------|--------|
| `infra/live/terragrunt.hcl` ligne 92 | `git_branch = "sprint-1-and-2"` | Revertu sur `master` par l'utilisateur |
| `apps/insurance-claims-agent/application.yaml` | `targetRevision: sprint-1-and-2` | Revertu sur `master` par l'utilisateur |
| `apps/insurance-claims-agent/eks/application.yaml` | `targetRevision: sprint-1-and-2` | Revertu sur `master` par l'utilisateur |
| `infra/live/003_k3d_argocd_config/terragrunt.hcl` ligne 17 | Ajout `"financial-dispute-agent", "insurance-claims-agent"` dans `target_namespaces` | À garder (nécessaire pour A2) |

## Architecture des agents

### B1+B2 — Financial Dispute Resolution (déterministe)

- **Pattern :** Step Functions + 12 Lambda (workflow ASL codé en dur)
- **IaC :** `infra/module/agents-sfn/` + `infra/live/006_aws_agents_sfn/`
- **k3d :** `apps/financial-dispute-agent/` (gVisor + PVC + FAISS + vLLM)
- **EKS :** `apps/financial-dispute-agent/eks/` (Bedrock + S3 Vectors + ECR)
- **Floci :** Testé via `terragrunt apply` (87 resources: 12 Lambda + 1 SFN + IAM)
- **RAG :** S3 Vectors (contract-chunks, 33635 chunks indexés)

### A2 — Insurance Claims Triage (autonome ReAct)

- **Pattern :** Strands SDK + 8 tools (l'agent décide quels tools appeler)
- **IaC :** `infra/module/agents-agentcore/` + `infra/live/010_aws_insurance_agentcore/`
- **k3d :** `apps/insurance-claims-agent/` (gVisor + PVC + FAISS + vLLM)
- **EKS :** `apps/insurance-claims-agent/eks/` (Bedrock + S3 Vectors + ECR)
- **Floci :** Testé via `terragrunt apply` (7 resources: runtime + endpoint + IAM + S3 Vectors)
- **RAG :** FAISS (k3d, 60 vectors 384d) / S3 Vectors (AWS, policy-chunks)
- **Data :** Kaggle vehicle fraud (15,420 claims) + Faker (20 policies, 50 claims)
- **Décisions :** FAST_TRACK_APPROVE, ADJUSTER_REVIEW, SIU_REFERRAL, DENY_COVERAGE, REQUEST_INFORMATION

## Tests validés

### k3d (cluster local)

| Test | Résultat | Date |
|------|----------|------|
| Cluster k3d recréé from scratch | ✅ | 2026-08-29 |
| ArgoCD installé + configuré | ✅ | 2026-08-29 |
| Image A2 buildée + poussée | ✅ | 2026-08-29 |
| Pod A2 démarré (gVisor, initContainer) | ✅ | 2026-08-29 |
| DuckDB créée (3.3 MB, Kaggle + Faker) | ✅ | 2026-08-29 |
| FAISS index buildé (60 vectors, 384d) | ✅ | 2026-08-29 |
| `/health` → 200 OK | ✅ | 2026-08-29 |
| `/stats` → 20 policies, 50 claims, 17 history, 5 fraud rules | ✅ | 2026-08-29 |
| `/triage/det CLM-0001` → FAST_TRACK_APPROVE (risk=0, payout=609.64€) | ✅ | 2026-08-29 |
| `/triage/det CLM-0003` → SIU_REFERRAL (risk=100, payout=0€) | ✅ | 2026-08-29 |
| `/triage/det CLM-0004` → DENY_COVERAGE (risk=0, payout=0€) | ✅ | 2026-08-29 |

### Floci (émulateur AWS)

| Test | Résultat | Date |
|------|----------|------|
| S3 Vectors : bucket + index créés | ✅ | 2026-08-29 |
| S3 Vectors : 30 vectors indexés (10 policies) | ✅ | 2026-08-29 |
| S3 Vectors : retrieval + metadata filter (policy_id) | ✅ | 2026-08-29 |
| AgentCore : `terragrunt apply` (7 resources) | ✅ | 2026-08-29 |
| AgentCore : runtime créé (status READY) | ✅ | 2026-08-29 |
| AgentCore : endpoint créé (name=prod) | ✅ | 2026-08-29 |
| AgentCore : `InvokeAgentRuntime` → 200, `{"output":"yes"}` | ✅ | 2026-08-29 |

### Limitations Floci

- `InvokeAgentRuntime` retourne une canned response (`{"output":"yes"}`) — le payload n'est pas traité
- `ListTagsForResource` non supporté sur les endpoints AgentCore → tags retirés du module
- Pas de data source `aws_s3vectors_vector_bucket` dans le provider AWS → ConflictException si le bucket existe déjà

## Ce qui reste à faire

### Sprint 4 (KEDA + vLLM)

- [ ] KEDA Scale-to-Zero avec SQS trigger
- [ ] vLLM validation et collecte de métriques
- [ ] KEDA ScaledObject sur le pod A2 (scale based on SQS queue depth)

### Sprint 5 (Observabilité + Résilience)

- [ ] Scénarios de panne (Cold Start, Circuit Breaker, Canary Rollback)
- [ ] Pipeline Continuous Training (DVC + Pandera + Argo Workflows + LoRA + Ragas + MLflow + Evidently)
- [ ] Langfuse tracing sur les appels LLM de A2
- [ ] Prometheus metrics sur l'API A2 (latence triage, risk score distribution)

### Sprint 6 (Finalisation)

- [ ] README finalisé
- [ ] Vidéo de démo
- [ ] Articles techniques

## Points d'attention pour la présentation

1. **Deux patterns d'agents** : B1+B2 (déterministe, Step Functions) vs A2 (autonome, ReAct/Strands). Comparer les deux approches.
2. **3 environnements** : k3d (dev), EKS (prod), AgentCore (serverless agents). Le même code agent tourne partout via env vars.
3. **RAG provider abstraction** : FAISS (local) vs S3 Vectors (AWS). Même interface, backends différents.
4. **gVisor + PSS restricted** : sécurité maximum sur k3d (syscall isolation + non-root + readOnlyRootFilesystem).
5. **Floci** : émulateur AWS pour tester l'IaC Terraform sans compte AWS. Limitations connues (canned responses, pas de tagging AgentCore).
6. **Kaggle dataset** : 15,420 sinistres réels (vehicle fraud detection) intégrés dans DuckDB. Pas seulement du Faker.
