from __future__ import annotations

import os

import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="OmniGuard", page_icon=None, layout="wide")
st.title("OmniGuard")
st.caption(
    "Browser-operated cyber-physical red-team range for robot identity attacks "
    "inside an NVIDIA Isaac Sim digital twin."
)

API = st.sidebar.text_input(
    "OmniGuard API URL",
    os.getenv("OMNIGUARD_API_URL", "http://localhost:8000"),
)
st.sidebar.caption(
    "On a Mac, open this UI via SSM port-forward to EC2:8501 "
    "(see docs/MAC_ACCESS.md). Do not publish the dashboard to the internet."
)


def post(path: str):
    try:
        response = requests.post(f"{API}{path}", timeout=20)
        response.raise_for_status()
        return response.json()
    except Exception as exc:  # noqa: BLE001
        st.error(f"API request failed: {exc}")
        return None


def get(path: str, default):
    try:
        response = requests.get(f"{API}{path}", timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as exc:  # noqa: BLE001
        st.error(f"API request failed: {exc}")
        return default


health = get("/health", {})
llm = health.get("llm") or {}
health_cols = st.columns(4)
health_cols[0].metric("API", health.get("status", "down").upper())
health_cols[1].metric("Robot backend", str(health.get("robot_backend", "unknown")).upper())
health_cols[2].metric("LLM provider", str(llm.get("provider", "fallback")).upper())
health_cols[3].metric(
    "LLM configured",
    "YES" if llm.get("configured") else "NO (fallback)",
)

st.subheader("Judge demo — four-button flow")
button_columns = st.columns(4)
with button_columns[0]:
    if st.button("Reset Demo", use_container_width=True):
        post("/api/reset")
        st.rerun()
with button_columns[1]:
    if st.button("Normal Operation", use_container_width=True, type="primary"):
        post("/api/demo/normal")
        st.rerun()
with button_columns[2]:
    if st.button("Attack - Protection OFF", use_container_width=True):
        post("/api/demo/attack?protection=false")
        st.rerun()
with button_columns[3]:
    if st.button("Attack - OmniGuard ON", use_container_width=True):
        post("/api/demo/attack?protection=true")
        st.rerun()

st.subheader("Scenario library")
scenarios = get("/api/scenarios", [])
if scenarios:
    titles = {s["id"]: f'{s["title"]} — {s["description"]}' for s in scenarios}
    selected = st.selectbox(
        "Scenario",
        options=list(titles.keys()),
        format_func=lambda sid: titles.get(sid, sid),
        index=list(titles.keys()).index("combined_attack")
        if "combined_attack" in titles
        else 0,
    )
    protection_on = st.checkbox("OmniGuard protection enabled", value=True)
    reset_first = st.checkbox(
        "Reset state before run",
        value=selected != "revoked_replay",
        help="Disable for revoked-credential replay after a protected attack.",
    )
    if st.button("Run selected scenario", type="primary"):
        post(
            f"/api/scenarios/{selected}/run"
            f"?protection={'true' if protection_on else 'false'}"
            f"&reset_first={'true' if reset_first else 'false'}"
        )
        st.rerun()
else:
    st.warning("Scenario catalog unavailable — is the API running?")

if st.button("Refresh status"):
    st.rerun()

state = get("/api/state", {})
metric_columns = st.columns(6)
metric_columns[0].metric("Robot", state.get("robot_status", "UNKNOWN"))
metric_columns[1].metric("Zone", state.get("robot_zone", "UNKNOWN"))
metric_columns[2].metric("Speed", f'{state.get("robot_speed", 0.0)} m/s')
metric_columns[3].metric("Credential", state.get("credential_status", "UNKNOWN"))
metric_columns[4].metric("Agent", state.get("agent_status", "UNKNOWN"))
metric_columns[5].metric(
    "Protection", "ON" if state.get("protection_enabled", False) else "OFF"
)
st.caption(
    f"Containment ack: {state.get('last_containment_ack') or 'none'} · "
    "LLM never issues robot movement — policy + allowlisted actuation do."
)

events = get("/api/events", [])
if events:
    latest = events[0]
    st.divider()
    left, right = st.columns([1, 2])
    with left:
        decision = latest.get("final_decision")
        if decision == "BLOCK":
            st.error("COMMAND BLOCKED")
        elif decision == "HOLD":
            st.warning("HELD FOR REVIEW")
        else:
            st.success("COMMAND ALLOWED")
        st.metric("AI anomaly risk", latest.get("anomaly_risk_score", 0.0))
        st.write("Policy:", latest.get("policy_decision"))
        st.write("Reasons:", ", ".join(latest.get("reasons", [])) or "None")
        features = latest.get("anomaly_features") or {}
        if features:
            st.write("Anomaly features:", features)
    with right:
        st.subheader("Ordered response")
        for action in latest.get("actions", []):
            st.write(f"- {action}")
        explanation = latest.get("incident_explanation")
        if explanation:
            st.subheader("Incident analyst")
            if isinstance(explanation, dict):
                provider = explanation.get("provider", "fallback")
                model = explanation.get("model", "n/a")
                fallback = explanation.get("fallback_used", True)
                badge = (
                    f"Provider: **{provider}** · Model: `{model}`"
                    + (" · **fallback**" if fallback else " · live LLM")
                )
                st.caption(badge)
                st.info(explanation.get("summary", str(explanation)))
                if explanation.get("physical_impact"):
                    st.write("Physical impact:", explanation["physical_impact"])
                if explanation.get("recommended_actions"):
                    st.write("Recommended:")
                    for item in explanation["recommended_actions"]:
                        st.write(f"- {item}")
            else:
                st.info(explanation)

    st.subheader("Evidence timeline")
    rows = []
    for event in events:
        rows.append(
            {
                "time": event.get("timestamp"),
                "agent": event.get("agent_id"),
                "device": event.get("device_id"),
                "destination": event.get("destination"),
                "speed": event.get("speed"),
                "AI risk": event.get("anomaly_risk_score"),
                "policy": event.get("policy_decision"),
                "decision": event.get("final_decision"),
                "actions": ", ".join(event.get("actions", [])),
            }
        )
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
else:
    st.info("Click Normal Operation or run a scenario to begin.")
