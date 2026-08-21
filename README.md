# OmniGuard

Browser-operated cyber-physical red-team range for robot identity attacks inside an NVIDIA Isaac Sim digital twin.

A stolen fleet credential may still authenticate. OmniGuard checks identity context, Zero-Trust policy and behavioural anomaly risk, then **deterministically** blocks, stops, revokes and quarantines before unsafe motion becomes a physical incident.

> NVIDIA provides the physically accurate world. OmniGuard turns it into a cyber-physical red-team range.

## Status (honest)

| Layer                                | Status                                                            |
| ------------------------------------ | ----------------------------------------------------------------- |
| Zero-Trust policy + containment      | Working                                                           |
| IsolationForest anomaly risk         | Working                                                           |
| Four-button + scenario dashboard     | Working (browser)                                                 |
| Fake-robot laptop path               | Working (no GPU)                                                  |
| Isaac Sim 6.0.1 move / e-stop bridge | Proven on AWS L40S (`:8899`); new composite awaits GPU acceptance |
| Real Claude / OpenAI explanation     | Optional via env; defaults to labeled fallback                    |
| Mac browser via SSM port-forward     | Documented — run on operator laptop                               |
| Production IAM / fleet controller    | Out of scope for hackathon                                        |

**Safety boundary:** AI may score and explain. Physical stop, revoke and quarantine stay in deterministic allowlisted code. An LLM never issues robot movement commands.

## Architecture

```text
Mac browser (preferred operator UI)
  -> AWS SSM port-forward localhost:8501
  -> Streamlit dashboard on EC2
  -> FastAPI OmniGuard API :8000
  -> policy + IsolationForest (+ optional LLM explanation)
  -> Isaac actuation adapter
  -> Isaac CommandBridge :8899
  -> iw.hub + UR10e + Robotiq 2F-140 in Isaac Sim
```

Laptop / CI path uses the same API with `simulator/fake_robot.py` instead of Isaac.

## Two preserved API paths

| Path                                | Port     | Role                                                                      |
| ----------------------------------- | -------- | ------------------------------------------------------------------------- |
| **Primary demo** `backend.main:app` | **8000** | Four-button + scenario catalog, anomaly, incident AI, optional Isaac push |
| **JWT broker** `broker.main:app`    | **8001** | Srikanth JWT `/token` + `/command`, replay/burst, `robot_adapter`         |

## Quick start — laptop (no GPU)

```bash
bash scripts/setup.sh
# or on AWS: bash scripts/getomni.sh
bash scripts/run_demo.sh
pytest -q
```

| Surface   | URL                        |
| --------- | -------------------------- |
| Dashboard | http://127.0.0.1:8501      |
| API docs  | http://127.0.0.1:8000/docs |

Judge buttons: **Reset** · **Normal** · **Attack - Protection OFF** · **Attack - OmniGuard ON**

Also available in the UI: scenario library (rogue device, geofence, speed, burst, combined, revoked replay).

## Isaac path (AWS GPU / DCV)

1. Close extra Isaac GUIs — keep one scene.
2. From a **DCV** terminal (needs `DISPLAY`):

```bash
/opt/IsaacSim/python.sh /home/ubuntu/omniguard/isaac/warehouse_robot_demo.py
# wait for: OmniGuard Isaac bridge listening on :8899
```

3. In another shell (do **not** use `run_demo.sh` — it starts the fake robot):

```bash
bash scripts/run_isaac_services.sh
```

4. From your Mac, forward the dashboard: [docs/MAC_ACCESS.md](docs/MAC_ACCESS.md)

Isaac Sim **6.0.1** robot assets (committed):

```text
/Isaac/Robots/Idealworks/iwhub/iw_hub.usd
/Isaac/Robots/UniversalRobots/ur10e/ur10e.usd
/Isaac/Robots/Robotiq/2F-140/Robotiq_2F_140_config.usd
```

The script assembles these bundled assets at runtime. See
[`isaac/README.md`](isaac/README.md) for mount overrides and the required GPU
visual/MOVE/STOP acceptance checks.

## Optional LLM explanation

```bash
# .env / shell — never commit keys
export LLM_PROVIDER=openai          # or bedrock | fallback
export OPENAI_API_KEY=...
export OPENAI_MODEL=gpt-4o-mini
# Bedrock:
# export LLM_PROVIDER=bedrock
# export BEDROCK_MODEL_ID=...
# export AWS_REGION=...
```

UI discloses provider/model and whether fallback was used.

## JWT broker (preserved)

```bash
bash scripts/run_jwt_broker.sh
BROKER_URL=http://127.0.0.1:8001 python scripts/normal_client.py
BROKER_URL=http://127.0.0.1:8001 python scripts/attack_client.py
```

## Decision scheme (primary backend)

```text
Protection OFF              -> ALLOW (unsafe comparison for judges)
Hard policy violation       -> BLOCK + contain
AI risk >= 0.80             -> BLOCK + contain (unknown behavioral threat)
AI risk 0.60–0.79           -> HOLD
AI risk < 0.60              -> ALLOW
OMNIGUARD_AI_ENFORCE=false  -> AI scores in shadow mode (no block)
```

### Judge AI narrative (rules vs ML)

1. **Learn normal** — IsolationForest trained only on synthetic normal fleet commands (`scripts/generate_training_data.py` + `scripts/train_anomaly_model.py`).
2. **Normal** — rules pass, low AI risk → ALLOW.
3. **Known compromise** — rogue device / restricted zone / excessive speed → hard policy DENY (AI also high).
4. **Unknown anomaly** — valid token, known device, allowed zone, speed under max → rules would allow; AI risk blocks (`/api/demo/anomaly`).

> Rules stop known unsafe actions. AI learns normal fleet behavior and surfaces attacks we did not pre-program. An LLM may explain afterward; it never moves the robot.

```bash
python scripts/generate_training_data.py
python scripts/train_anomaly_model.py
```

## Repo layout

```text
backend/     primary demo API, scenarios, anomaly, incident AI
broker/      JWT broker + robot_adapter (preserved)
dashboard/   Streamlit operator UI
simulator/   fake_robot (+ poll contract)
isaac/       CommandBridge + mobile-manipulator assembly + warehouse demo
scripts/     setup, run_demo, run_isaac_services, getomni, JWT clients
docs/        RUNBOOK, MAC_ACCESS, ALIGNMENT, demo script
tests/       FastAPI contract tests
```

## Docs

- [docs/RUNBOOK.md](docs/RUNBOOK.md) — event plan
- [docs/MAC_ACCESS.md](docs/MAC_ACCESS.md) — Mac → EC2 via SSM
- [docs/ALIGNMENT.md](docs/ALIGNMENT.md) — dual-path reconciliation
- [docs/demo-script.md](docs/demo-script.md)
- [isaac/README.md](isaac/README.md)

## Judge line

> OmniGuard executes attack scenarios against an Isaac Sim digital twin, uses behavioural risk and zero-trust context to detect compromised control, and performs policy-constrained containment before the same failure can reach live hardware.

AI detects and explains; deterministic code performs the safety-critical block, stop and credential revocation.
