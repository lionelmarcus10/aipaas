include "root" {
  path = find_in_parent_folders("terragrunt.hcl")
}

terraform {
  source = "../../module/vpc"
}

inputs = {
  name               = "aipaas-vpc"
  aws_region         = "eu-west-3"
  vpc_cidr           = "10.0.0.0/16"
  availability_zones = ["eu-west-3a", "eu-west-3b"]
  public_subnets     = ["10.0.1.0/24", "10.0.2.0/24"]
  private_subnets    = ["10.0.10.0/24", "10.0.11.0/24"]

  # Subnet-scoped tags for Kubernetes resource placement.
  # karpenter.sh/discovery: Karpenter (005_aws_eks) may provision nodes here.
  # kubernetes.io/role/*  : where AWS Load Balancer Controller may place LBs.
  private_subnet_tags = {
    "karpenter.sh/discovery"           = "aipaas-eks"
    "kubernetes.io/role/internal-elb"  = "1"
    "kubernetes.io/cluster/aipaas-eks" = "shared"
  }
  public_subnet_tags = {
    "kubernetes.io/role/elb"           = "1"
    "kubernetes.io/cluster/aipaas-eks" = "shared"
  }

  # NAT mode: instance (Spot, ~$1-2/mo) or gateway (On-Demand, ~$32/mo)
  # enable_nat_instance takes precedence over enable_nat_gateway
  # NOTE: pour tester contre floci, utiliser NAT Gateway (floci ne supporte pas CreateNetworkInterface)
  enable_nat_instance        = false
  enable_nat_gateway         = true
  enable_private_route_table = true

  # NAT instance config
  nat_instance_type       = "t3a.nano"
  enable_nat_instance_eip = true
  create_nat_key_pair     = false
  enable_nat_ssh          = false
}
