from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from pydantic import SecretStr

from app.core.errors import AppError
from app.db.models.llm import LlmExecutionContext, LlmResolution, StoredLlmCredential
from app.services import llm_credential_service as service


OWNER_ID = "11111111-1111-1111-1111-111111111111"


def _preferences(**updates):
    values = {
        "preferred_provider": None,
        "preferred_model": None,
        "preference_revision": 1,
        "allow_background_ai": False,
    }
    values.update(updates)
    return values


def _credential(status="valid"):
    return StoredLlmCredential(
        id="22222222-2222-2222-2222-222222222222",
        owner_id=OWNER_ID,
        provider="groq",
        key_hint="cret",
        status=status,
        credential_revision=3,
        last_validated_at=datetime.now(timezone.utc),
        api_key=SecretStr("user-secret"),
    )


def test_resolve_prefers_valid_owner_credential(monkeypatch):
    monkeypatch.setattr(service.repository, "get_preferences", lambda _owner: _preferences(preferred_provider="groq", preferred_model="llama-3.3-70b-versatile"))
    monkeypatch.setattr(service.repository, "get_credential", lambda *_args, **_kwargs: _credential())

    resolution = service.resolve(LlmExecutionContext(owner_id=OWNER_ID, feature="chat"))

    assert resolution.credential_source == "user"
    assert resolution.credential_revision == 3
    assert resolution.api_key.get_secret_value() == "user-secret"


def test_invalid_preferred_credential_never_falls_back(monkeypatch):
    monkeypatch.setattr(service.repository, "get_preferences", lambda _owner: _preferences(preferred_provider="groq", preferred_model="llama-3.3-70b-versatile"))
    monkeypatch.setattr(service.repository, "get_credential", lambda *_args, **_kwargs: _credential(status="invalid"))

    with pytest.raises(AppError) as raised:
        service.resolve(LlmExecutionContext(owner_id=OWNER_ID, feature="chat"))

    assert raised.value.code == "llm_credential_invalid"


def test_normal_automatic_work_cannot_spend_deployment_trial(monkeypatch):
    monkeypatch.setattr(service.repository, "get_preferences", lambda _owner: _preferences())
    monkeypatch.setattr(service.settings, "llm_credential_mode", "hybrid")
    monkeypatch.setattr(service.settings, "deployment_llm_privileged_user_ids_raw", "")

    with pytest.raises(AppError) as raised:
        service.resolve(
            LlmExecutionContext(
                owner_id=OWNER_ID,
                feature="question_suggestions",
                interaction_type="automatic",
            )
        )

    assert raised.value.code == "llm_background_usage_disabled"


def test_explicit_hybrid_work_uses_available_trial(monkeypatch):
    monkeypatch.setattr(service.repository, "get_preferences", lambda _owner: _preferences())
    monkeypatch.setattr(service.repository, "get_fallback_usage", lambda _owner: (2, 10))
    monkeypatch.setattr(service.settings, "llm_credential_mode", "hybrid")
    monkeypatch.setattr(service.settings, "llm_provider", "groq")
    monkeypatch.setattr(service.settings, "groq_api_key", "deployment-secret")
    monkeypatch.setattr(service.settings, "gemini_api_key", "")
    monkeypatch.setattr(service.settings, "groq_model", "llama-3.3-70b-versatile")
    monkeypatch.setattr(service.settings, "deployment_llm_privileged_user_ids_raw", "")
    monkeypatch.setattr(
        service,
        "validate_model",
        lambda provider, _model: "llama-3.3-70b-versatile" if provider == "groq" else _model,
    )

    resolution = service.resolve(LlmExecutionContext(owner_id=OWNER_ID, feature="chat"))

    assert resolution.credential_source == "deployment"
    assert resolution.privileged is False


def test_metering_records_each_invocation(monkeypatch):
    calls = []
    monkeypatch.setattr(service.repository, "start_usage_event", lambda *_args, **_kwargs: calls.append("started") or "event-1")
    monkeypatch.setattr(service.repository, "finish_usage_event", lambda *_args, **kwargs: calls.append(kwargs["status"]))
    monkeypatch.setattr(service.repository, "snapshot_run_resolution", lambda *_args, **_kwargs: None)
    resolution = LlmResolution(
        provider="groq",
        model="llama-3.3-70b-versatile",
        credential_source="deployment",
        api_key=SecretStr("secret"),
    )

    result = service.invoke_metered(
        LlmExecutionContext(owner_id=OWNER_ID, feature="chat"),
        resolution,
        lambda: SimpleNamespace(content="ok", usage_metadata={"input_tokens": 2, "output_tokens": 1}),
    )

    assert result.content == "ok"
    assert calls == ["started", "completed"]


def test_trial_exhaustion_stops_before_provider_callback(monkeypatch):
    called = False

    def exhaust(*_args, **_kwargs):
        raise ValueError("deployment_llm_trial_exhausted")

    def provider_call():
        nonlocal called
        called = True

    monkeypatch.setattr(service.repository, "start_usage_event", exhaust)
    resolution = LlmResolution(
        provider="groq",
        model="llama-3.3-70b-versatile",
        credential_source="deployment",
        api_key=SecretStr("secret"),
    )

    with pytest.raises(AppError) as raised:
        service.invoke_metered(
            LlmExecutionContext(owner_id=OWNER_ID, feature="chat"),
            resolution,
            provider_call,
        )

    assert raised.value.code == "deployment_llm_trial_exhausted"
    assert called is False


def test_provider_failures_do_not_retain_raw_exception_causes(monkeypatch):
    monkeypatch.setattr(service.repository, "start_usage_event", lambda *_args, **_kwargs: "event-1")
    monkeypatch.setattr(service.repository, "finish_usage_event", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(service.repository, "snapshot_run_resolution", lambda *_args, **_kwargs: None)
    resolution = LlmResolution(
        provider="groq",
        model="llama-3.3-70b-versatile",
        credential_source="user",
        credential_id="22222222-2222-2222-2222-222222222222",
        credential_revision=3,
        api_key=SecretStr("secret"),
    )

    with pytest.raises(AppError) as raised:
        service.invoke_metered(
            LlmExecutionContext(owner_id=OWNER_ID, feature="chat"),
            resolution,
            lambda: (_ for _ in ()).throw(RuntimeError("raw-provider-body")),
        )

    assert raised.value.code == "llm_provider_unavailable"
    assert raised.value.__cause__ is None
    assert "raw-provider-body" not in str(raised.value)
