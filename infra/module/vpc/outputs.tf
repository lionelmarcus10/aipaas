output "vpc_id" {
  description = "ID of the VPC"
  value       = module.vpc.vpc_id
}

output "vpc_cidr" {
  description = "CIDR block of the VPC"
  value       = module.vpc.vpc_cidr_block
}

output "public_subnet_ids" {
  description = "List of public subnet IDs"
  value       = module.vpc.public_subnets
}

output "private_subnet_ids" {
  description = "List of private subnet IDs"
  value       = module.vpc.private_subnets
}

output "public_route_table_ids" {
  description = "List of public route table IDs"
  value       = module.vpc.public_route_table_ids
}

output "public_route_table_id" {
  description = "First public route table ID (for peering)"
  value       = length(module.vpc.public_route_table_ids) > 0 ? module.vpc.public_route_table_ids[0] : null
}

output "private_route_table_ids" {
  description = "List of private route table IDs"
  value       = module.vpc.private_route_table_ids
}

output "nat_mode" {
  description = "Active NAT mode: 'instance', 'gateway', or 'none'"
  value       = local.use_nat_instance ? "instance" : (local.use_nat_gateway ? "gateway" : "none")
}

output "nat_instance_eni_id" {
  description = "Network interface ID of the NAT instance (null if NAT gateway or none)"
  value       = local.use_nat_instance ? module.nat_instance[0].eni_id : null
}

output "nat_gateway_id" {
  description = "ID of the NAT gateway (null if NAT instance or none)"
  value       = local.use_nat_gateway ? aws_nat_gateway.nat[0].id : null
}

output "nat_eip_public_ip" {
  description = "Public IP of the shared NAT EIP (stable across mode switches)"
  value       = local.create_shared_eip ? aws_eip.nat[0].public_ip : null
}

output "nat_eip_allocation_id" {
  description = "Allocation ID of the shared NAT EIP"
  value       = local.create_shared_eip ? aws_eip.nat[0].id : null
}

output "nat_key_pair_name" {
  description = "Name of the key pair for the NAT instance (null if none)"
  value       = local.nat_key_name != "" ? local.nat_key_name : null
}

output "nat_private_key_pem" {
  description = "Private key PEM for the NAT instance (sensitive)"
  value       = local.create_nat_key_pair ? tls_private_key.nat[0].private_key_pem : null
  sensitive   = true
}
