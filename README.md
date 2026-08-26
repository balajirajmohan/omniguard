# OmniGuard

Runtime security and governance for autonomous robots and physical AI.

OmniGuard sits between a controller and a robot. Before a machine moves, it evaluates the credential, agent, device, robot, physical zone, speed, and behavioral context. Unsafe commands can be blocked and contained through credential revocation, identity quarantine, session termination, and an emergency stop.

This repository is a hackathon prototype that runs with either a local fake robot or an NVIDIA Isaac Sim digital twin.

## Purpose

A robot credential can be valid and still be misused. A stolen or replayed credential may pass traditional authentication while requesting an unsafe action from a rogue device or through an abnormal control sequence.

OmniGuard demonstrates continuous authorization for physical systems: every command is checked at runtime, behavioral anomalies are scored, and deterministic containment is applied before cyber risk becomes a physical incident.

For the hackathon, the project provides a safe cyber-physical red-team range. The core demo shows:

- A valid credential used from an unknown controller to target a restricted human zone at unsafe speed.
- Individually valid base, arm, and gripper actions forming an abnormal manipulation sequence that hard rules alone would miss.
- The difference between an unprotected command path and OmniGuard enforcement.

## How it works

![OmniGuard operator console](assets/flow.png)

Safety-critical actions remain in deterministic, allowlisted code. AI scores behavior, while an optional LLM only explains incidents after containment. Neither can override hard policy or directly issue robot movement commands.

Implemented capabilities include:

- Zero-Trust checks for credential state, agent, device, robot, geofence, and speed.
- Behavioral scoring for individual commands and multi-action manipulation windows.
- Teleoperation leases, sequence validation, rate limits, and a deadman stop.
- Attack scenarios covering rogue devices, geofencing, overspeed, bursts, replay, AI-only anomalies, and malicious manipulation.
- Deterministic containment playbooks and durable incident evidence with investigation, feedback, and simulated recovery.
- Mock and Isaac Sim adapters behind an authenticated command bridge.

The browser communicates only with the OmniGuard API. It never receives the Isaac bridge credential or controls the simulator directly.

## Target industries and use cases

| Industry | Use case |
| --- | --- |
| Warehousing and logistics | Protect AMR fleets from rogue control, restricted-zone entry, replay, and unsafe speed. |
| Manufacturing | Govern mobile manipulators and robotic-cell actions using identity and safety context. |
| Healthcare robotics | Constrain service robots to approved areas and detect unusual behavior. |
| Critical infrastructure | Control autonomous inspection systems where incorrect actions could disrupt essential operations. |

## Run locally

Requirements: Python 3.10 or later, Node.js 20.19 or later, and a Bash-compatible shell. Isaac Sim is optional.

### 1. Start the API and local robot

From the repository root:

```bash
bash scripts/setup.sh
bash scripts/run_demo.sh
```

This starts the API, fake robot, and Streamlit fallback dashboard.

| Service | Address |
| --- | --- |
| Streamlit dashboard | http://127.0.0.1:8501 |
| API documentation | http://127.0.0.1:8000/docs |
| API health | http://127.0.0.1:8000/health |

Keep this terminal running.

### 2. Start the live operator console

In a second terminal:

```bash
cd ui-controller
npm ci
npm run dev
```

Open http://127.0.0.1:5173. The console provides legitimate and rogue control planes, keyboard and gamepad input, scenarios, decision traces, incident review, and session export.

### Optional paths

- Product site: run `npm ci && npm run dev` in `landing/`, then open http://localhost:5174. Its `/demo` route is a scripted preview by default.
- Isaac Sim: launch the bridge from `isaac/warehouse_robot_demo.py`, then run `bash scripts/run_isaac_services.sh`. See [isaac/README.md](isaac/README.md).
- Signed-JWT broker: run `bash scripts/run_jwt_broker.sh` to start the separate broker on port `8001`.

## Demo

![OmniGuard operator console](assets/demo1.gif)

![OmniGuard operator console](assets/demo2.gif)

## Test

```bash
source .venv/bin/activate
pytest -q

cd ui-controller
npm test
npm run build
```

## Project layout

```text
backend/        policy, AI scoring, teleoperation, containment, incidents
ui-controller/ live React operator and red-team console
dashboard/      Streamlit fallback dashboard
simulator/      local fake robot
isaac/          Isaac Sim warehouse and command bridge
broker/         optional JWT command broker
landing/        product site and scripted preview
scripts/        setup, launch, training, and demo utilities
tests/          backend, UI, containment, and bridge tests
```

## Scope

OmniGuard is a demonstrator, not a production robot safety system or certified controller. The default API uses local demo credentials and should remain on a private development machine. Production use would require hardened device identity, fleet-specific adapters, distributed state, network isolation, and independent safety certification.
