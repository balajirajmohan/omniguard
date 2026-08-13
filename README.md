# OmniGuard

Digital-twin red-team range for warehouse robot fleets.

NVIDIA Omniverse / Isaac Sim provides the physically accurate world. OmniGuard adds contextual identity, authorization, and containment so a compromised agent credential cannot turn into a physical incident.

> Attack the twin. Protect the real world.

## Architecture

```text
Operator / attack script
        │
        ▼
 OmniGuard identity broker (FastAPI + JWT policy)
        │
   ┌────┴────┐
   │ ALLOW   │ DENY + revoke + e-stop
   ▼         ▼
Isaac adapter   Security dashboard
   │
   ▼
Isaac Sim warehouse robot (Nova Carter)
```

## Hackathon runbook

**Start here for the full event path:** [docs/RUNBOOK.md](docs/RUNBOOK.md)

AWS Isaac Sim workstation (Terraform): [infra/terraform/README.md](infra/terraform/README.md)

## Quick start (Checkpoint B, no Isaac required)

### Option A — Dev Container (zero local setup)

Open in [VS Code](https://code.visualstudio.com/) with the [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers) or launch directly in [GitHub Codespaces](https://codespaces.new/balajirajmohan/omniguard):

1. Open the repo in VS Code
2. When prompted **"Reopen in Container"**, click it (or run **Dev Containers: Reopen in Container** from the command palette)
3. The container builds, installs all deps, and runs `honcho start` automatically

- **Broker API** → http://localhost:8000 *(forwarded automatically)*
- **Dashboard UI** → http://localhost:8501 *(opens in browser automatically)*

No Python, conda, or honcho installation needed on your machine.

### Option B — single command with honcho (local)

[honcho](https://honcho.readthedocs.io) reads the [`Procfile`](Procfile) and starts the broker + dashboard together in one terminal with colour-coded output.

```bash
# First time: create and activate a conda env, then install deps
conda create -n omniguard python=3.11 -y
conda activate omniguard
pip install -r requirements.txt   # installs honcho too

# Every time after: one command starts everything
honcho start
```

- **Broker API** → http://localhost:8000
- **Dashboard UI** → http://localhost:8501 *(open in browser)*

Press `Ctrl+C` to stop all services at once.

### Option C — manual terminals (fallback)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Terminal 1 — broker
uvicorn broker.main:app --reload --port 8000

# Terminal 2 — legitimate move
python clients/normal_client.py

# Terminal 3 — stolen token attack + reuse
python clients/attack_client.py --reuse

# Optional dashboard
streamlit run dashboard/app.py
```

**Checkpoint B:** normal client returns `ALLOW`; attack returns `DENY` + containment; reuse also fails.

## Isaac Sim (Checkpoint A)

Provision with Terraform (preferred):

```bash
# 1) Accept Marketplace terms:
# https://aws.amazon.com/marketplace/pp/prodview-bl35herdyozhw
# 2) Deploy
cd infra/terraform
cp terraform.tfvars.example terraform.tfvars   # set allowed_cidr_blocks + key
terraform init && terraform apply
```

Also see [docs/isaac-setup.md](docs/isaac-setup.md) and [docs/RUNBOOK.md](docs/RUNBOOK.md). Requires AWS `g6e.4xlarge` (L40S) — not available on macOS.

After the robot moves in simulation, wire [broker/isaac_adapter.py](broker/isaac_adapter.py) to Isaac Python scripting and enable with `OMNIGUARD_ISAAC_ENABLED=1`. Details: [docs/integration.md](docs/integration.md).

## Demo script

See [docs/demo-script.md](docs/demo-script.md). One-shot Checkpoint B (broker already running):

```bash
bash scripts/run_checkpoint_b.sh
```

## API surface

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Liveness |
| POST | `/tokens/demo-agent` | Issue legitimate fleet JWT |
| POST | `/tokens` | Issue custom JWT claims |
| POST | `/commands/move` | Contextual allow/deny + containment |
| GET | `/status` | Robot, revocations, events |
| GET | `/events` | Timeline |
| POST | `/demo/reset` | Clear demo state |

## Policy checks (in order)

1. Token valid and unrevoked
2. Identity allowed to control this robot
3. Destination zone permitted
4. Speed within `max_speed`
5. Device ID matches credential binding
6. Anomaly signals (human-zone intent, rogue device, command burst)

On compromise signals: deny command, revoke `jti`, quarantine identity, emergency-stop.
