# k3d-cluster module

Creates a k3d cluster (k3s in Docker) with optional gVisor syscall isolation.

## Variables

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `cluster_name` | string | — | k3d cluster name |
| `servers_count` | number | 1 | Number of server nodes |
| `agents_count` | number | 1 | Number of agent (worker) nodes |
| `kubernetes_version` | string | — | k3s version (e.g. `1.31.5-k3s1`) |
| `enable_gvisor` | bool | false | Mount runsc + shim + containerd config into all nodes |
| `gvisor_runsc_path` | string | `/usr/local/bin/runsc` | Host path to runsc binary |
| `gvisor_shim_path` | string | `/usr/local/bin/containerd-shim-runsc-v1` | Host path to shim binary |

## gVisor support

When `enable_gvisor = true`:

1. **Mounts** `runsc` + `containerd-shim-runsc-v1` into all k3d nodes (server + agents)
2. **Patches containerd config** via `config.toml.tmpl` (k3s template mechanism)
3. **Creates RuntimeClass** `gvisor` (handler: `runsc`) via `kubectl_manifest`

Pods can then opt into gVisor isolation with `runtimeClassName: gvisor`.

### Prerequisites

```bash
# Install gVisor on the host (requires sudo)
bash infra/scripts/install-gvisor.sh

# Verify
bash infra/scripts/install-gvisor.sh --check
```

### How it works

k3d runs k3s inside Docker containers. gVisor's `runsc` is a userspace kernel
that intercepts syscalls. To use it inside k3d:

1. Install `runsc` on the host
2. Mount it into the k3d node containers (via `volume` blocks)
3. Tell containerd (inside k3s) to register `runsc` as a runtime (via `config.toml.tmpl`)
4. Create a Kubernetes `RuntimeClass` so pods can request it

The `config.toml.tmpl` uses k3s's template mechanism (`{{ template "base" . }}`)
to extend the default containerd config without overwriting it.

### Limitations

- gVisor has ~10-15% overhead vs runc — use it only for pods that need isolation
- gVisor is not VM-grade isolation (unlike Kata Containers / Firecracker)
- gVisor doesn't support all syscalls — some workloads may fail
- For production EKS, consider Kata Containers or AWS Firecracker instead

## Outputs

| Output | Description |
|--------|-------------|
| `cluster_name` | k3d cluster name |
| `kubeconfig_path` | Path to the generated kubeconfig |
| `registry_name` | Local registry name |
| `gvisor_runtimeclass_name` | RuntimeClass name (only if `enable_gvisor = true`) |
