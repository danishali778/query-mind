import logging

from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.responses import StreamingResponse

from app.api.deps import CurrentUserDep, LlmAccessChecker
from app.api.v1.schemas.chat import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ChatRunAccepted,
    ChatRunRequest,
    ChatRunSnapshot,
    EditSqlRequest,
    SessionMessagesResponse,
    SessionSummary,
    UpdateSessionRequest,
)
from app.api.v1.schemas.common import MessageResponse
from app.core.errors import AppError, BadRequestError, NotFoundError, ServiceUnavailableError
from app.services import chat_service
from app.services import chat_run_service
from app.db.repositories.chat_run_repository import ActiveRunConflictError


router = APIRouter(prefix="/api/chat", tags=["Chat"])
logger = logging.getLogger(__name__)


@router.post("/runs", response_model=ChatRunAccepted, status_code=status.HTTP_202_ACCEPTED)
async def start_chat_run(
    request: ChatRunRequest,
    current_user: CurrentUserDep,
    _: object = Depends(LlmAccessChecker("chat")),
):
    try:
        return await chat_run_service.start_run(current_user.id, request)
    except ActiveRunConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except chat_run_service.RunLimitError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except chat_run_service.StreamingUnavailableError as exc:
        raise ServiceUnavailableError(str(exc)) from exc
    except ValueError as exc:
        detail = str(exc)
        if "not found" in detail.lower():
            raise NotFoundError(detail) from exc
        raise BadRequestError(detail) from exc


@router.get("/runs/{run_id}", response_model=ChatRunSnapshot)
async def get_chat_run(run_id: str, current_user: CurrentUserDep):
    snapshot = await chat_run_service.get_snapshot(current_user.id, run_id)
    if not snapshot:
        raise NotFoundError("Chat run not found.")
    return snapshot


@router.post("/runs/{run_id}/cancel", response_model=ChatRunSnapshot, status_code=status.HTTP_202_ACCEPTED)
async def cancel_chat_run(run_id: str, current_user: CurrentUserDep):
    snapshot = await chat_run_service.cancel_run(current_user.id, run_id)
    if not snapshot:
        raise NotFoundError("Chat run not found.")
    return snapshot


@router.get("/runs/{run_id}/events")
async def stream_chat_run_events(
    run_id: str,
    current_user: CurrentUserDep,
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
):
    if not await chat_run_service.get_snapshot(current_user.id, run_id):
        raise NotFoundError("Chat run not found.")
    try:
        sequence = int((last_event_id or "0").split("-", 1)[0])
    except ValueError:
        sequence = 0
    return StreamingResponse(
        chat_run_service.stream_events(current_user.id, run_id, sequence),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("", response_model=ChatResponse)
async def send_chat_message(
    request: ChatRequest,
    current_user: CurrentUserDep,
    _: object = Depends(LlmAccessChecker("chat")),
):
    try:
        result = await chat_service.send_message(
            current_user.id,
            connection_id=request.connection_id,
            message=request.message,
            session_id=request.session_id,
        )
        return ChatResponse.model_validate(result)
    except chat_service.ChatPersistenceError as exc:
        raise ServiceUnavailableError("Unable to persist chat state for this request.") from exc
    except ValueError as exc:
        detail = str(exc)
        if "not found" in detail.lower():
            raise NotFoundError(detail) from exc
        raise BadRequestError(detail) from exc
    except AppError:
        raise
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
    except chat_service.ChatEditNotFoundError as exc:
        raise NotFoundError(str(exc)) from exc
    except chat_service.ChatEditValidationError as exc:
        raise BadRequestError(str(exc)) from exc
    except chat_service.ChatPersistenceError as exc:
        raise ServiceUnavailableError("Unable to persist chat state for this request.") from exc
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
