"""Persistence for durable, owner-scoped authentication session revocation."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from app.db.orm_models import RevokedAuthSessionORM
from app.db.session import read_session_scope, session_scope


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def hash_session_id(session_id: str) -> str:
    return hashlib.sha256(session_id.encode("utf-8")).hexdigest()


def _upsert_existing(owner_id: str, session_hash: str, expires_at: datetime) -> None:
    with session_scope() as session:
        row = (
            session.query(RevokedAuthSessionORM)
            .filter(
                RevokedAuthSessionORM.owner_id == owner_id,
                RevokedAuthSessionORM.session_id_hash == session_hash,
            )
            .one()
        )
        if _as_utc(row.access_token_expires_at) < _as_utc(expires_at):
            row.access_token_expires_at = expires_at
        row.revoked_at = _utcnow()


def revoke_session(owner_id: str, session_id: str, expires_at: datetime) -> str:
    """Persist a hashed current-session revocation and return its digest."""
    session_hash = hash_session_id(session_id)
    try:
        with session_scope() as session:
            existing = (
                session.query(RevokedAuthSessionORM)
                .filter(
                    RevokedAuthSessionORM.owner_id == owner_id,
                    RevokedAuthSessionORM.session_id_hash == session_hash,
                )
                .one_or_none()
            )
            if existing is not None:
                if _as_utc(existing.access_token_expires_at) < _as_utc(expires_at):
                    existing.access_token_expires_at = expires_at
                existing.revoked_at = _utcnow()
            else:
                session.add(
                    RevokedAuthSessionORM(
                        owner_id=owner_id,
                        session_id_hash=session_hash,
                        access_token_expires_at=expires_at,
                        source="logout",
                    )
                )
    except IntegrityError:
        # A duplicate logout can race another worker after the initial lookup.
        _upsert_existing(owner_id, session_hash, expires_at)
    return session_hash


def is_session_revoked(owner_id: str, session_id: str, *, now: datetime | None = None) -> bool:
    session_hash = hash_session_id(session_id)
    checked_at = now or _utcnow()
    with read_session_scope() as session:
        row = (
            session.query(RevokedAuthSessionORM.id)
            .filter(
                RevokedAuthSessionORM.owner_id == owner_id,
                RevokedAuthSessionORM.session_id_hash == session_hash,
                RevokedAuthSessionORM.access_token_expires_at > checked_at,
            )
            .first()
        )
        return row is not None


def cleanup_expired(cutoff: datetime) -> int:
    with session_scope() as session:
        return int(
            session.query(RevokedAuthSessionORM)
            .filter(RevokedAuthSessionORM.access_token_expires_at <= cutoff)
            .delete(synchronize_session=False)
        )


def health_counts() -> dict[str, int]:
    now = _utcnow()
    with read_session_scope() as session:
        unexpired = (
            session.query(func.count(RevokedAuthSessionORM.id))
            .filter(RevokedAuthSessionORM.access_token_expires_at > now)
            .scalar()
        )
        expired = (
            session.query(func.count(RevokedAuthSessionORM.id))
            .filter(RevokedAuthSessionORM.access_token_expires_at <= now)
            .scalar()
        )
    return {
        "auth_unexpired_revoked_sessions": int(unexpired or 0),
        "auth_expired_revocations_pending_cleanup": int(expired or 0),
    }


__all__ = [
    "cleanup_expired",
    "hash_session_id",
    "health_counts",
    "is_session_revoked",
    "revoke_session",
]
