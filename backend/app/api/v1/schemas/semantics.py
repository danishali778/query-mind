"""API contracts for connection-scoped semantic definitions."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

SemanticKind = Literal[
    "table", "column", "entity", "dimension", "metric", "relationship",
    "filter", "date_policy", "synonym",
]


class CreateSemanticDefinitionRequest(BaseModel):
    kind: SemanticKind
    key: str | None = Field(default=None, max_length=120)
    display_name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=2000)
    payload: dict[str, Any]
    change_note: str | None = Field(default=None, max_length=500)


class UpdateSemanticDraftRequest(BaseModel):
    expected_draft_revision: int = Field(ge=1)
    display_name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=2000)
    payload: dict[str, Any]


class CreateSemanticVersionRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=2000)
    payload: dict[str, Any]
    change_note: str | None = Field(default=None, max_length=500)


class ValidateSemanticVersionRequest(BaseModel):
    run_preview: bool = True


class VerifySemanticVersionRequest(BaseModel):
    expected_schema_hash: str = Field(min_length=1, max_length=128)
    acknowledged_warning_codes: list[str] = Field(default_factory=list, max_length=50)
    change_note: str | None = Field(default=None, max_length=500)


class SemanticDefinitionVersionResponse(BaseModel):
    id: str
    definition_id: str
    version: int
    status: str
    display_name: str
    description: str = ""
    payload: dict[str, Any]
    schema_hash: str | None = None
    validation_status: str
    validation_report: dict[str, Any] = Field(default_factory=dict)
    change_note: str | None = None
    draft_revision: int
    created_by: str
    verified_by: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    validated_at: datetime | None = None
    verified_at: datetime | None = None
    deprecated_at: datetime | None = None


class SemanticDefinitionResponse(BaseModel):
    id: str
    owner_id: str
    connection_id: str
    kind: SemanticKind
    key: str
    versions: list[SemanticDefinitionVersionResponse] = Field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SemanticDefinitionListResponse(BaseModel):
    items: list[SemanticDefinitionResponse]
    total: int
    page: int
    page_size: int


class SemanticSummaryResponse(BaseModel):
    connection_id: str
    schema_hash: str | None = None
    total: int = 0
    draft: int = 0
    verified: int = 0
    deprecated: int = 0
    invalid: int = 0
    stale: int = 0
    last_validated_at: datetime | None = None


class SemanticImpactItemResponse(BaseModel):
    definition_version_id: str
    version: int
    consumer_type: str
    consumer_id: str
    usage_role: str
    created_at: datetime | None = None


class CreateSemanticSuggestionRequest(BaseModel):
    client_request_id: str
    requested_kinds: list[SemanticKind] = Field(min_length=1, max_length=9)
    business_context: str | None = Field(default=None, max_length=2000)

    @field_validator("client_request_id")
    @classmethod
    def validate_request_id(cls, value: str) -> str:
        from uuid import UUID

        try:
            return str(UUID(value))
        except (ValueError, AttributeError) as exc:
            raise ValueError("client_request_id must be a valid UUID") from exc


class SemanticSuggestionRunResponse(BaseModel):
    id: str
    connection_id: str
    client_request_id: str
    schema_hash: str
    requested_kinds: list[str]
    status: str
    candidates: list[dict[str, Any]] = Field(default_factory=list)
    failure_code: str | None = None
    failure_message: str | None = None
    created_at: datetime | None = None
    started_at: datetime | None = None
    cancel_requested_at: datetime | None = None
    finished_at: datetime | None = None
    updated_at: datetime | None = None


__all__ = [
    "CreateSemanticDefinitionRequest",
    "CreateSemanticSuggestionRequest",
    "CreateSemanticVersionRequest",
    "SemanticDefinitionListResponse",
    "SemanticDefinitionResponse",
    "SemanticImpactItemResponse",
    "SemanticSuggestionRunResponse",
    "SemanticSummaryResponse",
    "UpdateSemanticDraftRequest",
    "ValidateSemanticVersionRequest",
    "VerifySemanticVersionRequest",
]
