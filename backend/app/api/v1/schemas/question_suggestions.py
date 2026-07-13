"""API contracts for schema-aware question suggestions."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


SuggestionSurface = Literal["chat", "dashboard", "connection", "library"]


class QuestionSuggestionResponse(BaseModel):
    id: str
    surface: SuggestionSurface
    title: str
    prompt: str
    rationale: str = ""
    category: Literal["kpi", "trend", "comparison", "ranking", "segmentation", "anomaly"]
    source: Literal["deterministic", "ai"]
    based_on: list[str] = Field(default_factory=list)


class SuggestionFailureResponse(BaseModel):
    code: str
    message: str


class QuestionSuggestionListResponse(BaseModel):
    connection_id: str
    surface: SuggestionSurface
    status: Literal["fallback", "queued", "running", "ready", "failed", "disabled"]
    context_fingerprint: str
    schema_hash: str
    suggestions: list[QuestionSuggestionResponse] = Field(default_factory=list)
    refresh_required: bool
    ai_available: bool
    generated_at: datetime | None = None
    failure: SuggestionFailureResponse | None = None


class RefreshQuestionSuggestionsRequest(BaseModel):
    client_request_id: UUID
    expected_context_fingerprint: str = Field(min_length=64, max_length=64)
    force: bool = False


class DismissQuestionSuggestionRequest(BaseModel):
    expected_context_fingerprint: str = Field(min_length=64, max_length=64)


__all__ = [
    "DismissQuestionSuggestionRequest",
    "QuestionSuggestionListResponse",
    "QuestionSuggestionResponse",
    "RefreshQuestionSuggestionsRequest",
    "SuggestionFailureResponse",
    "SuggestionSurface",
]
