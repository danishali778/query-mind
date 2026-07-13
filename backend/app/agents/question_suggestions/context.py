"""Build a bounded, metadata-only discovery context for suggestions."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from pydantic import BaseModel, Field

from app.agents.schema_context.types import SchemaCatalog
from app.agents.schema_context.user_semantics import (
    SemanticContext,
    SemanticContextEntry,
    SemanticPolicy,
    apply_semantic_catalog_overlay,
    make_reference,
)


CONTRACT_VERSION = "question-suggestions-v1"
_KIND_PRIORITY = {
    "metric": 0,
    "entity": 1,
    "dimension": 2,
    "date_policy": 3,
    "relationship": 4,
    "filter": 5,
    "table": 6,
    "column": 7,
    "synonym": 8,
}


class SuggestionEvidence(BaseModel):
    reference: str
    label: str
    kind: str
    payload: dict[str, Any] = Field(default_factory=dict)
    description: str = ""


class SuggestionGenerationContext(BaseModel):
    schema_hash: str
    scope_revision: int
    semantic_fingerprint: str
    context_fingerprint: str
    semantic_version_ids: list[str] = Field(default_factory=list)
    catalog: SchemaCatalog
    evidence: list[SuggestionEvidence] = Field(default_factory=list)

    @property
    def evidence_by_reference(self) -> dict[str, SuggestionEvidence]:
        return {item.reference: item for item in self.evidence}


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _build_policy(entries: list[SemanticContextEntry], schema_hash: str) -> SemanticContext:
    policy = SemanticPolicy()
    policy_entries: list[SemanticContextEntry] = []
    for entry in entries:
        payload = entry.payload
        if entry.kind == "table" and payload.get("visibility") == "hidden":
            policy.hidden_tables[str(payload.get("table_name", "")).casefold()] = entry.reference
            policy_entries.append(entry)
        elif entry.kind == "column":
            key = f"{payload.get('table_name', '')}.{payload.get('column_name', '')}".casefold()
            if payload.get("classification") == "restricted":
                policy.restricted_columns[key] = entry.reference
                policy_entries.append(entry)
            elif payload.get("classification") == "sensitive":
                policy.sensitive_columns[key] = entry.reference
                policy_entries.append(entry)
    return SemanticContext(
        schema_hash=schema_hash,
        definitions=entries,
        policy_definitions=policy_entries,
        policy=policy,
    )


def build_generation_context(
    *,
    catalog: SchemaCatalog,
    scope_revision: int,
    rows: list[tuple[Any, Any]],
    max_characters: int,
) -> SuggestionGenerationContext:
    entries: list[SemanticContextEntry] = []
    for definition, version in rows:
        if version.schema_hash != catalog.schema_hash:
            continue
        entries.append(
            SemanticContextEntry(
                definition_id=definition.id,
                version_id=version.id,
                reference=make_reference(definition.kind, definition.key, version.version),
                kind=definition.kind,
                key=definition.key,
                display_name=version.display_name,
                description=version.description or "",
                version=version.version,
                payload=dict(version.payload or {}),
            )
        )
    entries.sort(key=lambda item: (_KIND_PRIORITY.get(item.kind, 99), item.key))
    semantic_ids = sorted(item.version_id for item in entries)
    semantic_fingerprint = _digest("|".join(semantic_ids))
    context_fingerprint = _digest(
        "|".join(
            [catalog.schema_hash, str(scope_revision), *semantic_ids, CONTRACT_VERSION]
        )
    )
    semantic_context = _build_policy(entries, catalog.schema_hash)
    safe_catalog = apply_semantic_catalog_overlay(catalog, semantic_context).model_copy(deep=True)
    for table in safe_catalog.tables:
        table.row_estimate = None
        for column in table.columns:
            column.sample_values = []

    evidence: list[SuggestionEvidence] = []
    consumed = 0
    for entry in entries:
        if entry.reference in semantic_context.policy.hidden_tables.values():
            continue
        if entry.reference in semantic_context.policy.restricted_columns.values():
            continue
        if entry.reference in semantic_context.policy.sensitive_columns.values():
            continue
        item = SuggestionEvidence(
            reference=entry.reference,
            label=entry.display_name,
            kind=entry.kind,
            payload=entry.payload,
            description=entry.description,
        )
        size = len(json.dumps(item.model_dump(mode="json"), ensure_ascii=True))
        if consumed + size > max_characters:
            continue
        evidence.append(item)
        consumed += size

    table_index = 0
    column_index = 0
    for table in safe_catalog.tables:
        if table.is_internal:
            continue
        table_index += 1
        table_ref = f"tbl_{table_index}"
        item = SuggestionEvidence(
            reference=table_ref,
            label=table.name,
            kind="physical_table",
            payload={"table_name": table.name},
        )
        size = len(json.dumps(item.model_dump(mode="json")))
        if consumed + size <= max_characters:
            evidence.append(item)
            consumed += size
        for column in table.columns:
            if column.is_sensitive:
                continue
            column_index += 1
            item = SuggestionEvidence(
                reference=f"col_{column_index}",
                label=f"{table.name}.{column.name}",
                kind="physical_column",
                payload={
                    "table_name": table.name,
                    "column_name": column.name,
                    "data_type": column.type,
                    "semantic_type": column.semantic_type,
                },
            )
            size = len(json.dumps(item.model_dump(mode="json")))
            if consumed + size <= max_characters:
                evidence.append(item)
                consumed += size

    return SuggestionGenerationContext(
        schema_hash=catalog.schema_hash,
        scope_revision=scope_revision,
        semantic_fingerprint=semantic_fingerprint,
        context_fingerprint=context_fingerprint,
        semantic_version_ids=semantic_ids,
        catalog=safe_catalog,
        evidence=evidence,
    )


__all__ = [
    "CONTRACT_VERSION",
    "SuggestionEvidence",
    "SuggestionGenerationContext",
    "build_generation_context",
]
