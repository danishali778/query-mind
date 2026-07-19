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
    agent_run_id: Optional[str] = None
    agent_run_status: Optional[str] = None
    agent_run_stage: Optional[str] = None
    agent_run_stage_label: Optional[str] = None
    semantic_lineage: list[dict] = Field(default_factory=list)
    response_kind: str = "answer"
    clarification_context: Optional[dict] = None
    presentation_kind: Optional[str] = None
    answer_metadata: Optional[dict] = None
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
    memory_state: Dict = Field(default_factory=dict)
    memory_revision: int = 1
    memory_updated_at: Optional[str] = None
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


class ChatAgentRun(BaseModel):
    id: str
    owner_id: str
    session_id: str
    connection_id: str
    user_message_id: str
    assistant_message_id: Optional[str] = None
    client_request_id: str
    celery_task_id: Optional[str] = None
    status: str
    current_stage: str
    current_stage_label: str
    failure_code: Optional[str] = None
    failure_message: Optional[str] = None
    created_at: str
    started_at: Optional[str] = None
    heartbeat_at: Optional[str] = None
    cancel_requested_at: Optional[str] = None
    finished_at: Optional[str] = None
    updated_at: Optional[str] = None
