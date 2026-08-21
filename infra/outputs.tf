output "public_ip" {
  description = "Public IP of the Isaac Sim GPU host."
  value       = aws_instance.isaac_sim.public_ip
}

output "ssh_command" {
  description = "SSH command to reach the instance."
  value       = "ssh -i <path-to-key>.pem ubuntu@${aws_instance.isaac_sim.public_ip}"
}

output "isaac_bridge_url" {
  description = "Set this as ISAAC_BRIDGE_URL on the machine running the OmniGuard broker, once warehouse_robot_demo.py is running on this host."
  value       = "http://${aws_instance.isaac_sim.public_ip}:8899"
}
