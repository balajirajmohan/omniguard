# OmniGuard

A security broker for robot fleet commands. A robot control token can be
technically valid and still be misused — OmniGuard checks identity, robot
authorization, destination zone, speed, device binding and command
behavior (replay/burst) on every command, and contains the credential the
moment something looks like a compromise.

## Status

- `broker/`, `scripts/`, `dashboard/` — done, tested locally, no GPU needed.
- `isaac/` — written against Isaac Sim 6.0's documented API, not yet run on
  real hardware. See [isaac/README.md](isaac/README.md) and
  [docs/cloud_gpu_setup.md](docs/cloud_gpu_setup.md) before touching it.
- `infra/` — Terraform for the AWS GPU instance Isaac Sim needs (this repo's
  dev machine is macOS, which can't run Isaac Sim at all). Syntax-validated
  with `terraform validate`, not yet applied against a real AWS account.
  See [infra/README.md](infra/README.md) — `terraform apply` creates a
  real, billable GPU instance, so that step is left for you to run and
  confirm deliberately.

## Run the broker + demo locally (no Isaac Sim required)

### Option A — Dev Container (zero local setup)

Open in [VS Code](https://code.visualstudio.com/) with the [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers), or launch in GitHub Codespaces:

1. Open the repo in VS Code.
2. When prompted **"Reopen in Container"**, click it (or run **Dev Containers: Reopen in Container** from the command palette).
3. The container builds, installs dependencies, and runs `honcho start` automatically via `.devcontainer/devcontainer.json`.

- **Broker API** → http://localhost:8000 *(forwarded automatically)*
- **Dashboard UI** → http://localhost:8501 *(opens in browser automatically)*

### Option B — one command with honcho (local)

[honcho](https://honcho.readthedocs.io) reads the [`Procfile`](Procfile) and starts the broker + dashboard together with colour-coded output.

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt   # installs honcho too

honcho start
```

Press `Ctrl+C` to stop both services at once.

### Option C — manual terminals

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

uvicorn broker.main:app --reload   # terminal 1

python3 scripts/normal_client.py   # terminal 2 — expect ALLOW
python3 scripts/attack_client.py   # terminal 2 — expect DENY, then DENY again (revoked)
```

## Dashboard

```bash
streamlit run dashboard/app.py
```

Buttons trigger the same normal/attack flows as the scripts, and render the
live incident feed, revoked-token count and quarantined-identity list.

## Wiring in real Isaac Sim

By default the broker uses `MockRobotController` (logs moves, no sim).
Once Isaac Sim is running on a GPU host with the bridge from `isaac/`:

```bash
export OMNIGUARD_ROBOT_BACKEND=isaac
export ISAAC_BRIDGE_URL=http://<gpu-host-ip>:8899
uvicorn broker.main:app --reload
```

## Security model

See the policy engine in [broker/policy.py](broker/policy.py). Every
`/command` request is checked for: token validity/expiry, revocation,
identity quarantine, robot authorization, zone permission (with `HUMAN_ZONE`
requiring an explicit `human_zone_authorized` claim even if listed), speed
limit, device binding, replay, and command burst. Any "critical" violation
(the ones that indicate misuse rather than a benign error) triggers full
containment: revoke the token's `jti`, quarantine the identity, emergency-
stop the robot, and log a red incident card.
