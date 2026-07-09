# AIPaaS Applications

Applications deployed **via GitOps** with ArgoCD (App-of-Apps pattern).

## Table of Contents

- [How It Works](#how-it-works)
- [Apps Overview](#apps-overview)
- [test-nginx](#test-nginx)
- [vLLM](#vllm)
- [financial-dispute-agent](#financial-dispute-agent)
- [KEDA](#keda)
- [Prometheus](#prometheus)
- [Grafana](#grafana)
- [Loki](#loki)
- [Promtail](#promtail)
- [OpenCost](#opencost)
- [Langfuse](#langfuse)
- [Argo Rollouts](#argo-rollouts)
- [Kyverno](#kyverno)
- [Network Policies](#network-policies)
- [Pod Security](#pod-security)
- [Shared Storage](#shared-storage)
- [k3d vs AWS Switch](#k3d-vs-aws-switch)
- [Rules](#rules)

---

## How It Works

1. **Terraform** creates the ArgoCD project, registers Helm repos, and deploys a single parent Application pointing to `apps/`.
2. **ArgoCD** recursively scans `apps/*/application.yaml` and creates child Applications.
3. Each `application.yaml` contains **all** the config:
   - Helm repo, chart name, version, and inline values
   - Or Git path for raw manifest apps
   - Sync policy, destination namespace, etc.

```
Terraform (Terragrunt)
  └─ creates k3d cluster + installs ArgoCD + creates parent Application
       └─ Parent App scans apps/*/application.yaml
            └─ Child App "vllm"               → renders apps/vllm/deployment.yaml
            └─ Child App "keda"               → pulls Helm chart + inline values
            └─ Child App "grafana"            → pulls Helm chart + inline values
            └─ Child App "loki"               → renders apps/loki/deployment.yaml
            └─ Child App "promtail"           → renders apps/promtail/deployment.yaml
            └─ Child App "kyverno"            → pulls Helm chart from GitHub
            └─ Child App "network-policies"   → renders apps/network-policies/
            └─ Child App "pod-security"       → renders apps/pod-security/
            └─ Child App "shared-storage"     → renders apps/shared-storage/
            └─ ... (all 15 apps)
```

---

## Apps Overview

| App | Mode | Namespace | Chart | Version | ArgoCD |
|-----|------|-----------|-------|---------|--------|
| [test-nginx](#test-nginx) | Git path | default | — | — | ✅ |
| [vLLM](#vllm) | Git path | aipaas | — | — | ✅ |
| [financial-dispute-agent](#financial-dispute-agent) | Git path | financial-dispute-agent | — | — | ✅ |
| [KEDA](#keda) | Helm chart | keda-system | keda | 2.20.1 | ✅ |
| [Prometheus](#prometheus) | Helm chart | observability | prometheus | 27.0.0 | ✅ |
| [Grafana](#grafana) | Git path | monitoring | — | — | ✅ |
| [Loki](#loki) | Git path | monitoring | — | — | ✅ |
| [Promtail](#promtail) | Git path | monitoring | — | — | ✅ |
| [OpenCost](#opencost) | Helm chart | opencost | opencost | 2.5.28 | ✅ |
| [Langfuse](#langfuse) | Helm chart | observability | langfuse | 1.5.40 | ✅ |
| [Argo Rollouts](#argo-rollouts) | Helm chart | argo-rollouts | argo-rollouts | 2.41.1 | ✅ |
| [Kyverno](#kyverno) | Helm chart (GitHub) | kyverno-system | kyverno | 3.3.4 | ✅ |
| [Network Policies](#network-policies) | Git path | multiple | — | — | ✅ |
| [Pod Security](#pod-security) | Git path | multiple | — | — | ✅ |
| [Shared Storage](#shared-storage) | Git path | financial-dispute-agent | — | — | ✅ |

---

## test-nginx

Simple nginx deployment for testing ArgoCD GitOps sync.

- **Mode**: Git path (raw manifests)
- **Namespace**: `default`
- **Replicas**: 0 (scale up for testing)
- **Image**: `nginx:1.27-alpine`

---

## vllm

vLLM inference server — CPU mode for k3d.

- **Mode**: Git path (raw manifests)
- **Namespace**: `aipaas`
- **Model**: `Qwen/Qwen2.5-0.5B-Instruct` (0.5B params, ~1 GB RAM in float16)
- **Image**: `vllm/vllm-openai-cpu:latest-x86_64`
- **Context**: `--max-model-len 4096`, `--max-num-seqs 1`, `--enforce-eager`
- **Resources**: 1-4 CPU, 4-8 Gi RAM
- **Storage**: `emptyDir` for HF cache + `/dev/shm` shared memory

Small enough for CPU-only k3d. Good enough for structured JSON reasoning.
Switch to AWS GPU: change image tag, model, resources, and add GPU limits.
See `apps/vllm/values.reference.yaml` for the GPU configuration reference.

---

## financial-dispute-agent

The Financial Dispute Resolution Agent deployed as a Kubernetes pod on k3d,
with gVisor syscall isolation and Pod Security Standard: restricted.

- **Mode**: Git path (raw manifests)
- **Namespace**: `financial-dispute-agent`
- **Runtime**: gVisor (`runtimeClassName: gvisor`) — syscall isolation
- **Image**: `aipaas-registry:5000/financial-dispute-agent:rag-fix`
- **API**: FastAPI (uvicorn :8000)
- **Storage**: DuckDB PVC + RAG FAISS index on PVC + `/tmp` emptyDir

### Architecture

```
┌─────────────────────────────────────────────────────┐
│  k3d cluster "aipaas"                               │
│                                                     │
│  Namespace: financial-dispute-agent                 │
│  ┌───────────────────────────────────────────────┐  │
│  │  Pod: financial-dispute-agent                 │  │
│  │  runtimeClassName: gvisor (syscall isolation) │  │
│  │  ┌─────────────────────────────────────────┐  │  │
│  │  │  initContainer: setup-db                │  │  │
│  │  │  - Generates DuckDB if not on PVC       │  │  │
│  │  │  - Builds FAISS RAG index if not on PVC │  │  │
│  │  └─────────────────────────────────────────┘  │  │
│  │  ┌─────────────────────────────────────────┐  │  │
│  │  │  Container: orchestrator                │  │  │
│  │  │  - FastAPI (uvicorn :8000)              │  │  │
│  │  │  - run_workflow() local orchestrator    │  │  │
│  │  │  - DuckDB (read-only, on PVC)           │  │  │
│  │  │  - RAG FAISS index (on PVC)             │  │  │
│  │  │  - runAsNonRoot: true (UID 10001)       │  │  │
│  │  │  - readOnlyRootFilesystem: true         │  │  │
│  │  │  - capabilities.drop: [ALL]             │  │  │
│  │  └─────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────┘  │
│  NetworkPolicy: deny-all + explicit allow           │
└─────────────────────────────────────────────────────┘
```

### Security Layers

| Layer | Mechanism | Purpose |
|-------|-----------|---------|
| **gVisor** | `runtimeClassName: gvisor` | Userspace kernel — intercepts syscalls, isolates from host kernel |
| **Non-root** | `runAsNonRoot: true`, `runAsUser: 10001` | Pod cannot escalate to root |
| **Read-only rootfs** | `readOnlyRootFilesystem: true` | Attacker cannot modify the filesystem |
| **No capabilities** | `capabilities.drop: [ALL]` | No privileged operations (no NET_ADMIN, no SYS_ADMIN, etc.) |
| **Seccomp** | `seccompProfile: RuntimeDefault` | Filter syscalls to the default profile |
| **No privilege escalation** | `allowPrivilegeEscalation: false` | No SETUID/SETGID escalation |
| **Pod Security** | Namespace label `enforce: restricted` | K8s admission controller rejects non-compliant pods |
| **NetworkPolicy** | deny-all + explicit allow | Zero-trust networking — only allowed flows |

### Build & Deploy

```bash
# 1. Build the container image (from the repo root — aipaas/)
docker build -t localhost:5001/financial-dispute-agent:rag-fix \
  -f agents/financial-dispute-agent/Dockerfile .

# 2. Push to the k3d local registry
docker push localhost:5001/financial-dispute-agent:rag-fix

# 3. ArgoCD syncs automatically (GitOps). For dev only:
kubectl apply -f apps/financial-dispute-agent/

# 4. Test the API
kubectl port-forward -n financial-dispute-agent svc/financial-dispute-agent 8080:80
curl http://localhost:8080/health
curl -X POST http://localhost:8080/workflow \
  -H "Content-Type: application/json" \
  -d '{"invoice_id": "INV-2357"}'
```

### gVisor Prerequisites

gVisor must be installed on the host and the k3d cluster must be created with
`enable_gvisor = true`:

```bash
bash infra/scripts/install-gvisor.sh
cd infra/live/001_k3d_init_cluster
terragrunt destroy -auto-approve
terragrunt apply -auto-approve
kubectl get runtimeclass gvisor
```

### Why gVisor for this Agent?

The agent processes external data (invoices, contracts from CUAD, B2B orders from MessyOps).
gVisor is a defense-in-depth measure:

- If a future version adds PDF parsing or code execution (e.g., the A2
  Vulnerability Patcher), gVisor prevents a compromised agent from
  escaping to the host kernel.
- gVisor intercepts syscalls in userspace — the container never directly
  calls the host kernel. Stronger than namespace+cgroup isolation alone.
- gVisor doesn't require KVM, suitable for k3d (Docker-in-Docker).

### AWS Deployment (Alternative)

The same agent can be deployed on AWS as Lambda functions + Step Functions
state machine, without Kubernetes. See:

- `infra/module/agents-sfn/` — generic Terraform module
- `infra/live/006_aws_agents_sfn/` — live config for this agent
- `agents/financial-dispute-agent/lambda/` — Lambda handler wrappers
- `agents/financial-dispute-agent/README.md` — full agent documentation (RAG, workflow, tools)

The K8s deployment (this directory) is for local dev/demo on k3d.
The AWS deployment is for production (or testing via Floci).

---

## keda

KEDA (Kubernetes Event-Driven Autoscaling) for vLLM Scale-to-Zero.

- **Mode**: Helm chart (`kedacore/keda`)
- **Namespace**: `keda-system`
- **Version**: 2.20.1
- **Config**: `watchNamespace: ""` (all namespaces), debug log level

### Planned Content (Sprint 4)

- `scaled-object.yaml` — ScaledObject with `aws-sqs-queue` trigger
- `minReplicaCount: 0`, configurable `queueLength`

### Prerequisites

- KEDA installed via Helm (chart `kedacore/keda`)
- SQS queue created via Terraform
- IAM credentials for KEDA (access key + secret)

---

## prometheus

Prometheus metrics scraper + time-series database.

- **Mode**: Helm chart (`prometheus-community/prometheus`)
- **Namespace**: `observability`
- **Version**: 27.0.0
- **Resources**: 500m CPU / 512Mi RAM (server)

Scrapes metrics from all pods in the cluster. Feeds Grafana dashboards.

---

## grafana

Grafana dashboards + log exploration UI.

- **Mode**: Git path (raw manifests)
- **Namespace**: `monitoring`
- **Image**: `grafana/grafana:10.5.15`
- **Login**: `admin` / `aipaas-dev`
- **Storage**: 1Gi PVC (`local-path`)
- **Datasources**: Prometheus (metrics), Loki (logs)

Pre-configured with Loki as datasource.
Access via port-forward: `kubectl port-forward -n monitoring svc/grafana 3000:80`

---

## loki

Loki — log aggregation system (Grafana stack).

- **Mode**: Git path (raw manifests)
- **Namespace**: `monitoring` (PSA: `privileged` — Promtail needs hostPath)
- **Image**: `grafana/loki:2.9.10`
- **Storage**: 5Gi PVC (`local-path`)
- **Port**: 3100

Stores logs from all pods in the k3d cluster. Promtail (DaemonSet)
tails container stdout/stderr and pushes logs here.

Query via Grafana: Explore → Loki → LogQL
Example: `{namespace="financial-dispute-agent"} |= "workflow"`

---

## promtail

Promtail — log shipper (DaemonSet).

- **Mode**: Git path (raw manifests)
- **Namespace**: `monitoring`
- **Image**: `grafana/promtail:2.9.10`
- **DaemonSet**: runs on every node

Tails all container stdout/stderr logs from `/var/log/pods/` and pushes them to Loki.

Labels every log line with: `namespace`, `pod_name`, `container_name`, `app`.

Query in Grafana:
```
{namespace="financial-dispute-agent"}          # all agent logs
{app="financial-dispute-agent"} |= "workflow"  # filter by keyword
{app="vllm"} |= "error"                         # vLLM errors
```

---

## opencost

OpenCost — Kubernetes cost monitoring (FinOps).

- **Mode**: Helm chart (`opencost/opencost`)
- **Namespace**: `opencost`
- **Version**: 2.5.28
- **Cluster name**: `aipaas-k3d`

Tracks cost per namespace, per workload, per label. Feeds FinOps dashboards.

---

## langfuse

Langfuse — LLM observability platform.

- **Mode**: Helm chart (`langfuse/langfuse-k8s`)
- **Namespace**: `observability`
- **Version**: 1.5.40
- **Resources**: 500m CPU / 512Mi RAM

Traces LLM calls, token usage, prompts, and responses. Used for LLMOps monitoring.
Synced at 0 replicas by default — scale up for validation.

---

## argo-rollouts

Argo Rollouts — progressive delivery controller (canary, blue-green).

- **Mode**: Helm chart (`argoproj/argo-rollouts`)
- **Namespace**: `argo-rollouts`
- **Version**: 2.41.1

Enables canary deployments with automated rollback (Panne #7).
Dashboard available via port-forward: `kubectl -n argo-rollouts port-forward svc/argo-rollouts-dashboard 3100:3100`

---

## kyverno

Kyverno — Kubernetes-native policy engine (admission controller).

- **Mode**: Helm chart from GitHub (`kyverno/kyverno` repo, path `charts/kyverno`)
- **Namespace**: `kyverno-system`
- **Version**: 3.3.4
- **Admission controller**: 3 replicas, `failurePolicy: Fail` (fail-closed)
- **Background scanning**: enabled (re-audits existing resources)
- **Reports**: enabled (audit results via `kubectl get policyreports`)

### How Kyverno works

```
kubectl apply / ArgoCD sync
       ↓
API Server admission webhook
       ↓
Kyverno intercepts → evaluates ClusterPolicies
       ↓
  enforce  → mutate or reject the resource
  audit    → log violation but allow (useful for testing)
       ↓
Resource created (or rejected)
```

### Policies to write — 3 concrete ones

1. **Disallow privileged containers** (enforce) — no `securityContext.privileged: true`
2. **Require resource limits** (enforce) — every container must define `resources.limits`
3. **Restrict image registries** (enforce) — only `ghcr.io/lionelmarcus10/*`, `docker.io/library/*`, or ECR

### Kyverno policy structure

```yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: <policy-name>
spec:
  validationFailureAction: Enforce   # Enforce = block, Audit = log only
  background: true                    # Also scan existing resources
  rules:
    - name: <rule-name>
      match:
        any:
          - resources:
              kinds:
                - Pod
      validate:
        # ... your validation logic here ...
```

### Tips

- Start with `validationFailureAction: Audit` to see violations without breaking things.
- Once verified, switch to `Enforce`.
- Use `exclude` to skip system namespaces (`kube-system`, `kyverno-system`, `argocd`).
- Test with `kubectl apply --dry-run=server` before going live.

### Useful commands

```bash
kubectl get policyreports -A                                          # See all violations
kubectl logs -n kyverno-system deploy/kyverno-admission-controller    # Admission requests
kyverno apply policies/disallow-privileged.yaml --resource manifest.yaml  # Test a policy
```

---

## network-policies

Network Policies — zero-trust networking model.

- **Mode**: Git path (raw manifests)
- **Namespaces**: all workload namespaces

### Architecture

```
base/deny-all.yaml   →  Default deny ingress+egress for every namespace
allow/               →  Explicit allow rules (YOU WRITE THESE — see below)
```

### How it works

1. **`base/deny-all.yaml`** blocks ALL traffic (ingress + egress) in every namespace.
2. **`allow/*.yaml`** re-enables specific flows explicitly.
3. Anything not explicitly allowed is blocked.

This is the **zero-trust** approach: default closed, explicit open.

### Critical Kubernetes behavior

A `NetworkPolicy` only affects pods that match **at least one** NetworkPolicy in their namespace.
If a namespace has **zero** NetworkPolicy resources, all traffic is allowed (Kubernetes default).
The `deny-all` fixes this by creating a policy that matches all pods (`podSelector: {}`) with no rules.

### What you need to write — `allow/` directory

Create one file per namespace with explicit allow rules. Examples:

**DNS (every namespace needs this):**
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-dns
  namespace: langfuse
spec:
  podSelector: {}
  policyTypes:
    - Egress
  egress:
    - to:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: kube-system
          podSelector:
            matchLabels:
              k8s-app: kube-dns
      ports:
        - protocol: UDP
          port: 53
        - protocol: TCP
          port: 53
```

**langfuse → postgres:**
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-langfuse-to-postgres
  namespace: langfuse
spec:
  podSelector:
    matchLabels:
      app.kubernetes.io/name: postgres
  policyTypes:
    - Ingress
  ingress:
    - from:
        - podSelector:
            matchLabels:
              app.kubernetes.io/part-of: langfuse
      ports:
        - protocol: TCP
          port: 5432
```

### Namespaces in this project

| Namespace | Purpose | Needs egress to |
|-----------|---------|-----------------|
| `argocd` | GitOps controller | Git (HTTPS 443), cluster API |
| `argo-rollouts` | Rollout controller | Cluster API, metrics |
| `default` | Test workloads | Varies |
| `keda-system` | Event-driven scaler | Cluster API, external metrics sources |
| `langfuse` | LLM observability | postgres (5432), redis (6379), clickhouse (9000) |
| `monitoring` | Monitoring stack (Grafana, Loki, Promtail) | Metrics scrape targets, storage |
| `opencost` | Cost monitoring | Metrics, cloud pricing API |
| `aipaas` | vLLM inference | HuggingFace (HTTPS 443), S3 (if model cache) |
| `financial-dispute-agent` | Agent pod | DuckDB (local), vLLM (if using local LLM) |

### Local vs AWS

| Environment | CNI | NetworkPolicy enforcement |
|-------------|-----|--------------------------|
| **k3d/k3s** | Flannel (default) | ❌ Flannel does NOT enforce NetworkPolicy |
| **k3d + Cilium** | Cilium | ✅ Full enforcement + Hubble visibility |
| **EKS** | vpc-cni (enableNetworkPolicy=true) | ✅ Enforced (configured in Terraform) |

**For local testing**: NetworkPolicy manifests will apply without error on k3d, but Flannel will **not enforce them**. To test enforcement locally, replace Flannel with Cilium:
```bash
k3d cluster create aipaas --k3s-arg "--flannel-backend=none"
helm install cilium cilium/cilium --namespace kube-system
```

---

## pod-security

Pod Security Admission (PSA) — built-in Kubernetes admission control.

- **Mode**: Git path (raw manifests)
- **Namespaces**: all workload namespaces

Replaces the deprecated PodSecurityPolicy (PSP, removed in K8s 1.25).

### Three levels

| Level | What it blocks |
|-------|----------------|
| `privileged` | Nothing (default, insecure) |
| `baseline` | `privileged: true`, `hostPath`, `hostNetwork`, `hostPID`, `hostIPC`, host ports, `allowPrivilegeEscalation`, undocumented capabilities |
| `restricted` | Everything in `baseline` + `runAsNonRoot: true` required, `seccompProfile` required, ALL capabilities dropped, no `hostPort`, no `allowPrivilegeEscalation` |

### What this app does

Labels every workload namespace with `enforce=restricted`. Any pod that violates
the restricted profile will be **rejected by the API server** before it starts.

### System namespaces (NOT restricted)

These stay `privileged` because their components need elevated permissions:
- `kube-system` (CNI, kube-proxy, metrics-server)
- `kyverno-system` (Kyverno admission controller)
- `argocd` (ArgoCD server — needs to read cluster resources)
- `monitoring` (Promtail needs hostPath to read /var/log/pods)

### What will break

Setting `restricted` will reject pods that:
- Run as root (many images default to root — `langfuse`, `postgres`, `redis`)
- Don't set `runAsNonRoot: true`
- Don't set `seccompProfile: RuntimeDefault`
- Don't drop ALL capabilities

**Fix**: Update your deployments to include:
```yaml
spec.template.spec:
  securityContext:
    runAsNonRoot: true
    runAsUser: 10001
    fsGroup: 10001
    seccompProfile:
      type: RuntimeDefault
  containers:
    - name: ...
      securityContext:
        allowPrivilegeEscalation: false
        capabilities:
          drop: ["ALL"]
```

If an image absolutely requires root (e.g., postgres official image), either:
1. Use a distroless/non-root alternative (`postgres` offers `:alpine` with `POSTGRES_USER`)
2. Move that namespace to `baseline` instead of `restricted`
3. Use Kyverno to **mutate** the pod and add the security context automatically

---

## shared-storage

Shared Storage — DuckDB database for the Financial Dispute Agent.

- **Mode**: Git path (raw manifests)
- **Namespace**: `financial-dispute-agent`

### Architecture (k3d — local dev)

On k3d, the DuckDB database is stored on a **hostPath** volume shared by all
agent pods. Since k3d runs on a single node, all pods naturally share the
same hostPath directory.

```
k3d node (k3d-aipaas-agent-0)
└── /data/duckdb/
    └── financial_dispute.duckdb (33 MB, generated once by initContainer)
    └── rag_index.faiss + rag_index.meta (RAG index, ~51 MB)

Agent pods (N replicas)
└── initContainer: setup-db
    └── Mounts /data/duckdb (RW)
    └── Runs setup_db.py if DB doesn't exist
    └── Builds FAISS RAG index if not on PVC
└── Container: orchestrator
    └── Mounts /data/duckdb → /app/data (RO)
    └── Reads /app/data/financial_dispute.duckdb
    └── Reads /app/data/rag_index.faiss
```

### Why not NFS on k3d?

k3d nodes are Docker containers. The kernel inside these containers does not
have the `nfs` kernel module, so `mount -t nfs` fails with "Not supported".
This is a fundamental limitation of Docker-in-Docker (k3d).

### Why not PVC with RWX on k3d?

k3d's default StorageClass (`local-path`) only supports `ReadWriteOnce`
(single node). There is no RWX storage driver available on k3d without
installing additional components (Longhorn, NFS provisioner + kernel module).

### Why hostPath?

- All agent pods run on the same k3d node → hostPath is shared naturally
- No kernel module needed (unlike NFS)
- No additional infrastructure (unlike Longhorn or NFS provisioner)
- The initContainer generates the DB once; all pods read the same file
- Pod Security Standard: `privileged` (hostPath is not allowed under
  `baseline` or `restricted`)

### Architecture (EKS — production)

On EKS, replace hostPath with **EFS** (Elastic File System):

1. Create an EFS filesystem
2. Install the `aws-efs-csi-driver` Helm chart
3. Create a StorageClass with `provisioner: efs.csi.aws.com`
4. Create a PVC with `accessModes: [ReadWriteMany]`
5. Replace the hostPath volume in the deployment with the EFS PVC
6. Switch the namespace back to `pod-security.kubernetes.io/enforce: restricted`

```yaml
# EKS replacement for the hostPath volume:
volumes:
  - name: duckdb-shared
    persistentVolumeClaim:
      claimName: duckdb-data  # PVC with EFS StorageClass (RWX)
```

### How the DB is generated

The `setup_db.py` script (bundled in the Docker image at `/app/data/setup_db.py`)
is run by the initContainer on first boot:

1. Downloads CUAD v1 (510 contracts) from Zenodo
2. Downloads MessyOps (17 B2B tables, 650k rows) from Kaggle
3. Generates synthetic invoices with Faker (7 test cases + 5 per supplier)
4. Builds a single DuckDB database (9 tables, scalable)

On subsequent pod restarts, the initContainer detects the DB already exists
on the shared volume and skips the setup (instant startup).

The RAG FAISS index (33635 chunks, 510 suppliers, dim=384) is also built
by the initContainer if not already on the PVC.

---

## k3d vs AWS Switch

For vLLM, edit `apps/vllm/deployment.yaml` to switch from CPU to GPU mode.
See `apps/vllm/values.reference.yaml` for reference.

For the financial-dispute-agent, the switch is handled by Terraform:
- **k3d**: FastAPI pod with FAISS RAG (this directory)
- **AWS**: Lambda + Step Functions + S3 Vectors RAG (`infra/live/006_aws_agents_sfn/`)

---

## Rules

Everything here must be applied **only** by ArgoCD.
Never run `kubectl apply` manually on these resources
(except for dev/testing — the `Makefile` `deploy-agent` target is dev-only).

All workloads are initially configured with **zero replicas**.
Modify the Helm values or manifests for the app you want to validate, then scale back to zero.

---

## Kustomize Overlays (k3d vs EKS)

Some apps have k3d-specific settings (gVisor, `local-path` storage, `aipaas-registry:5000` image, CPU-only vLLM).
To deploy the same apps on EKS without duplicating manifests, we use **Kustomize overlays** — lightweight patches that override only the fields that change.

### How it works

```
apps/vllm/
├── deployment.yaml          ← base (k3d, CPU) — inchangé
├── kustomization.yaml       ← 3 lignes: "applique deployment.yaml"
├── application.yaml         ← ArgoCD k3d (pointe vers apps/vllm/)
└── eks/                     ← overlay EKS
    ├── kustomization.yaml   ← "hérite de ../deployment.yaml + applique patch.yaml"
    ├── patch.yaml           ← juste les champs qui changent (image GPU, resources, nodeSelector)
    └── application.yaml     ← ArgoCD EKS (pointe vers apps/vllm/eks/)
```

ArgoCD k3d scans `apps/*/application.yaml` (base).
ArgoCD EKS scans `apps/*/eks/application.yaml` (overlays) + `apps/*/application.yaml` (apps without overlay).

### Apps with EKS overlays

| App | What changes on EKS | Patch size |
|-----|---------------------|------------|
| **vllm** | Image GPU, `nvidia.com/gpu: 1`, `nodeSelector: role=gpu`, model 7B | ~40 lines |
| **financial-dispute-agent** | Image ECR, no gVisor, `RAG_PROVIDER=s3vectors`, `LLM_PROVIDER=bedrock`, `storageClassName: gp3` | ~67 lines |
| **loki** | `storageClassName: gp3` (EBS) | ~7 lines |
| **grafana** | `storageClassName: gp3` (EBS) | ~7 lines |
| **shared-storage** | EFS StorageClass + PVC RWX (replaces NFS server) | ~33 lines |

### Apps without overlay (identical on k3d and EKS)

keda, prometheus, opencost, langfuse, argo-rollouts, kyverno, network-policies, pod-security, promtail, test-nginx — these apps use Helm charts or manifests that work the same way on both clusters. No patch needed.

### Deploying on EKS

```bash
# 1. Create the EKS cluster
terragrunt apply 004_aws_vpc
terragrunt apply 005_aws_eks
aws eks update-kubeconfig --name aipaas-eks --region eu-west-3

# 2. Install ArgoCD on EKS
terragrunt apply 007_aws_argocd_install

# 3. Configure ArgoCD (App-of-Apps EKS)
terragrunt apply 008_aws_argocd_config
# → ArgoCD discovers apps/*/eks/application.yaml + apps/*/application.yaml
# → syncs all apps on EKS with the right overlays

# 4. (Optional) Karpenter manifests
terragrunt apply 009_aws_karpenter_manifests
```

### Previewing a Kustomize overlay

```bash
# See the final YAML after patch merge (without deploying)
kubectl kustomize apps/vllm/eks/
kubectl kustomize apps/financial-dispute-agent/eks/
```
