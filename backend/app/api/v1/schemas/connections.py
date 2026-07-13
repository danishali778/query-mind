from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class ConnectionResponse(BaseModel):
    """Response after connecting."""

    id: str
    name: str
    db_type: str
    database: str
    host: Optional[str] = None
    port: Optional[int] = None
    status: str
    health_state: str
    message: str
    tables_count: Optional[int] = None
    readonly: bool = True
    ssl_mode: str = "disable"
    username: Optional[str] = None
    use_ssh: bool = False
    ssh_host: Optional[str] = None
    last_tested_at: datetime | None = None
    last_status: str = "unknown"
    last_error: Optional[str] = None
    latency_ms: float | None = None
    last_schema_sync_at: datetime | None = None
    credential_revision: int = 1
    credentials_updated_at: datetime | None = None
    has_ssl_root_certificate: bool = False
    has_ssl_client_certificate: bool = False
    has_ssl_client_private_key: bool = False
    scope_mode: str = "all"
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


class ConnectionRequest(BaseModel):
    """API-facing connection request payload."""

    owner_id: Optional[str] = None
    name: Optional[str] = None
    input_mode: Literal["fields", "uri"] = "fields"
    connection_uri: Optional[str] = Field(default=None, max_length=8192)
    db_type: str = "postgresql"
    host: Optional[str] = None
    port: Optional[int] = None
    database: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    ssl_mode: str = "disable"
    use_ssh: bool = False
    ssh_host: Optional[str] = None
    ssh_port: Optional[int] = 22
    ssh_username: Optional[str] = None
    ssh_password: Optional[str] = None
    ssh_private_key: Optional[str] = None
    ssl_root_certificate: Optional[str] = None
    ssl_client_certificate: Optional[str] = None
    ssl_client_private_key: Optional[str] = None
    scope_mode: Literal["all", "allowlist"] = "all"
    included_schemas: list[str] = Field(default_factory=list)
    included_tables: list[str] = Field(default_factory=list)


class ActiveConnection(BaseModel):
    """API-facing active connection payload."""

    id: str
    owner_id: str
    name: str
    db_type: str
    database: str
    host: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    status: str
    health_state: str
    tables_count: int = 0
    ssl_mode: str = "disable"
    readonly: bool = True
    use_ssh: bool = False
    ssh_host: Optional[str] = None
    last_tested_at: datetime | None = None
    last_status: str = "unknown"
    last_error: Optional[str] = None
    latency_ms: float | None = None
    last_schema_sync_at: datetime | None = None
    credential_revision: int = 1
    credentials_updated_at: datetime | None = None
    has_ssl_root_certificate: bool = False
    has_ssl_client_certificate: bool = False
    has_ssl_client_private_key: bool = False
    scope_mode: str = "all"
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


class ColumnInfo(BaseModel):
    """API-facing column payload."""

    model_config = ConfigDict(from_attributes=True)

    name: str
    type: str
    nullable: bool
    primary_key: bool
    sample_values: list[str] = Field(default_factory=list)


class ForeignKeyInfo(BaseModel):
    """API-facing foreign-key payload."""

    model_config = ConfigDict(from_attributes=True)

    column: str
    referred_table: str
    referred_column: str


class TableInfo(BaseModel):
    """API-facing table payload."""

    model_config = ConfigDict(from_attributes=True)

    name: str
    columns: list[ColumnInfo]
    foreign_keys: list[ForeignKeyInfo] = Field(default_factory=list)
    row_count: Optional[int] = None


class SchemaResponse(BaseModel):
    """Full schema of a connected database."""

    connection_id: str
    database: str
    tables: list[TableInfo]


class TestConnectionRequest(BaseModel):
    """Request to test a connection without saving."""

    input_mode: Literal["fields", "uri"] = "fields"
    connection_uri: Optional[str] = Field(default=None, max_length=8192)
    db_type: str = "postgresql"
    host: Optional[str] = None
    port: Optional[int] = None
    database: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    ssl_mode: str = "disable"

    use_ssh: bool = False
    ssh_host: Optional[str] = None
    ssh_port: Optional[int] = 22
    ssh_username: Optional[str] = None
    ssh_password: Optional[str] = None
    ssh_private_key: Optional[str] = None
    ssl_root_certificate: Optional[str] = None
    ssl_client_certificate: Optional[str] = None
    ssl_client_private_key: Optional[str] = None


class ConnectionDiagnosticCheck(BaseModel):
    code: str
    status: Literal["pending", "passed", "warning", "failed", "skipped"]
    label: str
    message: str | None = None


class ConnectionDiagnosticWarning(BaseModel):
    code: str
    message: str


class ConnectionInventorySchema(BaseModel):
    name: str
    tables: list[str] = Field(default_factory=list)


class TestConnectionResponse(BaseModel):
    """Response from testing a connection."""

    success: bool
    message: str
    tables_found: Optional[int] = None
    latency_ms: float | None = None
    diagnostic_id: str | None = None
    code: str = "connection_unknown"
    category: str = "unknown"
    suggestions: list[str] = Field(default_factory=list)
    checks: list[ConnectionDiagnosticCheck] = Field(default_factory=list)
    warnings: list[ConnectionDiagnosticWarning] = Field(default_factory=list)
    inventory: list[ConnectionInventorySchema] | None = None
    inventory_truncated: bool = False
    server_version: str | None = None
    role_has_write_privileges: bool | None = None


class UpdateConnectionSettingsRequest(BaseModel):
    """Patchable security settings for an existing connection."""

    ssl_mode: Optional[str] = None


class RotateConnectionCredentialsRequest(BaseModel):
    expected_credential_revision: int = Field(ge=1)
    username: str | None = None
    password: str | None = None
    ssl_mode: Literal["disable", "require", "verify-ca", "verify-full"] | None = None
    ssl_root_certificate: str | None = None
    ssl_client_certificate: str | None = None
    ssl_client_private_key: str | None = None
    ssh_username: str | None = None
    ssh_password: str | None = None
    ssh_private_key: str | None = None


class ConnectionScopePayload(BaseModel):
    mode: Literal["all", "allowlist"] = "all"
    included_schemas: list[str] = Field(default_factory=list)
    included_tables: list[str] = Field(default_factory=list)


class UpdateConnectionScopeRequest(ConnectionScopePayload):
    expected_scope_revision: int = Field(ge=1)
    acknowledged_impact_codes: list[str] = Field(default_factory=list)


class ConnectionScopeResponse(ConnectionScopePayload):
    connection_id: str
    revision: int
    updated_at: datetime | None = None


class ConnectionScopeImpact(BaseModel):
    code: str
    consumer_type: str
    consumer_id: str
    label: str


class ConnectionScopePreviewResponse(BaseModel):
    valid: bool
    normalized_scope: ConnectionScopePayload
    errors: list[dict] = Field(default_factory=list)
    warnings: list[dict] = Field(default_factory=list)
    impacts: list[ConnectionScopeImpact] = Field(default_factory=list)


class UpdateConnectionAutomationRequest(BaseModel):
    health_check_enabled: bool
    health_check_interval_minutes: Literal[15, 60, 360, 1440] = 60
    schema_refresh_enabled: bool
    schema_refresh_interval_hours: Literal[6, 12, 24, 168] = 24


class ConnectionAutomationResponse(UpdateConnectionAutomationRequest):
    connection_id: str
    next_health_check_at: datetime | None = None
    next_schema_refresh_at: datetime | None = None


class ConnectionHealthEventResponse(BaseModel):
    id: str
    source: str
    status: str
    diagnostic_code: str | None = None
    message: str | None = None
    latency_ms: float | None = None
    created_at: datetime


class ConnectionHealthHistoryResponse(BaseModel):
    connection_id: str
    items: list[ConnectionHealthEventResponse]
    next_cursor: str | None = None
    success_rate_24h: float
    success_rate_7d: float
    p50_latency_ms: float | None = None
    p95_latency_ms: float | None = None
    last_successful_schema_refresh_at: datetime | None = None
    next_health_check_at: datetime | None = None
    next_schema_refresh_at: datetime | None = None


class MermaidErdResponse(BaseModel):
    """Mermaid ERD payload."""

    connection_id: str
    format: str
    erd: str


class ErdJsonColumn(BaseModel):
    """Column payload inside JSON ERD output."""

    model_config = ConfigDict(from_attributes=True)

    name: str
    type: str
    primary_key: bool
    nullable: bool
    is_foreign_key: bool


class ErdJsonTable(BaseModel):
    """Table payload inside JSON ERD output."""

    model_config = ConfigDict(from_attributes=True)

    name: str
    row_count: Optional[int] = None
    columns: list[ErdJsonColumn] = Field(default_factory=list)


class ErdJsonRelationship(BaseModel):
    """Relationship payload inside JSON ERD output."""

    model_config = ConfigDict(from_attributes=True)

    from_table: str
    from_column: str
    to_table: str
    to_column: str
    type: str


class JsonErdResponse(BaseModel):
    """Structured JSON ERD payload."""

    connection_id: str
    format: str
    tables: list[ErdJsonTable] = Field(default_factory=list)
    relationships: list[ErdJsonRelationship] = Field(default_factory=list)
    table_count: int
    relationship_count: int


__all__ = [
    "ConnectionRequest",
    "ConnectionResponse",
    "ColumnInfo",
    "ForeignKeyInfo",
    "TableInfo",
    "SchemaResponse",
    "TestConnectionRequest",
    "TestConnectionResponse",
    "ActiveConnection",
    "UpdateConnectionSettingsRequest",
    "RotateConnectionCredentialsRequest",
    "ConnectionScopePayload",
    "UpdateConnectionScopeRequest",
    "ConnectionScopeResponse",
    "ConnectionScopePreviewResponse",
    "ConnectionAutomationResponse",
    "UpdateConnectionAutomationRequest",
    "ConnectionHealthHistoryResponse",
    "ConnectionHealthEventResponse",
    "ConnectionScopeImpact",
    "MermaidErdResponse",
    "ErdJsonColumn",
    "ErdJsonTable",
    "ErdJsonRelationship",
    "JsonErdResponse",
]
