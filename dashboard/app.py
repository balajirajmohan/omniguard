import time
import uuid

import requests
import streamlit as st

BROKER_URL = "http://localhost:8000"

st.set_page_config(page_title="OmniGuard", layout="wide")
st.title("OmniGuard — Fleet Command Security Dashboard")


def issue_token(device_id: str, human_zone_authorized: bool = False) -> str:
    resp = requests.post(
        f"{BROKER_URL}/token",
        json={
            "sub": "fleet-agent-01",
            "robots": ["robot-01"],
            "zones": ["ZONE_A", "ZONE_B"],
            "max_speed": 1.5,
            "device_id": device_id,
            "human_zone_authorized": human_zone_authorized,
            "ttl_seconds": 3600,
        },
    )
    resp.raise_for_status()
    return resp.json()["token"]


def send_command(token: str, device_id: str, target_zone: str, x: float, y: float, speed: float):
    payload = {
        "token": token,
        "command_id": str(uuid.uuid4()),
        "robot_id": "robot-01",
        "device_id": device_id,
        "target_zone": target_zone,
        "target_x": x,
        "target_y": y,
        "speed": speed,
    }
    resp = requests.post(f"{BROKER_URL}/command", json=payload)
    return resp.json()


def get_state() -> dict:
    resp = requests.get(f"{BROKER_URL}/state")
    resp.raise_for_status()
    return resp.json()


col_left, col_right = st.columns([1, 1])

with col_left:
    st.subheader("Send commands")

    st.markdown("**Legitimate fleet agent**")
    if st.button("Move robot-01 to ZONE_B (normal)"):
        token = issue_token(device_id="controller-01")
        result = send_command(token, "controller-01", "ZONE_B", x=10.0, y=4.0, speed=1.0)
        st.session_state["last_result"] = result

    st.markdown("---")
    st.markdown("**Attack simulation**")
    st.caption("Technically valid stolen token, rogue controller, restricted zone.")
    if st.button("Steal token → move robot-01 into HUMAN_ZONE (attack)", type="primary"):
        token = issue_token(device_id="controller-01")
        result = send_command(token, "rogue-controller", "HUMAN_ZONE", x=2.0, y=1.0, speed=1.0)
        st.session_state["last_result"] = result
        st.session_state["attack_token"] = token

    if st.session_state.get("attack_token") and st.button("Replay same revoked token"):
        result = send_command(
            st.session_state["attack_token"], "rogue-controller", "HUMAN_ZONE", x=2.0, y=1.0, speed=1.0
        )
        st.session_state["last_result"] = result

    st.markdown("---")
    if st.button("Reset demo state"):
        requests.post(f"{BROKER_URL}/reset")
        st.session_state.pop("attack_token", None)
        st.session_state.pop("last_result", None)

    if "last_result" in st.session_state:
        result = st.session_state["last_result"]
        if result["decision"] == "ALLOW":
            st.success(f"ALLOW — {result['reason']}")
        else:
            st.error(f"DENY — {result['reason']}")

with col_right:
    st.subheader("Fleet & security status")
    try:
        state = get_state()
    except requests.RequestException:
        st.warning("Broker not reachable at " + BROKER_URL)
        state = {"robot_state": {}, "quarantined_identities": [], "revoked_jtis": [], "incidents": []}

    for robot_id, robot in state["robot_state"].items():
        st.metric(
            f"{robot_id} status",
            robot.get("status", "IDLE"),
            help=f"zone={robot.get('zone')} speed={robot.get('speed')} identity={robot.get('last_identity')}",
        )

    st.write("**Quarantined identities:**", state["quarantined_identities"] or "none")
    st.write("**Revoked tokens (jti count):**", len(state["revoked_jtis"]))

st.markdown("---")
st.subheader("Incident timeline")

incidents = sorted(state.get("incidents", []), key=lambda i: i["timestamp"], reverse=True)

if not incidents:
    st.info("No incidents yet.")
else:
    for incident in incidents:
        ts = time.strftime("%H:%M:%S", time.localtime(incident["timestamp"]))
        with st.container(border=True):
            st.markdown(
                f":red[**Critical: Credential compromise detected**]  \n"
                f"`{ts}` {incident['message']}  \n"
                f"Violations: `{', '.join(incident['violations'])}`"
            )
