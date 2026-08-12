# Isaac Sim GPU host — Terraform (AWS)

Provisions a single EC2 GPU instance (default `g5.2xlarge`: 1x A10G, 24GB
VRAM, 32GB RAM — meets Isaac Sim's stated minimum with headroom), installs
the NVIDIA driver, and opens exactly two ports: SSH from your IP, and the
OmniGuard Isaac bridge (8899) from the broker's IP. It does **not** install
Isaac Sim itself — that's a large, interactive install you run by hand
after the instance is up (script is dropped on the box for you).

## Prerequisites

- AWS credentials configured (`aws configure` or env vars) with permission
  to create EC2 instances/security groups in the target account.
- An existing EC2 key pair in that region (`aws ec2 create-key-pair
  --key-name omniguard-isaac --query 'KeyMaterial' --output text >
  omniguard-isaac.pem && chmod 400 omniguard-isaac.pem`), if you don't
  already have one.
- A default VPC in the target region (most accounts have one; if not,
  `aws ec2 create-default-vpc` or point `main.tf` at an existing VPC/subnet).

## Usage

```bash
cd infra
cp terraform.tfvars.example terraform.tfvars
# edit terraform.tfvars: key_name, allowed_ssh_cidr, allowed_bridge_cidr

terraform init
terraform plan     # review before applying — this creates a billable GPU instance
terraform apply
```

`terraform apply` creates a real, billable AWS resource (a GPU instance
runs several dollars/hour). Review the plan output before confirming.

After apply:

```bash
terraform output ssh_command
terraform output isaac_bridge_url
```

SSH in, wait for `/home/ubuntu/BOOTSTRAP_DONE` to exist (driver install +
reboot takes a few minutes), then run `nvidia-smi` to confirm the GPU is
visible before installing Isaac Sim:

```bash
ssh -i <key>.pem ubuntu@<public_ip>
nvidia-smi
./install_isaac_sim.sh
```

Then follow [../isaac/README.md](../isaac/README.md) to run
`warehouse_robot_demo.py` and wire the broker to `isaac_bridge_url`.

## Tearing down

Stop paying for the GPU instance the moment you're done with it:

```bash
terraform destroy
```
