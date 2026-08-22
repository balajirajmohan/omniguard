"""One durable incident pipeline for all security BLOCK/HOLD decisions."""

from __future__ import annotations

import threading
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any

from backend.action_context import credential_fingerprint
from backend.incident_classification import (
    AUDIT_ONLY_REASONS,
    classify_security_record,
    playbook_for_hard_reasons,
)
from backend.incident_store import incident_store
from backend.investigation_service import investigation_service
from backend.risk_policy import risk_policy

_audit_lock = threading.RLock()
# key -> deque of timestamps (monotonic-ish via utc iso parsed as datetime)
_audit_buckets: dict[str, deque[datetime]] = defaultdict(deque)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _demo_run_id(state: dict[str, Any] | None) -> str:
    return str((state or {}).get("demo_run_id") or "unbound-demo-run")


def _window_cfg() -> tuple[int, int]:
    policy = risk_policy.raw.get("incident_policy") or risk_policy.raw.get("incident") or {}
    window = int(policy.get("low_level_event_window_seconds", 120))
    threshold = int(policy.get("low_level_event_threshold", 5))
    return window, threshold


def note_audit_event(
    *,
    reason: str,
    agent_id: str,
    device_id: str,
    robot_id: str,
    session_id: str | None = None,
    demo_run_id: str = "unbound-demo-run",
    event: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Record a low-level control event. Escalate only after threshold."""
    if reason not in AUDIT_ONLY_REASONS:
        return None
    window, threshold = _window_cfg()
    key = f"{demo_run_id}|{agent_id}|{device_id}|{robot_id}|{session_id or '-'}|{reason}"
    now = _utcnow()
    with _audit_lock:
        bucket = _audit_buckets[key]
        bucket.append(now)
        while bucket and (now - bucket[0]).total_seconds() > window:
            bucket.popleft()
        count = len(bucket)
        if count < threshold:
            return None
        # Reset bucket so we open one incident per threshold burst.
        supporting = list(bucket)
        bucket.clear()

    payload = {
        "final_decision": "HOLD",
        "decision_source": "hard_policy",
        "reasons": [reason, "CONTROL_PROTOCOL_THRESHOLD"],
        "requires_incident": True,
        "requires_human_review": True,
        "escalate_to_incident": True,
        "agent_id": agent_id,
        "device_id": device_id,
        "robot_id": robot_id,
        "playbook": "SUSPICIOUS_SESSION",
        "response_playbook": "SUSPICIOUS_SESSION",
        "policy_decision": "AI_HOLD",
        "audit_count": count,
        "supporting_events": [
            {"at": t.isoformat(), "reason": reason} for t in supporting
        ],
        "action_event": event
        or {
            "kind": "control_protocol_escalation",
            "reason": reason,
            "count": count,
        },
    }
    return record_security_decision(
        payload,
        credential="",
        demo_run_id=demo_run_id,
        schedule_investigation=True,
        contain=False,
    )


def record_security_decision(
    decision: dict[str, Any],
    *,
    credential: str,
    demo_run_id: str | None = None,
    state: dict[str, Any] | None = None,
    schedule_investigation: bool = True,
    contain: bool = False,
    containment_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create/correlate a durable incident when classification says so.

    Returns enrichment fields for the API response (incident_id, investigation_status).
    Never calls Sonnet synchronously.
    """
    kind = classify_security_record(decision)
    enrichment: dict[str, Any] = {
        "record_kind": kind,
        "incident_id": None,
        "investigation_status": None,
    }
    if kind == "AUDIT_EVENT":
        return enrichment

    agent_id = str(decision.get("agent_id") or "unknown")
    device_id = str(decision.get("device_id") or "unknown")
    robot_id = str(decision.get("robot_id") or "robot-01")
    run_id = demo_run_id or _demo_run_id(state)
    reasons = list(decision.get("reasons") or [])
    decision_source = str(
        decision.get("decision_source")
        or ("hard_policy" if any(r in {
            "UNKNOWN_DEVICE",
            "RESTRICTED_DESTINATION",
            "EXCESSIVE_SPEED",
            "REVOKED_CREDENTIAL",
            "UNAUTHORIZED_AGENT",
            "UNAUTHORIZED_ROBOT",
            "INVALID_CREDENTIAL",
        } for r in reasons) else "none")
    )
    playbook = (
        decision.get("response_playbook")
        or decision.get("playbook")
        or playbook_for_hard_reasons(reasons)
    )
    fp_cred = (
        credential_fingerprint(credential)
        if credential
        else str(decision.get("credential_fingerprint") or "cred-unknown")
    )
    fingerprint = (
        f"{run_id}|{fp_cred}|{device_id}|{playbook}|{decision_source}|"
        f"{','.join(sorted(reasons))}"
    )
    window = int(
        (risk_policy.raw.get("incident") or {}).get("correlation_window_seconds", 120)
    )

    action_event = decision.get("action_event") or {
        "final_decision": decision.get("final_decision"),
        "reasons": reasons,
        "destination": decision.get("destination"),
        "speed": decision.get("speed"),
        "decision_source": decision_source,
        "policy_decision": decision.get("policy_decision"),
        "at": _utcnow().isoformat(),
    }

    ai_evidence = dict(decision.get("ai_evidence") or {})
    if decision.get("anomaly_risk_score") is not None:
        ai_evidence.setdefault("anomaly_risk_score", decision.get("anomaly_risk_score"))
    if decision.get("behavioral_rule_score") is not None:
        ai_evidence.setdefault(
            "behavioral_rule_score", decision.get("behavioral_rule_score")
        )
    if decision.get("effective_risk") is not None:
        ai_evidence.setdefault("effective_risk", decision.get("effective_risk"))
    if decision.get("anomaly_features") is not None:
        ai_evidence.setdefault("anomaly_features", decision.get("anomaly_features"))
    ai_evidence["decision_source"] = decision_source
    if decision.get("audit_count"):
        ai_evidence["audit_count"] = decision.get("audit_count")
        ai_evidence["supporting_events"] = decision.get("supporting_events")

    incident = incident_store.open_or_correlate(
        fingerprint=fingerprint,
        agent_id=agent_id,
        device_id=device_id,
        robot_id=robot_id,
        action_event=action_event,
        hard_policy={
            "would_block": bool(decision.get("hard_policy_would_block", True)),
            "reasons": reasons,
        },
        ai_evidence=ai_evidence,
        model_version=decision.get("anomaly_model_version")
        or (decision.get("ai") or {}).get("model_version"),
        policy_version=risk_policy.version,
        playbook=playbook,
        decision_source=decision_source,
        demo_run_id=run_id,
        window_seconds=window,
    )

    if containment_result is not None:
        incident_store.update_fields(
            incident["incident_id"],
            status="CONTAINED" if containment_result.get("ok") else "OPEN",
            containment_json=containment_result,
        )
        incident = incident_store.get(incident["incident_id"]) or incident
    elif contain and not incident.get("containment"):
        # Placeholder until caller attaches bridge ack.
        incident_store.update_fields(
            incident["incident_id"],
            llm_explanation_json={
                "status": "PENDING",
                "investigation_status": "PENDING",
                "requested_at": _utcnow().isoformat(),
                "summary": None,
            },
        )

    # Mark investigation pending without fabricating LLM content.
    prior = dict(incident.get("llm_explanation") or {})
    if prior.get("status") not in {"COMPLETED", "FAILED", "RUNNING"}:
        incident_store.update_fields(
            incident["incident_id"],
            llm_explanation_json={
                **prior,
                "status": "PENDING",
                "investigation_status": "PENDING",
                "requested_at": prior.get("requested_at") or _utcnow().isoformat(),
                "summary": None,
            },
        )

    investigation_status = "PENDING"
    if schedule_investigation and decision.get("final_decision") in {"BLOCK", "HOLD"}:
        scheduled = investigation_service.schedule(incident["incident_id"])
        investigation_status = scheduled.get("investigation_status") or "PENDING"

    refreshed = incident_store.get(incident["incident_id"]) or incident
    llm = refreshed.get("llm_explanation") or {}
    enrichment.update(
        {
            "incident_id": refreshed["incident_id"],
            "investigation_status": llm.get("investigation_status")
            or llm.get("status")
            or investigation_status,
            "decision_source": decision_source,
            "response_playbook": playbook,
            "playbook": playbook,
        }
    )
    return enrichment
