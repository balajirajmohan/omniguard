"""Recovery state machine — simulated IdP steps explicitly labelled."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from backend.incident_store import incident_store

RECOVERY_STATES = [
    "CONTAINED",
    "CREDENTIAL_ROTATION_REQUIRED",
    "DEVICE_ATTESTATION_REQUIRED",
    "OPERATOR_REAUTHENTICATION_REQUIRED",
    "LIMITED_ACCESS",
    "ENHANCED_MONITORING",
    "RESTORED",
]

REQUIRED_FOR_RESTORE = {
    "old_credential_revoked",
    "new_credential_issued",
    "device_attested",
    "operator_reauthenticated",
    "related_incidents_closed",
    "risk_below_recovery_threshold",
}


class RecoveryManager:
    def start(self, incident_id: str) -> dict[str, Any]:
        incident = incident_store.get(incident_id)
        if not incident:
            return {"ok": False, "error": "INCIDENT_NOT_FOUND"}
        recovery = {
            "state": "CREDENTIAL_ROTATION_REQUIRED",
            "simulated": True,
            "label": "Simulated external identity-provider recovery",
            "evidence": {k: False for k in REQUIRED_FOR_RESTORE},
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "history": ["CONTAINED", "CREDENTIAL_ROTATION_REQUIRED"],
        }
        incident_store.update_fields(
            incident_id, status="RECOVERING", recovery_json=recovery
        )
        return {"ok": True, "incident_id": incident_id, "recovery": recovery}

    def advance(
        self,
        incident_id: str,
        *,
        evidence_updates: dict[str, bool] | None = None,
        force_state: str | None = None,
    ) -> dict[str, Any]:
        incident = incident_store.get(incident_id)
        if not incident:
            return {"ok": False, "error": "INCIDENT_NOT_FOUND"}
        recovery = dict(incident.get("recovery") or {})
        if not recovery:
            return self.start(incident_id)

        evidence = dict(recovery.get("evidence") or {})
        for key, value in (evidence_updates or {}).items():
            if key in REQUIRED_FOR_RESTORE:
                evidence[key] = bool(value)
        recovery["evidence"] = evidence
        recovery["simulated"] = True
        recovery["label"] = "Simulated external identity-provider recovery"

        if force_state:
            if force_state not in RECOVERY_STATES:
                return {"ok": False, "error": "INVALID_STATE"}
            recovery["state"] = force_state
        else:
            recovery["state"] = self._next_state(evidence, recovery.get("state"))

        history = list(recovery.get("history") or [])
        if not history or history[-1] != recovery["state"]:
            history.append(recovery["state"])
        recovery["history"] = history
        recovery["updated_at"] = datetime.now(timezone.utc).isoformat()

        status = "RESOLVED" if recovery["state"] == "RESTORED" else "RECOVERING"
        if recovery["state"] == "RESTORED" and not all(
            evidence.get(k) for k in REQUIRED_FOR_RESTORE
        ):
            return {
                "ok": False,
                "error": "MISSING_RECOVERY_EVIDENCE",
                "required": sorted(REQUIRED_FOR_RESTORE),
                "evidence": evidence,
            }

        incident_store.update_fields(
            incident_id, status=status, recovery_json=recovery
        )
        return {"ok": True, "incident_id": incident_id, "recovery": recovery}

    def _next_state(self, evidence: dict[str, bool], current: str | None) -> str:
        if not evidence.get("old_credential_revoked") or not evidence.get(
            "new_credential_issued"
        ):
            return "CREDENTIAL_ROTATION_REQUIRED"
        if not evidence.get("device_attested"):
            return "DEVICE_ATTESTATION_REQUIRED"
        if not evidence.get("operator_reauthenticated"):
            return "OPERATOR_REAUTHENTICATION_REQUIRED"
        if not evidence.get("related_incidents_closed"):
            return "LIMITED_ACCESS"
        if not evidence.get("risk_below_recovery_threshold"):
            return "ENHANCED_MONITORING"
        if all(evidence.get(k) for k in REQUIRED_FOR_RESTORE):
            return "RESTORED"
        return current or "LIMITED_ACCESS"


recovery_manager = RecoveryManager()
