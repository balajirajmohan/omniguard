data "aws_vpc" "default" {
  count   = var.use_default_vpc ? 1 : 0
  default = true
}

data "aws_subnets" "default_public" {
  count = var.use_default_vpc ? 1 : 0

  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default[0].id]
  }

  filter {
    name   = "default-for-az"
    values = ["true"]
  }
}

locals {
  vpc_id    = var.use_default_vpc ? data.aws_vpc.default[0].id : var.vpc_id
  subnet_id = var.use_default_vpc ? data.aws_subnets.default_public[0].ids[0] : var.subnet_id
}

check "network_configured" {
  assert {
    condition     = local.vpc_id != "" && local.subnet_id != ""
    error_message = "VPC and subnet must be set. Use use_default_vpc=true or pass vpc_id and subnet_id."
  }
}
