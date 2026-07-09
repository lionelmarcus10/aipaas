# TODO — Modules à créer

## 1. Module VPC AWS

- **Objectif** : VPC minimal pour héberger l'infra cloud (EC2, EKS, etc.)
- **Module** : `terraform-aws-modules/vpc/aws` v6.6.1
  - 195M+ downloads, publié avril 2026, maintenu par la communauté AWS
  - Repo : https://github.com/terraform-aws-modules/terraform-aws-vpc
- **Provider** : `hashicorp/aws` (latest)
- **Config minimale** :
  - `cidr = "10.0.0.0/16"`
  - `azs = ["eu-west-3a", "eu-west-3b"]`
  - `private_subnets = ["10.0.1.0/24", "10.0.2.0/24"]`
  - `public_subnets = ["10.0.101.0/24", "10.0.102.0/24"]`
  - `enable_nat_gateway = false` + `single_nat_gateway = true` (FinOps)
  - `enable_dns_hostnames = true`
  - `enable_dns_support = true`
- **Outputs clés** : `vpc_id`, `private_subnets`, `public_subnets`, `nat_public_ips`
- **Sécurité** : Flow logs activables via `enable_flow_log = true`

---

## ✅ Fait

- **Module ArgoCD** → `argocd-install` (Helm direct, chart v7.3.11) + `argocd-config` (provider oboukili/argocd) — lives `002` et `003`
- **metrics.md** → créé à la racine du projet (template S1)
