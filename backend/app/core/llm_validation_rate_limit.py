"""Owner-scoped throttling for outbound LLM credential validation attempts."""

from __future__ import annotations

from threading import Lock
import time

from redis.exceptions import RedisError

from app.core.config import settings
from app.core.db_connection_guardrails import get_redis_client
from app.core.errors import AppError


_memory_attempts: dict[str, tuple[int, float]] = {}
_memory_lock = Lock()


class LlmValidationRateLimitError(AppError):
    def __init__(self) -> None:
        super().__init__(
            "Too many credential validation attempts. Please wait and try again.",
            code="llm_provider_rate_limited",
            status_code=429,
        )


def _enforce_memory(owner_id: str, limit: int, window_seconds: int) -> None:
    now = time.monotonic()
    with _memory_lock:
        count, reset_at = _memory_attempts.get(owner_id, (0, now + window_seconds))
        if now >= reset_at:
            count = 0
            reset_at = now + window_seconds
        count += 1
        _memory_attempts[owner_id] = (count, reset_at)
    if count > limit:
        raise LlmValidationRateLimitError()


def enforce_llm_validation_rate_limit(owner_id: str) -> None:
    limit = settings.llm_credential_validation_rate_limit_attempts
    window = settings.llm_credential_validation_rate_limit_window_seconds
    try:
        client = get_redis_client()
        if client is None:
            raise RedisError("Redis is not configured.")
        key = f"qm:llm-credential-validation:{owner_id}"
        count = int(client.incr(key))
        if count == 1:
            client.expire(key, window)
        if count > limit:
            raise LlmValidationRateLimitError()
    except LlmValidationRateLimitError:
        raise
    except Exception:
        # Credential management remains usable during a Redis outage. This
        # process-local fallback still bounds accidental or single-node abuse.
        _enforce_memory(owner_id, limit, window)


__all__ = ["LlmValidationRateLimitError", "enforce_llm_validation_rate_limit"]
