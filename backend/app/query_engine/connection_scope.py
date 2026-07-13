"""Normalization and execution-time enforcement for connection object scope."""

from __future__ import annotations

import threading
import time

from sqlglot import exp, parse_one

from app.core.config import settings
from app.db.orm_models import DatabaseConnectionORM, SchemaSnapshotORM
from app.db.session import read_session_scope
from app.query_engine.schema_exclusions import DEFAULT_EXCLUDED_SCHEMAS, is_schema_excluded


_cache: dict[tuple[str, str], tuple[dict, float]] = {}
_lock = threading.RLock()


def normalize_scope(mode: str, schemas: list[str], tables: list[str]) -> dict:
    normalized_schemas = sorted({item.strip() for item in schemas if item.strip()}, key=str.casefold)
    normalized_tables: set[str] = set()
    for value in tables:
        value = value.strip()
        if not value:
            continue
        if value.count(".") != 1:
            raise ValueError("Included tables must use schema.table names.")
        schema_name, table_name = value.split(".", 1)
        if not schema_name or not table_name:
            raise ValueError("Included tables must use schema.table names.")
        if is_schema_excluded(schema_name, DEFAULT_EXCLUDED_SCHEMAS):
            raise ValueError("System schemas cannot be included.")
        normalized_tables.add(f"{schema_name}.{table_name}")
    for schema_name in normalized_schemas:
        if is_schema_excluded(schema_name, DEFAULT_EXCLUDED_SCHEMAS):
            raise ValueError("System schemas cannot be included.")
    if mode not in {"all", "allowlist"}:
        raise ValueError("Connection scope mode must be all or allowlist.")
    if mode == "allowlist" and not (normalized_schemas or normalized_tables):
        raise ValueError("Allowlist scope requires at least one schema or table.")
    return {
        "mode": mode,
        "included_schemas": normalized_schemas,
        "included_tables": sorted(normalized_tables, key=str.casefold),
    }


def validate_scope_inventory(scope: dict, inventory: list[dict]) -> list[dict]:
    available_schemas = {item["name"].casefold() for item in inventory}
    available_tables = {
        f"{item['name']}.{table}".casefold()
        for item in inventory
        for table in item.get("tables", [])
    }
    errors: list[dict] = []
    for schema_name in scope["included_schemas"]:
        if schema_name.casefold() not in available_schemas:
            errors.append({"code": "scope_schema_not_found", "message": "An included schema is not accessible."})
    for table_name in scope["included_tables"]:
        if table_name.casefold() not in available_tables:
            errors.append({"code": "scope_table_not_found", "message": "An included table is not accessible."})
    return errors


def invalidate_scope_cache(owner_id: str, connection_id: str) -> None:
    with _lock:
        _cache.pop((owner_id, connection_id), None)


def _load_scope(owner_id: str, connection_id: str) -> dict | None:
    key = (owner_id, connection_id)
    now = time.monotonic()
    with _lock:
        cached = _cache.get(key)
        if cached and now - cached[1] < settings.connection_scope_cache_ttl_seconds:
            return cached[0]
    with read_session_scope() as session:
        row = session.query(DatabaseConnectionORM).filter(
            DatabaseConnectionORM.id == connection_id,
            DatabaseConnectionORM.owner_id == owner_id,
        ).one_or_none()
        snapshot = None if not row else session.query(SchemaSnapshotORM).filter(
            SchemaSnapshotORM.connection_id == connection_id,
            SchemaSnapshotORM.owner_id == owner_id,
        ).one_or_none()
        known_tables = []
        if snapshot:
            for table in (snapshot.catalog_json or {}).get("tables", []):
                name = str(table.get("name") or "")
                schema_name = str(table.get("schema_name") or "")
                if name:
                    known_tables.append(name if "." in name else f"{schema_name or 'public'}.{name}")
        scope = None if not row else {
            "connection_id": row.id,
            "mode": row.scope_mode or "all",
            "included_schemas": list(row.included_schemas or []),
            "included_tables": list(row.included_tables or []),
            "revision": row.scope_revision or 1,
            "known_tables": known_tables,
        }
    if scope:
        with _lock:
            _cache[key] = (scope, now)
    return scope


def referenced_tables(sql: str) -> set[str]:
    tree = parse_one(sql, read="postgres")
    cte_names = {cte.alias_or_name.casefold() for cte in tree.find_all(exp.CTE)}
    tables: set[str] = set()
    for table in tree.find_all(exp.Table):
        name = table.name
        schema = table.db
        if not schema and name.casefold() in cte_names:
            continue
        tables.add(f"{schema or 'public'}.{name}")
    return tables


def validate_connection_scope_sql(owner_id: str, connection_id: str, sql: str) -> tuple[bool, str | None]:
    scope = _load_scope(owner_id, connection_id)
    if not scope:
        return False, "Connection access scope could not be verified."
    try:
        references = referenced_tables(sql)
    except Exception:
        return False, "Connection access scope could not parse this query safely."
    for canonical in references:
        schema_name, _table_name = canonical.split(".", 1)
        if is_schema_excluded(schema_name, DEFAULT_EXCLUDED_SCHEMAS):
            return False, "The query references an object outside this connection's allowed scope."
    known_tables = {item.casefold() for item in scope.get("known_tables", [])}
    if any(canonical.casefold() not in known_tables for canonical in references):
        return False, "The query references an unknown or unavailable database object."
    if scope["mode"] == "all":
        return True, None
    schemas = {item.casefold() for item in scope["included_schemas"]}
    tables = {item.casefold() for item in scope["included_tables"]}
    for canonical in references:
        schema_name, _table_name = canonical.split(".", 1)
        if schema_name.casefold() not in schemas and canonical.casefold() not in tables:
            return False, "The query references an object outside this connection's allowed scope."
    return True, None


__all__ = [
    "invalidate_scope_cache",
    "normalize_scope",
    "referenced_tables",
    "validate_connection_scope_sql",
    "validate_scope_inventory",
]
