"""OmniGuard security dashboard — Streamlit."""

from __future__ import annotations

import os
from datetime import datetime

import httpx
import streamlit as st

BASE_URL = os.getenv("OMNIGUARD_BASE_URL", "http://127.0.0.1:8000")

st.set_page_config(
    page_title="OmniGuard",
    page_icon=None,
    layout="wide",
)

st.markdown(
    """
    <style>
      .block-container { padding-top: 1.5rem; }
      .og-title { font-size: 2rem; font-weight: 700; letter-spacing: -0.02em; }
      .og-sub { color: #5b6570; margin-bottom: 1rem; }
      .pill {
        display: inline-block; padding: 0.25rem 0.7rem; border-radius: 999px;
        font-size: 0.85rem; font-weight: 600;
      }
      .pill-allow { background: #d1fae5; color: #065f46; }
      .pill-deny { background: #fee2e2; color: #991b1b; }
      .pill-idle { background: #e5e7eb; color: #374151; }
      .pill-contained { background: #fecaca; color: #7f1d1d; }
    </style>
    """,
    unsafe_allow_html=True,
)


def api_get(path: str):
    with httpx.Client(base_url=BASE_URL, timeout=5.0) as client:
        r = client.get(path)
        r.raise_for_status()
        return r.json()


def api_post(path: str, json=None, headers=None):
    with httpx.Client(base_url=BASE_URL, timeout=5.0) as client:
        r = client.post(path, json=json, headers=headers)
        return r


st.markdown('<div class="og-title">OmniGuard</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="og-sub">Digital-twin red-team range — contextual AuthZ for warehouse robots</div>',
    unsafe_allow_html=True,
)

col_a, col_b, col_c = st.columns([1, 1, 1])
with col_a:
    if st.button("Refresh status", use_container_width=True):
        st.rerun()
with col_b:
    if st.button("Reset demo", use_container_width=True):
        api_post("/demo/reset")
        st.success("Demo state reset")
        st.rerun()
with col_c:
    st.caption(f"Broker: `{BASE_URL}`")

try:
    status = api_get("/status")
except Exception as exc:  # noqa: BLE001
    st.error(f"Cannot reach broker at {BASE_URL}: {exc}")
    st.stop()

robot = status["robot"]
status_class = "pill-contained" if robot["status"] == "CONTAINED" else "pill-idle"

left, right = st.columns([1.2, 1])
with left:
    st.subheader("Robot status")
    st.markdown(
        f'<span class="pill {status_class}">{robot["status"]}</span>',
        unsafe_allow_html=True,
    )
    m1, m2, m3 = st.columns(3)
    m1.metric("Robot", robot["robot_id"])
    m2.metric("Zone", robot["zone"])
    m3.metric("Speed", f'{robot["speed"]} m/s')
    st.write("Last command:", robot.get("last_command") or "—")
    if robot.get("quarantined_identity"):
        st.error(f"Quarantined identity: `{robot['quarantined_identity']}`")

with right:
    st.subheader("Containment")
    st.write("Revoked tokens:", len(status["revoked_tokens"]))
    st.write("Quarantined identities:", ", ".join(status["quarantined_identities"]) or "—")
    st.json({"zones": status["zones"]})

st.divider()
st.subheader("Live demo controls")

c1, c2 = st.columns(2)
with c1:
    st.markdown("**Normal operator**")
    if st.button("ALLOW: move to ZONE_B", type="primary", use_container_width=True):
        tok = api_post("/tokens/demo-agent").json()
        move = api_post(
            "/commands/move",
            json={
                "robot_id": "robot-01",
                "destination_zone": "ZONE_B",
                "speed": 1.0,
                "device_id": tok["claims"]["device_id"],
            },
            headers={"Authorization": f"Bearer {tok['access_token']}"},
        ).json()
        st.session_state["last_decision"] = move
        st.rerun()

with c2:
    st.markdown("**Attack: stolen token + rogue controller → HUMAN_ZONE**")
    if st.button("DENY: launch attack", use_container_width=True):
        tok = api_post("/tokens/demo-agent").json()
        move = api_post(
            "/commands/move",
            json={
                "robot_id": "robot-01",
                "destination_zone": "HUMAN_ZONE",
                "speed": 1.2,
                "device_id": "rogue-controller",
            },
            headers={"Authorization": f"Bearer {tok['access_token']}"},
        ).json()
        st.session_state["last_decision"] = move
        st.rerun()

if "last_decision" in st.session_state:
    decision = st.session_state["last_decision"]
    pill = "pill-allow" if decision.get("decision") == "ALLOW" else "pill-deny"
    st.markdown(
        f'### Last decision '
        f'<span class="pill {pill}">{decision.get("decision")}</span>',
        unsafe_allow_html=True,
    )
    if decision.get("contained"):
        st.error(
            f"**Critical: Credential compromise detected**  \n"
            f"`{decision.get('identity')}` attempted to move "
            f"`{decision['command']['robot_id']}` into "
            f"`{decision['command']['destination_zone']}` from "
            f"`{decision['command']['device_id']}`. "
            f"Command blocked, credential revoked, robot contained."
        )
    st.json(decision)

st.divider()
st.subheader("Event timeline")
events = status.get("recent_events") or []
if not events:
    st.info("No events yet. Run a normal move or attack.")
else:
    for ev in events:
        ts = ev.get("timestamp", "")
        try:
            ts = datetime.fromisoformat(ts.replace("Z", "+00:00")).strftime("%H:%M:%S")
        except Exception:  # noqa: BLE001
            pass
        decision = ev.get("decision") or "—"
        st.markdown(
            f"**{ts}** · `{ev.get('event_type')}` · `{decision}` · risk `{ev.get('risk_score', 0):.2f}`  \n"
            f"{ev.get('message')}"
        )
