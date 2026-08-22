"""Glue: build context, score outside teleop locks, open incidents, contain."""

from __future__ import annotations

from typing import Any, Callable

from backend.action_context import (
    ActionContextBuilder,
    ActionType,
    action_type_for_arm,
    action_type_for_gripper,
)
from backend.action_history import action_history
from backend.containment import ContainmentExecutor, containment_executor
from backend.decision_orchestrator import DecisionResult, decision_orchestrator
from backend.incident_store import incident_store
from backend.risk_policy import risk_policy


class AIResponseEngine:
    def __init__(self) -> None:
        self.builder: ActionContextBuilder | None = None
        self.containment = containment_executor

    def bind(
        self,
        *,
        state_provider: Callable[[], dict[str, Any]],
        apply_identity_containment: Callable[[str, list[str]], None],
        terminate_session: Callable[[str], None],
    ) -> None:
        self.builder = ActionContextBuilder(state_provider)
        self.containment = ContainmentExecutor(
            apply_identity_containment=apply_identity_containment,
            terminate_session=terminate_session,
            manipulator_telemetry=lambda: (
                (state_provider() or {}).get("isaac_bridge_state")
                or (state_provider() or {}).get("mock_bridge_state")
                or {}
            ),
        )
        # Keep module singleton in sync for tests/imports.
        import backend.containment as containment_mod

        containment_mod.containment_executor = self.containment

    def evaluate_action(
        self,
        *,
        action_type: ActionType,
        agent_id: str,
        device_id: str,
        robot_id: str,
        credential: str,
        session_id: str | None,
        action_payload: dict[str, Any],
        hard_reasons: list[str] | None = None,
        protection_enabled: bool = True,
    ) -> tuple[DecisionResult, dict[str, Any] | None]:
        if self.builder is None:
            # Lazy default: empty state (tests may bind later).
            self.builder = ActionContextBuilder(lambda: {})

        provisional = self.builder.build(
            action_type=action_type,
            agent_id=agent_id,
            device_id=device_id,
            robot_id=robot_id,
            credential=credential,
            session_id=session_id,
            action_payload=action_payload,
            protection_enabled=protection_enabled,
        )
        window = action_history.summarize_window(provisional)
        context = self.builder.build(
            action_type=action_type,
            agent_id=agent_id,
            device_id=device_id,
            robot_id=robot_id,
            credential=credential,
            session_id=session_id,
            action_payload=action_payload,
            protection_enabled=protection_enabled,
            window=window,
        )
        # Record outside any teleop lock (caller must not hold teleop lock).
        action_history.record(context)

        decision = decision_orchestrator.decide(
            context,
            hard_reasons=hard_reasons,
            window_features=window,
            protection_enabled=protection_enabled,
        )

        incident = None
        if decision.requires_incident or decision.final_decision in {"BLOCK", "HOLD"}:
            fingerprint = (
                f"{context.credential_fingerprint}|{context.device_id}|"
                f"{decision.response_playbook or decision.decision_source}"
            )
            incident = incident_store.open_or_correlate(
                fingerprint=fingerprint,
                agent_id=agent_id,
                device_id=device_id,
                robot_id=robot_id,
                action_event=context.sanitized_dict(),
                hard_policy={
                    "would_block": decision.hard_policy_would_block,
                    "reasons": decision.hard_policy_reasons,
                },
                ai_evidence={
                    "anomaly_risk_score": decision.anomaly_risk_score,
                    "behavioral_rule_score": decision.behavioral_rule_score,
                    "effective_risk": decision.effective_risk,
                    "anomaly_features": decision.anomaly_features,
                    "decision_source": decision.decision_source,
                    "ai_mode": decision.ai_mode,
                },
                model_version=decision.anomaly_model_version,
                policy_version=risk_policy.version,
                playbook=decision.response_playbook,
                decision_source=decision.decision_source,
                window_seconds=int(
                    (risk_policy.raw.get("incident") or {}).get(
                        "correlation_window_seconds", 120
                    )
                ),
            )

        if decision.requires_containment and decision.response_playbook:
            result = self.containment.execute(
                playbook=decision.response_playbook,
                robot_id=robot_id,
                incident_id=(incident or {}).get("incident_id"),
                agent_id=agent_id,
                device_id=device_id,
            )
            if incident:
                incident_store.update_fields(
                    incident["incident_id"],
                    status="CONTAINED" if result.get("ok") else "OPEN",
                    containment_json=result,
                )
                incident = incident_store.get(incident["incident_id"])

        if decision.final_decision == "BLOCK":
            action_history.note_failure(agent_id, device_id)

        return decision, incident


ai_engine = AIResponseEngine()
