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

  # NAT is managed outside the module (shared EIP + switch instance/gateway)
  enable_nat_gateway     = false
  single_nat_gateway     = false
  one_nat_gateway_per_az = false

  tags = merge(var.tags, {
    Module = "vpc"
  })
}

# ---------------------------------------------------------------------------
# NAT mode — switch between NAT instance and NAT gateway with shared EIP
# ---------------------------------------------------------------------------

locals {
  use_nat_instance     = var.enable_nat_instance
  use_nat_gateway      = !var.enable_nat_instance && var.enable_nat_gateway
  use_nat_instance_eip = local.use_nat_instance && var.enable_nat_instance_eip
  create_nat_key_pair  = var.create_nat_key_pair && var.enable_nat_instance
  create_shared_eip    = local.use_nat_gateway || local.use_nat_instance_eip
  add_nat_route        = (local.use_nat_gateway || local.use_nat_instance) && var.enable_private_route_table
  nat_key_name         = local.create_nat_key_pair ? aws_key_pair.nat[0].key_name : (var.nat_key_pair_name != "" ? var.nat_key_pair_name : "")
}

# Shared Elastic IP — stable across NAT mode switches
resource "aws_eip" "nat" {
  count  = local.create_shared_eip ? 1 : 0
  domain = "vpc"

  tags = merge(var.tags, {
    Name = "${var.name}-nat-eip"
  })
}

# ---------------------------------------------------------------------------
# NAT Gateway mode (On-Demand, ~$32/month)
# ---------------------------------------------------------------------------

resource "aws_nat_gateway" "nat" {
  count         = local.use_nat_gateway ? 1 : 0
  allocation_id = aws_eip.nat[0].id
  subnet_id     = module.vpc.public_subnets[0]

  tags = merge(var.tags, {
    Name = "${var.name}-nat-gw"
  })

  depends_on = [module.vpc.igw_id]
}

# ---------------------------------------------------------------------------
# NAT Instance mode (Spot, ~$1-2/month)
# ---------------------------------------------------------------------------

module "nat_instance" {
  count  = local.use_nat_instance ? 1 : 0
  source = "int128/nat-instance/aws"

  name                        = var.name
  vpc_id                      = module.vpc.vpc_id
  public_subnet               = module.vpc.public_subnets[0]
  private_subnets_cidr_blocks = var.private_subnets
  private_route_table_ids     = []
  instance_types              = [var.nat_instance_type]
  use_spot_instance           = true
  key_name                    = local.nat_key_name

  tags = var.tags
}

# Attach the shared EIP to the NAT instance
resource "aws_eip_association" "nat_instance" {
  count = local.use_nat_instance_eip ? 1 : 0

  allocation_id        = aws_eip.nat[0].id
  network_interface_id = module.nat_instance[0].eni_id
}

# ---------------------------------------------------------------------------
# Private route table — default route via NAT (gateway or instance)
# ---------------------------------------------------------------------------

resource "aws_route" "private_nat" {
  for_each = local.add_nat_route ? toset(module.vpc.private_route_table_ids) : []

  route_table_id         = each.value
  destination_cidr_block = "0.0.0.0/0"

  nat_gateway_id       = local.use_nat_gateway ? aws_nat_gateway.nat[0].id : null
  network_interface_id = local.use_nat_instance ? module.nat_instance[0].eni_id : null
}

# ---------------------------------------------------------------------------
# Optional: SSH key pair for the NAT instance
# ---------------------------------------------------------------------------

resource "tls_private_key" "nat" {
  count     = local.create_nat_key_pair ? 1 : 0
  algorithm = "RSA"
  rsa_bits  = 2048
}

resource "aws_key_pair" "nat" {
  count      = local.create_nat_key_pair ? 1 : 0
  key_name   = "${var.name}-nat-key"
  public_key = tls_private_key.nat[0].public_key_openssh

  tags = var.tags
}

# ---------------------------------------------------------------------------
# Optional: SSH ingress rule for the NAT instance
# ---------------------------------------------------------------------------

locals {
  nat_sg_id = local.use_nat_instance ? try(
    module.nat_instance[0].sg_id,
    module.nat_instance[0].security_group_id,
    (length(try(module.nat_instance[0].security_group_ids, [])) > 0 ? module.nat_instance[0].security_group_ids[0] : null),
    null
  ) : null
}

resource "aws_security_group_rule" "nat_ssh" {
  count = local.use_nat_instance && var.enable_nat_ssh && local.nat_sg_id != null ? 1 : 0

  security_group_id = local.nat_sg_id
  type              = "ingress"
  cidr_blocks       = var.nat_ssh_cidrs
  from_port         = 22
  to_port           = 22
  protocol          = "tcp"
  description       = "Allow SSH to NAT instance"
}
