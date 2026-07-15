from __future__ import annotations

import pytest

from app.core import llm_validation_rate_limit as limiter


def test_validation_attempts_are_limited_per_owner_with_memory_fallback(monkeypatch):
    owner_id = "33333333-3333-3333-3333-333333333333"
    monkeypatch.setattr(limiter, "get_redis_client", lambda: None)
    monkeypatch.setattr(limiter.settings, "llm_credential_validation_rate_limit_attempts", 2)
    monkeypatch.setattr(limiter.settings, "llm_credential_validation_rate_limit_window_seconds", 60)
    limiter._memory_attempts.pop(owner_id, None)

    limiter.enforce_llm_validation_rate_limit(owner_id)
    limiter.enforce_llm_validation_rate_limit(owner_id)
    with pytest.raises(limiter.LlmValidationRateLimitError) as raised:
        limiter.enforce_llm_validation_rate_limit(owner_id)

    assert raised.value.code == "llm_provider_rate_limited"
