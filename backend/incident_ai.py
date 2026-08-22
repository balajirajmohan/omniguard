"""Optional Claude/OpenAI explanation with schema-validated fallback.

Safety boundary: this module never issues robot movement commands.
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field, ValidationError, field_validator

logger = logging.getLogger("omniguard.incident_ai")


class IncidentExplanation(BaseModel):
    summary: str
    physical_impact: str = ""
    why_suspicious: list[str] = Field(default_factory=list)
    containment_taken: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    provider: str = "fallback"
    model: str = "deterministic-template"
    generated_at: str = ""
    fallback_used: bool = True
    fallback_reason: str | None = None
    latency_ms: float | None = None

    @field_validator("why_suspicious", "containment_taken", "recommended_actions", mode="before")
    @classmethod
    def _ensure_list(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        if isinstance(value, list):
            if value and all(isinstance(item, str) and len(item) == 1 for item in value):
                return ["".join(value)]
            return [str(item) for item in value]
        return [str(value)]


def _fallback(event: dict, *, reason: str = "deterministic_template") -> dict:
    reasons = ", ".join(event.get("reasons", [])) or "abnormal command context"
    summary = (
        "A valid fleet credential attempted an unsafe robot command. "
        f"OmniGuard identified {reasons}. The command was rejected, the robot "
        "was stopped, and the credential was revoked. An operator should verify "
        "the originating device and rotate the affected agent credential."
    )
    payload = IncidentExplanation(
        summary=summary,
        physical_impact=(
            "Unsafe movement toward a restricted human zone at elevated speed "
            "could endanger people or equipment."
            if event.get("destination") == "RESTRICTED_ZONE"
            or "RESTRICTED_DESTINATION" in event.get("reasons", [])
            else "Abnormal command context could produce unintended physical motion."
        ),
        why_suspicious=list(event.get("reasons", []) or ["abnormal command context"]),
        containment_taken=list(event.get("actions", [])),
        recommended_actions=[
            "Verify the originating device identity",
            "Rotate the affected agent credential",
            "Review recent commands from this agent",
        ],
        provider="fallback",
        model="deterministic-template",
        generated_at=datetime.now(timezone.utc).isoformat(),
        fallback_used=True,
        fallback_reason=reason,
    )
    data = payload.model_dump()
    data.update(
        {
            "operator_summary": summary,
            "technical_summary": (
                f"decision_source={event.get('decision_source')} "
                f"anomaly_risk_score={event.get('anomaly_risk_score')} "
                f"playbook={event.get('response_playbook')}"
            ),
            "likely_root_cause": (
                "Action-window behavioural anomaly"
                if event.get("decision_source")
                in {"action_window_ai", "behavioral_rule", "hybrid_rule_ml", "ai_warning"}
                else "Hard-policy or identity violation"
            ),
        }
    )
    return data


def _parse_llm_json(text: str) -> dict | None:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(line for line in lines if not line.strip().startswith("```"))
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            try:
                data = json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                return None
        else:
            return None
    if not isinstance(data, dict):
        return None
    return data


def _normalize(
    data: dict,
    *,
    provider: str,
    model: str,
    latency_ms: float,
) -> dict:
    parsed = IncidentExplanation(
        summary=str(data.get("summary") or "Incident explanation unavailable."),
        physical_impact=str(data.get("physical_impact") or ""),
        why_suspicious=data.get("why_suspicious") or [],
        containment_taken=data.get("containment_taken")
        or data.get("actions")
        or [],
        recommended_actions=data.get("recommended_actions") or [],
        provider=provider,
        model=model,
        generated_at=datetime.now(timezone.utc).isoformat(),
        fallback_used=False,
        fallback_reason=None,
        latency_ms=latency_ms,
    )
    return parsed.model_dump()


def _explain_bedrock(event: dict) -> dict:
    model_id = os.getenv("BEDROCK_MODEL_ID")
    if not model_id:
        raise RuntimeError("BEDROCK_MODEL_ID not configured")
    import boto3

    started = time.perf_counter()
    prompt = (
        "Explain this cyber-physical security incident. "
        "Use only the supplied evidence. Return JSON with keys: "
        "summary, physical_impact, why_suspicious (array), "
        "containment_taken (array), recommended_actions (array). "
        "Never issue robot movement commands.\n\nEvidence:\n"
        + json.dumps(event, indent=2)
    )
    client = boto3.client(
        "bedrock-runtime",
        region_name=os.getenv("AWS_REGION", "us-east-1"),
    )
    response = client.converse(
        modelId=model_id,
        system=[
            {
                "text": (
                    "You are OmniGuard's cyber-physical incident analyst. "
                    "Explain only from the supplied evidence. Do not invent "
                    "facts. Do not issue robot movement commands. Return the "
                    "requested JSON structure."
                )
            }
        ],
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={"maxTokens": 400, "temperature": 0.1},
    )
    text = response["output"]["message"]["content"][0]["text"]
    parsed = _parse_llm_json(text)
    if not parsed:
        raise ValueError("bedrock response was not valid JSON object")
    return _normalize(
        parsed,
        provider="bedrock",
        model=model_id,
        latency_ms=(time.perf_counter() - started) * 1000,
    )


def _explain_openai(event: dict) -> dict:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not configured")
    from urllib import request

    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    started = time.perf_counter()
    body = {
        "model": model,
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are OmniGuard's cyber-physical incident analyst. "
                    "Explain only from the supplied evidence. Do not invent facts. "
                    "Do not issue robot movement commands. Return JSON with keys: "
                    "summary, physical_impact, why_suspicious, containment_taken, "
                    "recommended_actions."
                ),
            },
            {
                "role": "user",
                "content": "Evidence:\n" + json.dumps(event, indent=2),
            },
        ],
    }
    req = request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with request.urlopen(req, timeout=30) as resp:
        payload = json.loads(resp.read().decode())
    text = payload["choices"][0]["message"]["content"]
    parsed = _parse_llm_json(text)
    if not parsed:
        raise ValueError("openai response was not valid JSON object")
    return _normalize(
        parsed,
        provider="openai",
        model=model,
        latency_ms=(time.perf_counter() - started) * 1000,
    )


def _explain_anthropic(event: dict) -> dict:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not configured")
    from urllib import request

    model = os.getenv("ANTHROPIC_MODEL", "claude-3-5-haiku-latest")
    started = time.perf_counter()
    body = {
        "model": model,
        "max_tokens": 500,
        "temperature": 0.1,
        "system": (
            "You are OmniGuard's cyber-physical incident analyst. "
            "Return only a JSON object with keys summary, physical_impact, "
            "why_suspicious, containment_taken, recommended_actions. "
            "Never issue robot movement commands."
        ),
        "messages": [
            {
                "role": "user",
                "content": "Evidence:\n" + json.dumps(event, indent=2),
            }
        ],
    }
    req = request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(body).encode(),
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        method="POST",
    )
    with request.urlopen(req, timeout=30) as resp:
        payload = json.loads(resp.read().decode())
    text = payload["content"][0]["text"]
    parsed = _parse_llm_json(text)
    if not parsed:
        raise ValueError("anthropic response was not valid JSON object")
    return _normalize(
        parsed,
        provider="anthropic",
        model=model,
        latency_ms=(time.perf_counter() - started) * 1000,
    )


def explain_incident(event: dict) -> dict:
    provider = os.getenv("LLM_PROVIDER", "fallback").lower()
    if provider in {"", "fallback", "none", "template"}:
        return _fallback(event, reason="provider_not_configured")
    try:
        if provider == "bedrock":
            return _explain_bedrock(event)
        if provider == "openai":
            return _explain_openai(event)
        if provider in {"anthropic", "claude"}:
            return _explain_anthropic(event)
        return _fallback(event, reason=f"unknown_provider:{provider}")
    except (ValidationError, RuntimeError, ValueError, OSError, KeyError) as exc:
        logger.warning("LLM provider %s failed: %s", provider, exc)
        return _fallback(event, reason=f"{provider}_error:{exc}")
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected LLM failure for provider=%s", provider)
        return _fallback(event, reason=f"{provider}_unexpected:{exc}")


def llm_status() -> dict:
    provider = os.getenv("LLM_PROVIDER", "fallback").lower()
    if provider == "bedrock":
        model = os.getenv("BEDROCK_MODEL_ID") or ""
        live = bool(model)
    elif provider == "openai":
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        live = bool(os.getenv("OPENAI_API_KEY"))
    elif provider in {"anthropic", "claude"}:
        model = os.getenv("ANTHROPIC_MODEL", "claude-3-5-haiku-latest")
        live = bool(os.getenv("ANTHROPIC_API_KEY"))
    else:
        model = "deterministic-template"
        live = False
    return {
        "provider": provider if live else "fallback",
        "requested_provider": provider,
        "model": model if live else "deterministic-template",
        "configured": live,
        "mode": "live" if live else "deterministic_fallback",
        "controls_robot": False,
    }
