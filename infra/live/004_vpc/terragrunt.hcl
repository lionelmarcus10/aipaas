include "root" {
  path = find_in_parent_folders("terragrunt.hcl")
}

terraform {
  source = "../../module/vpc"
}

inputs = {
  name             = "aipaas-vpc"
  aws_region       = "eu-west-3"
  vpc_cidr         = "10.0.0.0/16"
  availability_zones = ["eu-west-3a", "eu-west-3b"]
  public_subnets   = ["10.0.1.0/24", "10.0.2.0/24"]
  private_subnets  = ["10.0.10.0/24", "10.0.11.0/24"]

  tags = {
    Project     = "aipaas"
    Environment = "dev"
    ManagedBy   = "terragrunt"
  }

  # NAT instance (FinOps — pas de NAT gateway)
  nat_instance_type      = "t3a.nano"
  enable_nat_instance_eip = true
  create_nat_key_pair     = false
  enable_nat_ssh          = false
}
