resource "aws_security_group" "isaac" {
  name_prefix = "${var.project_name}-isaac-"
  description = "OmniGuard Isaac Sim workstation (SSH, DCV, WebRTC)"
  vpc_id      = local.vpc_id

  tags = {
    Name = "${var.project_name}-isaac-sg"
  }

  lifecycle {
    create_before_destroy = true
  }
}

# SSH
resource "aws_vpc_security_group_ingress_rule" "ssh" {
  for_each = toset(var.allowed_cidr_blocks)

  security_group_id = aws_security_group.isaac.id
  description       = "SSH"
  cidr_ipv4         = each.value
  from_port         = 22
  to_port           = 22
  ip_protocol       = "tcp"
}

# Amazon DCV
resource "aws_vpc_security_group_ingress_rule" "dcv" {
  for_each = toset(var.allowed_cidr_blocks)

  security_group_id = aws_security_group.isaac.id
  description       = "Amazon DCV"
  cidr_ipv4         = each.value
  from_port         = 8443
  to_port           = 8443
  ip_protocol       = "tcp"
}

# Isaac WebRTC signaling
resource "aws_vpc_security_group_ingress_rule" "webrtc_signal" {
  for_each = toset(var.allowed_cidr_blocks)

  security_group_id = aws_security_group.isaac.id
  description       = "Isaac Sim WebRTC signaling"
  cidr_ipv4         = each.value
  from_port         = 49100
  to_port           = 49100
  ip_protocol       = "tcp"
}

# Isaac WebRTC media
resource "aws_vpc_security_group_ingress_rule" "webrtc_media" {
  for_each = toset(var.allowed_cidr_blocks)

  security_group_id = aws_security_group.isaac.id
  description       = "Isaac Sim WebRTC media"
  cidr_ipv4         = each.value
  from_port         = 47998
  to_port           = 47998
  ip_protocol       = "udp"
}

# Optional extra TCP (e.g. OmniGuard broker :8000)
resource "aws_vpc_security_group_ingress_rule" "extra_tcp" {
  for_each = {
    for pair in setproduct(var.allowed_cidr_blocks, var.extra_tcp_ports) :
    "${pair[0]}-${pair[1]}" => {
      cidr = pair[0]
      port = pair[1]
    }
  }

  security_group_id = aws_security_group.isaac.id
  description       = "OmniGuard extra TCP ${each.value.port}"
  cidr_ipv4         = each.value.cidr
  from_port         = each.value.port
  to_port           = each.value.port
  ip_protocol       = "tcp"
}

resource "aws_vpc_security_group_egress_rule" "all_ipv4" {
  security_group_id = aws_security_group.isaac.id
  description       = "Allow all outbound"
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
}
