# Resolve NVIDIA Isaac Sim Development Workstation (Linux) AMI.
# Prerequisite: accept Marketplace terms for prodview-bl35herdyozhw in this account/region.

data "aws_ami" "isaac_sim" {
  count = var.ami_id == "" ? 1 : 0

  most_recent = true
  owners      = ["aws-marketplace"]

  filter {
    name   = "name"
    values = [var.ami_name_filter]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }

  filter {
    name   = "architecture"
    values = ["x86_64"]
  }

  filter {
    name   = "state"
    values = ["available"]
  }
}

locals {
  ami_id = var.ami_id != "" ? var.ami_id : data.aws_ami.isaac_sim[0].id
}
