"""SQLite incident store — no credentials or bridge tokens."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data" / "omniguard_incidents.db"

LIFECYCLE = {
    "OPEN",
    "CONTAINED",
    "INVESTIGATING",
    "AWAITING_VERIFICATION",
    "RECOVERING",
    "RESOLVED",
    "FALSE_POSITIVE",
}

FEEDBACK = {
    "CONFIRMED_ATTACK",
    "FALSE_POSITIVE",
    "OPERATOR_ERROR",
    "MISCONFIGURATION",
    "EXPECTED_MAINTENANCE",
    "POLICY_GAP",
    "UNKNOWN",
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class IncidentStore:
    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = Path(
            os.getenv("OMNIGUARD_INCIDENT_DB", str(db_path or DEFAULT_DB))
        )
        self._lock = threading.RLock()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS incidents (
                        incident_id TEXT PRIMARY KEY,
                        status TEXT NOT NULL,
                        correlation_fingerprint TEXT,
                        first_event_at TEXT,
                        last_event_at TEXT,
                        event_count INTEGER DEFAULT 1,
                        agent_id TEXT,
                        device_id TEXT,
                        robot_id TEXT,
                        action_sequence_json TEXT,
                        hard_policy_json TEXT,
                        ai_evidence_json TEXT,
                        model_version TEXT,
                        policy_version TEXT,
                        containment_json TEXT,
                        agent_trace_json TEXT,
                        llm_explanation_json TEXT,
                        human_feedback_json TEXT,
                        recovery_json TEXT,
                        playbook TEXT,
                        decision_source TEXT
                    )
                    """
                )
                conn.commit()
            finally:
                conn.close()

    def reset_demo_state(self) -> None:
        with self._lock:
            conn = self._connect()
            try:
                conn.execute("DELETE FROM incidents")
                conn.commit()
            finally:
                conn.close()

    def open_or_correlate(
        self,
        *,
        fingerprint: str,
        agent_id: str,
        device_id: str,
        robot_id: str,
        action_event: dict[str, Any],
        hard_policy: dict[str, Any],
        ai_evidence: dict[str, Any],
        model_version: str | None,
        policy_version: str | None,
        playbook: str | None,
        decision_source: str | None,
        window_seconds: int = 120,
    ) -> dict[str, Any]:
        now = _utcnow()
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    """
                    SELECT * FROM incidents
                    WHERE correlation_fingerprint = ?
                      AND status IN ('OPEN','CONTAINED','INVESTIGATING','AWAITING_VERIFICATION')
                    ORDER BY last_event_at DESC LIMIT 1
                    """,
                    (fingerprint,),
                ).fetchone()
                if row:
                    last = datetime.fromisoformat(row["last_event_at"])
                    if now - last <= timedelta(seconds=window_seconds):
                        seq = json.loads(row["action_sequence_json"] or "[]")
                        seq.append(action_event)
                        conn.execute(
                            """
                            UPDATE incidents SET
                              last_event_at = ?,
                              event_count = event_count + 1,
                              action_sequence_json = ?,
                              ai_evidence_json = ?,
                              hard_policy_json = ?,
                              playbook = COALESCE(?, playbook),
                              decision_source = COALESCE(?, decision_source)
                            WHERE incident_id = ?
                            """,
                            (
                                now.isoformat(),
                                json.dumps(seq[-50:]),
                                json.dumps(ai_evidence),
                                json.dumps(hard_policy),
                                playbook,
                                decision_source,
                                row["incident_id"],
                            ),
                        )
                        conn.commit()
                        return self.get(row["incident_id"]) or {}

                incident_id = f"INC-{uuid.uuid4().hex[:10].upper()}"
                conn.execute(
                    """
                    INSERT INTO incidents (
                      incident_id, status, correlation_fingerprint,
                      first_event_at, last_event_at, event_count,
                      agent_id, device_id, robot_id,
                      action_sequence_json, hard_policy_json, ai_evidence_json,
                      model_version, policy_version, playbook, decision_source,
                      containment_json, agent_trace_json, llm_explanation_json,
                      human_feedback_json, recovery_json
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,NULL,NULL,NULL,NULL,NULL)
                    """,
                    (
                        incident_id,
                        "OPEN",
                        fingerprint,
                        now.isoformat(),
                        now.isoformat(),
                        1,
                        agent_id,
                        device_id,
                        robot_id,
                        json.dumps([action_event]),
                        json.dumps(hard_policy),
                        json.dumps(ai_evidence),
                        model_version,
                        policy_version,
                        playbook,
                        decision_source,
                    ),
                )
                conn.commit()
                return self.get(incident_id) or {}
            finally:
                conn.close()

    def update_fields(self, incident_id: str, **fields: Any) -> dict[str, Any] | None:
        if not fields:
            return self.get(incident_id)
        allowed = {
            "status",
            "containment_json",
            "agent_trace_json",
            "llm_explanation_json",
            "human_feedback_json",
            "recovery_json",
        }
        sets = []
        values: list[Any] = []
        for key, value in fields.items():
            if key not in allowed:
                continue
            if key.endswith("_json") and not isinstance(value, str):
                value = json.dumps(value)
            sets.append(f"{key} = ?")
            values.append(value)
        if not sets:
            return self.get(incident_id)
        values.append(incident_id)
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    f"UPDATE incidents SET {', '.join(sets)} WHERE incident_id = ?",
                    values,
                )
                conn.commit()
            finally:
                conn.close()
        return self.get(incident_id)

    def get(self, incident_id: str) -> dict[str, Any] | None:
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT * FROM incidents WHERE incident_id = ?", (incident_id,)
                ).fetchone()
                return self._row_to_dict(row) if row else None
            finally:
                conn.close()

    def list(self, *, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute(
                    "SELECT * FROM incidents ORDER BY last_event_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
                return [self._row_to_dict(r) for r in rows]
            finally:
                conn.close()

    def _row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        for key in (
            "action_sequence_json",
            "hard_policy_json",
            "ai_evidence_json",
            "containment_json",
            "agent_trace_json",
            "llm_explanation_json",
            "human_feedback_json",
            "recovery_json",
        ):
            raw = data.pop(key, None)
            out_key = key.replace("_json", "")
            if isinstance(raw, str) and raw:
                try:
                    data[out_key] = json.loads(raw)
                except json.JSONDecodeError:
                    data[out_key] = raw
            else:
                data[out_key] = None
        return data


incident_store = IncidentStore()
