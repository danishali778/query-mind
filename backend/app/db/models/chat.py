import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """A single message in a chat session."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    role: str
    content: str
    connection_id: Optional[str] = None
    sql: Optional[str] = None
    results: Optional[Dict] = None
    columns: List[str] = Field(default_factory=list)
    truncated: bool = False
    chart_recommendation: Optional[Any] = None
    is_pinned: bool = False
    error: Optional[str] = None
    parent_id: Optional[str] = None
    prev_query_id: Optional[str] = None
    agent_trace: Optional[list] = None
    agent_tier: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())

    def __init__(self, **data):
        if not data.get("id"):
            data["id"] = str(uuid.uuid4())
        if not data.get("created_at"):
            data["created_at"] = datetime.now().isoformat()
        super().__init__(**data)


class ChatSession(BaseModel):
    """A chat session with conversation history."""

    id: str
    owner_id: str
    connection_ids: list[str] = Field(default_factory=list)
    last_connection_id: Optional[str] = None
    title: Optional[str] = None
    messages: list[ChatMessage] = Field(default_factory=list)
    created_at: str = ""

    def __init__(self, **data):
        if not data.get("created_at"):
            data["created_at"] = datetime.now().isoformat()
        super().__init__(**data)


class SessionSummary(BaseModel):
    """Minimal chat session summary shared by repository and API layers."""

    id: str
    owner_id: str
    connection_ids: list[str] = Field(default_factory=list)
    last_connection_id: Optional[str] = None
    title: Optional[str] = None
    message_count: int = 0
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
