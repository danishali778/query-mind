"""Structural validation and safe preview compilation for semantic metadata."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlglot import exp, parse_one
from sqlglot.errors import ParseError

from app.agents.schema_context.catalog import catalog_table_by_name
from app.agents.schema_context.types import CatalogColumn, SchemaCatalog
from app.query_engine.safety import validate_query
from app.query_engine.result_serializer import serialize_data


_COMMENT_OR_STATEMENT = re.compile(r";|--|/\*|\*/|#")
_INSTRUCTION_TEXT = re.compile(
    r"\b(ignore|disregard|override)\b.{0,40}\b(instruction|prompt|system|rule)s?\b",
    re.IGNORECASE,
)
_DATE_TYPE = re.compile(r"date|time", re.IGNORECASE)
_NUMERIC_TYPE = re.compile(r"int|numeric|decimal|float|double|real|money", re.IGNORECASE)
_ALLOWED_FUNCTIONS = {"SUM", "COUNT", "AVG", "MIN", "MAX", "COALESCE", "NULLIF", "ROUND"}
_AGGREGATES = {"SUM", "COUNT", "AVG", "MIN", "MAX"}


@dataclass
class ValidationFinding:
    code: str
    message: str
    field: str | None = None

    def as_dict(self) -> dict[str, str]:
        payload = {"code": self.code, "message": self.message}
        if self.field:
            payload["field"] = self.field
        return payload


@dataclass
class StructuralValidation:
    normalized_payload: dict[str, Any]
    errors: list[ValidationFinding] = field(default_factory=list)
    warnings: list[ValidationFinding] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return not self.errors


@dataclass
class PreviewSpec:
    sql: str
    parameters: dict[str, Any] = field(default_factory=dict)
    result_kind: str = "generic"


def _table(catalog: SchemaCatalog, name: str):
    return catalog_table_by_name(catalog, name)


def _column(catalog: SchemaCatalog, table_name: str, column_name: str) -> CatalogColumn | None:
    table = _table(catalog, table_name)
    if not table:
        return None
    lower = column_name.lower()
    return next((column for column in table.columns if column.name.lower() == lower), None)


def _short(name: str) -> str:
    return name.split(".")[-1].lower()


def _identifier(name: str) -> str:
    return ".".join(f'"{part.replace(chr(34), chr(34) * 2)}"' for part in name.split("."))


def _table_error(result: StructuralValidation, catalog: SchemaCatalog, field_name: str, name: str) -> bool:
    if _table(catalog, name):
        return False
    result.errors.append(ValidationFinding("table_not_found", f"Table '{name}' does not exist.", field_name))
    return True


def _column_error(
    result: StructuralValidation,
    catalog: SchemaCatalog,
    table_name: str,
    field_name: str,
    column_name: str,
) -> CatalogColumn | None:
    column = _column(catalog, table_name, column_name)
    if not column:
        result.errors.append(
            ValidationFinding(
                "column_not_found",
                f"Column '{table_name}.{column_name}' does not exist.",
                field_name,
            )
        )
    return column


def validate_metric_expression(
    expression: str,
    tables: list[str],
    catalog: SchemaCatalog,
) -> tuple[str | None, list[ValidationFinding], list[ValidationFinding]]:
    errors: list[ValidationFinding] = []
    warnings: list[ValidationFinding] = []
    if _COMMENT_OR_STATEMENT.search(expression):
        return None, [ValidationFinding("unsafe_metric_expression", "Metric expressions cannot contain comments or statements.", "expression")], warnings
    try:
        tree = parse_one(expression, read="postgres")
    except ParseError:
        return None, [ValidationFinding("invalid_metric_expression", "Metric expression could not be parsed.", "expression")], warnings

    blocked_types = (
        exp.Select, exp.Subquery, exp.Window, exp.Insert, exp.Update, exp.Delete,
        exp.Create, exp.Drop, exp.Alter, exp.Command, exp.Union,
    )
    if isinstance(tree, blocked_types) or any(isinstance(node, blocked_types) for node in tree.walk()):
        errors.append(ValidationFinding("unsafe_metric_expression", "Metric expressions may contain only aggregate arithmetic.", "expression"))

    aggregate_found = False
    for function in tree.find_all(exp.Func):
        name = function.sql_name().upper()
        if name not in _ALLOWED_FUNCTIONS:
            errors.append(ValidationFinding("metric_function_not_allowed", f"Function '{name}' is not allowed.", "expression"))
        if name in _AGGREGATES:
            aggregate_found = True
    if not aggregate_found:
        errors.append(ValidationFinding("metric_aggregation_required", "Metric expressions require an approved aggregate function.", "expression"))

    declared = {_short(name): name for name in tables}
    for column in tree.find_all(exp.Column):
        if not column.table:
            errors.append(ValidationFinding("metric_column_unqualified", f"Column '{column.name}' must be table-qualified.", "expression"))
            continue
        table_name = declared.get(_short(column.table))
        if not table_name:
            errors.append(ValidationFinding("metric_table_not_declared", f"Table '{column.table}' is not declared by this metric.", "tables"))
            continue
        if not _column(catalog, table_name, column.name):
            errors.append(ValidationFinding("column_not_found", f"Column '{table_name}.{column.name}' does not exist.", "expression"))

    for star in tree.find_all(exp.Star):
        if not isinstance(star.parent, exp.Count):
            errors.append(ValidationFinding("metric_wildcard_not_allowed", "Wildcards are allowed only inside COUNT(*).", "expression"))

    for division in tree.find_all(exp.Div):
        denominator = division.expression
        if not (isinstance(denominator, exp.Nullif) or isinstance(denominator, exp.Literal)):
            warnings.append(ValidationFinding("metric_division_by_zero", "The metric may divide by zero; use NULLIF when appropriate.", "expression"))

    return (tree.sql(dialect="postgres") if not errors else None), errors, warnings


def validate_structure(
    kind: str,
    payload: dict[str, Any],
    catalog: SchemaCatalog,
    *,
    verified_definitions: dict[str, dict[str, Any]] | None = None,
    description: str = "",
) -> StructuralValidation:
    normalized = dict(payload)
    result = StructuralValidation(normalized_payload=normalized)
    verified_definitions = verified_definitions or {}

    if description and _INSTRUCTION_TEXT.search(description):
        result.warnings.append(
            ValidationFinding(
                "instruction_like_text",
                "This description resembles an instruction. It will be treated only as untrusted metadata.",
                "description",
            )
        )

    if kind == "table":
        _table_error(result, catalog, "table_name", payload["table_name"])

    elif kind == "column":
        if not _table_error(result, catalog, "table_name", payload["table_name"]):
            column = _column_error(result, catalog, payload["table_name"], "column_name", payload["column_name"])
            if column and column.is_sensitive and payload.get("classification") in {"public", "internal"}:
                result.errors.append(
                    ValidationFinding(
                        "sensitivity_cannot_be_weakened",
                        "Automatically sensitive columns cannot be classified as public or internal.",
                        "classification",
                    )
                )

    elif kind == "entity":
        table_name = payload["primary_table"]
        if not _table_error(result, catalog, "primary_table", table_name):
            key = _column_error(result, catalog, table_name, "primary_key", payload["primary_key"])
            if key and not key.primary_key:
                result.warnings.append(ValidationFinding("entity_key_not_physical_pk", "The selected entity key is not a physical primary key.", "primary_key"))
            if payload.get("display_column"):
                _column_error(result, catalog, table_name, "display_column", payload["display_column"])

    elif kind == "dimension":
        table_name = payload["table_name"]
        if not _table_error(result, catalog, "table_name", table_name):
            column = _column_error(result, catalog, table_name, "column_name", payload["column_name"])
            if column and column.is_sensitive:
                result.errors.append(ValidationFinding("sensitive_dimension", "Sensitive columns cannot be exposed as dimensions.", "column_name"))

    elif kind == "relationship":
        left = payload["left_table"]
        right = payload["right_table"]
        left_col = None if _table_error(result, catalog, "left_table", left) else _column_error(result, catalog, left, "left_column", payload["left_column"])
        right_col = None if _table_error(result, catalog, "right_table", right) else _column_error(result, catalog, right, "right_column", payload["right_column"])
        if left_col and right_col and left_col.type.lower() != right_col.type.lower():
            result.warnings.append(ValidationFinding("relationship_type_mismatch", "Relationship columns have different physical types."))
        left_table = _table(catalog, left)
        physical_fk = bool(
            left_col and left_col.fk_referred_table and _short(left_col.fk_referred_table) == _short(right)
        ) or bool(
            right_col and right_col.fk_referred_table and _short(right_col.fk_referred_table) == _short(left)
        )
        if left_table and not physical_fk:
            result.warnings.append(ValidationFinding("relationship_not_physical_fk", "This relationship is not backed by a physical foreign key."))

    elif kind == "metric":
        for table_name in payload["tables"]:
            _table_error(result, catalog, "tables", table_name)
        normalized_expression, errors, warnings = validate_metric_expression(payload["expression"], payload["tables"], catalog)
        result.errors.extend(errors)
        result.warnings.extend(warnings)
        if normalized_expression:
            normalized["expression"] = normalized_expression
        if len(payload["tables"]) > 1 and not payload.get("relationship_ids"):
            result.errors.append(ValidationFinding("metric_relationship_required", "Multi-table metrics require verified canonical relationships.", "relationship_ids"))
        for field_name in ("relationship_ids", "filter_ids"):
            for definition_id in payload.get(field_name, []):
                if definition_id not in verified_definitions:
                    result.errors.append(ValidationFinding("semantic_reference_not_verified", f"Referenced definition '{definition_id}' is not verified.", field_name))
        if payload.get("date_policy_id") and payload["date_policy_id"] not in verified_definitions:
            result.errors.append(ValidationFinding("semantic_reference_not_verified", "The date policy is not verified.", "date_policy_id"))
        if not payload.get("date_policy_id"):
            result.warnings.append(ValidationFinding("metric_without_date_policy", "This metric has no default date policy."))

    elif kind == "filter":
        table_name = payload["table_name"]
        if not _table_error(result, catalog, "table_name", table_name):
            for index, condition in enumerate(payload["conditions"]):
                column = _column_error(result, catalog, table_name, f"conditions.{index}.column", condition["column"])
                if column and column.is_sensitive:
                    result.errors.append(ValidationFinding("sensitive_filter", "Reusable filters cannot reference sensitive columns.", f"conditions.{index}.column"))
        result.warnings.append(ValidationFinding("filter_without_date_policy", "Reusable filters should be paired with a date policy for bounded analysis."))

    elif kind == "date_policy":
        table_name = payload["table_name"]
        if not _table_error(result, catalog, "table_name", table_name):
            column = _column_error(result, catalog, table_name, "column_name", payload["column_name"])
            if column and not (_DATE_TYPE.search(column.type) or column.semantic_type in {"date", "datetime"}):
                result.errors.append(ValidationFinding("date_column_required", "Date policies require a date or timestamp column.", "column_name"))

    elif kind == "synonym":
        target = verified_definitions.get(payload["target_definition_id"])
        if not target:
            result.errors.append(ValidationFinding("synonym_target_not_verified", "Synonyms must target a verified definition in this connection.", "target_definition_id"))

    return result


def _compile_filter_predicate(payload: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    clauses: list[str] = []
    params: dict[str, Any] = {}
    for index, condition in enumerate(payload["conditions"]):
        column = _identifier(condition["column"])
        operator = condition["operator"]
        value = condition.get("value")
        if operator in {"is_null", "is_not_null"}:
            clauses.append(f"{column} IS {'NOT ' if operator == 'is_not_null' else ''}NULL")
            continue
        if operator in {"in", "not_in"}:
            names = []
            for value_index, item in enumerate(value):
                key = f"p{index}_{value_index}"
                names.append(f":{key}")
                params[key] = item
            clauses.append(f"{column} {'NOT IN' if operator == 'not_in' else 'IN'} ({', '.join(names)})")
            continue
        if operator == "between":
            params[f"p{index}_0"], params[f"p{index}_1"] = value
            clauses.append(f"{column} BETWEEN :p{index}_0 AND :p{index}_1")
            continue
        sql_operator = {
            "eq": "=", "neq": "<>", "gt": ">", "gte": ">=", "lt": "<", "lte": "<=",
            "contains": "LIKE", "starts_with": "LIKE", "ends_with": "LIKE",
        }[operator]
        if operator == "contains":
            value = f"%{value}%"
        elif operator == "starts_with":
            value = f"{value}%"
        elif operator == "ends_with":
            value = f"%{value}"
        params[f"p{index}"] = value
        clauses.append(f"{column} {sql_operator} :p{index}")
    joiner = " AND " if payload["conjunction"] == "and" else " OR "
    return joiner.join(f"({clause})" for clause in clauses), params


def compile_preview(
    kind: str,
    payload: dict[str, Any],
    *,
    related_definitions: dict[str, dict[str, Any]] | None = None,
    sample_limit: int = 1000,
) -> PreviewSpec | None:
    related_definitions = related_definitions or {}
    if kind == "metric":
        tables = payload["tables"]
        from_sql = _identifier(tables[0])
        for relationship_id in payload.get("relationship_ids", []):
            relationship = related_definitions[relationship_id]["payload"]
            right_table = relationship["right_table"]
            join_keyword = "LEFT JOIN" if relationship.get("join_type") == "left" else "INNER JOIN"
            from_sql += (
                f" {join_keyword} {_identifier(right_table)} ON "
                f"{_identifier(relationship['left_table'])}.{_identifier(relationship['left_column'])} = "
                f"{_identifier(right_table)}.{_identifier(relationship['right_column'])}"
            )
        where_parts: list[str] = []
        parameters: dict[str, Any] = {}
        for filter_id in payload.get("filter_ids", []):
            predicate, predicate_params = _compile_filter_predicate(related_definitions[filter_id]["payload"])
            offset = len(parameters)
            for key, value in predicate_params.items():
                new_key = f"f{offset}_{key}"
                predicate = predicate.replace(f":{key}", f":{new_key}")
                parameters[new_key] = value
            where_parts.append(predicate)
        where_sql = f" WHERE {' AND '.join(where_parts)}" if where_parts else ""
        return PreviewSpec(
            sql=f"SELECT {payload['expression']} AS metric_value FROM {from_sql}{where_sql}",
            parameters=parameters,
            result_kind="metric",
        )

    if kind == "relationship":
        left_table = _identifier(payload["left_table"])
        right_table = _identifier(payload["right_table"])
        left_col = _identifier(payload["left_column"])
        right_col = _identifier(payload["right_column"])
        limit = max(1, min(5000, sample_limit))
        return PreviewSpec(
            sql=(
                f"WITH l AS (SELECT {left_col} AS k FROM {left_table} WHERE {left_col} IS NOT NULL LIMIT {limit}), "
                f"r AS (SELECT {right_col} AS k FROM {right_table} WHERE {right_col} IS NOT NULL LIMIT {limit}) "
                "SELECT (SELECT COUNT(*) FROM l) AS left_count, "
                "(SELECT COUNT(*) FROM r) AS right_count, "
                "(SELECT COUNT(*) FROM l JOIN r ON l.k = r.k) AS matched_count, "
                "(SELECT COUNT(*) FROM (SELECT k FROM l GROUP BY k HAVING COUNT(*) > 1) d) AS left_duplicate_keys, "
                "(SELECT COUNT(*) FROM (SELECT k FROM r GROUP BY k HAVING COUNT(*) > 1) d) AS right_duplicate_keys"
            ),
            result_kind="relationship",
        )

    if kind == "filter":
        predicate, parameters = _compile_filter_predicate(payload)
        table = _identifier(payload["table_name"])
        limit = max(1, min(5000, sample_limit))
        return PreviewSpec(
            sql=(
                f"WITH sample AS (SELECT * FROM {table} LIMIT {limit}) "
                f"SELECT COUNT(*) AS before_count, COUNT(*) FILTER (WHERE {predicate}) AS after_count FROM sample"
            ),
            parameters=parameters,
            result_kind="filter",
        )

    if kind == "date_policy":
        table = _identifier(payload["table_name"])
        column = _identifier(payload["column_name"])
        limit = max(1, min(5000, sample_limit))
        return PreviewSpec(
            sql=(
                f"WITH sample AS (SELECT {column} AS value FROM {table} LIMIT {limit}) "
                "SELECT MIN(value) AS minimum, MAX(value) AS maximum, "
                "COUNT(*) AS total_count, COUNT(*) FILTER (WHERE value IS NULL) AS null_count FROM sample"
            ),
            result_kind="date_policy",
        )
    return None


def execute_preview(engine: Engine, spec: PreviewSpec, *, timeout_seconds: int = 5) -> dict[str, Any]:
    """Execute a bounded parameterized diagnostic without query-history logging."""

    is_safe, reason = validate_query(spec.sql)
    if not is_safe:
        raise ValueError(reason or "Semantic preview query failed safety validation.")
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            if engine.dialect.name == "postgresql":
                connection.execute(text(f"SET LOCAL statement_timeout = {max(1, timeout_seconds) * 1000}"))
                connection.execute(text("SET TRANSACTION READ ONLY"))
            result = connection.execute(text(spec.sql), spec.parameters)
            row = result.mappings().first()
            transaction.rollback()
            return serialize_data(dict(row or {}))
        except Exception:
            transaction.rollback()
            raise


__all__ = [
    "PreviewSpec",
    "StructuralValidation",
    "ValidationFinding",
    "compile_preview",
    "execute_preview",
    "validate_metric_expression",
    "validate_structure",
]
