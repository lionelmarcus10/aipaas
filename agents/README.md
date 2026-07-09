# agents/

Code Python des agents **AWS Strands**.

## Contenu prévu
- `agent_research/` — Agent 1 (ex: recherche/analyse) + tools custom
- `agent_action/` — Agent 2 (ex: exécution d'actions conditionnelles)
- `tools/` — outils partagés (ex: mock DB, appel API)
- `orchestration/`
  - `case_a_bedrock_runtime/` — packaging pour Bedrock Agent Runtime
  - `case_b_step_functions/` — définition de la machine d'état
- `resilience/` — Circuit Breaker (Panne #2)

## Prérequis
- Python 3.11+
- `uv`
- SDK AWS Strands + accès Bedrock activé sur le compte AWS

## Sprint 2
Écrire 2 agents + tools, connecter à Bedrock, tester en local.
