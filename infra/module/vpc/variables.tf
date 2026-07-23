variable "name" {
  description = "Name prefix for VPC resources"
  type        = string
}

variable "aws_region" {
  description = "AWS region"
  type        = string
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
}

variable "availability_zones" {
  description = "List of availability zones"
  type        = list(string)
}

variable "public_subnets" {
  description = "List of public subnet CIDR blocks"
  type        = list(string)
}

variable "private_subnets" {
  description = "List of private subnet CIDR blocks"
  type        = list(string)
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}

# --- NAT mode switch ---

variable "enable_nat_instance" {
  description = "Enable a NAT instance (Spot). Takes precedence over enable_nat_gateway"
  type        = bool
  default     = true
}

variable "enable_nat_gateway" {
  description = "Enable a NAT Gateway (On-Demand). Only used when enable_nat_instance = false"
  type        = bool
  default     = false
}

variable "enable_private_route_table" {
  description = "Add default route (0.0.0.0/0) via NAT in private route tables. Set to false for VPCs that use peering for Internet access"
  type        = bool
  default     = true
}

# --- NAT instance config ---

variable "nat_instance_type" {
  description = "EC2 instance type for the NAT instance"
  type        = string
  default     = "t3a.nano"
}

variable "enable_nat_instance_eip" {
  description = "Allocate and associate an Elastic IP to the NAT instance"
  type        = bool
  default     = true
}

variable "create_nat_key_pair" {
  description = "Create an SSH key pair for the NAT instance"
  type        = bool
  default     = false
}

variable "nat_key_pair_name" {
  description = "Existing key pair name for NAT instance (ignored if create_nat_key_pair = true)"
  type        = string
  default     = ""
}

variable "enable_nat_ssh" {
  description = "Allow SSH to the NAT instance"
  type        = bool
  default     = false
}

variable "nat_ssh_cidrs" {
  description = "CIDR blocks allowed to SSH to the NAT instance"
  type        = list(string)
  default     = ["0.0.0.0/0"]
}
