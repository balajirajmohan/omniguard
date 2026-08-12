# OmniGuard Hackathon Runbook

End-to-end steps from zero to judging demo. Keep this open during the event.

Related docs:
- [Isaac day-zero checklist](isaac-setup.md)
- [Terraform AWS workstation](../infra/terraform/README.md)
- [Broker ↔ Isaac integration](integration.md)
- [3-minute demo script](demo-script.md)

---

## Roles (assign before hour 0)

| Role | Owns |
|------|------|
| Simulation | AWS Terraform, Isaac Sim, robot move, e-stop |
| Security | FastAPI broker, JWT policy, clients |
| UI / pitch | Streamlit dashboard, slides, talk track |
| Integration | Wire adapter, demo reset, rehearsal |

---

## Phase 0 — Prerequisites (before the 22-hour clock)

### 0.1 Accounts and tools

- [ ] AWS account + ~USD 200 credits / budget alarms
- [ ] EC2 GPU quota for `g6e.4xlarge` in `ap-south-1`
- [ ] Terraform `>= 1.5` and AWS CLI v2 on the laptop that will apply infra
- [ ] AWS credentials configured (`aws configure` or env vars)
- [ ] NICE DCV Client installed on Mac: https://www.nice-dcv.com/
- [ ] NVIDIA Developer Program membership (required for Isaac Sim license)
- [ ] GitHub access to this repo for the whole team

### 0.2 Subscribe to the Marketplace AMI (required once)

Terraform cannot skip Marketplace terms.

1. Open [NVIDIA Isaac Sim Development Workstation (Linux)](https://aws.amazon.com/marketplace/pp/prodview-bl35herdyozhw).
2. **View purchase options** → **Accept Terms** (software is $0; you pay EC2 only).
3. Wait until subscription shows as active.
4. Optional: discover the AMI ID for your region:

```bash
bash scripts/discover_isaac_ami.sh ap-south-1
```

### 0.3 Deploy the GPU workstation with Terraform

```bash
cd infra/terraform
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars:
#   allowed_cidr_blocks = ["YOUR.PUBLIC.IP/32"]
#   key_name            = "omniguard-isaac"   # existing key, OR
#   create_key_pair     = true + public_key_path
#   ami_id              = "ami-..."           # if auto-discover fails

terraform init
terraform plan
terraform apply
```

Save outputs:

```bash
terraform output
# public_ip, dcv_url, ssh_command, instance_id
```

### 0.4 First login (Checkpoint A start)

Per [NVIDIA AWS deployment docs](https://docs.isaacsim.omniverse.nvidia.com/latest/installation/install_advanced_cloud_setup_aws.html):

```bash
# SSH (from terraform output)
ssh -i <your.pem> ubuntu@<public_ip>

# Set DCV password (required every new instance)
sudo passwd ubuntu
sudo dcv list-sessions   # expect a console session
```

On your Mac, open DCV Client → `https://<public_ip>:8443` → user `ubuntu` → password you set.

### 0.5 Launch Isaac Sim on the instance

In a terminal **inside DCV**:

```bash
sudo chown -R ubuntu:root /opt/IsaacSim
cd ~/IsaacSim   # or /opt/IsaacSim per AMI layout
./post_install.sh
./warmup.sh     # may take 15+ minutes — do this before the clock
./isaac-sim.sh
```

Then:

1. Load a bundled warehouse USD (`warehouse.usd` / small warehouse digital twin).
2. Add **Nova Carter** (do not build a custom robot).
3. Mark `ZONE_A`, `ZONE_B`, `HUMAN_ZONE`.
4. Run one Python move: Zone A → Zone B.
5. Download assets locally on the instance.

### 0.6 Checkpoint A gate

- [ ] Isaac Sim launches
- [ ] Warehouse visible
- [ ] Robot moves A → B
- [ ] DCV usable from team Macs (CIDRs allowlisted)

**Do not start the 22-hour clock until Checkpoint A is green.**

### 0.7 Mac security track (Checkpoint B) — can run in parallel

On any laptop:

```bash
cd omniguard
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

uvicorn broker.main:app --reload --port 8000
# other terminals:
python clients/normal_client.py
python clients/attack_client.py --reuse
streamlit run dashboard/app.py
```

Checkpoint B:

- [ ] Normal → `ALLOW`
- [ ] Attack → `DENY` + `contained: true`
- [ ] Reuse → `DENY` (`token_revoked`)

---

## Phase 1 — Hours 0–3: Stabilize simulation

**Owner: Simulation**

1. Confirm instance still running (`aws ec2 describe-instances` or Terraform state).
2. Re-open DCV; re-launch Isaac if needed.
3. Rehearse A→B move until it is reliable under 60 seconds.
4. Document the exact scene path and robot prim path in a shared note.
5. Soft-stop the instance only if the team is idle (`terraform apply -var='instance_state=stopped'` if configured, or AWS Console Stop — keep EBS).

---

## Phase 2 — Hours 3–7: Harden the broker

**Owner: Security**

1. Clone/pull latest OmniGuard on all laptops.
2. Rehearse Checkpoint B until muscle memory.
3. Confirm policy reasons show: `device_mismatch`, `human_zone_breach` / `zone_forbidden`.
4. Practice `POST /demo/reset` between runs.
5. Optional: run broker on the GPU box too (same repo) so Isaac adapter is local.

```bash
curl -X POST http://127.0.0.1:8000/demo/reset
bash scripts/run_checkpoint_b.sh
```

---

## Phase 3 — Hours 7–12: Wire broker → Isaac

**Owner: Integration + Simulation**

1. Implement `_send_to_isaac` / `_send_estop_to_isaac` in `broker/isaac_adapter.py` (see [integration.md](integration.md)).
2. Start broker on the workstation:

```bash
export OMNIGUARD_ISAAC_ENABLED=1
uvicorn broker.main:app --host 0.0.0.0 --port 8000
```

3. From a laptop (or localhost on the GPU box):

```bash
python clients/normal_client.py --base-url http://<gpu-ip>:8000
# Security group must allow TCP 8000 from team CIDRs if remote
```

4. Prove:

- [ ] `ALLOW` moves the real Isaac robot
- [ ] `DENY` never moves it
- [ ] Containment triggers e-stop / zero velocity

If remote broker access is needed, add port 8000 in Terraform `extra_tcp_ports` and re-apply (keep source = team `/32` only).

---

## Phase 4 — Hours 12–16: Detection moment

**Owners: Simulation + UI**

1. Place a human / restricted zone marker in the twin (`HUMAN_ZONE`).
2. Optional before/after: once bypass adapter to show near-miss; then same attack through OmniGuard.
3. Dashboard shows red incident card with identity, zone, device, revoke.
4. Capture one screenshot of DENY + contained robot.

---

## Phase 5 — Hours 16–19: Polish

**Owner: UI / pitch**

1. Follow [demo-script.md](demo-script.md) word-for-word.
2. Streamlit open on projector laptop; Isaac DCV on second screen.
3. Write one-slide architecture + value line:

> NVIDIA tests whether robots work. OmniGuard tests compromised identities controlling those robots.

4. Record a **backup video** of the full flow.

---

## Phase 6 — Hours 19–22: Rehearse and protect

1. Run the exact demo **five times** from a clean reset.
2. Freeze code; no new features.
3. Prepare failover: if Isaac dies, run Checkpoint B only + backup video.
4. Cost: stop GPU instance when not rehearsing.

```bash
# After the event
cd infra/terraform
terraform destroy   # or stop instance and delete later
```

---

## Day-of demo checklist (print this)

```text
[ ] GPU instance RUNNING
[ ] DCV connected; Isaac scene loaded; robot at ZONE_A
[ ] Broker up (OMNIGUARD_ISAAC_ENABLED=1 if wired)
[ ] Dashboard open; POST /demo/reset done
[ ] normal_client → ALLOW (robot moves)
[ ] attack_client --reuse → DENY + revoke + e-stop
[ ] Pitch close sentence ready
[ ] Backup video on USB/local disk
```

---

## Cost and safety rules

- Prefer **Mumbai** (`ap-south-1`) for latency from India.
- Use **On-Demand** `g6e.4xlarge` (1× L40S, 128 GiB RAM).
- Restrict SG to team `IP/32` — never `0.0.0.0/0` on DCV/WebRTC if avoidable.
- Stop instance when idle; destroy after hackathon.
- Budget alarms: set in AWS Budgets (~USD 100 and USD 180).

---

## Failure modes

| Problem | Action |
|---------|--------|
| Marketplace AMI not found | Accept terms; set `ami_id` from `discover_isaac_ami.sh` |
| GPU quota | Request limit increase early; fallback `g6e.2xlarge` |
| DCV login fails | Re-SSH, `sudo passwd ubuntu`, check port 8443 |
| Isaac warmup forever | Start warmup before clock; keep instance warm |
| Adapter not ready | Demo Checkpoint B + video; still pitch value |
| Port 8000 unreachable | Run clients on GPU box over DCV terminal |

---

## Quick command cheat sheet

```bash
# Terraform
cd infra/terraform && terraform apply
terraform output dcv_url

# Broker (Mac)
uvicorn broker.main:app --reload --port 8000
streamlit run dashboard/app.py

# Demo
python clients/normal_client.py
python clients/attack_client.py --reuse
curl -X POST http://127.0.0.1:8000/demo/reset

# Isaac (on GPU box via DCV)
cd ~/IsaacSim && ./isaac-sim.sh
```
