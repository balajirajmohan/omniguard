# OmniGuard 22-Hour Hackathon Runbook

## 1. Freeze the MVP

Build exactly this:

1. A small warehouse scene in NVIDIA Isaac Sim.
2. One mobile robot called `robot-01`.
3. A normal fleet agent sends a permitted movement command.
4. An attacker reuses a valid credential and sends an abnormal command toward `RESTRICTED_ZONE` at excessive speed.
5. OmniGuard evaluates identity, policy and anomaly risk.
6. OmniGuard blocks the command, stops the simulated robot, revokes the credential and records an incident.
7. Claude or OpenAI explains the incident on a dashboard.

Do not build multiple robots, Kubernetes, ROS, Kafka, a custom warehouse, robot training, facial recognition or a locally hosted LLM.

## 2. Definition of Done

The project is complete when these four buttons work:

- `Reset Demo`
- `Normal Operation`
- `Attack - Protection OFF`
- `Attack - OmniGuard ON`

Expected results:

| Button                  | Expected result                                        |
| ----------------------- | ------------------------------------------------------ |
| Normal Operation        | Robot moves safely; command is allowed                 |
| Attack - Protection OFF | Dangerous command reaches the simulated robot          |
| Attack - OmniGuard ON   | Command is blocked; robot stops; credential is revoked |
| Reset Demo              | Robot and credential return to their initial states    |

### Live AWS / Isaac (judge path)

1. Laptop/mock: `bash scripts/run_demo.sh` (starts fake robot — fine for CI).
2. Isaac: launch `isaac/warehouse_robot_demo.py` in DCV until `:8899` listens, then `bash scripts/run_isaac_services.sh` (**no** fake robot).
3. Mac UI: SSM port-forward — see [MAC_ACCESS.md](MAC_ACCESS.md).
4. Isaac 6.0.1 robot: assemble bundled iw.hub + UR10e + Robotiq 2F-140 assets;
   complete the mount/MOVE/STOP checks in [isaac-setup.md](isaac-setup.md).

Do not call the product "complete" after curl smoke tests alone — judges need the browser scenario flow.

## 3. Assign Owners Now

For a three-person team:

| Owner            | Responsibility                    | First checkpoint                         |
| ---------------- | --------------------------------- | ---------------------------------------- |
| Simulator owner  | GPU access and Isaac Sim          | Robot moves and stops using Python       |
| Security owner   | FastAPI, policy and anomaly model | Normal request allowed; attack blocked   |
| Experience owner | Streamlit, LLM, story and slides  | Dashboard shows normal and attack events |

For a two-person team, combine Security and Experience. Only one person should work inside the Isaac Sim graphical session.

## 4. Create One Shared Repository

Use one existing GitHub/GitLab repository if available. Create a clean branch for the event.

Suggested layout:

```text
omniguard/
├── backend/
│   ├── main.py
│   ├── policy.py
│   ├── anomaly.py
│   └── incident_ai.py
├── dashboard/
│   └── app.py
├── simulator/
│   ├── fake_robot.py
│   └── isaac_bridge.py
├── data/
├── tests/
├── requirements.txt
├── .env.example
└── README.md
```

Every owner works on a separate branch and commits after every successful checkpoint. Do not attempt a complicated repository-history repair during the event; use a new clean repository if necessary.

## 5. Start the Backend on a Laptop Immediately

Do this even if GPU access has not arrived.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install fastapi uvicorn streamlit requests pydantic pyjwt scikit-learn pandas numpy joblib plotly boto3 python-dotenv
```

Start with an in-memory state object:

```python
STATE = {
    "protection_enabled": True,
    "credential_status": "ACTIVE",
    "robot_status": "STOPPED",
    "robot_zone": "SAFE_ZONE",
    "events": [],
}
```

Create these API endpoints:

| Method | Endpoint                            | Purpose                                    |
| ------ | ----------------------------------- | ------------------------------------------ |
| `GET`  | `/health`                           | Confirms backend is alive                  |
| `POST` | `/api/reset`                        | Resets robot, credential and events        |
| `POST` | `/api/commands`                     | Evaluates and queues a movement command    |
| `GET`  | `/api/robots/robot-01/next-command` | Simulator fetches the next allowed command |
| `POST` | `/api/robots/robot-01/telemetry`    | Simulator reports position/status          |
| `GET`  | `/api/state`                        | Dashboard reads current state              |
| `GET`  | `/api/events`                       | Dashboard reads the event timeline         |

Run it:

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

Verify:

```bash
curl http://localhost:8000/health
```

Expected:

```json
{"status": "ok"}
```

Checkpoint A: Do not continue until `/health` works.

## 6. Define the Two Commands

Normal command:

```json
{
  "credential": "fleet-agent-valid-token",
  "agent_id": "fleet-agent-01",
  "device_id": "fleet-controller-01",
  "robot_id": "robot-01",
  "destination": "SAFE_ZONE_B",
  "speed": 0.8
}
```

Attack command:

```json
{
  "credential": "fleet-agent-valid-token",
  "agent_id": "fleet-agent-01",
  "device_id": "unknown-attacker-device",
  "robot_id": "robot-01",
  "destination": "RESTRICTED_ZONE",
  "speed": 3.5
}
```

Important: the attack uses the same valid credential. This proves that token validation alone is insufficient.

## 7. Implement Deterministic Zero-Trust Policies

Evaluate every command independently.

Rules:

1. Credential must be active and unexpired.
2. Agent must be authorized for `robot-01`.
3. Device must be expected or explicitly trusted.
4. Destination must be within the agent's permitted zones.
5. Speed must be at or below `1.5`.
6. A revoked credential must never be accepted again.

Decision order:

```text
Invalid/revoked credential -> BLOCK
Unauthorized robot         -> BLOCK
Restricted destination     -> BLOCK
Excessive speed            -> BLOCK
Otherwise                  -> ask anomaly detector
```

When blocked, execute deterministic containment:

```text
Reject command
Clear command queue
Set robot action to STOP
Set credential status to REVOKED
Set agent status to QUARANTINED
Write incident event
Notify dashboard
```

Checkpoint B: Send the two JSON requests with `curl` or Swagger at `http://localhost:8000/docs`. Normal must return `ALLOW`; attack must return `BLOCK`.

## 8. Add a Real but Small AI Anomaly Detector

Use scikit-learn `IsolationForest`. Do not train a foundation model.

Generate approximately 500 normal synthetic commands with:

- Speed between `0.3` and `1.2`
- Known device equal to `1`
- Restricted destination equal to `0`
- Commands in last 10 seconds between `0` and `3`
- Previous failures between `0` and `1`

Model features:

```text
speed
known_device
restricted_destination
commands_last_10_seconds
previous_failures
```

Train once at startup or save with `joblib`. Convert the model result into a clear `risk_score` between `0.0` and `1.0`.

Use this final decision scheme:

```text
Hard policy violation -> BLOCK regardless of AI
AI risk >= 0.80       -> BLOCK and contain
AI risk 0.60-0.79     -> HOLD
AI risk < 0.60        -> ALLOW
```

The dashboard must separately display:

- `policy_decision`
- `anomaly_risk_score`
- `final_decision`
- `containment_actions`

Checkpoint C: Demonstrate a valid-looking command from an unknown device receiving a high anomaly score.

## 9. Build a Fake Robot Before Isaac Sim Integration

Create `simulator/fake_robot.py`. It should poll the backend every second.

Behaviour:

```text
If next command is MOVE -> update position and print MOVING
If next command is STOP -> set status STOPPED
If no command           -> wait one second
```

The fake robot proves the complete security workflow without GPU dependency.

Checkpoint D: Run backend + fake robot. Normal command changes the fake position. Attack command leaves it stopped.

## 10. Check the GPU Environment

As soon as access arrives, run:

```bash
nvidia-smi
free -h
df -h
python3 --version
docker --version
git --version
```

Record the GPU, free memory and disk space in the team chat.

For AWS:

1. Install/open the NICE DCV client if required.
2. Connect using the supplied host and credentials.
3. Open Isaac Sim from the provided workstation desktop/application menu.
4. Do not reinstall NVIDIA drivers.

For Brev:

1. Redeem the credit.
2. Select the organizer-recommended Isaac Sim environment/Launchable.
3. Prefer an L40S/RTX-class GPU.
4. Start the instance and connect using the provided method.
5. Confirm Isaac Sim is installed before changing the environment.

If Isaac Sim does not launch within 30 minutes, notify the organizer with the exact error and continue using the fake robot.

Checkpoint E: Isaac Sim opens and displays a blank or sample stage.

## 11. Create the Isaac Sim Scene

Use an existing small warehouse scene. Do not create the building manually.

Add only:

- One existing wheeled/mobile robot
- A start point
- `SAFE_ZONE_B`
- `RESTRICTED_ZONE`
- One mannequin/human obstacle if readily available
- One camera/viewport

Use simple visual floor markers or signs for the zones. Exact physical realism is less important than a visible security outcome.

Checkpoint F: Press Play and confirm the scene runs without crashing.

## 12. Control One Robot in Isaac Sim

Before networking, create a Python script that can:

```text
reset_robot()
move_robot_to_safe_zone()
move_robot_to_restricted_zone()
stop_robot()
```

Scripted waypoint movement is acceptable. The robot does not need autonomous navigation or reinforcement learning.

Checkpoint G: From Python, make the robot move and stop. Record a short backup video immediately.

## 13. Connect Isaac Sim to OmniGuard

Use simple HTTP polling. Do not introduce ROS unless the scene already depends on it and the team knows it.

Every 0.5-1 second, `isaac_bridge.py` calls:

```http
GET /api/robots/robot-01/next-command
```

Interpret responses:

```text
MOVE SAFE_ZONE_B      -> move to safe waypoint
MOVE RESTRICTED_ZONE  -> move to restricted waypoint
STOP                  -> immediately set zero velocity/stop controller
NONE                  -> do nothing
```

The bridge posts status back to:

```http
POST /api/robots/robot-01/telemetry
```

If the backend and Isaac Sim are on different machines:

1. Bind FastAPI to `0.0.0.0`.
2. Use the backend machine's reachable IP address.
3. Test `curl http://BACKEND_IP:8000/health` from the GPU workstation.
4. If port access is blocked, run the backend on the GPU workstation or use an SSH tunnel.

Checkpoint H: A normal dashboard/API command visibly moves the Isaac robot.

## 14. Build the Streamlit Dashboard

Run:

```bash
streamlit run dashboard/app.py --server.port 8501
```

The top of the dashboard should show:

- `Robot: robot-01`
- `Robot status: STOPPED/MOVING/CONTAINED`
- `Credential: ACTIVE/REVOKED`
- `Protection: ON/OFF`

Add four buttons:

1. `Reset Demo`
2. `Run Normal Operation`
3. `Run Attack - Protection OFF`
4. `Run Attack - OmniGuard ON`

Show the latest decision using large colours:

- Green: `ALLOWED`
- Red: `BLOCKED`
- Amber: `HELD FOR REVIEW`

Show an event table with timestamp, agent, device, robot, destination, speed, policy result, risk score and action.

Checkpoint I: All four buttons call the backend and update the event timeline.

## 15. Add Claude or OpenAI Last

Use one runtime LLM only. Do not put the LLM in the robot-control path.

After containment, send the incident JSON to Claude through Bedrock or to OpenAI and request strict JSON:

```json
{
  "summary": "...",
  "physical_impact": "...",
  "why_suspicious": ["..."],
  "containment_taken": ["..."],
  "recommended_actions": ["..."]
}
```

System instruction:

```text
You are OmniGuard's cyber-physical incident analyst. Explain only from the supplied evidence. Do not invent facts. Do not issue robot movement commands. Return the requested JSON structure.
```

If the LLM API fails, show a deterministic incident template. The security block must continue working without the LLM.

Checkpoint J: A blocked attack produces a readable incident explanation within the dashboard.

## 16. Exact Demo Script

Narrator says:

> This robot is controlled by a legitimate fleet agent. OmniGuard evaluates every command using identity context, safety policy and behavioural anomaly detection.

Click `Normal Operation`:

> The identity, device, destination and behaviour are expected, so the command is allowed.

Click `Reset`, then `Attack - Protection OFF`:

> The attacker has stolen a valid agent credential. Traditional authentication accepts it, and the robot begins an unsafe movement toward a restricted human zone.

Click `Reset`, then `Attack - OmniGuard ON`:

> This time OmniGuard sees a valid credential but an unknown device, abnormal speed and restricted destination. It blocks the command, stops the robot, revokes the credential and quarantines the agent.

Show the AI explanation:

> The incident agent now converts the technical evidence into physical-impact analysis and remediation guidance. The LLM explains the event; it is not allowed to control the robot.

Close with:

> NVIDIA provides the physically accurate digital twin. OmniGuard turns it into a cyber-physical red-team and pre-deployment security assurance range.

## 17. Timeline

| Time       | Required outcome                                                                  |
| ---------- | --------------------------------------------------------------------------------- |
| Hour 0-1   | Roles assigned; repository ready; GPU smoke test started; backend `/health` works |
| Hour 1-3   | Normal allowed and attack blocked through API; fake robot works                   |
| Hour 3-6   | Isaac scene loads; robot moves and stops using Python                             |
| Hour 6-9   | Isaac bridge receives allowed and stop commands                                   |
| Hour 9-12  | Dashboard buttons and timeline work                                               |
| Hour 12-14 | IsolationForest and risk display work                                             |
| Hour 14-16 | Claude/OpenAI explanation works                                                   |
| Hour 16-18 | UI polish and complete demo rehearsal                                             |
| Hour 18-20 | Slides, architecture and backup recording                                         |
| Hour 20-22 | Freeze code; rehearse; export evidence and video                                  |

If more than two hours behind, remove features. Never move the final rehearsal deadline.

## 18. Failure Ladder

| Failure                        | Immediate fallback                                     |
| ------------------------------ | ------------------------------------------------------ |
| No GPU allocation              | Continue backend/dashboard/fake robot                  |
| Isaac Sim installation problem | Use organizer's AMI/Launchable; do not rebuild drivers |
| Warehouse too heavy            | Blank floor plus shelves/cubes and one robot           |
| Robot navigation fails         | Script transform/waypoint movement                     |
| Network connection fails       | Run backend on GPU workstation                         |
| IsolationForest misbehaves     | Keep hard policies; show anomaly score as secondary    |
| LLM credentials fail           | Use deterministic incident template                    |
| Live demo unstable             | Play backup video and show live dashboard/API          |

## 19. Evidence to Save

Before the environment is terminated, save:

- Source repository and final commit hash
- Final USD scene or scene-setup script
- Trained anomaly model or deterministic training script
- Screenshots of normal and blocked events
- One complete backup demo video
- Architecture slide
- Incident JSON and AI explanation
- README with startup commands

## 20. Final Architecture Statement

```text
Command source
    -> OmniGuard API
        -> token and identity checks
        -> Zero-Trust safety policies
        -> IsolationForest anomaly score
        -> deterministic allow/block/containment
            -> Isaac Sim robot bridge
            -> event store and dashboard
            -> Claude/OpenAI incident explanation
```

The accurate statement for judges is:

> AI identifies abnormal behaviour and explains incidents. Deterministic, auditable code performs the safety-critical block, stop and credential revocation.
