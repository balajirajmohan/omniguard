# OmniGuard — Terraform: Isaac Sim AWS workstation

Provisions a **g6e.4xlarge** NVIDIA Isaac Sim Development Workstation (Linux) with security group, optional Elastic IP, and key pair.

Official NVIDIA guide: [AWS Deployment](https://docs.isaacsim.omniverse.nvidia.com/latest/installation/install_advanced_cloud_setup_aws.html)  
Marketplace: [Isaac Sim Development Workstation (Linux)](https://aws.amazon.com/marketplace/pp/prodview-bl35herdyozhw)

## Prerequisites

1. AWS credentials with EC2 permissions.
2. GPU quota for `g6e.4xlarge` in the target region (`ap-south-1` recommended).
3. **Accept Marketplace terms** for the Isaac Sim Linux AMI (one-time per account).
4. Terraform >= 1.5.

```bash
# Discover AMI after subscription
bash ../../scripts/discover_isaac_ami.sh ap-south-1
```

## Deploy

```bash
cd infra/terraform
cp terraform.tfvars.example terraform.tfvars
# Edit allowed_cidr_blocks to YOUR_PUBLIC_IP/32
# Set create_key_pair = true  OR  key_name / public_key_path

terraform init
terraform plan
terraform apply
terraform output
```

## After apply

```bash
# From terraform output ssh_command / dcv_url
ssh -i omniguard-isaac.pem ubuntu@<public_ip>
sudo passwd ubuntu
sudo dcv list-sessions
```

Open NICE DCV → `https://<public_ip>:8443`, then:

```bash
sudo chown -R ubuntu:root /opt/IsaacSim
cd ~/IsaacSim
./post_install.sh
./warmup.sh
./isaac-sim.sh
```

Full sequence: [docs/RUNBOOK.md](../../docs/RUNBOOK.md).

## Cost hygiene

```bash
# Stop compute when idle (keep disk) — use AWS Console Stop, or:
aws ec2 stop-instances --instance-ids $(terraform output -raw instance_id)

# Tear down after the hackathon
terraform destroy
```

## Variables of note

| Variable | Default | Notes |
|----------|---------|-------|
| `instance_type` | `g6e.4xlarge` | 1× L40S, 128 GiB; use `g6e.2xlarge` if quota blocked |
| `root_volume_gb` | `1024` | Marketplace minimum guidance ≥ 512 |
| `allowed_cidr_blocks` | *(required)* | Team public IPs `/32` |
| `extra_tcp_ports` | `[]` | Add `8000` only if broker must be remote |
| `ami_id` | `""` | Set explicitly if name filter finds nothing |

## Security

Inbound SSH (22), DCV (8443), WebRTC (49100/tcp, 47998/udp) are limited to `allowed_cidr_blocks`. Do not use `0.0.0.0/0` for hackathon DCV/WebRTC.
