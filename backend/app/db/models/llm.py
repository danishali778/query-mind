"""Domain contracts for owner-scoped LLM credentials and usage."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr


LlmProvider = Literal["gemini", "groq", "openai"]
CredentialSource = Literal["user", "deployment"]
InteractionType = Literal["explicit", "automatic"]


class LlmCredential(BaseModel):
    id: str
    owner_id: str
    provider: LlmProvider
    key_hint: str
    status: Literal["valid", "invalid"]
    credential_revision: int
    last_validated_at: datetime | None = None
    validation_failure_code: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class StoredLlmCredential(LlmCredential):
    model_config = ConfigDict(frozen=True)
    api_key: SecretStr = Field(exclude=True, repr=False)


class LlmExecutionContext(BaseModel):
    owner_id: str
    feature: str
    workflow_type: str | None = None
    workflow_id: str | None = None
    interaction_type: InteractionType = "explicit"


class LlmResolution(BaseModel):
    model_config = ConfigDict(frozen=True)
    provider: LlmProvider
    model: str
    credential_source: CredentialSource
    credential_id: str | None = None
    credential_revision: int | None = None
    privileged: bool = False
    api_key: SecretStr = Field(exclude=True, repr=False)


class LlmUsageEvent(BaseModel):
    id: str
    provider: LlmProvider
    model: str
    credential_source: CredentialSource
    feature: str
    workflow_type: str | None = None
    workflow_id: str | None = None
    interaction_type: InteractionType
    status: Literal["started", "completed", "failed"]
    failure_code: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    latency_ms: float | None = None
    created_at: datetime | None = None
    finished_at: datetime | None = None


__all__ = [
    "CredentialSource",
    "InteractionType",
    "LlmCredential",
    "LlmExecutionContext",
    "LlmProvider",
    "LlmResolution",
    "LlmUsageEvent",
    "StoredLlmCredential",
]
