variable "name" {
  description = "Name prefix for the peering connection"
  type        = string
}

variable "aws_region" {
  description = "AWS region"
  type        = string
}

variable "this_vpc_id" {
  description = "VPC ID of the requester (this VPC)"
  type        = string
}

variable "peer_vpc_id" {
  description = "VPC ID of the accepter (peer VPC)"
  type        = string
}

variable "this_rts_ids" {
  description = "Route table IDs in the requester VPC to add routes to"
  type        = list(string)
  default     = []
}

variable "peer_rts_ids" {
  description = "Route table IDs in the accepter VPC to add routes to"
  type        = list(string)
  default     = []
}

variable "auto_accept_peering" {
  description = "Auto accept the peering connection (same account)"
  type        = bool
  default     = true
}

variable "this_dns_resolution" {
  description = "Allow DNS resolution from this VPC to peer VPC"
  type        = bool
  default     = true
}

variable "peer_dns_resolution" {
  description = "Allow DNS resolution from peer VPC to this VPC"
  type        = bool
  default     = true
}

variable "route_internet_via_peering" {
  description = "Add 0.0.0.0/0 route via peering in requester route tables (for shared NAT)"
  type        = bool
  default     = false
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
  default     = {}
}
