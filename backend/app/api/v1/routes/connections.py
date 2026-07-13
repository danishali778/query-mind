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
    RotateConnectionCredentialsRequest,
    ConnectionScopePayload,
    ConnectionScopeResponse,
    ConnectionScopePreviewResponse,
    UpdateConnectionScopeRequest,
    ConnectionAutomationResponse,
    UpdateConnectionAutomationRequest,
    ConnectionHealthHistoryResponse,
    UpdateConnectionSettingsRequest,
)
from app.core.errors import AppError, BadRequestError, ServiceUnavailableError
from app.services import connection_service
from app.services import connection_experience_service
from app.services.connection_input import normalize_connection_input


router = APIRouter(prefix="/api/database", tags=["Database"])


@router.post("/test", response_model=TestConnectionResponse)
async def test_database_connection(config: TestConnectionRequest, current_user: CurrentUserDep):
    """Test a database connection without saving it."""
    request = normalize_connection_input(config.model_dump(exclude_unset=True))
    result = await connection_service.test_connection(current_user.id, request)
    return TestConnectionResponse.model_validate(result.model_dump())


@router.post("/connect", response_model=ConnectionResponse)
async def connect_database(config: ConnectionRequest, current_user: CurrentUserDep):
    """Connect to a database and save the connection."""
    try:
        domain_request = normalize_connection_input(config.model_dump(exclude_unset=True))
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
        logger.info("Connection failed for user %s type=%s", current_user.id, exc.__class__.__name__)
        raise BadRequestError(connection_service.sanitize_connection_error(exc)) from exc


@router.get("/connections", response_model=list[ActiveConnection])
async def list_connections(current_user: CurrentUserDep):
    return await connection_service.get_all_connections(current_user.id)


@router.post("/connections/{connection_id}/test", response_model=TestConnectionResponse)
async def test_saved_database_connection(connection_id: str, current_user: CurrentUserDep):
    result = await connection_service.test_saved_connection(current_user.id, connection_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Connection not found")
    return TestConnectionResponse.model_validate(result.model_dump())


@router.patch("/connections/{connection_id}/credentials", response_model=ActiveConnection)
async def rotate_connection_credentials(
    connection_id: str,
    req: RotateConnectionCredentialsRequest,
    current_user: CurrentUserDep,
):
    payload = req.model_dump(exclude={"expected_credential_revision"}, exclude_unset=True)
    return await connection_experience_service.rotate_credentials(
        current_user.id,
        connection_id,
        expected_revision=req.expected_credential_revision,
        changes=payload,
    )


@router.get("/connections/{connection_id}/scope", response_model=ConnectionScopeResponse)
async def get_connection_scope(connection_id: str, current_user: CurrentUserDep):
    return await connection_experience_service.get_scope(current_user.id, connection_id)


@router.post("/connections/{connection_id}/scope/discover")
async def discover_connection_scope(connection_id: str, current_user: CurrentUserDep):
    return await connection_experience_service.discover_scope(current_user.id, connection_id)


@router.post(
    "/connections/{connection_id}/scope/preview",
    response_model=ConnectionScopePreviewResponse,
)
async def preview_connection_scope(
    connection_id: str,
    req: ConnectionScopePayload,
    current_user: CurrentUserDep,
):
    return await connection_experience_service.preview_scope(
        current_user.id, connection_id, req.model_dump()
    )


@router.put("/connections/{connection_id}/scope", response_model=ConnectionScopeResponse)
async def update_connection_scope(
    connection_id: str,
    req: UpdateConnectionScopeRequest,
    current_user: CurrentUserDep,
):
    return await connection_experience_service.apply_scope(
        current_user.id,
        connection_id,
        expected_revision=req.expected_scope_revision,
        payload=req.model_dump(exclude={"expected_scope_revision", "acknowledged_impact_codes"}),
        acknowledged_codes=req.acknowledged_impact_codes,
    )


@router.get("/connections/{connection_id}/automation", response_model=ConnectionAutomationResponse)
async def get_connection_automation(connection_id: str, current_user: CurrentUserDep):
    return await connection_experience_service.get_automation(current_user.id, connection_id)


@router.patch("/connections/{connection_id}/automation", response_model=ConnectionAutomationResponse)
async def update_connection_automation(
    connection_id: str,
    req: UpdateConnectionAutomationRequest,
    current_user: CurrentUserDep,
):
    return await connection_experience_service.update_automation(
        current_user.id, connection_id, req.model_dump()
    )


@router.get("/connections/{connection_id}/health", response_model=ConnectionHealthHistoryResponse)
async def get_connection_health_history(
    connection_id: str,
    current_user: CurrentUserDep,
    cursor: str | None = None,
    limit: int = 25,
):
    return await connection_experience_service.health_history(
        current_user.id, connection_id, cursor=cursor, limit=limit
    )


@router.patch("/connections/{connection_id}", response_model=ActiveConnection)
async def update_connection_settings(
    connection_id: str,
    req: UpdateConnectionSettingsRequest,
    current_user: CurrentUserDep
):
    current = await connection_service.get_connection(current_user.id, connection_id)
    if not current:
        raise HTTPException(status_code=404, detail="Connection not found")
    if req.ssl_mode is None or req.ssl_mode == current.ssl_mode:
        return current
    return await connection_experience_service.rotate_credentials(
        current_user.id,
        connection_id,
        expected_revision=current.credential_revision,
        changes={"ssl_mode": req.ssl_mode},
    )


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
        logger.info("Schema load failed for connection %s type=%s", connection_id, exc.__class__.__name__)
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
        logger.info("Schema refresh failed for connection %s type=%s", connection_id, exc.__class__.__name__)
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
