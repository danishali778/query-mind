"""Structured SQL proposal parsing for the database analyst agent."""

from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from app.core.secret_detection import detect_secret


class AnalystProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    response_type: Literal["query", "clarification"] = "query"
    clarification_question: str | None = None
    analysis_summary: str
    relevant_tables: list[str]
    relevant_columns: list[str]
    sql: str | None
    column_metadata: dict[str, str] = Field(default_factory=dict)
    assumptions: list[str]
    semantic_refs: list[str] = Field(default_factory=list)

    @field_validator("analysis_summary")
    @classmethod
    def summary_must_not_be_empty(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("analysis_summary cannot be empty")
        return cleaned

    @field_validator("sql")
    @classmethod
    def clean_sql(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @model_validator(mode="after")
    def validate_response_contract(self):
        text_values = [
            self.analysis_summary,
            self.clarification_question or "",
            self.sql or "",
            *self.assumptions,
        ]
        if any(detect_secret(value) for value in text_values):
            raise ValueError("proposal contains credential-shaped content")
        if self.response_type == "query":
            if not self.sql:
                raise ValueError("query proposals require sql")
            if self.clarification_question is not None:
                raise ValueError("query proposals cannot include a clarification question")
        else:
            if self.sql is not None:
                raise ValueError("clarification proposals cannot include sql")
            if not (self.clarification_question or "").strip():
                raise ValueError("clarification proposals require clarification_question")
            if self.relevant_tables or self.relevant_columns or self.semantic_refs:
                raise ValueError("clarification proposals cannot cite schema evidence")
        return self


class AgentFinishError(ValueError):
    pass


def parse_agent_proposal(content: str) -> AnalystProposal:
    text = content.strip()
    if text.startswith("```"):
        raise AgentFinishError("Final proposal must be raw JSON, not a markdown code block.")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise AgentFinishError(f"Final proposal is not valid JSON: {exc}") from exc
    try:
        return AnalystProposal.model_validate(payload)
    except ValidationError as exc:
        raise AgentFinishError(f"Final proposal JSON failed validation: {exc}") from exc


# Backward-compatible names for older imports during the migration.
FinalAnswer = AnalystProposal
parse_final_answer = parse_agent_proposal


__all__ = [
    "AnalystProposal",
    "FinalAnswer",
    "AgentFinishError",
    "parse_agent_proposal",
    "parse_final_answer",
]

