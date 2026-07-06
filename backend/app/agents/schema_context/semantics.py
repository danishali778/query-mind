"""Semantic layer resolution for agent prompts and search scoring."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.agents.schema_context.catalog import catalog_table_by_name
from app.agents.schema_context.default_semantics import DEFAULT_ENTITIES, DEFAULT_METRIC_SYNONYMS
from app.agents.schema_context.scoring import tokenize
from app.agents.schema_context.types import SchemaCatalog


class EntityDefinition(BaseModel):
    name: str
    primary_table: str | None = None
    synonyms: list[str] = Field(default_factory=list)


class MetricDefinition(BaseModel):
    name: str
    description: str = ""
    expression: str = ""
    tables: list[str] = Field(default_factory=list)
    synonyms: list[str] = Field(default_factory=list)


class DatePolicy(BaseModel):
    table: str
    column: str
    meaning: str = ""


class MatchedSemantics(BaseModel):
    entities: list[EntityDefinition] = Field(default_factory=list)
    metrics: list[MetricDefinition] = Field(default_factory=list)
    date_policies: list[DatePolicy] = Field(default_factory=list)
    extra_synonyms: dict[str, list[str]] = Field(default_factory=dict)


def _find_table_for_entity(catalog: SchemaCatalog, entity_name: str) -> str | None:
    candidates = [entity_name] + [f"{entity_name}s", entity_name.rstrip("s")]
    for candidate in candidates:
        if catalog_table_by_name(catalog, candidate):
            return catalog_table_by_name(catalog, candidate).name  # type: ignore[union-attr]
    for table in catalog.tables:
        base = table.name.split(".")[-1].lower()
        if entity_name in base or base.startswith(entity_name):
            return table.name
    return None


def _default_date_column(table_name: str, catalog: SchemaCatalog) -> str | None:
    table = catalog_table_by_name(catalog, table_name)
    if not table:
        return None
    for col in table.columns:
        if col.name.lower() in {"created_at", "order_date", "placed_at", "timestamp"}:
            return col.name
        if col.semantic_type in {"datetime", "date"} and "created" in col.name.lower():
            return col.name
    for col in table.columns:
        if col.semantic_type in {"datetime", "date"}:
            return col.name
    return None


def resolve_semantics(question: str, catalog: SchemaCatalog) -> MatchedSemantics:
    tokens = set(tokenize(question))
    matched = MatchedSemantics(extra_synonyms=DEFAULT_METRIC_SYNONYMS)

    for entity_def in DEFAULT_ENTITIES:
        names = {entity_def["name"], *entity_def.get("synonyms", [])}
        if not tokens & names:
            continue
        primary_table = _find_table_for_entity(catalog, entity_def["name"])
        if not primary_table:
            continue
        matched.entities.append(
            EntityDefinition(
                name=entity_def["name"],
                primary_table=primary_table,
                synonyms=entity_def.get("synonyms", []),
            )
        )
        date_col = _default_date_column(primary_table, catalog)
        if date_col:
            matched.date_policies.append(
                DatePolicy(
                    table=primary_table,
                    column=date_col,
                    meaning=f"default date column for {entity_def['name']}",
                )
            )

    for metric_name, synonyms in DEFAULT_METRIC_SYNONYMS.items():
        if metric_name in tokens or tokens & set(synonyms):
            matched.metrics.append(
                MetricDefinition(
                    name=metric_name,
                    description=f"Business term '{metric_name}' matched in the question.",
                    synonyms=synonyms,
                )
            )

    return matched


def render_semantics_prompt(matched: MatchedSemantics) -> str:
    if not matched.entities and not matched.metrics and not matched.date_policies:
        return ""
    lines = ["BUSINESS DEFINITIONS"]
    for entity in matched.entities:
        lines.append(
            f"- {entity.name}: primary table `{entity.primary_table}`"
            + (f" (also known as: {', '.join(entity.synonyms)})" if entity.synonyms else "")
        )
    for metric in matched.metrics:
        lines.append(
            f"- {metric.name}: {metric.description}"
            + (f" Synonyms: {', '.join(metric.synonyms)}." if metric.synonyms else "")
        )
    for policy in matched.date_policies:
        lines.append(
            f"- date policy for `{policy.table}`: prefer `{policy.column}` ({policy.meaning})"
        )
    return "\n".join(lines)


__all__ = [
    "EntityDefinition",
    "MetricDefinition",
    "DatePolicy",
    "MatchedSemantics",
    "resolve_semantics",
    "render_semantics_prompt",
]
