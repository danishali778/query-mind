from datetime import datetime, timedelta, timezone
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, model_validator


ConnectionHealthState = Literal["live", "failed", "stale", "unknown"]
ConnectionLastStatus = Literal["unknown", "healthy", "failed"]
ConnectionRuntimeStatus = Literal["live", "offline", "warning"]
ConnectionScopeMode = Literal["all", "allowlist"]

CONNECTION_HEALTH_STALE_AFTER = timedelta(hours=24)


def _normalize_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def derive_connection_status(
    last_status: str | None,
    last_tested_at: datetime | None,
    *,
    now: datetime | None = None,
) -> tuple[ConnectionHealthState, ConnectionRuntimeStatus]:
    tested_at = _normalize_utc(last_tested_at)

    if last_status == "failed":
        return "failed", "offline"

    if last_status == "healthy" and tested_at is not None:
        now_utc = _normalize_utc(now or datetime.now(timezone.utc))
        assert now_utc is not None
        if now_utc - tested_at <= CONNECTION_HEALTH_STALE_AFTER:
            return "live", "live"
        return "stale", "warning"

    return "unknown", "warning"


class ConnectionRequest(BaseModel):
    """Canonical connection configuration used across persistence and query execution."""

    owner_id: Optional[str] = None
    name: Optional[str] = None
    db_type: str
    host: Optional[str] = "localhost"
    port: Optional[int] = None
    database: str
    username: Optional[str] = None
    password: Optional[str] = None
    ssl_mode: str = "disable"
    readonly: bool = True
    use_ssh: bool = False
    ssh_host: Optional[str] = None
    ssh_port: Optional[int] = 22
    ssh_username: Optional[str] = None
    ssh_password: Optional[str] = None
    ssh_private_key: Optional[str] = None
    ssl_root_certificate: Optional[str] = None
    ssl_client_certificate: Optional[str] = None
    ssl_client_private_key: Optional[str] = None
    scope_mode: ConnectionScopeMode = "all"
    included_schemas: list[str] = Field(default_factory=list)
    included_tables: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_ssh_config(self) -> "ConnectionRequest":
        if not self.use_ssh:
            return self

        if not self.ssh_host or not self.ssh_username:
            raise ValueError("SSH connections require ssh_host and ssh_username.")

        if self.ssh_password and self.ssh_private_key:
            raise ValueError("Provide either ssh_password or ssh_private_key, not both.")

        if not self.ssh_password and not self.ssh_private_key:
            raise ValueError("SSH connections require either ssh_password or ssh_private_key.")

        return self


class ActiveConnection(BaseModel):
    """Saved connection summary returned by the persistence layer."""

    id: str
    owner_id: str
    name: str
    db_type: str
    database: str
    host: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    status: ConnectionRuntimeStatus
    health_state: ConnectionHealthState = "unknown"
    tables_count: int = 0
    ssl_mode: str = "disable"
    readonly: bool = True
    use_ssh: bool = False
    ssh_host: Optional[str] = None
    last_tested_at: datetime | None = None
    last_status: ConnectionLastStatus = "unknown"
    last_error: Optional[str] = None
    latency_ms: float | None = None
    last_schema_sync_at: datetime | None = None
    credential_revision: int = 1
    credentials_updated_at: datetime | None = None
    has_ssl_root_certificate: bool = False
    has_ssl_client_certificate: bool = False
    has_ssl_client_private_key: bool = False
    scope_mode: ConnectionScopeMode = "all"
    included_schemas: list[str] = Field(default_factory=list)
    included_tables: list[str] = Field(default_factory=list)
    scope_revision: int = 1
    scope_updated_at: datetime | None = None
    health_check_enabled: bool = False
    health_check_interval_minutes: int = 60
    next_health_check_at: datetime | None = None
    schema_refresh_enabled: bool = False
    schema_refresh_interval_hours: int = 24
    next_schema_refresh_at: datetime | None = None


class ConnectionTestResult(BaseModel):
    success: bool
    message: str
    latency_ms: float | None = None
    diagnostic_id: str | None = None
    code: str = "connection_unknown"
    category: str = "unknown"
    suggestions: list[str] = Field(default_factory=list)
    checks: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[dict[str, Any]] = Field(default_factory=list)
    inventory: list[dict[str, Any]] | None = None
    inventory_truncated: bool = False
    server_version: str | None = None
    tables_found: int | None = None
    role_has_write_privileges: bool | None = None


class ConnectionHealthEvent(BaseModel):
    id: str
    connection_id: str
    source: str
    status: str
    diagnostic_code: str | None = None
    message: str | None = None
    latency_ms: float | None = None
    created_at: datetime


class ColumnInfo(BaseModel):
    """Canonical schema column representation."""

    name: str
    type: str
    nullable: bool
    primary_key: bool
    sample_values: list[str] = Field(default_factory=list)


class ForeignKeyInfo(BaseModel):
    """Canonical foreign-key representation."""

    column: str
    referred_table: str
    referred_column: str


class TableInfo(BaseModel):
    """Canonical database table schema representation."""

    name: str
    columns: list[ColumnInfo]
    foreign_keys: list[ForeignKeyInfo] = Field(default_factory=list)
    row_count: Optional[int] = None


__all__ = [
    "ConnectionRequest",
    "ActiveConnection",
    "ConnectionHealthState",
    "ConnectionLastStatus",
    "ConnectionRuntimeStatus",
    "ConnectionScopeMode",
    "ConnectionTestResult",
    "ConnectionHealthEvent",
    "derive_connection_status",
    "ColumnInfo",
    "ForeignKeyInfo",
    "TableInfo",
]
