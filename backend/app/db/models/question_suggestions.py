"""Domain contracts for connection-scoped question suggestions."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


SuggestionSurface = Literal["chat", "dashboard", "connection", "library"]
SuggestionCategory = Literal[
    "kpi", "trend", "comparison", "ranking", "segmentation", "anomaly"
]
SuggestionSource = Literal["deterministic", "ai"]
SuggestionSetStatus = Literal["queued", "running", "ready", "failed"]

SURFACES: tuple[SuggestionSurface, ...] = (
    "chat",
    "dashboard",
    "connection",
    "library",
)
DEFAULT_SURFACE_LIMITS: dict[SuggestionSurface, int] = {
    "chat": 6,
    "dashboard": 4,
    "connection": 4,
    "library": 8,
}

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_CODE_FENCE = re.compile(r"```|`{3,}")
_SQL_SHAPE = re.compile(
    r"\b(select|insert|update|delete|drop|alter|create|truncate|grant|revoke)\b\s+",
    re.IGNORECASE,
)
_WRITE_INTENT = re.compile(
    r"\b(insert|update|delete|drop|alter|create|truncate|grant|revoke|overwrite)\b",
    re.IGNORECASE,
)


def _safe_text(value: str, *, field: str) -> str:
    cleaned = value.strip()
    if _CONTROL.search(cleaned):
        raise ValueError(f"{field} contains control characters")
    if _CODE_FENCE.search(cleaned) or _SQL_SHAPE.search(cleaned):
        raise ValueError(f"{field} must be a natural-language analytical request")
    return cleaned


class QuestionSuggestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^qs_[a-f0-9]{16}$")
    surface: SuggestionSurface
    title: str = Field(min_length=1, max_length=80)
    prompt: str = Field(min_length=1, max_length=1000)
    rationale: str = Field(default="", max_length=240)
    category: SuggestionCategory
    source: SuggestionSource
    based_on: list[str] = Field(default_factory=list, max_length=5)

    @field_validator("title", "prompt", "rationale")
    @classmethod
    def validate_text(cls, value: str, info):
        cleaned = _safe_text(value, field=info.field_name)
        if info.field_name == "prompt" and _WRITE_INTENT.search(cleaned):
            raise ValueError("prompt must remain read-only and analytical")
        return cleaned

    @field_validator("based_on")
    @classmethod
    def validate_labels(cls, labels: list[str]) -> list[str]:
        return [_safe_text(label, field="based_on")[:80] for label in labels if label.strip()]


class QuestionSuggestionCandidate(BaseModel):
    """Strict untrusted model output before opaque IDs are assigned."""

    model_config = ConfigDict(extra="forbid")

    surface: SuggestionSurface
    title: str = Field(min_length=1, max_length=80)
    prompt: str = Field(min_length=1, max_length=1000)
    rationale: str = Field(default="", max_length=240)
    category: SuggestionCategory
    based_on_refs: list[str] = Field(min_length=1, max_length=5)

    @field_validator("title", "prompt", "rationale")
    @classmethod
    def validate_text(cls, value: str, info):
        cleaned = _safe_text(value, field=info.field_name)
        if info.field_name == "prompt" and _WRITE_INTENT.search(cleaned):
            raise ValueError("prompt must remain read-only and analytical")
        return cleaned


class QuestionSuggestionBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal[1] = 1
    chat: list[QuestionSuggestionCandidate] = Field(default_factory=list)
    dashboard: list[QuestionSuggestionCandidate] = Field(default_factory=list)
    connection: list[QuestionSuggestionCandidate] = Field(default_factory=list)
    library: list[QuestionSuggestionCandidate] = Field(default_factory=list)


class SuggestionSetRecord(BaseModel):
    id: str
    owner_id: str
    connection_id: str
    schema_hash: str
    semantic_fingerprint: str
    context_fingerprint: str
    semantic_version_ids: list[str] = Field(default_factory=list)
    generation_revision: int
    status: SuggestionSetStatus
    suggestions_json: dict[str, list[dict]] = Field(default_factory=dict)
    dismissed_ids: list[str] = Field(default_factory=list)
    client_request_id: str | None = None
    celery_task_id: str | None = None
    failure_code: str | None = None
    failure_message: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


__all__ = [
    "DEFAULT_SURFACE_LIMITS",
    "QuestionSuggestion",
    "QuestionSuggestionBundle",
    "QuestionSuggestionCandidate",
    "SURFACES",
    "SuggestionCategory",
    "SuggestionSetRecord",
    "SuggestionSetStatus",
    "SuggestionSource",
    "SuggestionSurface",
]
