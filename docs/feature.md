# Feature enhancements — overcoming the generic policy-engine competitors

None of these are built yet. This is the shortlist proposed to widen the gap
between OmniGuard and generic access-control products (Cerbos, Ping,
StrongDM) and the token-gated-robot-command prior art already found in
patents. See [implementation.md](implementation.md) for how each one maps
onto the existing code.

## 1. Real device binding (crypto, not string) — highest priority

**The gap it closes:** today `device_id` in `broker/policy.py` is just a
string the *client* includes in its own request body
(`broker/models.py`'s `CommandRequest.device_id`). An attacker who knows or
guesses the legitimate device's name (`"controller-01"`) can simply type it
into a forged request, and the current `DEVICE_MISMATCH` check passes for
free. It looks like a security control but isn't one — it's currently only
caught in the demo attack because the attack also targets `HUMAN_ZONE`,
which trips `ZONE_NOT_PERMITTED` independently.

**What it becomes:** each device is issued a secret at provisioning time
(never included in the JWT, never sent over the wire in plaintext). Every
command is signed with an HMAC of that secret over the command payload. The
broker recomputes the HMAC and rejects anything that doesn't match — an
attacker without the secret cannot forge a valid signature no matter how
much of the token or device name they know.

## 2. Path/corridor checking

**The gap it closes:** the current policy only checks the *destination*
zone. A route that starts and ends in permitted zones but cuts through
`HUMAN_ZONE` on the way would currently be allowed — a real safety gap, and
one no generic IAM/PBAC competitor could even notice, since none of them
have a concept of physical space or a route at all.

**What it becomes:** commands carry (or the broker derives, from Isaac
Sim's warehouse graph) the path the robot will travel, not just the
endpoint. The policy engine checks every zone the path crosses, not just
where it ends.

## 3. Graduated risk scoring

**The gap it closes:** the current engine is binary — ALLOW or DENY. A
command that's slightly off (e.g. speed 1% over limit, or a rarely-used but
technically-permitted zone) gets the same treatment as an outright attack.
Real-world security teams want a way to *notice* borderline behavior before
it becomes an incident.

**What it becomes:** every command gets a 0.0–1.0 risk score built from
multiple weak signals (unusual zone for this identity's history, speed near
the limit, first time seeing this device, time-of-day anomaly). Low risk →
allow. High risk → deny + contain (current behavior). Medium risk → allow
but flag, or require a step-up approval via the dashboard before executing.

## 4. Tamper-evident audit log

**The gap it closes:** the current incident log (`broker/state.py`,
`record_incident`) is a plain in-memory list — anyone with code access could
edit or delete an entry after the fact, silently. For a security product,
"the audit trail itself can be quietly rewritten" is a real credibility gap
that generic robot-control patents don't address either.

**What it becomes:** each incident record includes a hash of the previous
record plus its own content (a simple hash chain). Editing or deleting a
past entry breaks the chain from that point forward, and the broker can
expose a `/audit/verify` endpoint that walks the chain and reports whether
it's intact.

## Deliberately not doing (scope traps for this project stage)

- Live webhook/Slack alerting — nice polish, not a differentiator, easy to
  bolt on later without touching the policy engine.
- Full mTLS / PKI infrastructure for device identity — the HMAC approach in
  #1 gets 90% of the security value with a fraction of the setup cost.
- Multi-tenant / multi-fleet policy scoping — not relevant at single-demo
  scale.
