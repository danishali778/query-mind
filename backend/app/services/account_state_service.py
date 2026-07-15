"""Application-owned account activation and deactivation workflow."""

from __future__ import annotations

import functools

import anyio

from app.db.repositories import settings_repository
from app.integrations.supabase_auth import user_cache


async def set_user_active(user_id: str, is_active: bool) -> bool:
    updated = await anyio.to_thread.run_sync(
        functools.partial(settings_repository.set_user_active, user_id, is_active)
    )
    if updated:
        await user_cache.invalidate_user_cache(user_id)
    return updated


__all__ = ["set_user_active"]
