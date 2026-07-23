output "vpc_peering_id" {
  description = "ID of the VPC peering connection"
  value       = module.peering.vpc_peering_id
}

output "vpc_peering_accept_status" {
  description = "Accept status of the peering connection"
  value       = module.peering.vpc_peering_accept_status
}

output "this_vpc_id" {
  description = "Requester VPC ID"
  value       = module.peering.this_vpc_id
}

output "peer_vpc_id" {
  description = "Accepter VPC ID"
  value       = module.peering.peer_vpc_id
}

output "requester_routes" {
  description = "Routes created in the requester VPC"
  value       = module.peering.requester_routes
}

output "accepter_routes" {
  description = "Routes created in the accepter VPC"
  value       = module.peering.accepter_routes
}
