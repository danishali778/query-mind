"""Build bounded, owner-scoped conversation evidence for one chat turn."""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from app.agents.db_agent.tools import PriorAnalysisExecution
from app.agents.schema_context.types import SchemaCatalog
from app.agents.schema_context.user_semantics import (
    SemanticContext,
    apply_semantic_catalog_overlay,
)
from app.core.secret_detection import detect_secret
from app.query_engine.connection_scope import referenced_tables
from app.query_engine.results import QueryExecutionResult
from app.query_engine.semantic_policy import validate_ai_semantic_policy


MAX_CONVERSATION_PAIRS = 5


@dataclass(frozen=True)
class ConversationEvidenceContext:
    messages: list[dict] = field(default_factory=list)
    prior_results: dict[str, PriorAnalysisExecution] = field(default_factory=dict)

    def manifest(self) -> list[dict]:
        return [
            {
                "result_ref": item.result_ref,
                "question": item.question,
                "answer": item.answer,
                "tables": item.relevant_tables,
                "columns": item.result.columns,
                "row_count": item.result.row_count,
                "truncated": item.result.truncated,
                "method": item.method,
                "evidence": item.evidence[:5],
                "presentation_kind": item.presentation_kind,
                "captured_at": item.captured_at,
            }
            for item in self.prior_results.values()
        ]


def _completed_pairs(history: list[dict]) -> list[tuple[dict, dict]]:
    users = {item.get("id"): item for item in history if item.get("role") == "user"}
    pairs: list[tuple[dict, dict]] = []
    for assistant in history:
        if assistant.get("role") != "assistant":
            continue
        parent = users.get(assistant.get("parent_id"))
        if not parent or not assistant.get("content") or assistant.get("error"):
            continue
        if assistant.get("run_status") not in {None, "completed"}:
            continue
        pairs.append((parent, assistant))
    return pairs


def _canonical_catalog_tables(catalog: SchemaCatalog) -> set[str]:
    tables: set[str] = set()
    for table in catalog.tables:
        canonical = table.name if "." in table.name else f"{table.schema_name or 'public'}.{table.name}"
        tables.add(canonical.casefold())
    return tables


def _safe_prior_result(
    *,
    reference: str,
    user: dict,
    assistant: dict,
    connection_id: str,
    catalog: SchemaCatalog,
    semantic_context: SemanticContext,
) -> PriorAnalysisExecution | None:
    if assistant.get("connection_id") != connection_id:
        return None
    if assistant.get("agent_tier") not in {"agent", "fallback", "pipeline"}:
        return None
    sql = str(assistant.get("sql") or "").strip()
    results = assistant.get("results")
    columns = list(assistant.get("columns") or [])
    if not sql or not isinstance(results, dict) or not columns:
        return None
    rows = results.get("rows")
    if not isinstance(rows, list):
        return None
    if any(detect_secret(value) for value in (str(user.get("content") or ""), str(assistant.get("content") or ""), sql)):
        return None
    try:
        tables = referenced_tables(sql)
    except Exception:
        return None
    if any(table.casefold() not in _canonical_catalog_tables(catalog) for table in tables):
        return None
    if not validate_ai_semantic_policy(sql, semantic_context).allowed:
        return None

    metadata = assistant.get("answer_metadata")
    metadata = metadata if isinstance(metadata, dict) else {}
    evidence: list[dict] = []
    for item in metadata.get("evidence") or []:
        if not isinstance(item, dict):
            continue
        evidence_columns = [column for column in item.get("columns") or [] if column in columns]
        row_indexes = [
            index
            for index in item.get("row_indexes") or []
            if isinstance(index, int) and 0 <= index < len(rows)
        ]
        claim = str(item.get("claim") or "").strip()
        if not claim or detect_secret(claim):
            continue
        evidence.append(
            {
                "claim": claim,
                "result_ref": reference,
                "columns": evidence_columns,
                "row_indexes": row_indexes,
            }
        )

    result = QueryExecutionResult(
        success=True,
        columns=columns,
        rows=rows,
        row_count=int(results.get("row_count") or len(rows)),
        truncated=bool(results.get("truncated", False)),
        execution_time_ms=float(results.get("execution_time_ms") or 0.0),
    )
    return PriorAnalysisExecution(
        result_ref=reference,
        source_message_id=str(assistant.get("id")),
        question=str(user.get("content") or ""),
        answer=str(assistant.get("content") or ""),
        sql=sql,
        result=result,
        captured_at=str(assistant.get("created_at") or ""),
        presentation_kind=assistant.get("presentation_kind"),
        chart_recommendation=assistant.get("chart_recommendation"),
        column_metadata=dict(results.get("column_metadata") or {}),
        evidence=evidence,
        method=str(metadata.get("method") or "").strip() or None,
        limitations=[str(value) for value in (metadata.get("limitations") or [])[:12]],
        relevant_tables=sorted(tables),
    )


def build_conversation_evidence_context(
    history: list[dict],
    *,
    connection_id: str,
    catalog: SchemaCatalog,
    semantic_context: SemanticContext,
) -> ConversationEvidenceContext:
    pairs = _completed_pairs(history)[-MAX_CONVERSATION_PAIRS:]
    messages: list[dict] = []
    for user, assistant in pairs:
        user_content = str(user.get("content") or "")
        assistant_content = str(assistant.get("content") or "")
        if detect_secret(user_content) or detect_secret(assistant_content):
            continue
        messages.extend(
            [
                {"role": "user", "content": user_content},
                {
                    "role": "assistant",
                    "content": assistant_content,
                    "response_kind": assistant.get("response_kind") or "answer",
                },
            ]
        )

    safe_catalog = apply_semantic_catalog_overlay(catalog, semantic_context)
    prior_results: dict[str, PriorAnalysisExecution] = {}
    for user, assistant in reversed(pairs):
        reference = f"prior_result_{len(prior_results) + 1}"
        prior = _safe_prior_result(
            reference=reference,
            user=user,
            assistant=assistant,
            connection_id=connection_id,
            catalog=safe_catalog,
            semantic_context=semantic_context,
        )
        if prior is not None:
            prior_results[reference] = prior

    return ConversationEvidenceContext(messages=messages, prior_results=prior_results)


def render_prior_result_manifest(context: ConversationEvidenceContext) -> str:
    if not context.prior_results:
        return ""
    return json.dumps(context.manifest(), ensure_ascii=True, separators=(",", ":"))


__all__ = [
    "ConversationEvidenceContext",
    "MAX_CONVERSATION_PAIRS",
    "build_conversation_evidence_context",
    "render_prior_result_manifest",
]
