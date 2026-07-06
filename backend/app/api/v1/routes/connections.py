import logging

from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)

from app.api.deps import CurrentUserDep
from app.api.v1.schemas.common import StatusMessageResponse
from app.api.v1.schemas.connections import (
    ActiveConnection,
    ConnectionRequest,
    ConnectionResponse,
    JsonErdResponse,
    MermaidErdResponse,
    SchemaResponse,
    TestConnectionRequest,
    TestConnectionResponse,
    UpdateConnectionSettingsRequest,
)
from app.db.models.connection import ConnectionRequest as DomainConnectionRequest
from app.core.errors import AppError, BadRequestError, ServiceUnavailableError
from app.services import connection_service


router = APIRouter(prefix="/api/database", tags=["Database"])


@router.post("/test", response_model=TestConnectionResponse)
async def test_database_connection(config: TestConnectionRequest, current_user: CurrentUserDep):
    """Test a database connection without saving it."""
    request = DomainConnectionRequest(**config.model_dump())
    result = await connection_service.test_connection(current_user.id, request)
    message = result.message if result.success else connection_service.sanitize_connection_error(result.message)
    return TestConnectionResponse(
        success=result.success,
        message=message,
        tables_found=None,
        latency_ms=result.latency_ms,
    )


@router.post("/connect", response_model=ConnectionResponse)
async def connect_database(config: ConnectionRequest, current_user: CurrentUserDep):
    """Connect to a database and save the connection."""
    try:
        domain_request = DomainConnectionRequest(**config.model_dump())
        connection_id, _engine, _latency_ms = await connection_service.connect(current_user.id, domain_request)

        saved_connection = await connection_service.get_connection(current_user.id, connection_id)
        if not saved_connection:
            raise ServiceUnavailableError("Connection was saved but could not be reloaded.")

        response_data = saved_connection.model_dump()
        return ConnectionResponse(
            **response_data,
            message=f"Successfully connected to {domain_request.database}",
        )
    except AppError:
        raise
    except ValueError as exc:
        raise BadRequestError(str(exc)) from exc
    except Exception as exc:
        logger.error("Connection failed for user %s", current_user.id, exc_info=True)
        raise BadRequestError(connection_service.sanitize_connection_error(exc)) from exc


@router.get("/connections", response_model=list[ActiveConnection])
async def list_connections(current_user: CurrentUserDep):
    return await connection_service.get_all_connections(current_user.id)


@router.post("/connections/{connection_id}/test", response_model=TestConnectionResponse)
async def test_saved_database_connection(connection_id: str, current_user: CurrentUserDep):
    result = await connection_service.test_saved_connection(current_user.id, connection_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Connection not found")
    message = result.message if result.success else connection_service.sanitize_connection_error(result.message)
    return TestConnectionResponse(
        success=result.success,
        message=message,
        tables_found=None,
        latency_ms=result.latency_ms,
    )


@router.patch("/connections/{connection_id}", response_model=ActiveConnection)
async def update_connection_settings(
    connection_id: str,
    req: UpdateConnectionSettingsRequest,
    current_user: CurrentUserDep
):
    ok = await connection_service.update_settings(current_user.id, connection_id, req.ssl_mode)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to apply settings.")

    updated = await connection_service.get_connection(current_user.id, connection_id)
    if not updated:
        raise HTTPException(status_code=404, detail="Connection lost after update")
    return updated


@router.delete("/connections/{connection_id}", response_model=StatusMessageResponse)
async def disconnect_database(connection_id: str, current_user: CurrentUserDep):
    success = await connection_service.disconnect(current_user.id, connection_id)
    if not success:
        raise HTTPException(status_code=404, detail="Connection not found")
    return {"message": f"Disconnected {connection_id}", "status": "disconnected"}


def _schema_response(connection_id: str, database: str, tables) -> SchemaResponse:
    return SchemaResponse(
        connection_id=connection_id,
        database=database,
        tables=tables,
    )


@router.get("/connections/{connection_id}/schema", response_model=SchemaResponse)
async def get_database_schema(connection_id: str, current_user: CurrentUserDep):
    """Return the last synced schema snapshot for UI display."""
    try:
        tables = await connection_service.get_connection_schema(current_user.id, connection_id)
        if tables is None:
            raise HTTPException(status_code=404, detail="Connection not found")

        connection = await connection_service.get_connection(current_user.id, connection_id)
        return _schema_response(
            connection_id,
            connection.database if connection else "unknown",
            tables,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Schema load failed for connection %s", connection_id, exc_info=True)
        raise ServiceUnavailableError("Schema could not be loaded for this connection.") from exc


@router.post("/connections/{connection_id}/schema/refresh", response_model=SchemaResponse)
async def refresh_database_schema(connection_id: str, current_user: CurrentUserDep):
    """Force a live schema re-introspection and rebuild the persisted catalog."""
    try:
        tables = await connection_service.refresh_schema(current_user.id, connection_id)
        if tables is None:
            raise HTTPException(status_code=404, detail="Connection not found")

        connection = await connection_service.get_connection(current_user.id, connection_id)
        return _schema_response(
            connection_id,
            connection.database if connection else "unknown",
            tables,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Schema refresh failed for connection %s", connection_id, exc_info=True)
        raise ServiceUnavailableError("Schema refresh failed for this connection.") from exc


@router.get("/connections/{connection_id}/erd/mermaid", response_model=MermaidErdResponse)
async def get_erd_mermaid(connection_id: str, current_user: CurrentUserDep):
    schema = await connection_service.get_cached_schema(current_user.id, connection_id)
    if schema is None:
        raise HTTPException(status_code=404, detail="Connection not found")

    mermaid_text = connection_service.generate_erd_mermaid(schema)
    return {"connection_id": connection_id, "format": "mermaid", "erd": mermaid_text}


@router.get("/connections/{connection_id}/erd/json", response_model=JsonErdResponse)
async def get_erd_json(connection_id: str, current_user: CurrentUserDep):
    schema = await connection_service.get_cached_schema(current_user.id, connection_id)
    if schema is None:
        raise HTTPException(status_code=404, detail="Connection not found")

    erd_data = connection_service.generate_erd_json(schema)
    return {"connection_id": connection_id, "format": "json", **erd_data}
