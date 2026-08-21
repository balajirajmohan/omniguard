# OmniGuard

Cyber-physical security broker for warehouse robots inside an NVIDIA Isaac Sim digital twin.

A stolen fleet credential may still authenticate — OmniGuard checks identity context, Zero-Trust policy and behavioural anomaly risk, then **deterministically** blocks, stops, revokes and quarantines before unsafe motion becomes a physical incident.

> NVIDIA provides the physically accurate world. OmniGuard turns it into a cyber-physical red-team range.

## Aligned layout (hackathon MVP)

```text
omniguard/
├── backend/          # FastAPI: policy + IsolationForest + incident AI
├── dashboard/        # Four-button Streamlit demo
├── simulator/        # fake_robot.py + isaac_bridge.py (same HTTP contract)
├── isaac/            # GPU-day helpers (command bridge / warehouse starter)
├── tests/
├── docs/RUNBOOK.md   # 22-hour event runbook
├── infra/terraform/  # Preferred AWS Isaac Marketplace workstation
├── requirements.txt
├── .env.example
└── Procfile
```

## Quick start (no GPU)

```bash
bash scripts/setup.sh
bash scripts/run_demo.sh
```

Or with honcho:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
honcho start
```

Open:

| Surface | URL |
|---------|-----|
| Dashboard | http://127.0.0.1:8501 |
| API docs | http://127.0.0.1:8000/docs |
| Health | http://127.0.0.1:8000/health |

### Four-button demo

1. **Normal Operation** — ALLOW; fake robot moves to `SAFE_ZONE_B`
2. **Attack — Protection OFF** — dangerous command reaches the robot (before/after)
3. **Attack — OmniGuard ON** — BLOCK; stop; revoke; quarantine; incident explanation
4. **Reset Demo** — restore baseline

```bash
pytest -q
```

## API contract (source of truth)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Liveness |
| POST | `/api/reset` | Reset demo state |
| POST | `/api/commands` | Evaluate a movement command |
| POST | `/api/demo/normal` | Scripted normal path |
| POST | `/api/demo/attack?protection=` | Scripted attack ON/OFF |
| GET | `/api/state` | Dashboard state |
| GET | `/api/events` | Evidence timeline |
| GET | `/api/robots/robot-01/next-command` | Simulator poll |
| POST | `/api/robots/robot-01/telemetry` | Simulator ack |

## Decision scheme

```text
Protection OFF              -> ALLOW (unsafe path for judges)
Hard policy violation       -> BLOCK + contain
AI risk >= 0.80             -> BLOCK + contain
AI risk 0.60–0.79           -> HOLD
AI risk < 0.60              -> ALLOW
```

Safety-critical block/stop/revoke is **deterministic**. IsolationForest scores risk; Bedrock/Claude (optional) only explains incidents.

```bash
export LLM_PROVIDER=bedrock
export AWS_REGION=ap-south-1
export BEDROCK_MODEL_ID=your-claude-model-id
```

## Isaac Sim

1. Prove the laptop demo first (`fake_robot`).
2. On GPU: load a small warehouse + one mobile robot; implement TODOs in [`simulator/isaac_bridge.py`](simulator/isaac_bridge.py).
3. Stop `fake_robot` so only Isaac consumes the command queue.
4. Optional helpers: [`isaac/`](isaac/) (in-process HTTP bridge / warehouse starter).

GPU day-zero: [docs/isaac-setup.md](docs/isaac-setup.md) · Terraform: [infra/terraform/README.md](infra/terraform/README.md)

## Docs

- **Event runbook:** [docs/RUNBOOK.md](docs/RUNBOOK.md)
- **Alignment notes:** [docs/ALIGNMENT.md](docs/ALIGNMENT.md)
- **Demo script:** [docs/demo-script.md](docs/demo-script.md)

## Honest judge line

> AI detects abnormal behaviour and explains incidents. Deterministic, auditable code performs the safety-critical block, stop and credential revocation.
