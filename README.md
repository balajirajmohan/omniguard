# OmniGuard

Cyber-physical security broker for warehouse robots inside an NVIDIA Isaac Sim digital twin.

A stolen fleet credential may still authenticate — OmniGuard checks identity context, Zero-Trust policy and behavioural anomaly risk, then **deterministically** blocks, stops, revokes and quarantines before unsafe motion becomes a physical incident.

> NVIDIA provides the physically accurate world. OmniGuard turns it into a cyber-physical red-team range.

## Two complementary paths (both preserved)

| Path | Use for | Entry point |
|------|---------|-------------|
| **Primary (event demo)** | Four-button judges demo, fake robot, IsolationForest, incident AI | `backend.main:app` on **:8000** |
| **JWT broker (Srikanth)** | JWT claims, replay/burst, mock/Isaac HTTP push adapter | `broker.main:app` on **:8001** |

```text
omniguard/
├── backend/          # Runbook API + anomaly + incident AI (+ optional Isaac push)
├── broker/           # Srikanth JWT broker + robot_adapter (preserved)
├── dashboard/        # Four-button Streamlit demo → backend :8000
├── simulator/        # fake_robot + isaac_bridge (poll contract)
├── isaac/            # Srikanth command_bridge + warehouse demo
├── infra/            # Srikanth g5 user_data stack + terraform/ Marketplace
├── scripts/          # run_demo.sh (primary) + JWT clients + run_jwt_broker.sh
└── tests/
```

## Quick start — primary hackathon demo (no GPU)

> **Local demo only:** the `:8000` backend uses a shared demo credential string, not signed JWTs. `scripts/run_demo.sh` binds **127.0.0.1**. Prefer Srikanth's JWT broker on `:8001` when you need claim verification.

```bash
bash scripts/setup.sh
bash scripts/run_demo.sh
```

| Surface | URL |
|---------|-----|
| Dashboard | http://127.0.0.1:8501 |
| API docs | http://127.0.0.1:8000/docs |

Buttons: **Reset** · **Normal** · **Attack — Protection OFF** · **Attack — OmniGuard ON**

```bash
pytest -q
```

## Srikanth JWT broker (preserved)

```bash
bash scripts/run_jwt_broker.sh
# other terminal:
BROKER_URL=http://127.0.0.1:8001 python scripts/normal_client.py
BROKER_URL=http://127.0.0.1:8001 python scripts/attack_client.py
```

Isaac push (either path) when the GPU bridge is up:

```bash
export OMNIGUARD_ROBOT_BACKEND=isaac
export ISAAC_BRIDGE_URL=http://<gpu-host>:8899
```

Primary backend will then both queue poll commands *and* call Srikanth's `IsaacRobotController`. JWT broker uses the same adapter directly.

## Decision scheme (primary backend)

```text
Protection OFF              -> ALLOW (unsafe path for judges)
Hard policy violation       -> BLOCK + contain
AI risk >= 0.80             -> BLOCK + contain
AI risk 0.60–0.79           -> HOLD
AI risk < 0.60              -> ALLOW
```

## Docs

- [docs/RUNBOOK.md](docs/RUNBOOK.md) — 22-hour event plan  
- [docs/ALIGNMENT.md](docs/ALIGNMENT.md) — how the trees were reconciled  
- [docs/demo-script.md](docs/demo-script.md)  
- [isaac/README.md](isaac/README.md) · [infra/README.md](infra/README.md) · [infra/terraform/README.md](infra/terraform/README.md)

## Honest judge line

> AI detects abnormal behaviour and explains incidents. Deterministic, auditable code performs the safety-critical block, stop and credential revocation.
