# infra/

Infrastructure as Code and k3d cluster + ArgoCD bootstrap.

## Structure
```
infra/
├── module/                       # Reusable Terraform modules
│   ├── k3d-cluster/              # k3d cluster + node labels/taints
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   ├── outputs.tf
│   │   └── versions.tf
│   ├── argocd-install/           # Install ArgoCD via Helm (wait=true)
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   ├── outputs.tf
│   │   └── versions.tf
│   ├── argocd-config/            # Configure ArgoCD (repo, project, apps) via provider oboukili/argocd
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   ├── outputs.tf
│   │   └── versions.tf
│   ├── vpc/                      # AWS VPC (NAT instance/gateway switch, shared EIP)
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   ├── outputs.tf
│   │   └── versions.tf
│   ├── vpc-peering/              # AWS VPC peering (multi-cluster networking)
│   │   ├── main.tf
│   │   ├── providers.tf
│   │   ├── variables.tf
│   │   ├── outputs.tf
│   │   └── versions.tf
│   └── eks/                      # AWS EKS cluster (managed node groups, IRSA, KMS encryption)
│       ├── main.tf
│       ├── variables.tf
│       ├── outputs.tf
│       └── versions.tf
│   └── agents-sfn/               # Generic Step Functions agents (Lambda + SFN + IAM)
│       ├── main.tf               #   terraform-aws-modules/lambda/aws + aws_sfn_state_machine
│       ├── variables.tf          #   agents map (générique, agent-agnostic)
│       ├── outputs.tf
│       └── versions.tf
└── live/                         # Live configurations managed by Terragrunt
    ├── terragrunt.hcl            # Root config (local backend, generated into each module)
    ├── 001_k3d_init_cluster/     # Step 1: k3d cluster + local registry + node labels/taints + gVisor
    │   └── terragrunt.hcl
    ├── 002_k3d_argocd_install/   # Step 2: install ArgoCD via Helm
    │   └── terragrunt.hcl
    ├── 003_k3d_argocd_config/    # Step 3: configure ArgoCD (repo, project, parent app)
    │   └── terragrunt.hcl
    ├── 004_aws_vpc/              # Step 4: AWS VPC (NAT, subnets, route tables)
    │   └── terragrunt.hcl
    ├── 005_aws_eks/              # Step 5: AWS EKS cluster (managed node groups)
    │   └── terragrunt.hcl
    └── 006_aws_agents_sfn/       # Step 6: Step Functions agents (Lambda + SFN, testable via floci)
        ├── terragrunt.hcl
        └── financial-dispute-asl.json  # ASL definition with ${lambda_arns} placeholders
```

Reusable modules under `module/` deliberately contain **no `backend` block** — the
backend is a root-module concern. The root `live/terragrunt.hcl` uses
`remote_state { generate = ... }` so Terragrunt writes `backend.tf` into each
module copy in `.terragrunt-cache` at init time.

## Providers

Terraform `>= 1.9.0` is required (cross-variable `validation` blocks in the EKS module).

| Provider | Constraint | Usage |
|----------|------------|-------|
| [moio/k3d](https://registry.terraform.io/providers/moio/k3d/latest) | 0.0.12 | k3d cluster creation (pinned exactly — pre-1.0 provider) |
| [gavinbunney/kubectl](https://registry.terraform.io/providers/gavinbunney/kubectl/latest) | ~> 1.19 | Node labels & taints (server-side apply) |
| [hashicorp/kubernetes](https://registry.terraform.io/providers/hashicorp/kubernetes/latest) | ~> 3.2 | ArgoCD namespace |
| [hashicorp/helm](https://registry.terraform.io/providers/hashicorp/helm/latest) | ~> 3.2 | ArgoCD Helm chart deployment |
| [hashicorp/local](https://registry.terraform.io/providers/hashicorp/local/latest) | ~> 2.9 | Ephemeral resource for ArgoCD password retrieval |
| [oboukili/argocd](https://registry.terraform.io/providers/oboukili/argocd/latest) | ~> 6.2 | ArgoCD configuration (repo, project, apps) |
| [hashicorp/aws](https://registry.terraform.io/providers/hashicorp/aws/latest) | ~> 6.61 | VPC, VPC peering, EKS, Lambda, Step Functions |
| [hashicorp/tls](https://registry.terraform.io/providers/hashicorp/tls/latest) | ~> 4.3 | NAT instance SSH key pair generation |

Modules use `~>` (allow patches, block minor bumps) rather than exact pins, so
security patches are not blocked. Exact reproducibility comes from
`.terraform.lock.hcl` in each live directory.

## Registry Modules

| Module | Version | Usage |
|--------|---------|-------|
| [terraform-aws-modules/eks/aws](https://registry.terraform.io/modules/terraform-aws-modules/eks/aws/21.25.0) | 21.25.0 | EKS control plane, managed node groups, IRSA, KMS |
| [terraform-aws-modules/vpc/aws](https://registry.terraform.io/modules/terraform-aws-modules/vpc/aws/6.7.0) | 6.7.0 | VPC, subnets, route tables, IGW |
| [int128/nat-instance/aws](https://registry.terraform.io/modules/int128/nat-instance/aws/2.1.0) | 2.1.0 | Spot NAT instance (cost-optimized NAT alternative) |
| [terraform-aws-modules/lambda/aws](https://registry.terraform.io/modules/terraform-aws-modules/lambda/aws/8.8.0) | 8.8.0 | Lambda functions (ZIP + container image, IAM role, CloudWatch logs) |

## ArgoCD Password Management

ArgoCD generates its admin password at install time and stores it in the `argocd-initial-admin-secret` Kubernetes secret.

The `argocd-config` module retrieves this password at runtime via an **ephemeral resource** `local_command` that runs `kubectl get secret`:
- The password is **never stored** in tfstate or plan files
- The password is **never entered manually** in live configs
- The ephemeral resource also waits for the `argocd-server` pod to be `Ready` before retrieving the secret

## Bootstrap Order

```bash
# 001 — Create k3d cluster (two-step due to kubectl provider chicken-and-egg)
cd live/001_k3d_init_cluster
terragrunt apply -target k3d_cluster.this
terragrunt apply

# 002 — Install ArgoCD (wait=true, blocks until pods are ready)
cd ../002_k3d_argocd_install
terragrunt apply

# 003 — Configure ArgoCD (password retrieved at runtime via ephemeral, not in state)
cd ../003_k3d_argocd_config
terragrunt apply
```

## gVisor (runsc) Sandboxing

The k3d-cluster module supports optional gVisor isolation. When `enable_gvisor = true`:

1. **runsc + containerd-shim-runsc-v1** are mounted into all k3d nodes
2. **containerd config** is patched to register runsc as a runtime
3. **RuntimeClass "gvisor"** is created so pods can opt into syscall isolation

### Prerequisites

```bash
# Install gVisor on the host (requires sudo)
bash infra/scripts/install-gvisor.sh

# Verify installation
bash infra/scripts/install-gvisor.sh --check
```

### Enable gVisor

```bash
# The live config 001_k3d_init_cluster already has enable_gvisor = true.
# If the cluster exists, destroy and recreate it:
cd live/001_k3d_init_cluster
terragrunt destroy -auto-approve
terragrunt apply -target k3d_cluster.this -auto-approve
terragrunt apply

# Verify the RuntimeClass
kubectl get runtimeclass gvisor
```

### Use gVisor in a pod

```yaml
spec:
  runtimeClassName: gvisor  # ← syscall isolation
  containers:
    - name: app
      image: my-app:latest
```

gVisor intercepts syscalls in userspace, isolating the pod from the host kernel.
This is critical for agents that process untrusted data or execute generated code.

## agents-sfn Module

The `agents-sfn` module deploys Step Functions agents generically. Each agent in
the `agents` map gets:
- N Lambda functions (via `terraform-aws-modules/lambda/aws`)
- 1 IAM role for Step Functions to invoke those Lambdas
- 1 `aws_sfn_state_machine` with the ASL definition (ARNs injected via `templatestring()`)

### ASL Templating

The ASL definition uses `${lambda_arns["name"]}` placeholders. The module
replaces them with actual Lambda ARNs at apply time:

```json
{
  "PARSE_INVOICE": {
    "Type": "Task",
    "Resource": "${lambda_arns["parse_invoice"]}",
    "Next": "FETCH_CONTRACT"
  }
}
```

The ASL is stored in a separate JSON file (read via `file()`) to avoid HCL
interpolation of the `${...}` placeholders.

### Testing with floci

```bash
# 1. Start floci
cd /root/projects/floci-test && docker compose up -d

# 2. Deploy via Terragrunt against floci (ZIPs are built by Terraform automatically)
source /root/projects/floci-test/env.floci
cd infra/live/006_aws_agents_sfn
terragrunt plan    # 87 resources: 12 Lambdas + 1 SFN + IAM roles
terragrunt apply

# 4. Test the state machine
aws stepfunctions start-execution \
  --state-machine-arn $(terragrunt output -raw state_machine_arns | jq -r '."financial-dispute"') \
  --input '{"invoice_id":"INV-6188"}' \
  --endpoint-url $AWS_ENDPOINT_URL

# 5. Check execution
aws stepfunctions describe-execution \
  --execution-arn $EXEC_ARN \
  --endpoint-url $AWS_ENDPOINT_URL

# 6. Clean up
terragrunt destroy -auto-approve
```
