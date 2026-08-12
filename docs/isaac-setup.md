# Checkpoint A — Isaac Sim Day-Zero Checklist

Complete this **before** the 22-hour hackathon clock. Stop and fix any failed step before continuing.

macOS cannot run Isaac Sim locally. Use AWS.

## 1. Cloud prerequisites

- [ ] AWS account with billing / credits (~USD 200 recommended)
- [ ] EC2 GPU service quota approved for `g6e.4xlarge` in `ap-south-1` (Mumbai)
- [ ] AWS Marketplace subscription: **NVIDIA Isaac Sim Development Workstation** (Linux)
- [ ] EC2 key pair created
- [ ] Security group restricted to team IPs:

| Port | Purpose |
|------|---------|
| TCP 22 | SSH |
| TCP 8443 | Amazon DCV |
| TCP 49100 | WebRTC (if used) |
| UDP 47998 | WebRTC (if used) |

## 2. Provision the workstation (Terraform)

**Preferred:** use [infra/terraform](../infra/terraform) — see that README and [RUNBOOK.md](RUNBOOK.md) Phase 0.

```bash
# Accept Marketplace terms first:
# https://aws.amazon.com/marketplace/pp/prodview-bl35herdyozhw
cd infra/terraform
cp terraform.tfvars.example terraform.tfvars
# set allowed_cidr_blocks = ["YOUR.IP/32"] and create_key_pair = true
terraform init && terraform apply
bash ../../scripts/discover_isaac_ami.sh ap-south-1   # if AMI lookup fails
```

| Setting | Value |
|---------|-------|
| Instance | `g6e.4xlarge` (On-Demand, not Spot) |
| GPU | 1× NVIDIA L40S (~44 GiB usable) |
| vCPU / RAM | 16 / 128 GiB |
| Region | `ap-south-1` (Mumbai) |
| Storage | 1 TB gp3 SSD |
| AMI | NVIDIA Isaac Sim Linux Marketplace image |

After launch:

1. Connect from Mac via **Amazon DCV** (port 8443).
2. Confirm NVIDIA driver and GPU are visible (`nvidia-smi`).
3. Launch **Isaac Sim 6.0**.

## 3. Simulation smoke test

1. Load a bundled warehouse USD, for example:
   - `small_warehouse_digital_twin.usd`
   - `warehouse.usd`
   - `warehouse_with_forklifts.usd`
2. Add a bundled mobile robot (e.g. **Nova Carter**). Do not import a custom robot.
3. Mark three destinations: `ZONE_A`, `ZONE_B`, `HUMAN_ZONE`.
4. Run one Isaac Python movement example so the robot visibly moves Zone A → Zone B.
5. Download warehouse / robot assets **locally on the instance** so demos do not wait on network loads.

## 4. Checkpoint A (must be green)

- [ ] Isaac Sim launches successfully
- [ ] Warehouse scene loads
- [ ] One mobile robot appears
- [ ] Python script moves robot Zone A → Zone B
- [ ] Mac can reach the GPU machine over DCV
- [ ] Git repo accessible on the instance

**If Checkpoint A is not green, do not spend demo time on dashboard polish.**

## 5. Cost hygiene

- Stop the instance when nobody is working.
- Set AWS Budget alarms (e.g. ₹8,000 and ₹11,000 / USD equivalents).
- Keep code and USD paths on EBS/Git; local NVMe can be lost after stop.
- Terminate and delete unused volumes after the event.

## 6. OmniGuard integration note

Once Checkpoint A and Checkpoint B (broker ALLOW/DENY) both pass, point the broker's Isaac adapter at the control script on this workstation. Denied commands must never reach the robot controller; on containment, send zero-velocity / emergency-stop.
