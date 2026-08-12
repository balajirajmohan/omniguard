# Key material: create new, import from file, or use existing key_name.

resource "tls_private_key" "isaac" {
  count = var.create_key_pair ? 1 : 0

  algorithm = "RSA"
  rsa_bits  = 4096
}

resource "aws_key_pair" "generated" {
  count = var.create_key_pair ? 1 : 0

  key_name   = "${var.project_name}-isaac"
  public_key = tls_private_key.isaac[0].public_key_openssh
}

resource "local_sensitive_file" "private_key" {
  count = var.create_key_pair ? 1 : 0

  content         = tls_private_key.isaac[0].private_key_pem
  filename        = "${path.module}/omniguard-isaac.pem"
  file_permission = "0600"
}

resource "aws_key_pair" "imported" {
  count = !var.create_key_pair && var.key_name == "" && var.public_key_path != "" ? 1 : 0

  key_name   = "${var.project_name}-isaac"
  public_key = file(var.public_key_path)
}

locals {
  resolved_key_name = (
    var.create_key_pair ? aws_key_pair.generated[0].key_name :
    var.key_name != "" ? var.key_name :
    var.public_key_path != "" ? aws_key_pair.imported[0].key_name :
    null
  )
}

check "key_pair_configured" {
  assert {
    condition     = local.resolved_key_name != null
    error_message = "Configure a key pair: set create_key_pair=true, or key_name, or public_key_path."
  }
}

resource "aws_instance" "isaac" {
  ami                         = local.ami_id
  instance_type               = var.instance_type
  subnet_id                   = local.subnet_id
  vpc_security_group_ids      = [aws_security_group.isaac.id]
  key_name                    = local.resolved_key_name
  associate_public_ip_address = true

  root_block_device {
    volume_type           = "gp3"
    volume_size           = var.root_volume_gb
    delete_on_termination = true
    encrypted             = true
  }

  metadata_options {
    http_endpoint = "enabled"
    http_tokens   = "required"
  }

  tags = {
    Name = var.instance_name
  }

  lifecycle {
    ignore_changes = [ami]
  }
}

resource "aws_eip" "isaac" {
  count  = var.associate_elastic_ip ? 1 : 0
  domain = "vpc"

  tags = {
    Name = "${var.project_name}-isaac-eip"
  }
}

resource "aws_eip_association" "isaac" {
  count = var.associate_elastic_ip ? 1 : 0

  instance_id   = aws_instance.isaac.id
  allocation_id = aws_eip.isaac[0].id
}

locals {
  public_ip = var.associate_elastic_ip ? aws_eip.isaac[0].public_ip : aws_instance.isaac.public_ip
}
