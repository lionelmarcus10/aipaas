provider "aws" {
  region = var.aws_region
}

# ---------------------------------------------------------------------------
# VPC — using terraform-aws-modules/vpc/aws
# ---------------------------------------------------------------------------

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 6.5"

  name = var.name
  cidr = var.vpc_cidr

  azs             = var.availability_zones
  public_subnets  = var.public_subnets
  private_subnets = var.private_subnets

  enable_dns_support   = true
  enable_dns_hostnames = true

  # No NAT gateway — we use a NAT instance instead (FinOps)
  enable_nat_gateway     = false
  single_nat_gateway     = false
  one_nat_gateway_per_az = false

  tags = merge(var.tags, {
    Module = "vpc"
  })
}

# ---------------------------------------------------------------------------
# NAT Instance — using int128/nat-instance/aws (same as troooble)
# ---------------------------------------------------------------------------

locals {
  create_nat_key_pair = var.create_nat_key_pair && var.nat_key_pair_name == ""
  nat_key_name        = local.create_nat_key_pair ? aws_key_pair.nat[0].key_name : (var.nat_key_pair_name != "" ? var.nat_key_pair_name : "")
}

# Optional: SSH key pair for the NAT instance
resource "tls_private_key" "nat" {
  count    = local.create_nat_key_pair ? 1 : 0
  algorithm = "RSA"
  rsa_bits  = 2048
}

resource "aws_key_pair" "nat" {
  count      = local.create_nat_key_pair ? 1 : 0
  key_name   = "${var.name}-nat-key"
  public_key = tls_private_key.nat[0].public_key_openssh

  tags = var.tags
}

# Elastic IP for the NAT instance
resource "aws_eip" "nat" {
  count = var.enable_nat_instance_eip ? 1 : 0
  domain = "vpc"

  tags = merge(var.tags, {
    Name = "${var.name}-nat-eip"
  })
}

module "nat_instance" {
  source = "int128/nat-instance/aws"

  name                        = var.name
  vpc_id                      = module.vpc.vpc_id
  public_subnet               = module.vpc.public_subnets[0]
  private_subnets_cidr_blocks = var.private_subnets
  private_route_table_ids     = module.vpc.private_route_table_ids
  instance_types              = [var.nat_instance_type]
  key_name                    = local.nat_key_name

  tags = var.tags
}

# Associate the EIP to the NAT instance
resource "aws_eip_association" "nat_instance" {
  count = var.enable_nat_instance_eip ? 1 : 0

  allocation_id        = aws_eip.nat[0].id
  network_interface_id = module.nat_instance.eni_id
}

# Optional: SSH ingress rule for the NAT instance
locals {
  nat_sg_id = try(
    module.nat_instance.sg_id,
    module.nat_instance.security_group_id,
    (length(try(module.nat_instance.security_group_ids, [])) > 0 ? module.nat_instance.security_group_ids[0] : null),
    null
  )
}

resource "aws_security_group_rule" "nat_ssh" {
  count = var.enable_nat_ssh && local.nat_sg_id != null ? 1 : 0

  security_group_id = local.nat_sg_id
  type              = "ingress"
  cidr_blocks       = var.nat_ssh_cidrs
  from_port         = 22
  to_port           = 22
  protocol          = "tcp"
  description       = "Allow SSH to NAT instance"
}
