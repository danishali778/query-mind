"""Schema namespaces excluded during database sync and introspection."""

from __future__ import annotations

# PostgreSQL system schemas plus common Supabase platform schemas.
# Tables in these namespaces are never stored on the connection catalog.
DEFAULT_EXCLUDED_SCHEMAS: frozenset[str] = frozenset(
    {
        "information_schema",
        "pg_catalog",
        "auth",
        "storage",
        "realtime",
        "supabase_functions",
        "supabase_migrations",
        "extensions",
        "graphql",
        "graphql_public",
        "vault",
        "pgbouncer",
        "_realtime",
        "net",
        "cron",
        "_analytics",
        "supabase",
        "pgsodium",
        "pgtle",
    }
)


def merge_excluded_schemas(extra: list[str] | None = None) -> frozenset[str]:
    """Return default excluded schemas plus any extra names from config."""
    if not extra:
        return DEFAULT_EXCLUDED_SCHEMAS
    extra_set = {name.strip().lower() for name in extra if name.strip()}
    return DEFAULT_EXCLUDED_SCHEMAS | extra_set


def is_schema_excluded(schema_name: str | None, excluded: frozenset[str]) -> bool:
    """True when a schema namespace should be omitted from sync/introspection."""
    if schema_name is None:
        return False
    lower = schema_name.lower()
    if lower in excluded:
        return True
    return lower.startswith("pg_toast")


__all__ = [
    "DEFAULT_EXCLUDED_SCHEMAS",
    "is_schema_excluded",
    "merge_excluded_schemas",
]
