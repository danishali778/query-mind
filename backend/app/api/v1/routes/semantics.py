"""Connection-scoped semantic definition routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import CurrentUserDep, LlmAccessChecker
from app.api.v1.schemas.common import StatusMessageResponse
from app.api.v1.schemas.semantics import (
    CreateSemanticDefinitionRequest,
    CreateSemanticSuggestionRequest,
    CreateSemanticVersionRequest,
    SemanticDefinitionListResponse,
    SemanticDefinitionResponse,
    SemanticImpactItemResponse,
    SemanticSummaryResponse,
    SemanticSuggestionRunResponse,
    UpdateSemanticDraftRequest,
    ValidateSemanticVersionRequest,
    VerifySemanticVersionRequest,
)
from app.services import semantic_service
from app.services import semantic_suggestion_service


router = APIRouter(
    prefix="/api/database/connections/{connection_id}/semantics",
    tags=["Semantic Definitions"],
)


@router.get("/summary", response_model=SemanticSummaryResponse)
async def get_semantic_summary(connection_id: str, current_user: CurrentUserDep):
    return await semantic_service.summary(current_user.id, connection_id)


@router.post("/suggestions", response_model=SemanticSuggestionRunResponse, status_code=202)
async def create_semantic_suggestions(
    connection_id: str,
    request: CreateSemanticSuggestionRequest,
    current_user: CurrentUserDep,
    _: object = Depends(LlmAccessChecker("semantic_suggestions")),
):
    return await semantic_suggestion_service.start(
        owner_id=current_user.id,
        connection_id=connection_id,
        client_request_id=request.client_request_id,
        requested_kinds=request.requested_kinds,
        business_context=request.business_context,
    )


@router.get("/suggestions/{run_id}", response_model=SemanticSuggestionRunResponse)
async def get_semantic_suggestions(
    connection_id: str, run_id: str, current_user: CurrentUserDep
):
    run = await semantic_suggestion_service.get(current_user.id, connection_id, run_id)
    return semantic_suggestion_service.snapshot(run)


@router.post("/suggestions/{run_id}/cancel", response_model=SemanticSuggestionRunResponse)
async def cancel_semantic_suggestions(
    connection_id: str, run_id: str, current_user: CurrentUserDep
):
    return await semantic_suggestion_service.cancel(current_user.id, connection_id, run_id)


@router.get("/definitions", response_model=SemanticDefinitionListResponse)
async def list_semantic_definitions(
    connection_id: str,
    current_user: CurrentUserDep,
    kind: str | None = Query(default=None),
    status: str | None = Query(default=None),
    validation_status: str | None = Query(default=None),
    search: str | None = Query(default=None, max_length=160),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
):
    return await semantic_service.list_definitions(
        current_user.id,
        connection_id,
        kind=kind,
        status=status,
        validation_status=validation_status,
        search=search,
        page=page,
        page_size=page_size,
    )


@router.post("/definitions", response_model=SemanticDefinitionResponse, status_code=201)
async def create_semantic_definition(
    connection_id: str,
    request: CreateSemanticDefinitionRequest,
    current_user: CurrentUserDep,
):
    return await semantic_service.create_definition(
        current_user.id,
        connection_id,
        kind=request.kind,
        key=request.key,
        display_name=request.display_name,
        description=request.description,
        payload=request.payload,
        change_note=request.change_note,
    )


@router.get("/definitions/{definition_id}", response_model=SemanticDefinitionResponse)
async def get_semantic_definition(
    connection_id: str, definition_id: str, current_user: CurrentUserDep
):
    return await semantic_service.get_definition(current_user.id, connection_id, definition_id)


@router.patch("/definitions/{definition_id}/draft", response_model=SemanticDefinitionResponse)
async def update_semantic_draft(
    connection_id: str,
    definition_id: str,
    request: UpdateSemanticDraftRequest,
    current_user: CurrentUserDep,
):
    return await semantic_service.update_draft(
        current_user.id,
        connection_id,
        definition_id,
        expected_revision=request.expected_draft_revision,
        display_name=request.display_name,
        description=request.description,
        payload=request.payload,
    )


@router.post("/definitions/{definition_id}/versions", response_model=SemanticDefinitionResponse, status_code=201)
async def create_semantic_version(
    connection_id: str,
    definition_id: str,
    request: CreateSemanticVersionRequest,
    current_user: CurrentUserDep,
):
    return await semantic_service.create_version(
        current_user.id,
        connection_id,
        definition_id,
        display_name=request.display_name,
        description=request.description,
        payload=request.payload,
        change_note=request.change_note,
    )


@router.delete("/definitions/{definition_id}/draft", response_model=StatusMessageResponse)
async def delete_semantic_draft(
    connection_id: str, definition_id: str, current_user: CurrentUserDep
):
    await semantic_service.delete_draft(current_user.id, connection_id, definition_id)
    return StatusMessageResponse(status="deleted", message="Semantic draft deleted.")


@router.post(
    "/definitions/{definition_id}/versions/{version}/validate",
    response_model=SemanticDefinitionResponse,
)
async def validate_semantic_version(
    connection_id: str,
    definition_id: str,
    version: int,
    request: ValidateSemanticVersionRequest,
    current_user: CurrentUserDep,
):
    return await semantic_service.validate_version(
        current_user.id,
        connection_id,
        definition_id,
        version,
        run_preview=request.run_preview,
    )


@router.post(
    "/definitions/{definition_id}/versions/{version}/verify",
    response_model=SemanticDefinitionResponse,
)
async def verify_semantic_version(
    connection_id: str,
    definition_id: str,
    version: int,
    request: VerifySemanticVersionRequest,
    current_user: CurrentUserDep,
):
    return await semantic_service.verify_version(
        current_user.id,
        connection_id,
        definition_id,
        version,
        expected_schema_hash=request.expected_schema_hash,
        acknowledged_warning_codes=request.acknowledged_warning_codes,
        change_note=request.change_note,
    )


@router.post(
    "/definitions/{definition_id}/versions/{version}/deprecate",
    response_model=SemanticDefinitionResponse,
)
async def deprecate_semantic_version(
    connection_id: str,
    definition_id: str,
    version: int,
    current_user: CurrentUserDep,
):
    return await semantic_service.deprecate_version(
        current_user.id, connection_id, definition_id, version
    )


@router.get(
    "/definitions/{definition_id}/impact",
    response_model=list[SemanticImpactItemResponse],
)
async def get_semantic_impact(
    connection_id: str, definition_id: str, current_user: CurrentUserDep
):
    return await semantic_service.impact(current_user.id, connection_id, definition_id)


__all__ = ["router"]
