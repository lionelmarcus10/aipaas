# apps/keda/

Configuration KEDA pour le Scale-to-Zero du déploiement vLLM.

## Contenu prévu (Sprint 4)

- `scaled-object.yaml` — ScaledObject avec trigger `aws-sqs-queue`
- `scaled-object.yaml` — `minReplicaCount: 0`, `queueLength` configurable

## Prérequis

- KEDA installé via Helm (chart `kedacore/keda`)
- File SQS créée via Terraform
- Credentials IAM pour KEDA (access key + secret)
