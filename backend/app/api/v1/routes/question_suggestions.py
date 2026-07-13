"""Connection-scoped schema-aware question suggestion routes."""

from fastapi import APIRouter, Query

from app.api.deps import CurrentUserDep
from app.api.v1.schemas.question_suggestions import (
    DismissQuestionSuggestionRequest,
    QuestionSuggestionListResponse,
    RefreshQuestionSuggestionsRequest,
    SuggestionSurface,
)
from app.services import question_suggestion_service


router = APIRouter(
    prefix="/api/database/connections/{connection_id}/question-suggestions",
    tags=["Question Suggestions"],
)


@router.get("", response_model=QuestionSuggestionListResponse)
async def get_question_suggestions(
    connection_id: str,
    current_user: CurrentUserDep,
    surface: SuggestionSurface = Query(default="chat"),
    limit: int | None = Query(default=None, ge=1, le=8),
):
    return await question_suggestion_service.get(
        current_user.id, connection_id, surface, limit
    )


@router.post("/refresh", response_model=QuestionSuggestionListResponse, status_code=202)
async def refresh_question_suggestions(
    connection_id: str,
    request: RefreshQuestionSuggestionsRequest,
    current_user: CurrentUserDep,
    surface: SuggestionSurface = Query(default="chat"),
    limit: int | None = Query(default=None, ge=1, le=8),
):
    return await question_suggestion_service.refresh(
        owner_id=current_user.id,
        connection_id=connection_id,
        surface=surface,
        client_request_id=str(request.client_request_id),
        expected_context_fingerprint=request.expected_context_fingerprint,
        force=request.force,
        limit=limit,
    )


@router.post(
    "/{suggestion_id}/dismiss", response_model=QuestionSuggestionListResponse
)
async def dismiss_question_suggestion(
    connection_id: str,
    suggestion_id: str,
    request: DismissQuestionSuggestionRequest,
    current_user: CurrentUserDep,
    surface: SuggestionSurface = Query(default="chat"),
    limit: int | None = Query(default=None, ge=1, le=8),
):
    return await question_suggestion_service.dismiss(
        owner_id=current_user.id,
        connection_id=connection_id,
        suggestion_id=suggestion_id,
        expected_context_fingerprint=request.expected_context_fingerprint,
        surface=surface,
        limit=limit,
    )


__all__ = ["router"]
