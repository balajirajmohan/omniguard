"""Optional Claude/OpenAI explanation with a safe local fallback.

Safety boundary: this module never issues robot movement commands.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone


def _fallback(event: dict) -> dict:
    reasons = ", ".join(event.get("reasons", [])) or "abnormal command context"
    summary = (
        "A valid fleet credential attempted an unsafe robot command. "
        f"OmniGuard identified {reasons}. The command was rejected, the robot "
        "was stopped, and the credential was revoked. An operator should verify "
        "the originating device and rotate the affected agent credential."
    )
    return {
        "summary": summary,
        "physical_impact": (
            "Unsafe movement toward a restricted human zone at elevated speed "
            "could endanger people or equipment."
            if event.get("destination") == "RESTRICTED_ZONE"
            or "RESTRICTED_DESTINATION" in event.get("reasons", [])
            else "Abnormal command context could produce unintended physical motion."
        ),
        "why_suspicious": event.get("reasons", []) or ["abnormal command context"],
        "containment_taken": event.get("actions", []),
        "recommended_actions": [
            "Verify the originating device identity",
            "Rotate the affected agent credential",
            "Review recent commands from this agent",
        ],
        "provider": "fallback",
        "model": "deterministic-template",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "fallback_used": True,
    }


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


def _normalize(data: dict, *, provider: str, model: str, fallback_used: bool) -> dict:
    return {
        "summary": data.get("summary") or "Incident explanation unavailable.",
        "physical_impact": data.get("physical_impact") or "",
        "why_suspicious": list(data.get("why_suspicious") or []),
        "containment_taken": list(
            data.get("containment_taken") or data.get("actions") or []
        ),
        "recommended_actions": list(data.get("recommended_actions") or []),
        "provider": provider,
        "model": model,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "fallback_used": fallback_used,
    }


def _explain_bedrock(event: dict) -> dict | None:
    model_id = os.getenv("BEDROCK_MODEL_ID")
    if not model_id:
        return None
    import boto3

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
        return None
    return _normalize(parsed, provider="bedrock", model=model_id, fallback_used=False)


def _explain_openai(event: dict) -> dict | None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    from urllib import request

    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
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
        return None
    return _normalize(parsed, provider="openai", model=model, fallback_used=False)


def explain_incident(event: dict) -> dict:
    provider = os.getenv("LLM_PROVIDER", "fallback").lower()
    try:
        if provider == "bedrock":
            result = _explain_bedrock(event)
            if result:
                return result
        elif provider == "openai":
            result = _explain_openai(event)
            if result:
                return result
    except Exception:
        pass
    return _fallback(event)


def llm_status() -> dict:
    provider = os.getenv("LLM_PROVIDER", "fallback").lower()
    if provider == "bedrock":
        model = os.getenv("BEDROCK_MODEL_ID") or ""
        configured = bool(model)
    elif provider == "openai":
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        configured = bool(os.getenv("OPENAI_API_KEY"))
    else:
        model = "deterministic-template"
        configured = True
    return {
        "provider": provider,
        "model": model,
        "configured": configured,
        "controls_robot": False,
    }
