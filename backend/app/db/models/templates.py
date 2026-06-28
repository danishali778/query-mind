from datetime import datetime

from pydantic import BaseModel, Field


class GeneratedQueryTemplate(BaseModel):
    """A persisted AI-generated query template."""

    id: str
    owner_id: str
    connection_id: str
    title: str
    description: str
    sql: str
    category: str
    category_color: str
    tags: list[str] = Field(default_factory=list)
    icon: str
    icon_bg: str
    difficulty: str
    created_at: datetime


class TemplateGenerationState(BaseModel):
    """Durable generation status for a user's connection."""

    owner_id: str
    connection_id: str
    status: str = "not_started"
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    updated_at: datetime | None = None

