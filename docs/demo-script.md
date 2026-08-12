# OmniGuard Demo Script (one page)

**Pitch line:** NVIDIA helps customers test whether robots work. OmniGuard tests what happens when the identities controlling those robots are compromised.

## Setup (2 minutes)

1. Start the broker: `uvicorn broker.main:app --reload --port 8000`
2. Optional dashboard: `streamlit run dashboard/app.py`
3. Reset state: `curl -X POST http://127.0.0.1:8000/demo/reset`

## Demo flow (3 minutes)

### 1. Normal operator (safe)

```bash
python clients/normal_client.py
```

**Say:** A valid fleet agent on the bound controller moves `robot-01` Zone A → Zone B.

**Show:** Decision `ALLOW`, robot status `MOVING` / zone `ZONE_B`.

### 2. Attack without OmniGuard (story beat)

**Say:** The same stolen JWT is valid. Without contextual guardrails, the attacker sends the robot into `HUMAN_ZONE` from `rogue-controller` — a cyber event becomes a physical near-miss.

*(On Isaac: optionally show the unsafe path once with the broker bypassed / adapter direct.)*

### 3. Attack with OmniGuard (winning moment)

```bash
python clients/attack_client.py --reuse
```

**Say:** Token signature is still valid — but OmniGuard sees device mismatch + restricted-zone intent.

**Show:**

- Decision `DENY`
- Reasons: `device_mismatch`, `human_zone_breach` / `zone_forbidden`
- Credential `jti` revoked, identity quarantined
- Robot action `STUB_ESTOP` / contained
- Incident card: *Critical: Credential compromise detected*

### 4. Blocked reuse

The `--reuse` flag immediately resends the same token.

**Show:** Second `DENY` (`token_revoked` or `identity_quarantined`). Containment sticks.

## Close

> Omniverse gives us the physically accurate world. OmniGuard turns it into a cyber-physical red-team range — inject the attack, measure blast radius, validate guardrails, produce evidence the fleet is safe to deploy.

## Reset between rehearsals

```bash
curl -X POST http://127.0.0.1:8000/demo/reset
```

Run the exact demo at least five times. Record a backup video once A+B are green on Isaac.
