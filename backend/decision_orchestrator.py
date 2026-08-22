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

    anomaly_risk_score: float | None = None  # IsolationForest only
    behavioral_rule_score: float | None = None  # separate deterministic rule
    effective_risk: float | None = None  # max(ml, rule) used for thresholds
    anomaly_model: str | None = None
    anomaly_model_version: str | None = None
    anomaly_features: dict[str, Any] = Field(default_factory=dict)
    ai_mode: str = "observe"
    model_confidence: float | None = None  # always null unless calibrated

    requires_incident: bool = False
    requires_containment: bool = False
    requires_human_review: bool = False
    requires_pause_stop: bool = False  # HOLD must stop motion without revoking
    response_playbook: str | None = None
    ai_degraded: bool = False


def _source_for(*, ml_hit: bool, rule_hit: bool, warning: bool = False) -> str:
    if ml_hit and rule_hit:
        return "hybrid_rule_ml"
    if rule_hit:
        return "behavioral_rule"
    if ml_hit:
        return "action_window_ai"
    if warning:
        return "ai_warning"
    return "none"


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
        ml_risk, selected, info = action_window_detector.score(features)
        rule_risk = float(info.get("behavioral_rule_score") or 0.0)
        effective = float(info.get("effective_risk") or max(ml_risk, rule_risk))
        degraded = bool(info.get("degraded") or info.get("ai_unavailable"))

        warning = action_window_detector.warning_threshold
        critical = action_window_detector.critical_threshold

        if not action_window_detector.available and rule_risk <= 0:
            return DecisionResult(
                final_decision="ALLOW",
                policy_decision="PERMIT",
                decision_source="deterministic_fallback",
                hard_policy_would_block=False,
                hard_policy_reasons=[],
                anomaly_risk_score=0.0,
                behavioral_rule_score=0.0,
                effective_risk=0.0,
                anomaly_model="IsolationForest",
                anomaly_model_version=action_window_detector.model_version,
                anomaly_features=selected,
                ai_mode=ai_mode,
                model_confidence=None,
                ai_degraded=True,
            )

        ml_critical = ml_risk >= critical
        rule_critical = rule_risk >= critical
        ml_warning = ml_risk >= warning
        rule_warning = rule_risk >= warning
        effective_critical = effective >= critical
        effective_warning = effective >= warning

        base = DecisionResult(
            final_decision="ALLOW",
            policy_decision="PERMIT",
            decision_source="none",
            hard_policy_would_block=False,
            hard_policy_reasons=[],
            anomaly_risk_score=ml_risk,
            behavioral_rule_score=rule_risk,
            effective_risk=effective,
            anomaly_model="IsolationForest",
            anomaly_model_version=str(info.get("model_version")),
            anomaly_features=selected,
            ai_mode=ai_mode,
            model_confidence=None,
            ai_degraded=degraded,
        )

        if ai_mode == "observe":
            if effective_warning:
                base.decision_source = _source_for(
                    ml_hit=ml_critical or ml_warning,
                    rule_hit=rule_critical or rule_warning,
                )
            if effective_critical:
                base.requires_human_review = True
            return base

        if ai_mode == "advise":
            if effective_critical or effective_warning:
                base.final_decision = "HOLD"
                base.policy_decision = "AI_ADVISE_HOLD"
                base.decision_source = _source_for(
                    ml_hit=ml_critical or ml_warning,
                    rule_hit=rule_critical or rule_warning,
                    warning=True,
                )
                base.requires_human_review = True
                base.requires_incident = effective_critical
                base.requires_pause_stop = True
                base.response_playbook = "SUSPICIOUS_SESSION"
            return base

        # enforce
        if effective_critical:
            playbook = self._playbook_for(context, features)
            return DecisionResult(
                final_decision="BLOCK",
                policy_decision="AI_DENY",
                decision_source=_source_for(ml_hit=ml_critical, rule_hit=rule_critical),
                hard_policy_would_block=False,
                hard_policy_reasons=[],
                anomaly_risk_score=ml_risk,
                behavioral_rule_score=rule_risk,
                effective_risk=effective,
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
        if effective_warning:
            return DecisionResult(
                final_decision="HOLD",
                policy_decision="AI_HOLD",
                decision_source=_source_for(
                    ml_hit=ml_warning, rule_hit=rule_warning, warning=True
                ),
                hard_policy_would_block=False,
                hard_policy_reasons=[],
                anomaly_risk_score=ml_risk,
                behavioral_rule_score=rule_risk,
                effective_risk=effective,
                anomaly_model="IsolationForest",
                anomaly_model_version=str(info.get("model_version")),
                anomaly_features=selected,
                ai_mode=ai_mode,
                model_confidence=None,
                requires_incident=True,
                requires_containment=False,
                requires_pause_stop=True,
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
