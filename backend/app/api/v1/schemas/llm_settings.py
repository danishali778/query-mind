"""API contracts for owner-scoped LLM credentials and usage."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, SecretStr


Provider = Literal["gemini", "groq", "openai"]


class SaveLlmCredentialRequest(BaseModel):
    api_key: SecretStr
    model: str = Field(min_length=1, max_length=200)
    expected_credential_revision: int | None = Field(default=None, ge=1)


class DeleteLlmCredentialRequest(BaseModel):
    expected_credential_revision: int = Field(ge=1)
    replacement_provider: Provider | None = None


class UpdateLlmPreferencesRequest(BaseModel):
    expected_preference_revision: int = Field(ge=1)
    preferred_provider: Provider | None = None
    preferred_model: str | None = Field(default=None, min_length=1, max_length=200)
    allow_background_ai: bool = False


class LlmProviderConfiguration(BaseModel):
    provider: Provider
    enabled: bool
    configured: bool
    status: str | None = None
    key_hint: str | None = None
    credential_revision: int | None = None
    last_validated_at: datetime | None = None
    validation_failure_code: str | None = None
    allowed_models: list[str]


class DeploymentFallbackConfiguration(BaseModel):
    available: bool
    privileged: bool
    calls_used: int
    calls_limit: int
    calls_remaining: int


class LlmConfigurationResponse(BaseModel):
    mode: str
    preferred_provider: Provider | None = None
    preferred_model: str | None = None
    preference_revision: int
    allow_background_ai: bool
    providers: list[LlmProviderConfiguration]
    deployment_fallback: DeploymentFallbackConfiguration


class LlmCredentialResponse(BaseModel):
    id: str
    owner_id: str
    provider: Provider
    key_hint: str
    status: str
    credential_revision: int
    preference_revision: int
    last_validated_at: datetime | None = None
    validation_failure_code: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class LlmPreferencesResponse(BaseModel):
    preferred_provider: Provider | None = None
    preferred_model: str | None = None
    preference_revision: int
    allow_background_ai: bool


class LlmUsageEventResponse(BaseModel):
    id: str
    provider: Provider
    model: str
    credential_source: Literal["user", "deployment"]
    feature: str
    workflow_type: str | None = None
    workflow_id: str | None = None
    interaction_type: Literal["explicit", "automatic"]
    status: str
    failure_code: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    latency_ms: float | None = None
    created_at: datetime | None = None
    finished_at: datetime | None = None


class LlmUsageResponse(BaseModel):
    items: list[LlmUsageEventResponse]
    next_cursor: datetime | None = None


class LlmPreflightResponse(BaseModel):
    available: bool
    provider: Provider
    model: str
    credential_source: Literal["user", "deployment"]


class DeleteResponse(BaseModel):
    deleted: bool


__all__ = [name for name in globals() if name.endswith(("Request", "Response", "Configuration"))]
