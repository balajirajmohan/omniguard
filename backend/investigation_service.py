"""Bounded background Sonnet/OpenRouter investigation — never on the safety path."""

from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any, Callable

from backend.incident_store import incident_store
from backend.risk_policy import risk_policy

logger = logging.getLogger("omniguard.investigation")

MAX_WORKERS = 2


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class InvestigationService:
    """Schedule at most one pending/running LLM investigation per incident."""

    def __init__(self, *, max_workers: int = MAX_WORKERS) -> None:
        self._lock = threading.RLock()
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="omniguard-llm"
        )
        self._inflight: set[str] = set()
        self._state_provider: Callable[[], dict[str, Any]] | None = None

    def bind(self, state_provider: Callable[[], dict[str, Any]]) -> None:
        self._state_provider = state_provider

    def shutdown(self, wait: bool = False) -> None:
        self._executor.shutdown(wait=wait, cancel_futures=True)

    def schedule(
        self,
        incident_id: str,
        *,
        force: bool = False,
    ) -> dict[str, Any]:
        """Queue background investigation. Idempotent unless force=True (manual)."""
        incident = incident_store.get(incident_id)
        if not incident:
            return {"ok": False, "error": "INCIDENT_NOT_FOUND", "incident_id": incident_id}

        prior = dict(incident.get("llm_explanation") or {})
        status = str(prior.get("status") or "").upper()
        if status == "COMPLETED" and not force:
            return {
                "ok": True,
                "incident_id": incident_id,
                "investigation_status": "COMPLETED",
                "scheduled": False,
                "explanation": prior,
            }

        max_calls = int((risk_policy.raw.get("llm") or {}).get("max_calls_per_incident", 2))
        call_count = int(prior.get("call_count") or 0)
        if call_count == 0 and incident.get("agent_trace"):
            call_count = 1
        if call_count >= max_calls:
            return {
                "ok": False,
                "error": "LLM_CALL_LIMIT",
                "incident_id": incident_id,
                "investigation_status": status or "COMPLETED",
                "max_calls_per_incident": max_calls,
                "call_count": call_count,
                "explanation": prior or None,
            }

        with self._lock:
            if incident_id in self._inflight:
                return {
                    "ok": True,
                    "incident_id": incident_id,
                    "investigation_status": "PENDING",
                    "scheduled": False,
                    "note": "already_queued_or_running",
                }
            self._inflight.add(incident_id)

        pending = {
            "status": "PENDING",
            "investigation_status": "PENDING",
            "provider": None,
            "model": None,
            "fallback_used": False,
            "requested_at": _utcnow(),
            "started_at": None,
            "completed_at": None,
            "call_count": call_count,
            "summary": None,
        }
        incident_store.update_fields(
            incident_id,
            status="INVESTIGATING",
            llm_explanation_json={**prior, **pending},
        )

        self._executor.submit(self._run_job, incident_id, force)
        return {
            "ok": True,
            "incident_id": incident_id,
            "investigation_status": "PENDING",
            "scheduled": True,
        }

    def _run_job(self, incident_id: str, force: bool) -> None:
        try:
            self._execute(incident_id, force=force)
        except Exception as exc:  # noqa: BLE001
            logger.exception("investigation job crashed for %s: %s", incident_id, exc)
            try:
                incident_store.update_fields(
                    incident_id,
                    llm_explanation_json={
                        "status": "FAILED",
                        "investigation_status": "FAILED",
                        "provider": "openrouter",
                        "error_category": "unexpected_error",
                        "fallback_available": True,
                        "fallback_used": False,
                        "completed_at": _utcnow(),
                        "detail": str(exc),
                    },
                )
            except Exception:  # noqa: BLE001
                logger.exception("failed to persist investigation crash for %s", incident_id)
        finally:
            with self._lock:
                self._inflight.discard(incident_id)

    def _execute(self, incident_id: str, *, force: bool) -> None:
        from backend.agent import InvestigationAgent
        from backend.incident_ai import explain_incident

        incident = incident_store.get(incident_id)
        if not incident:
            return

        prior = dict(incident.get("llm_explanation") or {})
        prior["status"] = "RUNNING"
        prior["investigation_status"] = "RUNNING"
        prior["started_at"] = _utcnow()
        incident_store.update_fields(incident_id, llm_explanation_json=prior)

        state_provider = self._state_provider or (lambda: {})
        agent = InvestigationAgent(state_provider)
        try:
            trace = agent.run_v2(incident)
            incident_store.update_fields(
                incident_id, status="INVESTIGATING", agent_trace_json=trace
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("agent.run_v2 failed for %s: %s", incident_id, exc)
            trace = {
                "agent": "omniguard-investigation-v2",
                "ok": False,
                "error": str(exc),
                "execution_authorized": False,
            }

        event_payload = {
            **incident,
            "reasons": (incident.get("hard_policy") or {}).get("reasons")
            or [incident.get("playbook") or "incident"],
            "actions": ((incident.get("containment") or {}).get("acknowledged") or []),
            "decision_source": incident.get("decision_source"),
            "anomaly_risk_score": (incident.get("ai_evidence") or {}).get(
                "anomaly_risk_score"
            ),
            "response_playbook": incident.get("playbook"),
        }
        try:
            explanation = dict(explain_incident(event_payload) or {})
        except Exception as exc:  # noqa: BLE001
            logger.warning("explain_incident failed for %s: %s", incident_id, exc)
            explanation = {
                "status": "FAILED",
                "provider": "openrouter",
                "error_category": "provider_error",
                "fallback_available": True,
                "fallback_used": False,
                "detail": str(exc),
            }

        call_count = int(prior.get("call_count") or 0) + 1
        explanation["call_count"] = call_count
        explanation["requested_at"] = prior.get("requested_at")
        explanation["started_at"] = prior.get("started_at")
        explanation["completed_at"] = _utcnow()
        if explanation.get("fallback_used"):
            explanation["status"] = "COMPLETED"
            explanation["investigation_status"] = "COMPLETED"
            explanation["mode"] = "deterministic_fallback"
        elif explanation.get("status") == "FAILED":
            explanation["investigation_status"] = "FAILED"
        else:
            explanation["status"] = "COMPLETED"
            explanation["investigation_status"] = "COMPLETED"
            explanation["mode"] = "live"

        incident_store.update_fields(
            incident_id,
            status="CONTAINED" if (incident.get("containment") or {}).get("ok") else "OPEN",
            llm_explanation_json=explanation,
            agent_trace_json=trace,
        )


investigation_service = InvestigationService()
