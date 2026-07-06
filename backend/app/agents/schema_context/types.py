"""Schema catalog types for the database agent."""

from pydantic import BaseModel, Field


class CatalogColumn(BaseModel):
    name: str
    type: str
    nullable: bool = True
    primary_key: bool = False
    fk_referred_table: str | None = None
    fk_referred_column: str | None = None
    semantic_type: str = "unknown"
    sample_values: list[str] = Field(default_factory=list)
    is_sensitive: bool = False


class CatalogTable(BaseModel):
    name: str
    schema_name: str | None = None
    row_estimate: int | None = None
    importance_score: float = 0.0
    is_internal: bool = False
    columns: list[CatalogColumn] = Field(default_factory=list)


class SchemaCatalog(BaseModel):
    connection_id: str
    db_type: str
    schema_hash: str
    tables: list[CatalogTable] = Field(default_factory=list)
    captured_at: str


class ScoredTable(BaseModel):
    name: str
    score: float
    reason: str
    matched_columns: list[str] = Field(default_factory=list)


__all__ = [
    "CatalogColumn",
    "CatalogTable",
    "SchemaCatalog",
    "ScoredTable",
]
