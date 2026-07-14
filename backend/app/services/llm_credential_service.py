"""Secure owner-scoped LLM credential lifecycle and resolution."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
from fastapi import status
from pydantic import SecretStr

from app.core.config import settings
from app.core.errors import AppError, ConflictError, NotFoundError, ServiceUnavailableError
from app.core.llm_validation_rate_limit import enforce_llm_validation_rate_limit
from app.db.models.llm import LlmExecutionContext, LlmProvider, LlmResolution
from app.db.repositories import llm_credential_repository as repository


SUPPORTED_PROVIDERS = ("gemini", "groq", "openai")


def _error(message: str, code: str, status_code: int) -> AppError:
    return AppError(message, code=code, status_code=status_code)


def _provider(value: str) -> LlmProvider:
    provider = value.strip().lower()
    if provider not in SUPPORTED_PROVIDERS:
        raise _error("This LLM provider is not supported.", "llm_model_not_allowed", 422)
    return provider  # type: ignore[return-value]


def allowed_models(provider: str) -> list[str]:
    return settings.llm_allowed_models[_provider(provider)]


def validate_model(provider: str, model: str) -> str:
    normalized = model.strip()
    if normalized not in allowed_models(provider):
        raise _error("The selected model is not enabled by this QueryMind deployment.", "llm_model_not_allowed", 422)
    return normalized


def _validate_key_shape(api_key: str) -> str:
    value = api_key.strip()
    if not value or len(value.encode("utf-8")) > settings.llm_credential_max_bytes:
        raise _error("The API key is empty or exceeds the configured size limit.", "llm_credential_validation_failed", 422)
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise _error("The API key contains unsupported control characters.", "llm_credential_validation_failed", 422)
    return value


def validate_provider_credential(provider: str, model: str, api_key: str) -> None:
    """Validate access without generating content or exposing provider errors."""
    provider = _provider(provider)
    model = validate_model(provider, model)
    api_key = _validate_key_shape(api_key)
    timeout = httpx.Timeout(settings.llm_credential_validation_timeout_seconds)
    try:
        with httpx.Client(timeout=timeout, follow_redirects=False) as client:
            if provider == "openai":
                response = client.get(
                    f"https://api.openai.com/v1/models/{model}",
                    headers={"Authorization": f"Bearer {api_key}"},
                )
            elif provider == "groq":
                response = client.get(
                    f"https://api.groq.com/openai/v1/models/{model}",
                    headers={"Authorization": f"Bearer {api_key}"},
                )
            else:
                gemini_model = model.removeprefix("models/")
                response = client.get(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{gemini_model}",
                    headers={"x-goog-api-key": api_key},
                )
    except (httpx.TimeoutException, httpx.NetworkError) as exc:
        raise ServiceUnavailableError(
            "The provider could not be reached to validate this credential.",
            code="llm_provider_unavailable",
        ) from None

    if response.status_code in {401, 403}:
        raise _error("The provider rejected this API key.", "llm_credential_invalid", 422)
    if response.status_code == 404:
        raise _error("The API key cannot access the selected model.", "llm_model_not_allowed", 422)
    if response.status_code == 429:
        raise _error("The provider rate-limited credential validation.", "llm_provider_rate_limited", 429)
    if response.status_code >= 500:
        raise ServiceUnavailableError("The provider is temporarily unavailable.", code="llm_provider_unavailable")
    if not response.is_success:
        raise _error("The provider could not validate this credential.", "llm_credential_validation_failed", 422)


def get_configuration(owner_id: str) -> dict[str, Any]:
    preferences = repository.get_preferences(owner_id)
    credential_map = {item.provider: item for item in repository.list_credentials(owner_id)}
    used, limit = repository.get_fallback_usage(owner_id)
    privileged = owner_id in settings.deployment_llm_privileged_user_ids
    deployment_available = bool(settings.deployment_llm_api_key(settings.resolved_llm_provider))
    providers = []
    for provider in SUPPORTED_PROVIDERS:
        credential = credential_map.get(provider)
        providers.append(
            {
                "provider": provider,
                "enabled": bool(allowed_models(provider)),
                "configured": credential is not None,
                "status": credential.status if credential else None,
                "key_hint": credential.key_hint if credential else None,
                "credential_revision": credential.credential_revision if credential else None,
                "last_validated_at": credential.last_validated_at if credential else None,
                "validation_failure_code": credential.validation_failure_code if credential else None,
                "allowed_models": allowed_models(provider),
            }
        )
    return {
        "mode": settings.llm_credential_mode,
        **preferences,
        "providers": providers,
        "deployment_fallback": {
            "available": deployment_available and settings.llm_credential_mode != "byok_required",
            "privileged": privileged,
            "calls_used": used,
            "calls_limit": limit,
            "calls_remaining": max(0, limit - used),
        },
    }


def save_credential(
    owner_id: str,
    provider: str,
    *,
    api_key: str,
    model: str,
    expected_revision: int | None,
) -> dict[str, Any]:
    provider = _provider(provider)
    model = validate_model(provider, model)
    api_key = _validate_key_shape(api_key)
    enforce_llm_validation_rate_limit(owner_id)
    validate_provider_credential(provider, model, api_key)
    try:
        credential, preference_revision = repository.save_validated_credential(
            owner_id, provider, api_key, model, expected_revision
        )
    except ValueError as exc:
        if str(exc) == "credential_revision_conflict":
            raise ConflictError("The credential changed in another session.", code="llm_credential_conflict") from exc
        raise
    return {
        **credential.model_dump(),
        "preference_revision": preference_revision,
    }


def revalidate_credential(owner_id: str, provider: str) -> dict[str, Any]:
    provider = _provider(provider)
    stored = repository.get_credential(owner_id, provider, include_secret=True)
    if not stored:
        raise NotFoundError("LLM credential not found.", code="llm_credential_not_found")
    preferences = repository.get_preferences(owner_id)
    model = preferences["preferred_model"] if preferences["preferred_provider"] == provider else settings.llm_default_model(provider)
    model = validate_model(provider, model)
    api_key = stored.api_key.get_secret_value()
    enforce_llm_validation_rate_limit(owner_id)
    validate_provider_credential(provider, model, api_key)
    try:
        credential, preference_revision = repository.save_validated_credential(
            owner_id, provider, api_key, model, stored.credential_revision
        )
    except ValueError as exc:
        raise ConflictError("The credential changed in another session.", code="llm_credential_conflict") from exc
    return {**credential.model_dump(), "preference_revision": preference_revision}


def update_preferences(
    owner_id: str,
    *,
    expected_revision: int,
    preferred_provider: str | None,
    preferred_model: str | None,
    allow_background_ai: bool,
) -> dict:
    if preferred_provider is not None:
        preferred_provider = _provider(preferred_provider)
        credential = repository.get_credential(owner_id, preferred_provider)
        if not credential:
            raise NotFoundError("Configure this provider before selecting it.", code="llm_credential_not_found")
        preferred_model = validate_model(preferred_provider, preferred_model or settings.llm_default_model(preferred_provider))
    else:
        preferred_model = None
    try:
        return repository.update_preferences(
            owner_id,
            expected_revision=expected_revision,
            provider=preferred_provider,
            model=preferred_model,
            allow_background_ai=allow_background_ai,
        )
    except ValueError as exc:
        raise ConflictError("LLM preferences changed in another session.", code="llm_credential_conflict") from exc


def delete_credential(
    owner_id: str,
    provider: str,
    *,
    expected_revision: int,
    replacement_provider: str | None,
) -> None:
    provider = _provider(provider)
    preferences = repository.get_preferences(owner_id)
    replacement_model = None
    if preferences["preferred_provider"] == provider:
        remaining = [item for item in repository.list_credentials(owner_id) if item.provider != provider]
        if remaining:
            if not replacement_provider:
                raise _error("Choose a replacement preferred provider before deleting this credential.", "llm_credential_conflict", 409)
            replacement_provider = _provider(replacement_provider)
            if not any(item.provider == replacement_provider for item in remaining):
                raise NotFoundError("Replacement credential not found.", code="llm_credential_not_found")
            replacement_model = settings.llm_default_model(replacement_provider)
        else:
            replacement_provider = None
    try:
        deleted = repository.delete_credential(
            owner_id,
            provider,
            expected_revision=expected_revision,
            replacement_provider=replacement_provider,
            replacement_model=replacement_model,
        )
    except ValueError as exc:
        raise ConflictError("The credential changed in another session.", code="llm_credential_conflict") from exc
    if not deleted:
        raise NotFoundError("LLM credential not found.", code="llm_credential_not_found")


def resolve(context: LlmExecutionContext) -> LlmResolution:
    preferences = repository.get_preferences(context.owner_id)
    provider = preferences["preferred_provider"]
    if provider:
        credential = repository.get_credential(context.owner_id, provider, include_secret=True)
        if credential:
            if credential.status != "valid":
                raise _error("Your selected API key must be replaced or revalidated.", "llm_credential_invalid", 428)
            if context.interaction_type == "automatic" and not preferences["allow_background_ai"]:
                raise _error("Background AI is disabled for this account.", "llm_background_usage_disabled", 428)
            model = validate_model(provider, preferences["preferred_model"] or settings.llm_default_model(provider))
            return LlmResolution(
                provider=provider,
                model=model,
                credential_source="user",
                credential_id=credential.id,
                credential_revision=credential.credential_revision,
                api_key=credential.api_key,
            )

    mode = settings.llm_credential_mode.strip().lower()
    privileged = context.owner_id in settings.deployment_llm_privileged_user_ids
    if mode == "byok_required":
        raise _error("Configure a personal LLM API key to use this feature.", "llm_credential_required", 428)
    if context.interaction_type == "automatic" and not privileged and mode != "deployment":
        raise _error("Automatic AI requires a personal key with background usage enabled.", "llm_background_usage_disabled", 428)

    deployment_provider = settings.resolved_llm_provider
    deployment_key = settings.deployment_llm_api_key(deployment_provider)
    if not deployment_key:
        raise ServiceUnavailableError("Deployment LLM fallback is not configured.", code="deployment_llm_unavailable")
    used, limit = repository.get_fallback_usage(context.owner_id)
    unmetered = privileged or mode == "deployment"
    if not unmetered and used >= limit:
        raise _error("Your QueryMind deployment-key trial is exhausted. Add a personal API key.", "deployment_llm_trial_exhausted", 402)
    return LlmResolution(
        provider=deployment_provider,
        model=validate_model(deployment_provider, settings.resolved_llm_model),
        credential_source="deployment",
        credential_revision=None,
        privileged=unmetered,
        api_key=SecretStr(deployment_key),
    )


def preflight(owner_id: str, feature: str, *, interaction_type: str = "explicit") -> dict[str, Any]:
    resolution = resolve(
        LlmExecutionContext(owner_id=owner_id, feature=feature, interaction_type=interaction_type)
    )
    return {
        "available": True,
        "provider": resolution.provider,
        "model": resolution.model,
        "credential_source": resolution.credential_source,
    }


def _runtime_failure_code(exc: Exception) -> str:
    status_code = getattr(exc, "status_code", None)
    if status_code is None:
        response = getattr(exc, "response", None)
        status_code = getattr(response, "status_code", None)
    if status_code in {401, 403}:
        return "llm_credential_invalid" if status_code == 401 else "llm_provider_permission_denied"
    if status_code == 429:
        return "llm_provider_rate_limited"
    if isinstance(status_code, int) and status_code >= 500:
        return "llm_provider_unavailable"
    name = exc.__class__.__name__.lower()
    if "authentication" in name or "unauthorized" in name:
        return "llm_credential_invalid"
    if "permission" in name:
        return "llm_provider_permission_denied"
    if "rate" in name or "quota" in name:
        return "llm_provider_rate_limited"
    if "timeout" in name or "connection" in name:
        return "llm_provider_unavailable"
    if isinstance(exc, AppError):
        return exc.code
    return "llm_provider_unavailable"


def _raise_sanitized_runtime_error(exc: Exception, code: str) -> None:
    if isinstance(exc, AppError):
        raise exc
    if code == "llm_credential_invalid":
        raise _error("The selected API key was rejected by the provider.", code, 428) from None
    if code == "llm_provider_permission_denied":
        raise _error("The selected API key cannot use this model.", code, 403) from None
    if code == "llm_provider_rate_limited":
        raise _error("The selected provider is currently rate-limiting requests.", code, 429) from None
    raise ServiceUnavailableError("The selected LLM provider is temporarily unavailable.", code=code) from None


def _usage_metadata(result: Any) -> tuple[int | None, int | None]:
    metadata = getattr(result, "usage_metadata", None) or {}
    if not metadata:
        response_metadata = getattr(result, "response_metadata", None) or {}
        metadata = response_metadata.get("token_usage") or response_metadata.get("usage") or {}
    if not metadata:
        generations = getattr(result, "generations", None) or []
        for generation_group in generations:
            candidates = generation_group if isinstance(generation_group, list) else [generation_group]
            for generation in candidates:
                message = getattr(generation, "message", None)
                input_tokens, output_tokens = _usage_metadata(message or generation)
                if input_tokens is not None or output_tokens is not None:
                    return input_tokens, output_tokens
    return metadata.get("input_tokens") or metadata.get("prompt_tokens"), metadata.get("output_tokens") or metadata.get("completion_tokens")


def invoke_metered(context: LlmExecutionContext, resolution: LlmResolution, callback: Callable[[], Any]) -> Any:
    try:
        event_id = repository.start_usage_event(
            context.owner_id,
            resolution,
            feature=context.feature,
            workflow_type=context.workflow_type,
            workflow_id=context.workflow_id,
            interaction_type=context.interaction_type,
        )
    except ValueError as exc:
        raise _error("Your QueryMind deployment-key trial is exhausted. Add a personal API key.", "deployment_llm_trial_exhausted", 402) from exc
    repository.snapshot_run_resolution(context.owner_id, context.workflow_type, context.workflow_id, resolution)
    started = time.perf_counter()
    try:
        result = callback()
        input_tokens, output_tokens = _usage_metadata(result)
        repository.finish_usage_event(
            context.owner_id,
            event_id,
            status="completed",
            latency_ms=(time.perf_counter() - started) * 1000,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        return result
    except Exception as exc:
        code = _runtime_failure_code(exc)
        repository.finish_usage_event(
            context.owner_id,
            event_id,
            status="failed",
            failure_code=code,
            latency_ms=(time.perf_counter() - started) * 1000,
        )
        if code == "llm_credential_invalid" and resolution.credential_source == "user" and resolution.credential_id:
            repository.mark_credential_invalid(context.owner_id, resolution.credential_id, code)
        _raise_sanitized_runtime_error(exc, code)


async def ainvoke_metered(
    context: LlmExecutionContext,
    resolution: LlmResolution,
    callback: Callable[[], Awaitable[Any]],
) -> Any:
    try:
        event_id = repository.start_usage_event(
            context.owner_id,
            resolution,
            feature=context.feature,
            workflow_type=context.workflow_type,
            workflow_id=context.workflow_id,
            interaction_type=context.interaction_type,
        )
    except ValueError as exc:
        raise _error("Your QueryMind deployment-key trial is exhausted. Add a personal API key.", "deployment_llm_trial_exhausted", 402) from exc
    repository.snapshot_run_resolution(context.owner_id, context.workflow_type, context.workflow_id, resolution)
    started = time.perf_counter()
    try:
        result = await callback()
        input_tokens, output_tokens = _usage_metadata(result)
        repository.finish_usage_event(
            context.owner_id,
            event_id,
            status="completed",
            latency_ms=(time.perf_counter() - started) * 1000,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        return result
    except Exception as exc:
        code = _runtime_failure_code(exc)
        repository.finish_usage_event(
            context.owner_id,
            event_id,
            status="failed",
            failure_code=code,
            latency_ms=(time.perf_counter() - started) * 1000,
        )
        if code == "llm_credential_invalid" and resolution.credential_source == "user" and resolution.credential_id:
            repository.mark_credential_invalid(context.owner_id, resolution.credential_id, code)
        _raise_sanitized_runtime_error(exc, code)


def list_usage(
    owner_id: str,
    *,
    limit: int = 50,
    before=None,
    provider: str | None = None,
    credential_source: str | None = None,
    feature: str | None = None,
    status: str | None = None,
    since=None,
):
    if provider is not None:
        provider = _provider(provider)
    if credential_source not in {None, "user", "deployment"}:
        raise _error("Unknown credential source filter.", "llm_credential_validation_failed", 422)
    if status not in {None, "started", "completed", "failed"}:
        raise _error("Unknown usage status filter.", "llm_credential_validation_failed", 422)
    return repository.list_usage_events(
        owner_id,
        limit=min(max(limit, 1), 100),
        before=before,
        provider=provider,
        credential_source=credential_source,
        feature=feature,
        status=status,
        since=since,
    )


__all__ = [
    "ainvoke_metered",
    "allowed_models",
    "delete_credential",
    "get_configuration",
    "invoke_metered",
    "list_usage",
    "preflight",
    "resolve",
    "revalidate_credential",
    "save_credential",
    "update_preferences",
    "validate_model",
    "validate_provider_credential",
]
