"""Authenticated LLM credential, preference, and usage endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Query

from app.api.deps import CurrentUserDep
from app.api.v1.schemas.llm_settings import (
    DeleteLlmCredentialRequest,
    DeleteResponse,
    LlmConfigurationResponse,
    LlmCredentialResponse,
    LlmPreferencesResponse,
    LlmPreflightResponse,
    LlmUsageResponse,
    SaveLlmCredentialRequest,
    UpdateLlmPreferencesRequest,
)
from app.services import llm_credential_service


router = APIRouter(prefix="/api/settings/llm", tags=["LLM Settings"])


@router.get("", response_model=LlmConfigurationResponse)
def get_llm_configuration(current_user: CurrentUserDep):
    return llm_credential_service.get_configuration(current_user.id)


@router.put("/credentials/{provider}", response_model=LlmCredentialResponse)
def save_llm_credential(provider: str, request: SaveLlmCredentialRequest, current_user: CurrentUserDep):
    return llm_credential_service.save_credential(
        current_user.id,
        provider,
        api_key=request.api_key.get_secret_value(),
        model=request.model,
        expected_revision=request.expected_credential_revision,
    )


@router.post("/credentials/{provider}/validate", response_model=LlmCredentialResponse)
def revalidate_llm_credential(provider: str, current_user: CurrentUserDep):
    return llm_credential_service.revalidate_credential(current_user.id, provider)


@router.delete("/credentials/{provider}", response_model=DeleteResponse)
def delete_llm_credential(
    provider: str,
    request: DeleteLlmCredentialRequest,
    current_user: CurrentUserDep,
):
    llm_credential_service.delete_credential(
        current_user.id,
        provider,
        expected_revision=request.expected_credential_revision,
        replacement_provider=request.replacement_provider,
    )
    return {"deleted": True}


@router.patch("/preferences", response_model=LlmPreferencesResponse)
def update_llm_preferences(request: UpdateLlmPreferencesRequest, current_user: CurrentUserDep):
    return llm_credential_service.update_preferences(
        current_user.id,
        expected_revision=request.expected_preference_revision,
        preferred_provider=request.preferred_provider,
        preferred_model=request.preferred_model,
        allow_background_ai=request.allow_background_ai,
    )


@router.get("/usage", response_model=LlmUsageResponse)
def get_llm_usage(
    current_user: CurrentUserDep,
    limit: int = Query(default=50, ge=1, le=100),
    before: datetime | None = None,
    since: datetime | None = None,
    provider: Literal["gemini", "groq", "openai"] | None = None,
    source: Literal["user", "deployment"] | None = None,
    feature: str | None = Query(default=None, min_length=1, max_length=80),
    status: Literal["started", "completed", "failed"] | None = None,
):
    items = llm_credential_service.list_usage(
        current_user.id,
        limit=limit,
        before=before,
        since=since,
        provider=provider,
        credential_source=source,
        feature=feature,
        status=status,
    )
    return {"items": items, "next_cursor": items[-1].created_at if len(items) == limit else None}


@router.get("/preflight", response_model=LlmPreflightResponse)
def preflight_llm_access(
    current_user: CurrentUserDep,
    feature: str = Query(default="chat", min_length=1, max_length=80),
    interaction_type: Literal["explicit", "automatic"] = "explicit",
):
    return llm_credential_service.preflight(
        current_user.id,
        feature,
        interaction_type=interaction_type,
    )


__all__ = ["router"]
