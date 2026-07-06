"""Tests for LLM provider configuration."""

from app.core.config import Settings


def test_resolved_provider_prefers_gemini_when_only_gemini_key_set(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    settings = Settings()
    assert settings.resolved_llm_provider == "gemini"


def test_resolved_model_uses_gemini_model(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.5-flash")
    monkeypatch.setenv("AGENT_MODEL", "")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    settings = Settings()
    assert settings.resolved_llm_provider == "gemini"
    assert settings.resolved_llm_model == "gemini-2.5-flash"
