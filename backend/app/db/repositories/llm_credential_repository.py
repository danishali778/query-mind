"""Owner-scoped persistence for LLM credentials, preferences, and usage."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import delete, desc, func, select

from app.core.config import settings
from app.core.security import decrypt, encrypt
from app.db.models.llm import LlmCredential, LlmResolution, LlmUsageEvent, StoredLlmCredential
from app.db.orm_models import (
    ChatAgentRunORM,
    DashboardGenerationRunORM,
    LlmUsageEventORM,
    QuestionSuggestionSetORM,
    SemanticSuggestionRunORM,
    UserLlmCredentialORM,
    UserSettingsORM,
    UserSubscriptionORM,
)
from app.db.session import read_session_scope, session_scope


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _to_summary(row: UserLlmCredentialORM) -> LlmCredential:
    return LlmCredential(
        id=row.id,
        owner_id=row.owner_id,
        provider=row.provider,
        key_hint=row.key_hint,
        status=row.status,
        credential_revision=row.credential_revision,
        last_validated_at=row.last_validated_at,
        validation_failure_code=row.validation_failure_code,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _to_stored(row: UserLlmCredentialORM) -> StoredLlmCredential:
    from pydantic import SecretStr

    value = decrypt(row.encrypted_api_key)
    if not value:
        raise RuntimeError("Stored LLM credential cannot be decrypted.")
    return StoredLlmCredential(**_to_summary(row).model_dump(), api_key=SecretStr(value))


def list_credentials(owner_id: str) -> list[LlmCredential]:
    with read_session_scope() as session:
        rows = session.scalars(
            select(UserLlmCredentialORM)
            .where(UserLlmCredentialORM.owner_id == owner_id)
            .order_by(UserLlmCredentialORM.provider)
        ).all()
        return [_to_summary(row) for row in rows]


def get_credential(owner_id: str, provider: str, *, include_secret: bool = False):
    with read_session_scope() as session:
        row = session.scalar(
            select(UserLlmCredentialORM).where(
                UserLlmCredentialORM.owner_id == owner_id,
                UserLlmCredentialORM.provider == provider,
            )
        )
        if not row:
            return None
        return _to_stored(row) if include_secret else _to_summary(row)


def save_validated_credential(
    owner_id: str,
    provider: str,
    api_key: str,
    model: str,
    expected_revision: int | None,
) -> tuple[LlmCredential, int]:
    now = _utcnow()
    with session_scope() as session:
        row = session.scalar(
            select(UserLlmCredentialORM)
            .where(
                UserLlmCredentialORM.owner_id == owner_id,
                UserLlmCredentialORM.provider == provider,
            )
            .with_for_update()
        )
        if row:
            if expected_revision is None or row.credential_revision != expected_revision:
                raise ValueError("credential_revision_conflict")
            row.encrypted_api_key = encrypt(api_key) or ""
            row.key_hint = api_key[-4:]
            row.status = "valid"
            row.validation_failure_code = None
            row.last_validated_at = now
            row.credential_revision += 1
            row.updated_at = now
        else:
            if expected_revision is not None:
                raise ValueError("credential_revision_conflict")
            row = UserLlmCredentialORM(
                owner_id=owner_id,
                provider=provider,
                encrypted_api_key=encrypt(api_key) or "",
                key_hint=api_key[-4:],
                status="valid",
                credential_revision=1,
                last_validated_at=now,
            )
            session.add(row)
            session.flush()

        preference = session.get(UserSettingsORM, owner_id)
        if preference and not preference.preferred_llm_provider:
            preference.preferred_llm_provider = provider
            preference.preferred_llm_model = model
            preference.ai_model = model
            preference.llm_preference_revision = (preference.llm_preference_revision or 1) + 1
            preference.updated_at = now
        session.flush()
        return _to_summary(row), (preference.llm_preference_revision if preference else 1)


def mark_credential_invalid(owner_id: str, credential_id: str, failure_code: str) -> None:
    with session_scope() as session:
        row = session.scalar(
            select(UserLlmCredentialORM).where(
                UserLlmCredentialORM.id == credential_id,
                UserLlmCredentialORM.owner_id == owner_id,
            )
        )
        if row:
            row.status = "invalid"
            row.validation_failure_code = failure_code
            row.updated_at = _utcnow()


def get_preferences(owner_id: str) -> dict:
    with read_session_scope() as session:
        row = session.get(UserSettingsORM, owner_id)
        if not row:
            return {
                "preferred_provider": None,
                "preferred_model": None,
                "preference_revision": 1,
                "allow_background_ai": False,
            }
        return {
            "preferred_provider": row.preferred_llm_provider,
            "preferred_model": row.preferred_llm_model,
            "preference_revision": row.llm_preference_revision or 1,
            "allow_background_ai": bool(row.allow_background_ai),
        }


def update_preferences(
    owner_id: str,
    *,
    expected_revision: int,
    provider: str | None,
    model: str | None,
    allow_background_ai: bool,
) -> dict:
    with session_scope() as session:
        row = session.scalar(
            select(UserSettingsORM)
            .where(UserSettingsORM.owner_id == owner_id)
            .with_for_update()
        )
        if not row:
            raise RuntimeError("Account settings are unavailable for this user.")
        if (row.llm_preference_revision or 1) != expected_revision:
            raise ValueError("preference_revision_conflict")
        row.preferred_llm_provider = provider
        row.preferred_llm_model = model
        row.ai_model = model or ""
        row.allow_background_ai = allow_background_ai
        row.llm_preference_revision = (row.llm_preference_revision or 1) + 1
        row.updated_at = _utcnow()
        session.flush()
        return {
            "preferred_provider": row.preferred_llm_provider,
            "preferred_model": row.preferred_llm_model,
            "preference_revision": row.llm_preference_revision,
            "allow_background_ai": bool(row.allow_background_ai),
        }


def delete_credential(
    owner_id: str,
    provider: str,
    *,
    expected_revision: int,
    replacement_provider: str | None,
    replacement_model: str | None,
) -> bool:
    with session_scope() as session:
        row = session.scalar(
            select(UserLlmCredentialORM)
            .where(
                UserLlmCredentialORM.owner_id == owner_id,
                UserLlmCredentialORM.provider == provider,
            )
            .with_for_update()
        )
        if not row:
            return False
        if row.credential_revision != expected_revision:
            raise ValueError("credential_revision_conflict")
        preference = session.get(UserSettingsORM, owner_id)
        if preference and preference.preferred_llm_provider == provider:
            preference.preferred_llm_provider = replacement_provider
            preference.preferred_llm_model = replacement_model
            preference.ai_model = replacement_model or ""
            preference.llm_preference_revision = (preference.llm_preference_revision or 1) + 1
            preference.updated_at = _utcnow()
        session.delete(row)
        return True


def get_fallback_usage(owner_id: str) -> tuple[int, int]:
    with session_scope() as session:
        row = session.get(UserSubscriptionORM, owner_id)
        if not row:
            row = UserSubscriptionORM(
                owner_id=owner_id,
                plan_type="free",
                queries_used=0,
                queries_limit=100,
                ai_used=0,
                ai_limit=30,
                deployment_llm_calls_used=0,
                deployment_llm_calls_limit=settings.deployment_llm_trial_call_limit,
            )
            session.add(row)
            session.flush()
        return row.deployment_llm_calls_used or 0, row.deployment_llm_calls_limit


def start_usage_event(
    owner_id: str,
    resolution: LlmResolution,
    *,
    feature: str,
    workflow_type: str | None,
    workflow_id: str | None,
    interaction_type: str,
) -> str:
    with session_scope() as session:
        if resolution.credential_source == "deployment" and not resolution.privileged:
            subscription = session.scalar(
                select(UserSubscriptionORM)
                .where(UserSubscriptionORM.owner_id == owner_id)
                .with_for_update()
            )
            if not subscription:
                subscription = UserSubscriptionORM(
                    owner_id=owner_id,
                    plan_type="free",
                    queries_used=0,
                    queries_limit=100,
                    ai_used=0,
                    ai_limit=30,
                    deployment_llm_calls_used=0,
                    deployment_llm_calls_limit=settings.deployment_llm_trial_call_limit,
                )
                session.add(subscription)
                session.flush()
            used = subscription.deployment_llm_calls_used or 0
            limit = subscription.deployment_llm_calls_limit
            if used >= limit:
                raise ValueError("deployment_llm_trial_exhausted")
            subscription.deployment_llm_calls_used = used + 1
            subscription.updated_at = _utcnow()

        event = LlmUsageEventORM(
            owner_id=owner_id,
            provider=resolution.provider,
            model=resolution.model,
            credential_source=resolution.credential_source,
            credential_id=resolution.credential_id,
            credential_revision=resolution.credential_revision,
            feature=feature,
            workflow_type=workflow_type,
            workflow_id=workflow_id,
            interaction_type=interaction_type,
            status="started",
        )
        session.add(event)
        session.flush()
        return event.id


def finish_usage_event(
    owner_id: str,
    event_id: str,
    *,
    status: str,
    latency_ms: float,
    failure_code: str | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
) -> None:
    with session_scope() as session:
        event = session.scalar(
            select(LlmUsageEventORM).where(
                LlmUsageEventORM.id == event_id,
                LlmUsageEventORM.owner_id == owner_id,
            )
        )
        if not event:
            return
        event.status = status
        event.failure_code = failure_code
        event.input_tokens = input_tokens
        event.output_tokens = output_tokens
        event.latency_ms = latency_ms
        event.finished_at = _utcnow()


def list_usage_events(
    owner_id: str,
    *,
    limit: int = 50,
    before: datetime | None = None,
    provider: str | None = None,
    credential_source: str | None = None,
    feature: str | None = None,
    status: str | None = None,
    since: datetime | None = None,
) -> list[LlmUsageEvent]:
    with read_session_scope() as session:
        statement = select(LlmUsageEventORM).where(LlmUsageEventORM.owner_id == owner_id)
        if before:
            statement = statement.where(LlmUsageEventORM.created_at < before)
        if since:
            statement = statement.where(LlmUsageEventORM.created_at >= since)
        if provider:
            statement = statement.where(LlmUsageEventORM.provider == provider)
        if credential_source:
            statement = statement.where(LlmUsageEventORM.credential_source == credential_source)
        if feature:
            statement = statement.where(LlmUsageEventORM.feature == feature)
        if status:
            statement = statement.where(LlmUsageEventORM.status == status)
        rows = session.scalars(statement.order_by(desc(LlmUsageEventORM.created_at)).limit(limit)).all()
        return [
            LlmUsageEvent(
                id=row.id,
                provider=row.provider,
                model=row.model,
                credential_source=row.credential_source,
                feature=row.feature,
                workflow_type=row.workflow_type,
                workflow_id=row.workflow_id,
                interaction_type=row.interaction_type,
                status=row.status,
                failure_code=row.failure_code,
                input_tokens=row.input_tokens,
                output_tokens=row.output_tokens,
                latency_ms=row.latency_ms,
                created_at=row.created_at,
                finished_at=row.finished_at,
            )
            for row in rows
        ]


def delete_expired_usage_events(cutoff: datetime) -> int:
    with session_scope() as session:
        result = session.execute(delete(LlmUsageEventORM).where(LlmUsageEventORM.created_at < cutoff))
        return int(result.rowcount or 0)


def health_counts() -> dict[str, int | float]:
    """Return sanitized deployment-wide aggregates without owner or credential data."""
    with read_session_scope() as session:
        credential_counts = dict(
            session.execute(
                select(UserLlmCredentialORM.status, func.count(UserLlmCredentialORM.id)).group_by(
                    UserLlmCredentialORM.status
                )
            ).all()
        )
        source_counts = dict(
            session.execute(
                select(LlmUsageEventORM.credential_source, func.count(LlmUsageEventORM.id)).group_by(
                    LlmUsageEventORM.credential_source
                )
            ).all()
        )
        total, failed, average_latency, exhausted = session.execute(
            select(
                func.count(LlmUsageEventORM.id),
                func.count(LlmUsageEventORM.id).filter(LlmUsageEventORM.status == "failed"),
                func.avg(LlmUsageEventORM.latency_ms),
                func.count(LlmUsageEventORM.id).filter(
                    LlmUsageEventORM.failure_code == "deployment_llm_trial_exhausted"
                ),
            )
        ).one()
    total = int(total or 0)
    failed = int(failed or 0)
    return {
        "llm_valid_credentials": int(credential_counts.get("valid", 0)),
        "llm_invalid_credentials": int(credential_counts.get("invalid", 0)),
        "llm_byok_invocations": int(source_counts.get("user", 0)),
        "llm_deployment_invocations": int(source_counts.get("deployment", 0)),
        "llm_trial_exhaustions": int(exhausted or 0),
        "llm_provider_failure_rate": round(failed / total, 4) if total else 0.0,
        "llm_average_latency_ms": round(float(average_latency or 0.0), 2),
    }


_RUN_MODELS = {
    "chat_run": ChatAgentRunORM,
    "dashboard_run": DashboardGenerationRunORM,
    "semantic_suggestion": SemanticSuggestionRunORM,
    "question_suggestion": QuestionSuggestionSetORM,
}


def snapshot_run_resolution(owner_id: str, workflow_type: str | None, workflow_id: str | None, resolution: LlmResolution) -> None:
    model = _RUN_MODELS.get(workflow_type or "")
    if not model or not workflow_id:
        return
    with session_scope() as session:
        row = session.scalar(select(model).where(model.id == workflow_id, model.owner_id == owner_id))
        if not row:
            return
        row.llm_provider = resolution.provider
        row.llm_model = resolution.model
        row.llm_credential_source = resolution.credential_source
        row.llm_credential_revision = resolution.credential_revision


__all__ = [
    "delete_credential",
    "delete_expired_usage_events",
    "finish_usage_event",
    "get_credential",
    "get_fallback_usage",
    "get_preferences",
    "health_counts",
    "list_credentials",
    "list_usage_events",
    "mark_credential_invalid",
    "save_validated_credential",
    "snapshot_run_resolution",
    "start_usage_event",
    "update_preferences",
]
