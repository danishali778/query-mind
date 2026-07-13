"""Normalize API connection inputs without retaining raw connection URIs."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from sqlalchemy.engine import make_url

from app.core.errors import BadRequestError
from app.db.models.connection import ConnectionRequest


_URI_QUERY_KEYS = {"sslmode"}
_URI_SCHEMES = {"postgres", "postgresql"}


def normalize_connection_input(data: dict[str, Any]) -> ConnectionRequest:
    raw = dict(data)
    input_mode = str(raw.pop("input_mode", "fields") or "fields")
    connection_uri = raw.pop("connection_uri", None)
    raw.pop("owner_id", None)

    if input_mode == "uri":
        if not connection_uri:
            raise BadRequestError("A PostgreSQL connection URI is required.", code="connection_uri_invalid")
        if len(connection_uri) > 8192:
            raise BadRequestError("The connection URI is too long.", code="connection_uri_invalid")
        split = urlsplit(connection_uri)
        if split.scheme.lower() not in _URI_SCHEMES or split.fragment:
            raise BadRequestError("Only postgres:// and postgresql:// URIs are supported.", code="connection_uri_invalid")
        conflicting = {
            key for key in ("host", "port", "database", "username", "password")
            if key in raw and raw.get(key) not in (None, "")
        }
        if conflicting:
            raise BadRequestError(
                "Do not combine a connection URI with individual database fields.",
                code="connection_uri_conflict",
            )
        try:
            parsed = make_url(connection_uri)
        except Exception as exc:
            raise BadRequestError("The PostgreSQL connection URI is invalid.", code="connection_uri_invalid") from exc
        unknown = set(parsed.query) - _URI_QUERY_KEYS
        if unknown:
            raise BadRequestError(
                "The connection URI contains unsupported or unsafe parameters.",
                code="connection_uri_parameter_rejected",
            )
        raw.update(
            {
                "db_type": "postgresql",
                "host": parsed.host,
                "port": parsed.port or 5432,
                "database": parsed.database,
                "username": parsed.username,
                "password": parsed.password,
                "ssl_mode": parsed.query.get("sslmode", raw.get("ssl_mode", "require")),
            }
        )
    elif input_mode != "fields":
        raise BadRequestError("Unsupported connection input mode.", code="connection_input_mode_invalid")

    raw.setdefault("db_type", "postgresql")
    raw["host"] = raw.get("host") or "localhost"
    raw["port"] = raw.get("port") or 5432
    if not str(raw.get("database") or "").strip():
        raise BadRequestError("Database name is required.", code="connection_database_required")
    if raw.get("password") == "":
        raw["password"] = None
    try:
        return ConnectionRequest(**raw)
    except ValueError as exc:
        raise BadRequestError(str(exc), code="connection_configuration_invalid") from exc


__all__ = ["normalize_connection_input"]
