"""Loads and freezes verified semantic metadata for analytical runs."""

from __future__ import annotations

import functools

import anyio

from app.agents.schema_context.user_semantics import SemanticContext, build_semantic_context
from app.core.config import settings
from app.db.repositories import semantic_repository
from app.db.session import read_session_scope


def _load_sync(user_id: str, connection_id: str, catalog, question: str) -> SemanticContext:
    if not settings.semantic_layer_enabled:
        return SemanticContext(schema_hash=catalog.schema_hash)
    with read_session_scope() as session:
        rows = semantic_repository.list_active_verified_sync(session, user_id, connection_id)
        return build_semantic_context(
            catalog=catalog,
            rows=rows,
            question=question,
            max_definitions=settings.semantic_context_max_definitions,
            max_characters=settings.semantic_context_max_characters,
        )


async def load_context(user_id: str, connection_id: str, catalog, question: str) -> SemanticContext:
    return await anyio.to_thread.run_sync(
        functools.partial(_load_sync, user_id, connection_id, catalog, question)
    )


__all__ = ["load_context"]
