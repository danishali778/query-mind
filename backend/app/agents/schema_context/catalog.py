"""Build a searchable schema catalog from introspected TableInfo."""

from __future__ import annotations

import hashlib
import math
import re
from datetime import datetime, timezone

from app.agents.schema_context.sensitivity import filter_sample_values
from app.agents.schema_context.types import CatalogColumn, CatalogTable, SchemaCatalog
from app.db.models.connection import TableInfo

_INTERNAL_PATTERNS = re.compile(
    r"(audit|log|migration|_history|alembic|celery|pg_|information_schema)",
    re.IGNORECASE,
)

_MONEY_NAME = re.compile(r"(amount|price|revenue|cost|total|fee|salary|payment|paid)", re.I)
_DATE_NAME = re.compile(r"(^date$|_date$|_at$|timestamp|datetime)", re.I)
_CATEGORY_NAME = re.compile(r"(type|status|category|tier|kind|mode|state|level|role|gender|priority|source|method|format)", re.I)
_EMAIL_NAME = re.compile(r"email", re.I)
_PHONE_NAME = re.compile(r"phone|mobile", re.I)
_NAME_NAME = re.compile(r"(^name$|_name$|first_name|last_name|full_name)", re.I)
_BOOL_TYPE = re.compile(r"bool", re.I)
_JSON_TYPE = re.compile(r"json", re.I)
_NUMERIC_TYPE = re.compile(r"(int|numeric|decimal|float|double|real|money)", re.I)
_TEXT_TYPE = re.compile(r"(text|varchar|char|string)", re.I)


def _infer_semantic_type(col_name: str, col_type: str) -> str:
    name = col_name.lower()
    ctype = col_type.lower()
    if _EMAIL_NAME.search(name):
        return "email"
    if _PHONE_NAME.search(name):
        return "phone"
    if _NAME_NAME.search(name):
        return "name"
    if _MONEY_NAME.search(name) and _NUMERIC_TYPE.search(ctype):
        return "money"
    if _DATE_NAME.search(name):
        return "datetime" if "timestamp" in ctype or "_at" in name else "date"
    if _CATEGORY_NAME.search(name) and _TEXT_TYPE.search(ctype):
        return "category"
    if _BOOL_TYPE.search(ctype):
        return "boolean"
    if _JSON_TYPE.search(ctype):
        return "json"
    if _NUMERIC_TYPE.search(ctype):
        return "quantity" if "count" in name or "qty" in name else "numeric"
    if _TEXT_TYPE.search(ctype):
        if len(name) <= 4 or name.endswith("_id") or name == "id":
            return "identifier"
        return "free_text"
    return "unknown"


def _is_internal(table_name: str) -> bool:
    base = table_name.split(".")[-1]
    return bool(_INTERNAL_PATTERNS.search(base))


def _parse_schema_name(display_name: str) -> tuple[str | None, str]:
    if "." in display_name:
        schema, table = display_name.split(".", 1)
        return schema, table
    return None, display_name


def _fk_out_degree(table: TableInfo) -> int:
    return len(table.foreign_keys)


def _fk_in_degree(table_name: str, all_tables: list[TableInfo]) -> int:
    count = 0
    for other in all_tables:
        for fk in other.foreign_keys:
            if fk.referred_table == table_name:
                count += 1
    return count


def _importance(table: TableInfo, all_tables: list[TableInfo]) -> float:
    if _is_internal(table.name):
        return 0.0
    out_deg = _fk_out_degree(table)
    in_deg = _fk_in_degree(table.name, all_tables)
    row_part = 0.0
    if table.row_count and table.row_count > 0:
        row_part = min(math.log10(table.row_count + 1) / 6.0, 1.0)
    fk_part = min((out_deg + in_deg) / 10.0, 1.0)
    return round(fk_part * 0.6 + row_part * 0.4, 3)


def compute_schema_hash(tables: list[TableInfo]) -> str:
    parts: list[str] = []
    for table in sorted(tables, key=lambda t: t.name):
        for col in sorted(table.columns, key=lambda c: c.name):
            parts.append(f"{table.name}:{col.name}:{col.type}:{col.primary_key}")
        for fk in sorted(table.foreign_keys, key=lambda f: (f.column, f.referred_table)):
            parts.append(f"fk:{table.name}:{fk.column}->{fk.referred_table}.{fk.referred_column}")
    digest = hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()
    return digest[:16]


def build_catalog(connection_id: str, db_type: str, tables: list[TableInfo]) -> SchemaCatalog:
    """Convert introspected schema into a searchable catalog."""
    catalog_tables: list[CatalogTable] = []
    for table in tables:
        schema_name, _ = _parse_schema_name(table.name)
        columns: list[CatalogColumn] = []
        for col in table.columns:
            semantic = _infer_semantic_type(col.name, col.type)
            samples, is_sensitive = filter_sample_values(col.name, semantic, col.sample_values)
            fk_table = None
            fk_col = None
            for fk in table.foreign_keys:
                if fk.column == col.name:
                    fk_table = fk.referred_table
                    fk_col = fk.referred_column
                    break
            columns.append(
                CatalogColumn(
                    name=col.name,
                    type=col.type,
                    nullable=col.nullable,
                    primary_key=col.primary_key,
                    fk_referred_table=fk_table,
                    fk_referred_column=fk_col,
                    semantic_type=semantic,
                    sample_values=samples,
                    is_sensitive=is_sensitive,
                )
            )
        catalog_tables.append(
            CatalogTable(
                name=table.name,
                schema_name=schema_name,
                row_estimate=table.row_count,
                importance_score=_importance(table, tables),
                is_internal=_is_internal(table.name),
                columns=columns,
            )
        )
    return SchemaCatalog(
        connection_id=connection_id,
        db_type=db_type,
        schema_hash=compute_schema_hash(tables),
        tables=catalog_tables,
        captured_at=datetime.now(timezone.utc).isoformat(),
    )


def catalog_table_by_name(catalog: SchemaCatalog, name: str) -> CatalogTable | None:
    """Lookup table by display name (case-insensitive)."""
    lower = name.lower()
    for table in catalog.tables:
        if table.name.lower() == lower:
            return table
        short = table.name.split(".")[-1].lower()
        if short == lower:
            return table
    return None


__all__ = [
    "build_catalog",
    "compute_schema_hash",
    "catalog_table_by_name",
]
