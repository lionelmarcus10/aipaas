# apps/vllm/

Déploiement vLLM en mode CPU sur le cluster k3d.

## Contenu prévu (Sprint 4)

- `deployment.yaml` — Deployment vLLM avec modèle léger (Qwen2.5-0.5B-Instruct)
- `service.yaml` — Service ClusterIP exposant l'API OpenAI-compatible
- `pvc-cache.yaml` — PVC pour le cache des poids HuggingFace (anti Cold Start)

## Modèle de test

```yaml
args: ["--model", "Qwen/Qwen2.5-0.5B-Instruct", "--device", "cpu", "--dtype", "float32"]
```

Modèle < 1GB, téléchargeable rapidement, fonctionne en CPU sur k3d.
