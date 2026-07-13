"""Domain models and typed payload contracts for semantic definitions."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


SemanticKind = Literal[
    "table",
    "column",
    "entity",
    "dimension",
    "metric",
    "relationship",
    "filter",
    "date_policy",
    "synonym",
]
DefinitionStatus = Literal["draft", "verified", "deprecated"]
ValidationStatus = Literal["unvalidated", "valid", "invalid", "stale"]

_SAFE_TEXT = re.compile(r"^[^\x00-\x08\x0b\x0c\x0e-\x1f\x7f]*$")
_KEY = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")


def normalize_key(value: str) -> str:
    key = re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")
    if not key or not _KEY.fullmatch(key):
        raise ValueError("Definition key must contain letters or numbers.")
    return key[:120]


class StrictPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TableSemanticPayload(StrictPayload):
    kind: Literal["table"] = "table"
    table_name: str = Field(min_length=1, max_length=255)
    synonyms: list[str] = Field(default_factory=list, max_length=25)
    visibility: Literal["included", "hidden"] = "included"


class ColumnSemanticPayload(StrictPayload):
    kind: Literal["column"] = "column"
    table_name: str = Field(min_length=1, max_length=255)
    column_name: str = Field(min_length=1, max_length=255)
    semantic_type: Literal[
        "unknown", "identifier", "numeric", "quantity", "money", "date",
        "datetime", "category", "boolean", "json", "email", "phone",
        "name", "address", "free_text",
    ] = "unknown"
    classification: Literal["public", "internal", "sensitive", "restricted"] = "public"
    synonyms: list[str] = Field(default_factory=list, max_length=25)


class EntitySemanticPayload(StrictPayload):
    kind: Literal["entity"] = "entity"
    primary_table: str = Field(min_length=1, max_length=255)
    primary_key: str = Field(min_length=1, max_length=255)
    display_column: str | None = Field(default=None, max_length=255)
    synonyms: list[str] = Field(default_factory=list, max_length=25)


class DimensionSemanticPayload(StrictPayload):
    kind: Literal["dimension"] = "dimension"
    table_name: str = Field(min_length=1, max_length=255)
    column_name: str = Field(min_length=1, max_length=255)
    label: str = Field(min_length=1, max_length=160)
    format: str | None = Field(default=None, max_length=80)
    synonyms: list[str] = Field(default_factory=list, max_length=25)


class RelationshipSemanticPayload(StrictPayload):
    kind: Literal["relationship"] = "relationship"
    left_table: str = Field(min_length=1, max_length=255)
    left_column: str = Field(min_length=1, max_length=255)
    right_table: str = Field(min_length=1, max_length=255)
    right_column: str = Field(min_length=1, max_length=255)
    cardinality: Literal["one_to_one", "one_to_many", "many_to_one", "many_to_many"]
    join_type: Literal["inner", "left"] = "left"
    canonical: bool = True


class MetricSemanticPayload(StrictPayload):
    kind: Literal["metric"] = "metric"
    expression: str = Field(min_length=1, max_length=4000)
    tables: list[str] = Field(min_length=1, max_length=12)
    relationship_ids: list[str] = Field(default_factory=list, max_length=12)
    filter_ids: list[str] = Field(default_factory=list, max_length=12)
    date_policy_id: str | None = None
    display_format: Literal["number", "currency", "percent", "duration"] = "number"
    synonyms: list[str] = Field(default_factory=list, max_length=25)


class FilterCondition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    column: str = Field(min_length=1, max_length=255)
    operator: Literal[
        "eq", "neq", "in", "not_in", "gt", "gte", "lt", "lte", "between",
        "is_null", "is_not_null", "contains", "starts_with", "ends_with",
    ]
    value: Any = None

    @model_validator(mode="after")
    def validate_value_shape(self):
        if self.operator in {"is_null", "is_not_null"}:
            self.value = None
        elif self.operator in {"in", "not_in", "between"}:
            if not isinstance(self.value, list) or not self.value:
                raise ValueError(f"{self.operator} requires a non-empty list value.")
            if self.operator == "between" and len(self.value) != 2:
                raise ValueError("between requires exactly two values.")
        elif self.value is None:
            raise ValueError(f"{self.operator} requires a value.")
        return self


class FilterSemanticPayload(StrictPayload):
    kind: Literal["filter"] = "filter"
    table_name: str = Field(min_length=1, max_length=255)
    conjunction: Literal["and", "or"] = "and"
    conditions: list[FilterCondition] = Field(min_length=1, max_length=20)


class DatePolicySemanticPayload(StrictPayload):
    kind: Literal["date_policy"] = "date_policy"
    table_name: str = Field(min_length=1, max_length=255)
    column_name: str = Field(min_length=1, max_length=255)
    meaning: str = Field(min_length=1, max_length=500)
    timezone: str = Field(default="UTC", min_length=1, max_length=80)
    default_grain: Literal["day", "week", "month", "quarter", "year"] = "month"


class SynonymSemanticPayload(StrictPayload):
    kind: Literal["synonym"] = "synonym"
    phrase: str = Field(min_length=1, max_length=120)
    target_definition_id: str


SemanticPayload = Annotated[
    Union[
        TableSemanticPayload,
        ColumnSemanticPayload,
        EntitySemanticPayload,
        DimensionSemanticPayload,
        MetricSemanticPayload,
        RelationshipSemanticPayload,
        FilterSemanticPayload,
        DatePolicySemanticPayload,
        SynonymSemanticPayload,
    ],
    Field(discriminator="kind"),
]


class SemanticDefinitionVersion(BaseModel):
    id: str
    definition_id: str
    version: int
    status: DefinitionStatus
    display_name: str
    description: str = ""
    payload: dict[str, Any]
    schema_hash: str | None = None
    validation_status: ValidationStatus = "unvalidated"
    validation_report: dict[str, Any] = Field(default_factory=dict)
    change_note: str | None = None
    draft_revision: int = 1
    created_by: str
    verified_by: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    validated_at: datetime | None = None
    verified_at: datetime | None = None
    deprecated_at: datetime | None = None


class SemanticDefinition(BaseModel):
    id: str
    owner_id: str
    connection_id: str
    kind: SemanticKind
    key: str
    versions: list[SemanticDefinitionVersion] = Field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SemanticLineageItem(BaseModel):
    definition_id: str
    version_id: str
    reference: str
    kind: SemanticKind
    display_name: str
    version: int
    usage_role: Literal["applied", "policy_enforced"] = "applied"
    verification_status: Literal["verified"] = "verified"


class SemanticValidationReport(BaseModel):
    errors: list[dict[str, str]] = Field(default_factory=list)
    warnings: list[dict[str, str]] = Field(default_factory=list)
    schema_hash: str
    normalized_payload: dict[str, Any]
    preview: dict[str, Any] = Field(default_factory=dict)
    validated_at: datetime


class SemanticSuggestionRun(BaseModel):
    id: str
    owner_id: str
    connection_id: str
    client_request_id: str
    schema_hash: str
    requested_kinds: list[SemanticKind]
    business_context: str | None = None
    status: Literal["queued", "running", "completed", "failed", "cancelled"]
    candidates_json: list[dict[str, Any]] = Field(default_factory=list)
    celery_task_id: str | None = None
    failure_code: str | None = None
    failure_message: str | None = None
    created_at: datetime | None = None
    started_at: datetime | None = None
    cancel_requested_at: datetime | None = None
    finished_at: datetime | None = None
    updated_at: datetime | None = None


def validate_payload(kind: SemanticKind, payload: dict[str, Any]) -> dict[str, Any]:
    candidate = dict(payload)
    candidate.setdefault("kind", kind)
    from pydantic import TypeAdapter

    parsed = TypeAdapter(SemanticPayload).validate_python(candidate)
    return parsed.model_dump(mode="json")


def validate_safe_text(value: str, *, field_name: str, max_length: int) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"{field_name} cannot be empty.")
    if len(cleaned) > max_length:
        raise ValueError(f"{field_name} is too long.")
    if not _SAFE_TEXT.fullmatch(cleaned):
        raise ValueError(f"{field_name} contains unsupported control characters.")
    return cleaned


__all__ = [
    "DefinitionStatus",
    "SemanticDefinition",
    "SemanticDefinitionVersion",
    "SemanticKind",
    "SemanticLineageItem",
    "SemanticPayload",
    "SemanticValidationReport",
    "SemanticSuggestionRun",
    "ValidationStatus",
    "normalize_key",
    "validate_payload",
    "validate_safe_text",
]
