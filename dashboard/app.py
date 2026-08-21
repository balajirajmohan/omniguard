from __future__ import annotations

import json
import os
import time

import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="OmniGuard", page_icon=None, layout="wide")
st.title("OmniGuard Command Center")
st.caption(
    "Browser-operated cyber-physical red-team range for robot identity attacks "
    "inside an NVIDIA Isaac Sim digital twin."
)

API = st.sidebar.text_input(
    "OmniGuard API URL",
    os.getenv("OMNIGUARD_API_URL", "http://localhost:8000"),
)
st.sidebar.caption("Mac access: SSM port-forward to EC2:8501 (docs/MAC_ACCESS.md).")
auto_refresh = st.sidebar.checkbox("Auto-refresh while active", value=True)


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
anomaly = health.get("anomaly") or {}
health_cols = st.columns(6)
health_cols[0].metric("API", str(health.get("status", "down")).upper())
health_cols[1].metric("Robot", str(health.get("robot_backend", "?")).upper())
health_cols[2].metric(
    "AI enforce",
    "ON" if health.get("ai_enforcement_enabled") else "SHADOW",
)
health_cols[3].metric(
    "Model",
    "READY" if health.get("model_available") else "DOWN",
)
health_cols[4].metric(
    "Artifact",
    "VERIFIED" if health.get("artifact_verified") else "DEGRADED",
)
llm_label = (
    f"{llm.get('provider')}/{llm.get('model')}"
    if llm.get("configured")
    else "deterministic fallback"
)
health_cols[5].metric("LLM", llm_label)

with st.expander("AI anomaly model", expanded=False):
    st.write(
        f"**{anomaly.get('model_name')}** `{anomaly.get('model_version')}` · "
        f"critical≥{health.get('critical_threshold')} · "
        f"warning≥{health.get('warning_threshold')}"
    )
    st.caption(anomaly.get("judge_note", ""))
    if anomaly.get("eval_metrics"):
        st.write(anomaly["eval_metrics"])

st.subheader("Judge demo")
button_columns = st.columns(5)
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
with button_columns[4]:
    if st.button("AI-only anomaly", use_container_width=True):
        post("/api/demo/anomaly")
        st.rerun()

st.subheader("Scenario cards")
scenarios = get("/api/scenarios", [])
if scenarios:
    cols = st.columns(2)
    for idx, scenario in enumerate(scenarios):
        with cols[idx % 2]:
            st.markdown(f"**{scenario['title']}**")
            st.caption(scenario.get("description", ""))
            st.write(
                f"Expected: `{scenario.get('expected_action')}` · "
                f"signals: {', '.join(scenario.get('expected_signals') or ['none'])}"
            )
            c1, c2 = st.columns(2)
            if c1.button("Run OFF", key=f"off-{scenario['id']}", use_container_width=True):
                post(
                    f"/api/scenarios/{scenario['id']}/run?protection=false&reset_first=true"
                )
                st.rerun()
            if c2.button("Run ON", key=f"on-{scenario['id']}", use_container_width=True):
                post(
                    f"/api/scenarios/{scenario['id']}/run?protection=true&reset_first="
                    f"{'false' if scenario.get('requires_prior_revoke') else 'true'}"
                )
                st.rerun()
else:
    st.warning("Scenario catalog unavailable")

if st.button("Run investigation agent"):
    post("/api/investigate")
    st.rerun()
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
    f"Containment ack: {state.get('last_containment_ack') or 'none'} "
    "(sent ≠ executed until Isaac acknowledgement)"
)

bridge = state.get("isaac_bridge_state") or {}
if bridge:
    pos = bridge.get("position") or {}
    st.write(
        "Live Isaac state:",
        f"pos=({pos.get('x')}, {pos.get('y')})",
        f"motion={bridge.get('motion_state')}",
        f"speed={bridge.get('speed')}",
    )
    # Simple warehouse map
    try:
        import pandas as pd

        map_df = pd.DataFrame(
            [
                {"x": float(pos.get("x") or 0.0), "y": float(pos.get("y") or 0.0)},
                {"x": 0.0, "y": 0.0},
                {"x": 10.0, "y": 4.0},
                {"x": 6.0, "y": 8.0},
            ]
        )
        st.scatter_chart(map_df, x="x", y="y")
    except Exception:  # noqa: BLE001
        pass

events = get("/api/events", [])
if events:
    latest = events[0]
    risk = float(latest.get("anomaly_risk_score") or 0.0)
    critical = float(health.get("critical_threshold") or 0.8)
    warning = float(health.get("warning_threshold") or 0.6)
    st.subheader("Risk gauge")
    st.progress(min(max(risk, 0.0), 1.0))
    st.write(
        f"Risk **{risk:.2f}** · warning≥{warning} · critical≥{critical} · "
        f"caught_by=`{latest.get('caught_by')}`"
    )
    left, right = st.columns([1, 2])
    with left:
        decision = latest.get("final_decision")
        if decision == "BLOCK":
            st.error("COMMAND BLOCKED")
        elif decision == "HOLD":
            st.warning("AI WARNING / HOLD")
        else:
            st.success("COMMAND ALLOWED")
        if latest.get("caught_by") == "ai_anomaly":
            st.warning("Caught by AI (hard policy would ALLOW)")
        elif latest.get("caught_by") == "hard_policy":
            st.info("Caught by hard policy")
        elif latest.get("caught_by") == "ai_warning":
            st.warning("AI warning band")
        elif latest.get("caught_by") == "ai_shadow":
            st.info("AI shadow alert (not enforced)")
        st.write("Policy:", latest.get("policy_decision"))
        st.write("Hard policy would block:", latest.get("hard_policy_would_block"))
        st.write("Reasons:", ", ".join(latest.get("reasons", [])) or "None")
        st.write("Behavior source:", (latest.get("behavior") or {}).get("source"))
        st.write("Features:", latest.get("anomaly_features"))
    with right:
        st.subheader("Ordered response")
        for action in latest.get("actions", []):
            st.write(f"- {action}")
        explanation = latest.get("incident_explanation")
        if explanation:
            st.subheader("Incident analyst")
            if isinstance(explanation, dict):
                mode = (
                    "deterministic fallback"
                    if explanation.get("fallback_used")
                    else "live LLM"
                )
                st.caption(
                    f"{explanation.get('provider')}/{explanation.get('model')} · {mode}"
                    + (
                        f" · reason={explanation.get('fallback_reason')}"
                        if explanation.get("fallback_reason")
                        else ""
                    )
                )
                st.info(explanation.get("summary", str(explanation)))
            else:
                st.info(explanation)
        st.download_button(
            "Export latest incident JSON",
            data=json.dumps(get("/api/incidents/latest", {}), indent=2),
            file_name="omniguard-incident.json",
            mime="application/json",
        )

    st.subheader("Evidence timeline")
    timeline = latest.get("timeline") or get("/api/timeline", [])
    if timeline:
        st.dataframe(pd.DataFrame(timeline), use_container_width=True, hide_index=True)
    rows = []
    for event in events:
        rows.append(
            {
                "time": event.get("timestamp"),
                "decision": event.get("final_decision"),
                "caught_by": event.get("caught_by"),
                "AI risk": event.get("anomaly_risk_score"),
                "policy": event.get("policy_decision"),
                "hard_policy": event.get("hard_policy_would_block"),
                "actions": ", ".join(event.get("actions", [])),
            }
        )
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
else:
    st.info("Run Normal Operation or a scenario card to begin.")

if auto_refresh and state.get("robot_status") in {
    "MOVING",
    "CONTAINED",
    "CONTAINMENT_FAILED",
}:
    if state.get("last_containment_ack") in {"ESTOP_QUEUED", "CONTAINMENT_REQUESTED", "STOP_QUEUED"}:
        time.sleep(1.5)
        st.rerun()
