import logging

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import CurrentUserDep, RateLimitChecker
from app.api.v1.schemas.chat import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    EditSqlRequest,
    SessionMessagesResponse,
    SessionSummary,
    UpdateSessionRequest,
)
from app.api.v1.schemas.common import MessageResponse
from app.core.errors import BadRequestError, NotFoundError, ServiceUnavailableError
from app.services import chat_service


router = APIRouter(prefix="/api/chat", tags=["Chat"])
logger = logging.getLogger(__name__)


@router.post("", response_model=ChatResponse)
async def send_chat_message(
    request: ChatRequest,
    current_user: CurrentUserDep,
    _: object = Depends(RateLimitChecker("ai")),
):
    try:
        result = await chat_service.send_message(
            current_user.id,
            connection_id=request.connection_id,
            message=request.message,
            session_id=request.session_id,
        )
        return ChatResponse.model_validate(result)
    except ValueError as exc:
        detail = str(exc)
        if "not found" in detail.lower():
            raise NotFoundError(detail) from exc
        raise BadRequestError(detail) from exc
    except Exception as exc:
        logger.error("Chat request failed for user %s", current_user.id, exc_info=True)
        raise ServiceUnavailableError("AI processing failed for this request.") from exc


@router.get("/sessions", response_model=list[SessionSummary])
async def list_sessions(current_user: CurrentUserDep):
    return await chat_service.list_sessions(current_user.id)


@router.post("/sessions", response_model=SessionSummary)
async def create_session(current_user: CurrentUserDep, connection_id: str | None = None):
    try:
        return await chat_service.create_session_summary(current_user.id, connection_id)
    except ValueError as exc:
        raise NotFoundError(str(exc)) from exc


@router.patch("/sessions/{session_id}", response_model=SessionSummary)
async def update_session(session_id: str, request: UpdateSessionRequest, current_user: CurrentUserDep):
    try:
        return await chat_service.update_session_summary(current_user.id, session_id, request.title)
    except ValueError as exc:
        raise NotFoundError(str(exc)) from exc


@router.delete("/sessions/{session_id}", response_model=MessageResponse)
async def delete_session(session_id: str, current_user: CurrentUserDep):
    success = await chat_service.delete_session(current_user.id, session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found.")
    return {"message": f"Session {session_id} deleted."}


@router.get("/sessions/{session_id}/messages", response_model=SessionMessagesResponse)
async def get_session_messages(session_id: str, current_user: CurrentUserDep):
    try:
        return await chat_service.get_session_messages_response(current_user.id, session_id)
    except ValueError as exc:
        raise NotFoundError(str(exc)) from exc


@router.post("/{session_id}/message/{message_id}/edit-sql", response_model=ChatMessage)
async def edit_chat_sql(
    session_id: str,
    message_id: str,
    request: EditSqlRequest,
    current_user: CurrentUserDep,
):
    try:
        return await chat_service.edit_message_sql(
            current_user.id,
            session_id,
            message_id,
            request.sql,
            request.connection_id,
        )
    except ValueError as exc:
        raise NotFoundError(str(exc)) from exc
    except Exception as exc:
        raise ServiceUnavailableError("Unable to re-run the edited SQL at the moment.") from exc


@router.post("/{session_id}/message/{message_id}/pin", response_model=MessageResponse)
async def toggle_pin_message(
    session_id: str,
    message_id: str,
    is_pinned: bool,
    current_user: CurrentUserDep,
):
    success = await chat_service.toggle_pin_status(current_user.id, session_id, message_id, is_pinned)
    if not success:
        raise HTTPException(status_code=404, detail="Message not found.")

    return MessageResponse(message="Pin status updated")
