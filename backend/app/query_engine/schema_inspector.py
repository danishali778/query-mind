from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from app.core.config import settings
from app.db.models.connection import ColumnInfo, ForeignKeyInfo, TableInfo
from app.query_engine.schema_exclusions import is_schema_excluded, merge_excluded_schemas

_ENUM_KEYWORDS = {
    "type",
    "status",
    "category",
    "tier",
    "kind",
    "mode",
    "state",
    "level",
    "role",
    "gender",
    "priority",
    "source",
    "method",
    "format",
}


def _is_enum_like(col_name: str, col_type: str) -> bool:
    type_lower = col_type.lower()
    is_text = any(token in type_lower for token in ("varchar", "text", "character varying", "char"))
    name_lower = col_name.lower()
    has_keyword = any(keyword in name_lower for keyword in _ENUM_KEYWORDS)
    return is_text and has_keyword


def _get_distinct_values(engine: Engine, qualified_table_name: str, col_name: str, max_values: int = 15) -> list[str]:
    try:
        with engine.connect() as conn:
            quoted_column = _quote_identifier(col_name)
            count_result = conn.execute(text(f"SELECT COUNT(DISTINCT {quoted_column}) FROM {qualified_table_name}"))
            count = count_result.scalar()
            if count is None or count > max_values:
                return []
            rows = conn.execute(
                text(
                    f"SELECT DISTINCT {quoted_column} FROM {qualified_table_name} "
                    f"WHERE {quoted_column} IS NOT NULL ORDER BY {quoted_column}"
                )
            ).fetchall()
            return [str(row[0]) for row in rows]
    except Exception:
        return []


def _quote_identifier(identifier: str) -> str:
    return f'"{identifier.replace(chr(34), chr(34) * 2)}"'


def _qualify_table_name(schema_name: str | None, table_name: str) -> str:
    table = _quote_identifier(table_name)
    if not schema_name:
        return table
    return f"{_quote_identifier(schema_name)}.{table}"


def _display_table_name(schema_name: str | None, table_name: str) -> str:
    if not schema_name or schema_name in {"public", "main"}:
        return table_name
    return f"{schema_name}.{table_name}"


def _excluded_schemas() -> frozenset[str]:
    return merge_excluded_schemas(settings.catalog_excluded_schemas_extra)


def _get_user_schema_names(inspector) -> list[str | None]:
    try:
        schema_names = inspector.get_schema_names()
    except Exception:
        return [None]

    excluded = _excluded_schemas()
    user_schemas = [schema for schema in schema_names if not is_schema_excluded(schema, excluded)]
    return user_schemas or [None]


def get_table_names(engine: Engine) -> list[str]:
    inspector = inspect(engine)
    table_names: list[str] = []
    for schema_name in _get_user_schema_names(inspector):
        for table_name in inspector.get_table_names(schema=schema_name):
            table_names.append(_display_table_name(schema_name, table_name))
    return table_names


def _get_row_estimates(engine: Engine) -> dict[str, int]:
    """Fetch approximate row counts from pg_class (Postgres only)."""
    estimates: dict[str, int] = {}
    excluded = _excluded_schemas()
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT n.nspname AS schema_name, c.relname AS table_name,
                           GREATEST(c.reltuples, 0)::bigint AS row_estimate
                    FROM pg_class c
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE c.relkind = 'r'
                      AND n.nspname NOT IN ('information_schema', 'pg_catalog')
                      AND n.nspname NOT LIKE 'pg_toast%'
                    """
                )
            ).fetchall()
            for schema_name, table_name, row_estimate in rows:
                if is_schema_excluded(schema_name, excluded):
                    continue
                display = _display_table_name(schema_name, table_name)
                estimates[display] = int(row_estimate)
                estimates[table_name] = int(row_estimate)
    except Exception:
        return {}
    return estimates


def _canonical_table(schema_name: str | None, table_name: str) -> str:
    return f"{schema_name or 'public'}.{table_name}"


def discover_schema_inventory(engine: Engine, max_objects: int = 5000) -> tuple[list[dict], bool]:
    """Return name-only user schema inventory; never inspect columns or values."""
    inspector = inspect(engine)
    inventory: list[dict] = []
    count = 0
    truncated = False
    for schema_name in _get_user_schema_names(inspector):
        display_schema = schema_name or "public"
        names: list[str] = []
        for table_name in inspector.get_table_names(schema=schema_name):
            if count >= max_objects:
                truncated = True
                break
            names.append(table_name)
            count += 1
        inventory.append({"name": display_schema, "tables": names})
        if truncated:
            break
    return inventory, truncated


def get_schema(
    engine: Engine,
    *,
    scope_mode: str = "all",
    included_schemas: list[str] | None = None,
    included_tables: list[str] | None = None,
) -> list[TableInfo]:
    """Discover full schema: tables, columns, PKs, FKs, and approximate row counts."""
    inspector = inspect(engine)
    tables: list[TableInfo] = []
    row_estimates = _get_row_estimates(engine)
    excluded = _excluded_schemas()

    allowed_schemas = {item.casefold() for item in (included_schemas or [])}
    allowed_tables = {item.casefold() for item in (included_tables or [])}
    for schema_name in _get_user_schema_names(inspector):
        for table_name in inspector.get_table_names(schema=schema_name):
            canonical = _canonical_table(schema_name, table_name)
            if scope_mode == "allowlist" and not (
                (schema_name or "public").casefold() in allowed_schemas
                or canonical.casefold() in allowed_tables
            ):
                continue
            display_name = _display_table_name(schema_name, table_name)
            pk_columns: set[str] = set()
            try:
                pk = inspector.get_pk_constraint(table_name, schema=schema_name)
                pk_columns = set(pk.get("constrained_columns", []))
            except Exception:
                pass

            columns: list[ColumnInfo] = []
            qualified_table = _qualify_table_name(schema_name, table_name)
            for col in inspector.get_columns(table_name, schema=schema_name):
                col_name = col["name"]
                col_type = str(col["type"])
                sample_values = (
                    _get_distinct_values(engine, qualified_table, col_name) if _is_enum_like(col_name, col_type) else []
                )
                columns.append(
                    ColumnInfo(
                        name=col_name,
                        type=col_type,
                        nullable=col.get("nullable", True),
                        primary_key=col_name in pk_columns,
                        sample_values=sample_values,
                    )
                )

            foreign_keys: list[ForeignKeyInfo] = []
            try:
                for fk in inspector.get_foreign_keys(table_name, schema=schema_name):
                    referred_table = fk.get("referred_table", "")
                    referred_schema = fk.get("referred_schema")
                    if referred_schema and is_schema_excluded(referred_schema, excluded):
                        continue
                    display_referred_table = _display_table_name(referred_schema, referred_table) if referred_table else ""
                    constrained_cols = fk.get("constrained_columns", [])
                    referred_cols = fk.get("referred_columns", [])
                    for local_col, remote_col in zip(constrained_cols, referred_cols):
                        foreign_keys.append(
                            ForeignKeyInfo(
                                column=local_col,
                                referred_table=display_referred_table,
                                referred_column=remote_col,
                            )
                        )
            except Exception:
                pass

            row_count = row_estimates.get(display_name)
            if row_count is None:
                row_count = row_estimates.get(table_name)

            tables.append(
                TableInfo(
                    name=display_name,
                    columns=columns,
                    foreign_keys=foreign_keys,
                    row_count=row_count,
                )
            )

    return tables


def generate_erd_mermaid(schema: list[TableInfo]) -> str:
    lines = ["erDiagram"]
    for table in schema:
        lines.append(f"    {table.name} {{")
        for col in table.columns:
            col_type = col.type.split("(")[0].upper()
            tags = ""
            if col.primary_key:
                tags = " PK"
            fk_match = next((fk for fk in table.foreign_keys if fk.column == col.name), None)
            if fk_match:
                tags = " FK" if not col.primary_key else " PK,FK"
            lines.append(f"        {col_type} {col.name}{tags}")
        lines.append("    }")

    for table in schema:
        for fk in table.foreign_keys:
            lines.append(f'    {fk.referred_table} ||--o{{ {table.name} : "{fk.column}"')

    return "\n".join(lines)


def generate_erd_json(schema: list[TableInfo]) -> dict:
    tables = []
    relationships = []

    for table in schema:
        tables.append(
            {
                "name": table.name,
                "row_count": table.row_count,
                "columns": [
                    {
                        "name": col.name,
                        "type": col.type,
                        "primary_key": col.primary_key,
                        "nullable": col.nullable,
                        "is_foreign_key": any(fk.column == col.name for fk in table.foreign_keys),
                    }
                    for col in table.columns
                ],
            }
        )
        for fk in table.foreign_keys:
            relationships.append(
                {
                    "from_table": table.name,
                    "from_column": fk.column,
                    "to_table": fk.referred_table,
                    "to_column": fk.referred_column,
                    "type": "many-to-one",
                }
            )

    return {
        "tables": tables,
        "relationships": relationships,
        "table_count": len(tables),
        "relationship_count": len(relationships),
    }


__all__ = [
    "get_table_names",
    "get_schema",
    "discover_schema_inventory",
    "generate_erd_mermaid",
    "generate_erd_json",
]
