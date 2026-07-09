# AIPaaS — Build, Push & Deploy images to Kubernetes registry
#
# Usage:
#   make build-agent          # Build the financial-dispute-agent image
#   make push-agent           # Push to the k3d local registry
#   make deploy-agent         # Apply the Kubernetes manifests
#   make build-push-agent     # Build + push in one command
#   make full-agent           # Build + push + deploy
#   make restart-agent        # Restart the pod (pull new image)
#   make logs-agent           # Tail agent logs
#   make test-agent           # Run a test workflow against the agent pod
#   make status               # Show pod status for all AIPaaS namespaces
#
# Registry:
#   k3d local:  aipaas-registry:5000 (internal) / localhost:5001 (host)
#   EKS / ECR:  set REGISTRY=<account>.dkr.ecr.<region>.amazonaws.com
#
# Versioning:
#   make build-agent TAG=v0.1.0   # tag the image with a version
#   make build-agent TAG=$(git rev-parse --short HEAD)  # tag with git SHA

# --- Configuration ---
REGISTRY    ?= aipaas-registry:5000
AGENT_IMAGE  = $(REGISTRY)/financial-dispute-agent
TAG         ?= latest
DOCKERFILE   = agents/financial-dispute-agent/Dockerfile
BUILD_CTX    = .
AGENT_NS     = financial-dispute-agent
VLLM_NS      = aipaas

# --- Colors ---
C_RESET = \033[0m
C_CYAN  = \033[36m
C_GREEN = \033[32m
C_YELL  = \033[33m

# ============================================================
# Agent image — build, push, deploy
# ============================================================

.PHONY: build-agent
build-agent: ## Build the financial-dispute-agent Docker image
	@printf "$(C_CYAN)==> Building $(AGENT_IMAGE):$(TAG)$(C_RESET)\n"
	docker build -t $(AGENT_IMAGE):$(TAG) -f $(DOCKERFILE) $(BUILD_CTX)
	@printf "$(C_GREEN)==> Image built: $(AGENT_IMAGE):$(TAG)$(C_RESET)\n"

.PHONY: push-agent
push-agent: ## Push the agent image to the registry
	@printf "$(C_CYAN)==> Pushing $(AGENT_IMAGE):$(TAG)$(C_RESET)\n"
	docker push $(AGENT_IMAGE):$(TAG)
	@printf "$(C_GREEN)==> Image pushed: $(AGENT_IMAGE):$(TAG)$(C_RESET)\n"

.PHONY: build-push-agent
build-push-agent: build-agent push-agent ## Build + push the agent image

.PHONY: deploy-agent
deploy-agent: ## Deploy the agent to Kubernetes (kubectl apply)
	@printf "$(C_CYAN)==> Deploying agent manifests$(C_RESET)\n"
	kubectl apply -f apps/financial-dispute-agent/deployment.yaml
	@printf "$(C_GREEN)==> Deployed. Run 'make status' to check.$(C_RESET)\n"

.PHONY: full-agent
full-agent: build-push-agent deploy-agent restart-agent ## Build + push + deploy + restart

.PHONY: restart-agent
restart-agent: ## Restart the agent pod to pull the new image
	@printf "$(C_CYAN)==> Restarting agent pods$(C_RESET)\n"
	kubectl rollout restart deployment/financial-dispute-agent -n $(AGENT_NS)
	kubectl rollout status deployment/financial-dispute-agent -n $(AGENT_NS) --timeout=120s

.PHONY: logs-agent
logs-agent: ## Tail agent logs
	kubectl logs -n $(AGENT_NS) -l app=financial-dispute-agent -f --tail=50

.PHONY: test-agent
test-agent: ## Run a test workflow against the agent pod
	@printf "$(C_CYAN)==> Running test workflow INV-2375$(C_RESET)\n"
	@POD=$$(kubectl get pods -n $(AGENT_NS) -o jsonpath='{.items[0].metadata.name}'); \
	kubectl exec -n $(AGENT_NS) $$POD -- python3 -c "\
import urllib.request, json, time; \
start=time.time(); \
req=urllib.request.Request('http://localhost:8000/workflow', \
data=json.dumps({'invoice_id':'INV-2375'}).encode(), \
headers={'Content-Type':'application/json'}); \
r=urllib.request.urlopen(req, timeout=300); \
data=json.loads(r.read()); \
elapsed=time.time()-start; \
print(f'Completed in {elapsed:.1f}s'); \
print(f'final_decision: {data.get(\"final_decision\",\"UNKNOWN\")}'); \
print(f'actions: {len(data.get(\"actions_executed\",[]))}'); \
[t and print(f'  {t[\"state\"]} -> {t.get(\"decision\",\"\")}') for t in data.get('trace',[])]"

# ============================================================
# vLLM (reference — vLLM uses a public image, no build needed)
# ============================================================

.PHONY: deploy-vllm
deploy-vllm: ## Deploy vLLM to Kubernetes
	kubectl apply -f apps/vllm/deployment.yaml

.PHONY: restart-vllm
restart-vllm: ## Restart vLLM pods
	kubectl rollout restart deployment/vllm -n $(VLLM_NS)
	kubectl rollout status deployment/vllm -n $(VLLM_NS) --timeout=600s

.PHONY: logs-vllm
logs-vllm: ## Tail vLLM logs
	kubectl logs -n $(VLLM_NS) -l app=vllm -f --tail=50

# ============================================================
# Cluster status
# ============================================================

.PHONY: status
status: ## Show pod status for all AIPaaS namespaces
	@printf "$(C_CYAN)==> Pods$(C_RESET)\n"
	kubectl get pods -n $(AGENT_NS) -o wide 2>/dev/null || echo "  (namespace not found)"
	@echo ""
	kubectl get pods -n $(VLLM_NS) -o wide 2>/dev/null || echo "  (namespace not found)"
	@echo ""
	@printf "$(C_CYAN)==> gVisor check$(C_RESET)\n"
	@POD=$$(kubectl get pods -n $(AGENT_NS) -o jsonpath='{.items[0].metadata.name}' 2>/dev/null); \
	if [ -n "$$POD" ]; then \
		kubectl get pod -n $(AGENT_NS) $$POD -o jsonpath='{.spec.runtimeClassName}' 2>/dev/null; \
		echo " (runtimeClassName for $$POD)"; \
	else \
		echo "  (no agent pod found)"; \
	fi

.PHONY: gvisor-check
gvisor-check: ## Verify gVisor is active on the agent pod
	@POD=$$(kubectl get pods -n $(AGENT_NS) -o jsonpath='{.items[0].metadata.name}'); \
	CID=$$(kubectl get pod -n $(AGENT_NS) $$POD -o jsonpath='{.status.containerStatuses[0].containerID}' | sed 's/containerd:\/\///'); \
	RUNTIME=$$(docker exec k3d-aipaas-agent-0 crictl inspect $$CID 2>/dev/null | grep "runtimeType" | head -1); \
	echo "Pod:    $$POD"; \
	echo "Runtime: $$RUNTIME"; \
	if echo "$$RUNTIME" | grep -q "runsc"; then \
		printf "$(C_GREEN)gVisor: ACTIVE$(C_RESET)\n"; \
	else \
		printf "$(C_YELL)gVisor: NOT ACTIVE$(C_RESET)\n"; \
	fi

# ============================================================
# Cleanup
# ============================================================

.PHONY: clean-agent
clean-agent: ## Delete the agent deployment and namespace
	@printf "$(C_YELL)==> Deleting agent deployment$(C_RESET)\n"
	kubectl delete deployment financial-dispute-agent -n $(AGENT_NS) --ignore-not-found
	kubectl delete service financial-dispute-agent -n $(AGENT_NS) --ignore-not-found
	kubectl delete namespace $(AGENT_NS) --ignore-not-found

# ============================================================
# Help
# ============================================================

.PHONY: help
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  $(C_CYAN)%-20s$(C_RESET) %s\n", $$1, $$2}'

.DEFAULT_GOAL := help
