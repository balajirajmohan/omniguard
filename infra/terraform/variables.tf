variable "aws_region" {
  description = "AWS region for the Isaac Sim workstation. Mumbai recommended for India latency."
  type        = string
  default     = "ap-south-1"
}

variable "project_name" {
  description = "Name prefix for resources"
  type        = string
  default     = "omniguard"
}

variable "instance_type" {
  description = "EC2 instance type. g6e.4xlarge = 1x L40S, 16 vCPU, 128 GiB RAM."
  type        = string
  default     = "g6e.4xlarge"
}

variable "root_volume_gb" {
  description = "Root EBS volume size in GiB (Marketplace recommends >= 512)"
  type        = number
  default     = 1024
}

variable "ami_id" {
  description = "Optional explicit AMI ID. Leave empty to auto-discover Isaac Sim Marketplace AMI."
  type        = string
  default     = ""
}

variable "ami_name_filter" {
  description = "AMI name filter used when ami_id is empty"
  type        = string
  default     = "*Isaac*Sim*Development*Workstation*"
}

variable "allowed_cidr_blocks" {
  description = "CIDR blocks allowed to reach SSH/DCV/WebRTC (use your public IP /32)"
  type        = list(string)
}

variable "extra_tcp_ports" {
  description = "Optional extra TCP ports to open to allowed CIDRs (e.g. broker 8000)"
  type        = list(number)
  default     = []
}

variable "key_name" {
  description = "Existing EC2 key pair name. Ignored if create_key_pair = true."
  type        = string
  default     = ""
}

variable "create_key_pair" {
  description = "If true, generate a TLS key and create an EC2 key pair"
  type        = bool
  default     = false
}

variable "public_key_path" {
  description = "Path to an existing public key to import when create_key_pair is false and key_name is empty"
  type        = string
  default     = ""
}

variable "use_default_vpc" {
  description = "Use the account default VPC and a public subnet"
  type        = bool
  default     = true
}

variable "subnet_id" {
  description = "Optional subnet ID when use_default_vpc = false"
  type        = string
  default     = ""
}

variable "vpc_id" {
  description = "Optional VPC ID when use_default_vpc = false"
  type        = string
  default     = ""
}

variable "associate_elastic_ip" {
  description = "Allocate and associate an Elastic IP for a stable DCV endpoint"
  type        = bool
  default     = true
}

variable "instance_name" {
  description = "Name tag for the EC2 instance"
  type        = string
  default     = "omniguard-isaac-sim"
}
