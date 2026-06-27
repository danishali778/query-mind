"""Reusable SQLAlchemy column types for the app database."""

from __future__ import annotations

from sqlalchemy import CHAR, JSON, Text
from sqlalchemy.dialects import postgresql
from sqlalchemy.types import TypeDecorator


class GUID(TypeDecorator):
    """Platform-independent UUID type that returns string values.

    Supabase/Postgres stores these as UUID columns. Tests can still use SQLite,
    where the value is stored as a 36-character string.
    """

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(postgresql.UUID(as_uuid=False))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        return str(value)


JsonType = JSON().with_variant(postgresql.JSONB, "postgresql")
StringArray = JSON().with_variant(postgresql.ARRAY(Text), "postgresql")
UuidArray = JSON().with_variant(postgresql.ARRAY(postgresql.UUID(as_uuid=False)), "postgresql")


__all__ = ["GUID", "JsonType", "StringArray", "UuidArray"]