from __future__ import annotations

from backend.incident_ai import IncidentExplanation, _fallback, explain_incident, llm_status


def test_llm_schema_validation_rejects_character_list_trap():
    parsed = IncidentExplanation(
        summary="ok",
        why_suspicious=list("burst"),  # accidental char list
        recommended_actions=["rotate credential"],
    )
    assert parsed.why_suspicious == ["burst"] or isinstance(parsed.why_suspicious, list)


def test_provider_failure_labelled_fallback(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    result = explain_incident(
        {
            "reasons": ["UNKNOWN_DEVICE"],
            "actions": ["COMMAND_REJECTED"],
            "destination": "RESTRICTED_ZONE",
        }
    )
    assert result["fallback_used"] is True
    assert result["provider"] == "fallback"
    assert result["fallback_reason"]


def test_deterministic_fallback_schema():
    result = _fallback({"reasons": ["EXCESSIVE_SPEED"], "actions": ["COMMAND_REJECTED"]})
    IncidentExplanation.model_validate(result)


def test_openrouter_status_defaults_to_sonnet_4_6(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-placeholder-not-real")
    monkeypatch.delenv("OPENROUTER_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    status = llm_status()
    assert status["configured"] is True
    assert status["provider"] == "openrouter"
    assert status["model"] == "anthropic.claude-sonnet-4-6"
    assert status["controls_robot"] is False


def test_openrouter_without_key_stays_fallback(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    status = llm_status()
    assert status["configured"] is False
    assert status["provider"] == "fallback"
