"""Versioned dashboard plan contract for AI dashboard generation."""

from __future__ import annotations

import re
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


ALLOWED_VISUALIZATIONS = (
    "auto",
    "kpi",
    "bar",
    "line",
    "area",
    "pie",
    "donut",
    "table",
)
AllowedVisualization = Literal["auto", "kpi", "bar", "line", "area", "pie", "donut", "table"]

ALLOWED_SIZES = ("quarter", "half", "three-quarter", "full")
AllowedSize = Literal["quarter", "half", "three-quarter", "full"]

_WRITE_INTENT = re.compile(
    r"\b(insert|update|delete|drop|alter|truncate|create\s+table|grant|revoke|merge|upsert|"
    r"write\s+to|modify\s+data|mutate)\b",
    re.IGNORECASE,
)
_SQL_FIELD_HINT = re.compile(r"\b(select|with|from|join|group\s+by)\b", re.IGNORECASE)


class WidgetPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_key: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str = Field(min_length=1, max_length=100)
    question: str = Field(min_length=1, max_length=500)
    purpose: str = Field(default="", max_length=300)
    visualization: AllowedVisualization = "auto"
    size: AllowedSize = "half"
    time_range: str | None = Field(default=None, max_length=100)
    semantic_refs: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("title", "question", "purpose", "time_range", mode="before")
    @classmethod
    def _strip_text(cls, value):
        if value is None:
            return value
        return str(value).strip()

    @field_validator("client_key")
    @classmethod
    def _require_client_key(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("client_key is required")
        try:
            return str(uuid.UUID(cleaned))
        except (ValueError, AttributeError) as exc:
            raise ValueError("client_key must be a valid UUID") from exc

    @field_validator("question")
    @classmethod
    def _reject_write_or_sql_question(cls, value: str) -> str:
        if _WRITE_INTENT.search(value):
            raise ValueError("Widget questions must be read-only analytical requests")
        # Plans must not embed executable SQL.
        if value.lstrip().upper().startswith(("SELECT", "WITH")) or (
            _SQL_FIELD_HINT.search(value) and ";" in value
        ):
            raise ValueError("Widget plans must not include SQL")
        return value

    @field_validator("semantic_refs", mode="before")
    @classmethod
    def _normalize_semantic_refs(cls, value):
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError("semantic_refs must be a list")
        return list(dict.fromkeys(str(item).strip() for item in value if str(item).strip()))


class DashboardPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal[1] = 1
    title: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=500)
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    widgets: list[WidgetPlan] = Field(min_length=1, max_length=8)

    @field_validator("title", "description", mode="before")
    @classmethod
    def _strip_text(cls, value):
        if value is None:
            return value
        return str(value).strip()

    @field_validator("assumptions", "warnings", mode="before")
    @classmethod
    def _normalize_string_lists(cls, value):
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError("must be a list of strings")
        return [str(item).strip() for item in value if str(item).strip()]

    @model_validator(mode="after")
    def _validate_widgets(self) -> "DashboardPlan":
        keys = [widget.client_key for widget in self.widgets]
        if len(keys) != len(set(keys)):
            raise ValueError("Widget client_key values must be unique")
        titles = [widget.title.casefold() for widget in self.widgets]
        if len(titles) != len(set(titles)):
            raise ValueError("Widget titles must be unique")
        return self


def parse_dashboard_plan(payload: dict | DashboardPlan) -> DashboardPlan:
    if isinstance(payload, DashboardPlan):
        return payload
    return DashboardPlan.model_validate(payload)


def reject_write_oriented_prompt(prompt: str) -> None:
    if _WRITE_INTENT.search(prompt or ""):
        raise ValueError("Dashboard prompts must be read-only analytical requests")


__all__ = [
    "ALLOWED_VISUALIZATIONS",
    "ALLOWED_SIZES",
    "AllowedVisualization",
    "AllowedSize",
    "WidgetPlan",
    "DashboardPlan",
    "parse_dashboard_plan",
    "reject_write_oriented_prompt",
]
