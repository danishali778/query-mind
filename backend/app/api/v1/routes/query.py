from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import CurrentUserDep, RateLimitChecker
from app.api.v1.schemas.query import QueryRequest, QueryResult
from app.core.errors import BadRequestError, NotFoundError
from app.services.query_execution_service import execute_for_connection


router = APIRouter(prefix="/api/query", tags=["Query"])


@router.post("/execute", response_model=QueryResult)
async def execute_sql_query(
    request: QueryRequest, 
    current_user: CurrentUserDep,
    _: object = Depends(RateLimitChecker("query"))
):
    """Execute a read-only SQL query against a connected database."""
    try:
        result = await execute_for_connection(
            current_user.id,
            request.connection_id,
            request.sql,
            row_limit=request.row_limit or 500,
            readonly=True,
        )
        return QueryResult.model_validate(result.model_dump())
    except ValueError as exc:
        detail = str(exc)
        if "not found" in detail.lower():
            raise NotFoundError(detail) from exc
        raise BadRequestError(detail) from exc
