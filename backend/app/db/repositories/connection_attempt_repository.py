"""Audit persistence for database connection attempts."""

from __future__ import annotations

from app.db.orm_models import ConnectionAttemptORM
from app.db.session import session_scope


def log_connection_attempt(
    *,
    owner_id: str,
    action: str,
    db_type: str | None,
    host: str | None,
    port: int | None,
    decision: str,
    success: bool,
    error_code: str | None = None,
    duration_ms: float | None = None,
) -> None:
    with session_scope() as session:
        session.add(
            ConnectionAttemptORM(
                owner_id=owner_id,
                action=action,
                db_type=db_type,
                host=host,
                port=port,
                decision=decision,
                success=success,
                error_code=error_code,
                duration_ms=duration_ms,
            )
        )


__all__ = ["log_connection_attempt"]
