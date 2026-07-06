"""Structured SQL proposal parsing for the database analyst agent."""

from __future__ import annotations

import json

from pydantic import BaseModel, Field, ValidationError, field_validator


class AnalystProposal(BaseModel):
    analysis_summary: str
    relevant_tables: list[str]
    relevant_columns: list[str]
    sql: str | None
    column_metadata: dict[str, str] = Field(default_factory=dict)
    assumptions: list[str]

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

