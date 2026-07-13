from fastapi import APIRouter, HTTPException, Body
from typing import Optional

from app.api.deps import CurrentUserDep
from app.api.v1.schemas.common import MessageResponse
from app.api.v1.schemas.query_library import (
    FolderSummary,
    FolderCreateResponse,
    LibraryStats,
    PublicTemplatesResponse,
    QueryRunRecord,
    RunSavedQueryResponse,
    SaveQueryRequest,
    SaveQueryResponse,
    SavedQuery,
    ScheduleConfig,
    ScheduleStatusResponse,
    TemplateGenerationResponse,
    UpdateQueryRequest,
)
from app.db.models.query_library import (
    SaveQueryInput,
    ScheduleConfig as DomainScheduleConfig,
    UpdateQueryInput,
)
from app.services import query_library_service as store


router = APIRouter(prefix="/api/library", tags=["Query Library"])


@router.get("/queries", response_model=list[SavedQuery])
async def list_queries(
    current_user: CurrentUserDep,
    folder: Optional[str] = None,
    tag: Optional[str] = None,
    connection_id: Optional[str] = None,
    recently_run: bool = False,
):
    """List saved queries with optional filters."""
    queries = await store.list_queries(
        user_id=current_user.id,
        folder=folder,
        tag=tag,
        connection_id=connection_id,
        recently_run=recently_run
    )
    return [q.model_dump() for q in queries]


@router.post("/queries", response_model=SaveQueryResponse)
async def save_query(req: SaveQueryRequest, current_user: CurrentUserDep):
    """Save a new query to the library. Returns existing query if duplicate SQL found."""
    query, created = await store.save_query(current_user.id, SaveQueryInput(**req.model_dump()))
    return {**query.model_dump(), "created": created}


@router.get("/queries/{query_id}", response_model=SavedQuery)
async def get_query(query_id: str, current_user: CurrentUserDep):
    """Get a single saved query."""
    query = await store.get_query(current_user.id, query_id)
    if not query:
        raise HTTPException(status_code=404, detail="Query not found.")
    return query.model_dump()


@router.put("/queries/{query_id}", response_model=SavedQuery)
async def update_query(query_id: str, req: UpdateQueryRequest, current_user: CurrentUserDep):
    """Update an existing saved query."""
    query = await store.update_query(
        current_user.id,
        query_id,
        UpdateQueryInput(**req.model_dump(exclude_unset=True)),
    )
    if not query:
        raise HTTPException(status_code=404, detail="Query not found.")
    return query.model_dump()


@router.delete("/queries/{query_id}", response_model=MessageResponse)
async def delete_query(query_id: str, current_user: CurrentUserDep):
    """Delete a saved query."""
    success = await store.delete_query(current_user.id, query_id)
    if not success:
        raise HTTPException(status_code=404, detail="Query not found.")
    return {"message": "Query deleted."}


@router.post("/queries/{query_id}/run", response_model=RunSavedQueryResponse)
async def run_query(query_id: str, current_user: CurrentUserDep):
    """Execute a saved query and increment its run count."""
    try:
        result = await store.run_saved_query(current_user.id, query_id, row_limit=500)
    except ValueError as exc:
        detail = str(exc)
        status_code = 400 if "connection_id" in detail else 404
        raise HTTPException(status_code=status_code, detail=detail) from exc

    return {
        "query_id": query_id,
        "success": result.success,
        "columns": result.columns,
        "rows": result.rows,
        "row_count": result.row_count,
        "execution_time_ms": result.execution_time_ms,
        "error": result.error,
        "error_code": result.error_code,
    }


@router.get("/queries/{query_id}/runs", response_model=list[QueryRunRecord])
async def get_run_history(query_id: str, current_user: CurrentUserDep, limit: int = 20):
    """Get run history for a saved query."""
    query = await store.get_query(current_user.id, query_id)
    if not query:
        raise HTTPException(status_code=404, detail="Query not found.")
    runs = await store.get_run_history(current_user.id, query_id, limit=limit)
    return [r.model_dump() for r in runs]


@router.get("/folders", response_model=list[FolderSummary])
async def list_folders(current_user: CurrentUserDep):
    """List all folders with query counts."""
    return await store.list_folders(current_user.id)


@router.post("/folders", status_code=201, response_model=FolderCreateResponse)
async def create_folder(current_user: CurrentUserDep, name: str = Body(..., embed=True)):
    """Create a new (possibly empty) folder."""
    name = name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Folder name is required.")
    await store.create_folder(current_user.id, name)
    return {"name": name}


@router.get("/tags", response_model=list[str])
async def list_tags(current_user: CurrentUserDep):
    """List all unique tags."""
    return await store.list_tags(current_user.id)


@router.get("/stats", response_model=LibraryStats)
async def get_stats(current_user: CurrentUserDep):
    """Get library-wide statistics."""
    return await store.get_stats(current_user.id)


# ── Schedule endpoints ────────────────────────────────

@router.get("/queries/{query_id}/schedule", response_model=ScheduleStatusResponse)
async def get_schedule(query_id: str, current_user: CurrentUserDep):
    """Get the schedule configuration for a saved query."""
    try:
        return await store.get_schedule_status(current_user.id, query_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/queries/{query_id}/schedule", response_model=ScheduleStatusResponse)
async def set_schedule(query_id: str, config: ScheduleConfig, current_user: CurrentUserDep):
    """Create or update the schedule for a saved query."""
    try:
        return await store.set_schedule(current_user.id, query_id, DomainScheduleConfig(**config.model_dump()))
    except ValueError as exc:
        detail = str(exc)
        status_code = 400 if "without a database connection" in detail else 404
        raise HTTPException(status_code=status_code, detail=detail) from exc


# ── Public Library endpoints ──────────────────────────

@router.get("/public", response_model=PublicTemplatesResponse)
async def list_public_templates(current_user: CurrentUserDep, connection_id: Optional[str] = None):
    """Return AI-generated templates for a connection plus generation status."""
    try:
        return await store.get_public_templates(current_user.id, connection_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/public/generate", response_model=TemplateGenerationResponse)
async def trigger_template_generation(connection_id: str, current_user: CurrentUserDep):
    """Manually trigger (or re-trigger) template generation for a connection."""
    try:
        return await store.trigger_template_generation(current_user.id, connection_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/public/{template_id}/clone", response_model=SaveQueryResponse)
async def clone_public_template(template_id: str, current_user: CurrentUserDep, connection_id: Optional[str] = None):
    """Clone an AI-generated template into the user's query library."""
    try:
        query, created = await store.clone_public_template(current_user.id, template_id, connection_id)
    except ValueError as exc:
        detail = str(exc)
        status_code = 404 if "not found" in detail.lower() else 400
        raise HTTPException(status_code=status_code, detail=detail) from exc
    return {**query.model_dump(), "created": created}


@router.delete("/queries/{query_id}/schedule", response_model=ScheduleStatusResponse)
async def remove_schedule(query_id: str, current_user: CurrentUserDep):
    """Remove the schedule from a saved query."""
    try:
        return await store.remove_schedule(current_user.id, query_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
