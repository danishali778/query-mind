from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from app.db.models.connection import ColumnInfo, ForeignKeyInfo, TableInfo

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


def _get_user_schema_names(inspector) -> list[str | None]:
    try:
        schema_names = inspector.get_schema_names()
    except Exception:
        return [None]

    excluded = {"information_schema", "pg_catalog"}
    user_schemas = [schema for schema in schema_names if schema not in excluded and not schema.startswith("pg_toast")]
    return user_schemas or [None]


def get_table_names(engine: Engine) -> list[str]:
    inspector = inspect(engine)
    table_names: list[str] = []
    for schema_name in _get_user_schema_names(inspector):
        for table_name in inspector.get_table_names(schema=schema_name):
            table_names.append(_display_table_name(schema_name, table_name))
    return table_names


def get_schema(engine: Engine) -> list[TableInfo]:
    """Discover full schema: tables, columns, PKs, FKs, and approximate row counts."""
    inspector = inspect(engine)
    tables: list[TableInfo] = []

    for schema_name in _get_user_schema_names(inspector):
        for table_name in inspector.get_table_names(schema=schema_name):
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

            row_count = None
            try:
                with engine.connect() as conn:
                    result = conn.execute(text(f"SELECT COUNT(*) FROM {qualified_table}"))
                    row_count = result.scalar()
            except Exception:
                pass

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
    "generate_erd_mermaid",
    "generate_erd_json",
]
