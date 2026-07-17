"""Typed final outcomes for the result-aware database chat agent."""

from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from app.core.secret_detection import detect_secret


ResponseType = Literal[
    "direct_answer",
    "clarification",
    "schema_answer",
    "data_analysis",
    "refusal",
]
PresentationKind = Literal["none", "table", "kpi", "chart"]


class ClarificationContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason_code: str = Field(min_length=1, max_length=80)
    expected_input: Literal[
        "metric",
        "table",
        "time_range",
        "grain",
        "identifier",
        "business_definition",
        "metric_table_or_outcome",
        "other",
    ]


class AgentChartSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["bar", "line", "pie", "area", "kpi"]
    title: str = Field(min_length=1, max_length=160)
    x_column: str | None = None
    y_columns: list[str] = Field(default_factory=list, max_length=8)
    color_column: str | None = None
    tooltip_columns: list[str] = Field(default_factory=list, max_length=12)
    is_grouped: bool = False
    is_dual_axis: bool = False
    x_label: str | None = Field(default=None, max_length=120)
    y_label: str | None = Field(default=None, max_length=120)


class AgentPresentation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: PresentationKind = "none"
    chart: AgentChartSpec | None = None

    @model_validator(mode="after")
    def validate_chart_presence(self):
        if self.kind == "chart" and self.chart is None:
            raise ValueError("chart presentation requires chart configuration")
        if self.kind != "chart" and self.chart is not None:
            raise ValueError("only chart presentation may include chart configuration")
        return self


class AgentEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim: str = Field(min_length=1, max_length=500)
    result_ref: str = Field(pattern=r"^result_[1-9][0-9]*$")
    columns: list[str] = Field(default_factory=list, max_length=12)
    row_indexes: list[int] = Field(default_factory=list, max_length=20)

    @field_validator("row_indexes")
    @classmethod
    def row_indexes_are_non_negative(cls, value: list[int]) -> list[int]:
        if any(index < 0 for index in value):
            raise ValueError("evidence row indexes must be non-negative")
        return value


class ChatAgentOutcome(BaseModel):
    """The only accepted final response from the decision agent."""

    model_config = ConfigDict(extra="forbid")

    response_type: ResponseType
    answer: str = Field(min_length=1, max_length=8000)
    clarification_context: ClarificationContext | None = None
    result_ref: str | None = Field(default=None, pattern=r"^result_[1-9][0-9]*$")
    presentation: AgentPresentation = Field(default_factory=AgentPresentation)
    evidence: list[AgentEvidence] = Field(default_factory=list, max_length=20)
    method: str | None = Field(default=None, max_length=2000)
    limitations: list[str] = Field(default_factory=list, max_length=12)
    relevant_tables: list[str] = Field(default_factory=list, max_length=20)
    relevant_columns: list[str] = Field(default_factory=list, max_length=50)
    column_metadata: dict[str, str] = Field(default_factory=dict)
    semantic_refs: list[str] = Field(default_factory=list, max_length=30)

    @field_validator("answer")
    @classmethod
    def answer_must_be_safe(cls, value: str) -> str:
        cleaned = value.strip()
        if detect_secret(cleaned):
            raise ValueError("outcome contains credential-shaped content")
        return cleaned

    @field_validator("method")
    @classmethod
    def method_must_be_safe(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if detect_secret(cleaned):
            raise ValueError("method contains credential-shaped content")
        return cleaned or None

    @model_validator(mode="after")
    def validate_response_contract(self):
        text_values = [
            self.answer,
            self.method or "",
            *self.limitations,
            *(item.claim for item in self.evidence),
        ]
        if self.presentation.chart:
            text_values.extend(
                [
                    self.presentation.chart.title,
                    self.presentation.chart.x_label or "",
                    self.presentation.chart.y_label or "",
                ]
            )
        if any(detect_secret(value) for value in text_values):
            raise ValueError("outcome contains credential-shaped content")
        non_analysis = {"direct_answer", "clarification", "schema_answer", "refusal"}
        if self.response_type in non_analysis:
            if self.result_ref is not None or self.evidence:
                raise ValueError(f"{self.response_type} cannot reference query results")
            if self.presentation.kind not in {"none", "table"}:
                raise ValueError(f"{self.response_type} cannot request a data visualization")
        if self.response_type == "clarification":
            if self.clarification_context is None:
                raise ValueError("clarification requires clarification_context")
        elif self.clarification_context is not None:
            raise ValueError("only clarification may include clarification_context")
        if self.response_type == "data_analysis":
            if self.result_ref is None:
                raise ValueError("data_analysis requires result_ref")
            if not self.evidence:
                raise ValueError("data_analysis requires at least one evidence item")
        return self


class AgentFinishError(ValueError):
    pass


def parse_agent_outcome(content: str) -> ChatAgentOutcome:
    text = content.strip()
    if text.startswith("```"):
        raise AgentFinishError("Final outcome must be raw JSON, not a markdown code block.")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise AgentFinishError(f"Final outcome is not valid JSON: {exc}") from exc
    try:
        return ChatAgentOutcome.model_validate(payload)
    except ValidationError as exc:
        raise AgentFinishError(f"Final outcome JSON failed validation: {exc}") from exc


# Backward-compatible import names while callers and tests migrate.
AnalystProposal = ChatAgentOutcome
FinalAnswer = ChatAgentOutcome
parse_agent_proposal = parse_agent_outcome
parse_final_answer = parse_agent_outcome


__all__ = [
    "AgentChartSpec",
    "AgentEvidence",
    "AgentFinishError",
    "AgentPresentation",
    "AnalystProposal",
    "ChatAgentOutcome",
    "ClarificationContext",
    "FinalAnswer",
    "parse_agent_outcome",
    "parse_agent_proposal",
    "parse_final_answer",
]
