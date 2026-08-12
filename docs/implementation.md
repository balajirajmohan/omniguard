# Implementation plan — feature.md against the current codebase

Each section lists exactly what changes, in which existing file, plus any
new file. Ordered by priority from [feature.md](feature.md). None of this
is built yet — this is the plan to build it.

## 1. Real device binding (crypto, not string)

**New:**
- `broker/devices.py` — `issue_device_secret(device_id) -> str` (random
  secret, stored server-side only), `verify_signature(device_id, payload,
  signature) -> bool` (recompute HMAC-SHA256 and compare).
- Add a device secret store to `broker/state.py` (`device_secrets: dict[str,
  str]`), separate from the revocation/quarantine sets already there.

**Changed:**
- `broker/models.py` — `CommandRequest` gains a `signature: str` field
  (hex-encoded HMAC). `device_id` stays, but now only identifies *which*
  secret to check against — it's no longer trusted on its own.
- `broker/policy.py` — replace the current
  `if request.device_id != claims.get("device_id")` string check with:
  look up the secret for `claims["device_id"]`, recompute the HMAC over
  the command payload, compare to `request.signature`. Mismatch (wrong
  secret, or no secret registered for that device) → `DEVICE_MISMATCH`,
  same severity as today.
- `broker/main.py` — `/token` (or a new `/devices/register` endpoint) also
  returns the freshly-generated device secret once, at provisioning time —
  exactly like a real system would hand a device its credential once and
  never repeat it.
- `scripts/normal_client.py`, `attack_client.py`, `dashboard/app.py` —
  normal client signs commands with the real secret; attack client either
  has no secret (simplest attack: signature check fails outright) or signs
  with a *wrong* secret to prove forged signatures are rejected even when
  `device_id` string matches.

**Effort:** small — one new module, one field on the request model, one
policy check swapped out.

## 2. Path/corridor checking

**New:**
- `broker/warehouse.py` — a small static map: `ZONE_ADJACENCY` (which zones
  border which) and/or named corridors, e.g. `CORRIDOR_A_TO_B = ["ZONE_A",
  "CORRIDOR_1", "ZONE_B"]`. Doesn't need real Isaac Sim geometry yet — a
  hardcoded graph is enough to demo the concept.

**Changed:**
- `broker/models.py` — `CommandRequest` gains `route: list[str] |
  None` (ordered list of zones the path crosses; optional, defaults to
  just `[target_zone]` for backward compatibility with today's demo).
- `broker/policy.py` — new check: for each zone in `route`, run the same
  zone-permission logic already applied to `target_zone` today. Any zone
  in the route failing that check produces the same `ZONE_NOT_PERMITTED` /
  `HUMAN_ZONE_UNAUTHORIZED` violations, attributed to that specific zone in
  the message.
- Once Isaac Sim is actually running (`isaac/warehouse_robot_demo.py`),
  the route can be computed from real waypoint geometry instead of the
  static graph — that's a follow-up once hardware is available, not
  blocking this feature's policy-side logic.

**Effort:** small-medium — mostly in the policy engine; real geometry
integration is a later, hardware-dependent step.

## 3. Graduated risk scoring

**Changed:**
- `broker/state.py` — track per-identity history needed for baselining:
  zones previously visited, typical speed range. A simple `dict[str,
  dict]` keyed by identity is enough; no new storage technology needed.
- `broker/policy.py` — `PolicyResult` gains a `risk_score: float` field.
  Compute it from weighted signals: `0.3` if zone is new for this identity,
  `0.2` if speed is within 10% of `max_speed`, `0.2` if device hasn't been
  seen for this identity before, `0.3` if outside a configured "normal
  hours" window. Sum, cap at 1.0.
- `broker/main.py` — branch on score instead of pure allow/deny: `< 0.4` →
  allow; `0.4–0.7` → allow but log a `"flagged"` event (visible on the
  dashboard, no containment); `> 0.7` → deny (existing containment path
  unchanged).
- `dashboard/app.py` — show the risk score per command/incident, and a
  distinct (yellow) "flagged" pill separate from the existing
  allow/deny/contained states.

**Effort:** medium — touches the policy engine's return shape and the
broker's branching logic, but no new external dependencies.

## 4. Tamper-evident audit log

**Changed:**
- `broker/state.py` — `record_incident` computes `entry_hash =
  sha256(prev_hash + json.dumps(incident_fields, sort_keys=True))` and
  stores `prev_hash` on each incident. First entry chains from a fixed
  genesis constant.
- `broker/main.py` — new `GET /audit/verify` endpoint: walk `state.incidents`
  in order, recompute each hash from its stored fields, compare to the
  next entry's `prev_hash`. Return `{"intact": bool, "broken_at":
  incident_id | None}`.
- `dashboard/app.py` — small "Audit trail: intact ✅ / broken ⚠️" indicator
  that calls `/audit/verify`.

**Effort:** small — pure addition, no changes to existing fields or
behavior, safe to build last.

## Suggested build order

1. Device binding (fixes a real, demoable gap in the existing attack story
   — the attack script can be extended to show "even with the right device
   *name*, no valid signature = still blocked").
2. Path/corridor checking (second-strongest differentiator, ties directly
   to having a digital twin).
3. Risk scoring (adds nuance to the demo without breaking the existing
   binary allow/deny checkpoint tests).
4. Tamper-evident audit log (additive, zero risk to existing behavior,
   good to do whenever there's spare time before the demo).
