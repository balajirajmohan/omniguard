output "instance_id" {
  description = "EC2 instance ID"
  value       = aws_instance.isaac.id
}

output "public_ip" {
  description = "Public IP for SSH and DCV"
  value       = local.public_ip
}

output "ami_id" {
  description = "AMI used for the workstation"
  value       = local.ami_id
}

output "instance_type" {
  value = aws_instance.isaac.instance_type
}

output "security_group_id" {
  value = aws_security_group.isaac.id
}

output "key_name" {
  value = local.resolved_key_name
}

output "ssh_command" {
  description = "SSH into the workstation as ubuntu"
  value       = "ssh -i ${var.create_key_pair ? "${path.module}/omniguard-isaac.pem" : "<your.pem>"} ubuntu@${local.public_ip}"
}

output "dcv_url" {
  description = "Open in NICE DCV Client or browser"
  value       = "https://${local.public_ip}:8443"
}

output "next_steps" {
  value = <<-EOT
    1. ssh -i <pem> ubuntu@${local.public_ip}
    2. sudo passwd ubuntu
    3. sudo dcv list-sessions
    4. Open DCV: https://${local.public_ip}:8443
    5. cd ~/IsaacSim && ./post_install.sh && ./warmup.sh && ./isaac-sim.sh
    See docs/RUNBOOK.md Phase 0.
  EOT
}
