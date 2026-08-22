"""Load declarative AI risk policy (observe / advise / enforce)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATH = ROOT / "config" / "risk_policy.yaml"

DEFAULT_POLICY: dict[str, Any] = {
    "version": "action-risk-policy-v1-default",
    "warning_risk": 0.60,
    "critical_risk": 0.80,
    "ai_cannot_bypass_hard_policy": True,
    "actions": {
        "BASE_MOVE": {"ai_mode": "observe"},
        "BASE_STOP": {"ai_mode": "observe"},
        "ARM_PRESET": {"ai_mode": "enforce"},
        "ARM_JOINTS": {"ai_mode": "enforce"},
        "GRIPPER_OPEN": {"ai_mode": "enforce"},
        "GRIPPER_CLOSE": {"ai_mode": "enforce"},
    },
    "warning_decision": "HOLD",
    "critical_decision": "BLOCK",
    "llm": {"max_calls_per_incident": 2, "max_agent_rounds": 5},
    "incident": {"correlation_window_seconds": 120},
}


class RiskPolicy:
    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(os.getenv("OMNIGUARD_RISK_POLICY", str(path or DEFAULT_PATH)))
        self.raw: dict[str, Any] = dict(DEFAULT_POLICY)
        self.load_error: str | None = None
        self.reload()

    def reload(self) -> None:
        try:
            if self.path.exists():
                loaded = yaml.safe_load(self.path.read_text()) or {}
                if not isinstance(loaded, dict):
                    raise ValueError("risk policy must be a mapping")
                merged = dict(DEFAULT_POLICY)
                merged.update(loaded)
                actions = dict(DEFAULT_POLICY["actions"])
                actions.update(loaded.get("actions") or {})
                merged["actions"] = actions
                self.raw = merged
                self.load_error = None
            else:
                self.raw = dict(DEFAULT_POLICY)
                self.load_error = "missing_policy_file"
        except Exception as exc:  # noqa: BLE001 — degrade safely
            self.raw = dict(DEFAULT_POLICY)
            self.load_error = str(exc)

    @property
    def version(self) -> str:
        return str(self.raw.get("version", "unknown"))

    @property
    def warning_risk(self) -> float:
        return float(self.raw.get("warning_risk", 0.60))

    @property
    def critical_risk(self) -> float:
        return float(self.raw.get("critical_risk", 0.80))

    def ai_mode_for(self, action_type: str) -> str:
        """Return observe|advise|enforce. OMNIGUARD_AI_ENFORCE=false forces observe."""
        if os.getenv("OMNIGUARD_AI_ENFORCE", "true").lower() in {"0", "false", "no"}:
            return "observe"
        entry = (self.raw.get("actions") or {}).get(action_type) or {}
        mode = str(entry.get("ai_mode", "observe")).lower()
        if mode not in {"observe", "advise", "enforce"}:
            return "observe"
        return mode

    def status(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "warning_risk": self.warning_risk,
            "critical_risk": self.critical_risk,
            "load_error": self.load_error,
            "actions": self.raw.get("actions"),
            "llm": self.raw.get("llm"),
        }


risk_policy = RiskPolicy()
