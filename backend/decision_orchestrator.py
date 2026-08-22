"""Decision orchestrator — hard policy first, then action-window AI, never LLM."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from backend.action_anomaly import action_window_detector
from backend.action_context import ActionContext
from backend.risk_policy import risk_policy


class DecisionResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    decision_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    final_decision: str  # ALLOW | ALLOW_WITH_MONITORING | HOLD | BLOCK
    policy_decision: str
    decision_source: str

    hard_policy_would_block: bool
    hard_policy_reasons: list[str] = Field(default_factory=list)

    anomaly_risk_score: float | None = None
    anomaly_model: str | None = None
    anomaly_model_version: str | None = None
    anomaly_features: dict[str, Any] = Field(default_factory=dict)
    ai_mode: str = "observe"
    model_confidence: float | None = None  # always null unless calibrated

    requires_incident: bool = False
    requires_containment: bool = False
    requires_human_review: bool = False
    response_playbook: str | None = None
    ai_degraded: bool = False


class DecisionOrchestrator:
    def decide(
        self,
        context: ActionContext,
        *,
        hard_reasons: list[str] | None = None,
        window_features: dict[str, Any] | None = None,
        protection_enabled: bool | None = None,
    ) -> DecisionResult:
        hard_reasons = list(hard_reasons or [])
        protection = (
            context.protection_enabled if protection_enabled is None else protection_enabled
        )
        hard_block = bool(hard_reasons)

        if hard_block:
            return DecisionResult(
                final_decision="BLOCK" if protection else "ALLOW",
                policy_decision="DENY" if protection else "BYPASSED",
                decision_source="hard_policy" if protection else "none",
                hard_policy_would_block=True,
                hard_policy_reasons=hard_reasons,
                requires_incident=protection,
                requires_containment=protection,
                response_playbook="SINGLE_UNSAFE_COMMAND" if protection else None,
                model_confidence=None,
            )

        if not protection:
            return DecisionResult(
                final_decision="ALLOW",
                policy_decision="BYPASSED",
                decision_source="none",
                hard_policy_would_block=False,
                hard_policy_reasons=[],
                model_confidence=None,
            )

        ai_mode = risk_policy.ai_mode_for(context.action_type.value)
        features = window_features or {}
        risk, selected, info = action_window_detector.score(features)
        degraded = bool(info.get("degraded") or info.get("ai_unavailable"))

        if not action_window_detector.available:
            return DecisionResult(
                final_decision="ALLOW",
                policy_decision="PERMIT",
                decision_source="deterministic_fallback",
                hard_policy_would_block=False,
                hard_policy_reasons=[],
                anomaly_risk_score=0.0,
                anomaly_model="IsolationForest",
                anomaly_model_version=action_window_detector.model_version,
                anomaly_features=selected,
                ai_mode=ai_mode,
                model_confidence=None,
                ai_degraded=True,
            )

        warning = risk_policy.warning_risk
        critical = risk_policy.critical_risk
        # Prefer artifact thresholds when verified.
        warning = min(warning, action_window_detector.warning_threshold)
        critical = max(critical, action_window_detector.critical_threshold)
        warning = action_window_detector.warning_threshold
        critical = action_window_detector.critical_threshold

        base = DecisionResult(
            final_decision="ALLOW",
            policy_decision="PERMIT",
            decision_source="none",
            hard_policy_would_block=False,
            hard_policy_reasons=[],
            anomaly_risk_score=risk,
            anomaly_model="IsolationForest",
            anomaly_model_version=str(info.get("model_version")),
            anomaly_features=selected,
            ai_mode=ai_mode,
            model_confidence=None,
            ai_degraded=degraded,
        )

        if ai_mode == "observe":
            base.decision_source = "action_window_ai" if risk >= warning else "none"
            if risk >= critical:
                base.requires_human_review = True
            return base

        if ai_mode == "advise":
            if risk >= critical or risk >= warning:
                base.final_decision = "HOLD"
                base.policy_decision = "AI_ADVISE_HOLD"
                base.decision_source = "ai_warning"
                base.requires_human_review = True
                base.requires_incident = risk >= critical
            return base

        # enforce
        if risk >= critical:
            playbook = self._playbook_for(context, features)
            return DecisionResult(
                final_decision="BLOCK",
                policy_decision="AI_DENY",
                decision_source="action_window_ai",
                hard_policy_would_block=False,
                hard_policy_reasons=[],
                anomaly_risk_score=risk,
                anomaly_model="IsolationForest",
                anomaly_model_version=str(info.get("model_version")),
                anomaly_features=selected,
                ai_mode=ai_mode,
                model_confidence=None,
                requires_incident=True,
                requires_containment=True,
                requires_human_review=True,
                response_playbook=playbook,
                ai_degraded=degraded,
            )
        if risk >= warning:
            return DecisionResult(
                final_decision="HOLD",
                policy_decision="AI_HOLD",
                decision_source="ai_warning",
                hard_policy_would_block=False,
                hard_policy_reasons=[],
                anomaly_risk_score=risk,
                anomaly_model="IsolationForest",
                anomaly_model_version=str(info.get("model_version")),
                anomaly_features=selected,
                ai_mode=ai_mode,
                model_confidence=None,
                requires_incident=True,
                requires_containment=False,
                requires_human_review=True,
                response_playbook="SUSPICIOUS_SESSION",
                ai_degraded=degraded,
            )
        return base

    def _playbook_for(self, context: ActionContext, features: dict[str, Any]) -> str:
        arm = float(features.get("arm_count_10s") or 0)
        grip = float(features.get("gripper_count_10s") or 0)
        switches = float(features.get("action_switch_count_10s") or 0)
        if arm >= 1 and grip >= 1 and switches >= 3:
            return "UNSAFE_MANIPULATION_SEQUENCE"
        if context.device_id not in {"fleet-controller-01"}:
            return "ROGUE_DEVICE"
        return "CRITICAL_PHYSICAL_RISK"


decision_orchestrator = DecisionOrchestrator()
