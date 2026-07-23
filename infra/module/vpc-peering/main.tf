# ---------------------------------------------------------------------------
# VPC Peering — using grem11n/vpc-peering/aws
# ---------------------------------------------------------------------------

module "peering" {
  source = "grem11n/vpc-peering/aws"

  providers = {
    aws.this = aws.this
    aws.peer = aws.peer
  }

  name                 = var.name
  this_vpc_id          = var.this_vpc_id
  peer_vpc_id          = var.peer_vpc_id
  auto_accept_peering  = var.auto_accept_peering
  this_dns_resolution  = var.this_dns_resolution
  peer_dns_resolution  = var.peer_dns_resolution
  this_rts_ids         = var.this_rts_ids
  peer_rts_ids         = var.peer_rts_ids

  tags = merge(var.tags, {
    Module = "vpc-peering"
  })
}

# ---------------------------------------------------------------------------
# Optional: route Internet traffic (0.0.0.0/0) via peering
# Use case: requester VPC has no NAT, uses peer VPC's NAT for Internet access
# ---------------------------------------------------------------------------

resource "aws_route" "internet_via_peering" {
  for_each = var.route_internet_via_peering ? toset(var.this_rts_ids) : []

  provider                 = aws.this
  route_table_id           = each.value
  destination_cidr_block   = "0.0.0.0/0"
  vpc_peering_connection_id = module.peering.vpc_peering_id
}
