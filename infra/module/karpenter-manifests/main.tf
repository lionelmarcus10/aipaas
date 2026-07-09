# ---------------------------------------------------------------------------
# Module: karpenter-manifests
# ---------------------------------------------------------------------------
# Crée les manifests K8s Karpenter (NodePool + EC2NodeClass) via le provider
# Kubernetes. Le module EKS (005) crée l'infrastructure IAM/SQS; ce module
# crée les ressources K8s qui disent à Karpenter comment provisionner.
# ---------------------------------------------------------------------------

terraform {
  required_providers {
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.30"
    }
  }
}

variable "cluster_name" {
  description = "EKS cluster name"
  type        = string
}

variable "cluster_endpoint" {
  description = "EKS cluster API server endpoint"
  type        = string
}

variable "cluster_ca_certificate" {
  description = "Base64-encoded CA certificate for the EKS cluster"
  type        = string
}

variable "node_pools" {
  description = <<-EOT
    Map of Karpenter NodePools to create. Each entry defines:
      - labels: node labels
      - taints: node taints (map of {key => {key, value, effect}})
      - capacity_types: ["on-demand", "spot"]
      - instance_types: list of EC2 instance types
      - min_size / max_size: scaling bounds
  EOT
  type = map(object({
    labels         = map(string)
    taints         = map(map(string))
    capacity_types = list(string)
    instance_types = list(string)
    min_size       = number
    max_size       = number
  }))
}

# Provider Kubernetes — se connecte au cluster EKS
provider "kubernetes" {
  host                   = "https://${var.cluster_endpoint}"
  cluster_ca_certificate = base64decode(var.cluster_ca_certificate)
}

# ---------------------------------------------------------------------------
# EC2NodeClass — définit comment provisionner (AMI, subnet, security group)
# ---------------------------------------------------------------------------
resource "kubernetes_manifest" "nodeclass" {
  for_each = var.node_pools

  yaml_body = yamlencode({
    apiVersion = "karpenter.k8s.aws/v1"
    kind       = "EC2NodeClass"
    metadata = {
      name = "aipaas-${each.key}"
    }
    spec = {
      amiFamily = each.key == "gpu" ? "AL2023" : "AL2023"
      subnetSelectorTerms = [{
        tags = {
          "karpenter.sh/discovery" = var.cluster_name
        }
      }]
      securityGroupSelectorTerms = [{
        tags = {
          "karpenter.sh/discovery" = var.cluster_name
        }
      }]
      # GPU pool: require NVIDIA drivers
      blockDeviceMappings = each.key == "gpu" ? [
        {
          deviceName = "/dev/xvda"
          ebs = {
            volumeSize          = "100Gi"
            volumeType          = "gp3"
            deleteOnTermination = true
          }
        }
      ] : []
    }
  })
}

# ---------------------------------------------------------------------------
# NodePool — définit quels pods provisionner et les limites de scaling
# ---------------------------------------------------------------------------
resource "kubernetes_manifest" "nodepool" {
  for_each = var.node_pools

  yaml_body = yamlencode({
    apiVersion = "karpenter.sh/v1"
    kind       = "NodePool"
    metadata = {
      name = "aipaas-${each.key}"
    }
    spec = {
      template = {
        metadata = {
          labels = merge(each.value.labels, {
            "karpenter.sh/nodepool" = "aipaas-${each.key}"
          })
        }
        spec = {
          nodeClassRef = {
            group = "karpenter.k8s.aws"
            kind  = "EC2NodeClass"
            name  = "aipaas-${each.key}"
          }
          taints = [
            for k, t in each.value.taints : {
              key    = t.key
              value  = t.value
              effect = t.effect
            }
          ]
          requirements = concat(
            [
              {
                key      = "karpenter.k8s.aws/instance-category"
                operator = "In"
                values   = ["t", "g"]
              },
              {
                key      = "karpenter.sh/capacity-type"
                operator = "In"
                values   = each.value.capacity_types
              },
            ],
            each.key == "gpu" ? [
              {
                key      = "karpenter.k8s.aws/instance-gpu-count"
                operator = "IsPresent"
              }
            ] : []
          )
        }
      }
      limits = {
        cpu    = each.key == "gpu" ? "16" : "32"
        memory = each.key == "gpu" ? "64Gi" : "64Gi"
      }
      disruption = {
        consolidationPolicy = "WhenEmptyOrUnderutilized"
        consolidateAfter    = "30s"
      }
    }
  })

  depends_on = [kubernetes_manifest.nodeclass]
}
