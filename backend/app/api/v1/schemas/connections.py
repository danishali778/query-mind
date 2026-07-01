from __future__ import annotations

from typing import Optional

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
    message: str
    tables_count: Optional[int] = None
    readonly: bool = True


class ConnectionRequest(BaseModel):
    """API-facing connection request payload."""

    owner_id: Optional[str] = None
    name: Optional[str] = None
    db_type: str
    host: Optional[str] = "localhost"
    port: Optional[int] = None
    database: str
    username: Optional[str] = None
    password: Optional[str] = None
    ssl_mode: str = "disable"
    use_ssh: bool = False
    ssh_host: Optional[str] = None
    ssh_port: Optional[int] = 22
    ssh_username: Optional[str] = None
    ssh_password: Optional[str] = None
    ssh_private_key: Optional[str] = None


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
    tables_count: int = 0
    ssl_mode: str = "disable"
    readonly: bool = True
    use_ssh: bool = False
    ssh_host: Optional[str] = None


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

    db_type: str
    host: Optional[str] = "localhost"
    port: Optional[int] = None
    database: str
    username: Optional[str] = None
    password: Optional[str] = None
    ssl_mode: str = "disable"

    use_ssh: bool = False
    ssh_host: Optional[str] = None
    ssh_port: Optional[int] = 22
    ssh_username: Optional[str] = None
    ssh_password: Optional[str] = None
    ssh_private_key: Optional[str] = None


class TestConnectionResponse(BaseModel):
    """Response from testing a connection."""

    success: bool
    message: str
    tables_found: Optional[int] = None


class UpdateConnectionSettingsRequest(BaseModel):
    """Patchable security settings for an existing connection."""

    ssl_mode: Optional[str] = None


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
    "MermaidErdResponse",
    "ErdJsonColumn",
    "ErdJsonTable",
    "ErdJsonRelationship",
    "JsonErdResponse",
]
