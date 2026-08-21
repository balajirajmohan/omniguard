variable "aws_region" {
  description = "AWS region to provision the Isaac Sim GPU host in."
  type        = string
  default     = "us-east-1"
}

variable "instance_type" {
  description = "GPU instance type. g5.2xlarge = 1x A10G (24GB VRAM), 8 vCPU, 32GB RAM — meets Isaac Sim's stated 16GB VRAM / 32GB RAM minimum with headroom."
  type        = string
  default     = "g5.2xlarge"
}

variable "root_volume_size_gb" {
  description = "Root EBS volume size. Isaac Sim plus cached USD assets easily exceeds the default 8-30GB Ubuntu images ship with."
  type        = number
  default     = 200
}

variable "key_name" {
  description = "Name of an existing EC2 key pair to associate for SSH access. Create one in the AWS console/CLI first — Terraform does not manage the private key."
  type        = string
}

variable "allowed_ssh_cidr" {
  description = "CIDR allowed to SSH into the instance on port 22. Set this to your own IP (e.g. \"203.0.113.4/32\"), never 0.0.0.0/0."
  type        = string
}

variable "allowed_bridge_cidr" {
  description = "CIDR allowed to reach the OmniGuard Isaac bridge on port 8899. Set this to the broker's IP/CIDR — the bridge has no auth of its own."
  type        = string
}

variable "name_prefix" {
  description = "Prefix for resource names/tags."
  type        = string
  default     = "omniguard-isaac-sim"
}
