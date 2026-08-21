"""Optional Claude-on-Bedrock explanation with a safe local fallback."""

from __future__ import annotations

import json
import os


def _fallback(event: dict) -> str:
    reasons = ", ".join(event.get("reasons", [])) or "abnormal command context"
    return (
        "A valid fleet credential attempted an unsafe robot command. "
        f"OmniGuard identified {reasons}. The command was rejected, the robot "
        "was stopped, and the credential was revoked. An operator should verify "
        "the originating device and rotate the affected agent credential."
    )


def explain_incident(event: dict) -> dict:
    """Return a structured incident explanation.

    Prefer Bedrock Claude when LLM_PROVIDER=bedrock; otherwise use a
    deterministic template. Never issues robot movement commands.
    """
    text = _fallback(event)
    if os.getenv("LLM_PROVIDER", "fallback").lower() == "bedrock":
        model_id = os.getenv("BEDROCK_MODEL_ID")
        if model_id:
            try:
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
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    pass
            except Exception:
                text = _fallback(event)

    return {
        "summary": text,
        "physical_impact": (
            "Unsafe movement toward a restricted human zone at elevated speed "
            "could endanger people or equipment."
            if "RESTRICTED" in ",".join(event.get("reasons", []))
            or event.get("destination") == "RESTRICTED_ZONE"
            else "Abnormal command context could produce unintended physical motion."
        ),
        "why_suspicious": event.get("reasons", []) or ["abnormal command context"],
        "containment_taken": event.get("actions", []),
        "recommended_actions": [
            "Verify the originating device identity",
            "Rotate the affected agent credential",
            "Review recent commands from this agent",
        ],
    }
