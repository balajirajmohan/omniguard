# OmniGuard Demo Script (3 minutes)

**Pitch:** In IT, a stolen credential exposes data. In physical AI, it can move machinery. OmniGuard proves dangerous identity misuse is contained inside an NVIDIA digital twin before real robots or people are at risk.

## Setup

```bash
bash scripts/run_demo.sh
# Dashboard http://127.0.0.1:8501
```

## Act 1 — Normal

Click **Normal Operation**.

> Known fleet identity and controller request Zone B at normal speed. Policy and behaviour look expected, so the command is allowed.

Show: `ALLOW`, robot moves / arrives `SAFE_ZONE_B`.

## Act 2 — Unprotected

Click **Reset**, then **Attack — Protection OFF**.

> The attacker reuses a *valid* agent credential from a rogue device toward a restricted human zone at excessive speed. Traditional authentication would accept it — the robot begins unsafe movement.

Show: `ALLOW` with `BYPASSED`, fake robot prints danger / enters `RESTRICTED_ZONE`.

## Act 3 — OmniGuard ON

Click **Reset**, then **Attack — OmniGuard ON**.

> Same valid credential, but OmniGuard sees unknown device, restricted destination and abnormal speed/behaviour. It blocks the command, stops the robot, revokes the credential and quarantines the agent.

Show: `BLOCK`, risk score, revoke/quarantine, incident analyst text.

## Close

> NVIDIA provides the physically accurate digital twin. OmniGuard turns it into a cyber-physical red-team and pre-deployment security assurance range.
>
> AI detects and explains. Deterministic code performs the safety-critical block, stop and revocation.
