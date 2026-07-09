# ---------------------------------------------------------------------------
# Variables — alphabetical order, Type → Description → Default
# ---------------------------------------------------------------------------

variable "availability_zones" {
  type        = list(string)
  description = "List of availability zones"
}

variable "aws_region" {
  type        = string
  description = "AWS region"
}

variable "create_nat_key_pair" {
  type        = bool
  description = "Create an SSH key pair for the NAT instance"
  default     = false
}

variable "enable_nat_gateway" {
  type        = bool
  description = "Enable a NAT Gateway (On-Demand). Only used when enable_nat_instance = false"
  default     = false
}

variable "enable_nat_instance" {
  type        = bool
  description = "Enable a NAT instance (Spot). Takes precedence over enable_nat_gateway"
  default     = true
}

variable "enable_nat_instance_eip" {
  type        = bool
  description = "Allocate and associate an Elastic IP to the NAT instance"
  default     = true
}

variable "enable_nat_ssh" {
  type        = bool
  description = "Allow SSH to the NAT instance"
  default     = false
}

variable "enable_private_route_table" {
  type        = bool
  description = "Add default route (0.0.0.0/0) via NAT in private route tables. Set to false for VPCs that use peering for Internet access"
  default     = true
}

variable "name" {
  type        = string
  description = "Name prefix for VPC resources"
}

variable "nat_instance_type" {
  type        = string
  description = "EC2 instance type for the NAT instance"
  default     = "t3a.nano"
}

variable "nat_key_pair_name" {
  type        = string
  description = "Existing key pair name for NAT instance (ignored if create_nat_key_pair = true)"
  default     = ""
}

variable "nat_ssh_cidrs" {
  type        = list(string)
  description = "CIDR blocks allowed to SSH to the NAT instance"
  default     = ["0.0.0.0/0"]
}

variable "private_subnet_tags" {
  type        = map(string)
  description = "Additional tags for private subnets only, e.g. { \"karpenter.sh/discovery\" = \"<cluster-name>\" } so Karpenter can place nodes there"
  default     = {}
}

variable "private_subnets" {
  type        = list(string)
  description = "List of private subnet CIDR blocks"
}

variable "public_subnet_tags" {
  type        = map(string)
  description = "Additional tags for public subnets only, e.g. { \"kubernetes.io/role/elb\" = \"1\" } for public load balancers"
  default     = {}
}

variable "public_subnets" {
  type        = list(string)
  description = "List of public subnet CIDR blocks"
}

variable "tags" {
  type        = map(string)
  description = "Tags to apply to all resources"
  default     = {}
}

variable "vpc_cidr" {
  type        = string
  description = "CIDR block for the VPC"
}
