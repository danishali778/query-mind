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
from app.services import connection_service
from app.services import query_template_service


router = APIRouter(prefix="/api/database", tags=["Database"])


@router.post("/test", response_model=TestConnectionResponse)
async def test_database_connection(config: TestConnectionRequest, current_user: CurrentUserDep):
    """Test a database connection without saving it."""
    request = DomainConnectionRequest(**config.model_dump())
    success, message = await connection_service.test_connection(request)
    return TestConnectionResponse(
        success=success,
        message=message,
        tables_found=None, # test_connection no longer returns count
    )


@router.post("/connect", response_model=ConnectionResponse)
async def connect_database(config: ConnectionRequest, current_user: CurrentUserDep):
    """Connect to a database and save the connection."""
    try:
        domain_request = DomainConnectionRequest(**config.model_dump())
        connection_id, engine = await connection_service.connect(current_user.id, domain_request)
        
        # Get table count
        schema = await connection_service.get_cached_schema(current_user.id, connection_id)
        tables_count = len(schema) if schema else 0
        name = domain_request.name or f"{domain_request.db_type}-{domain_request.database}"
        
        # Trigger background AI template generation
        schema_text = await connection_service.get_schema_for_ai(current_user.id, connection_id)
        if schema_text:
            query_template_service.start_template_generation(connection_id, schema_text, domain_request.db_type)

        return ConnectionResponse(
            id=connection_id,
            name=name,
            db_type=domain_request.db_type,
            database=domain_request.database,
            host=domain_request.host,
            port=domain_request.port,
            status="connected",
            message=f"Successfully connected to {domain_request.database}",
            tables_count=tables_count,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Connection failed: {str(e)}")


@router.get("/connections", response_model=list[ActiveConnection])
async def list_connections(current_user: CurrentUserDep):
    return await connection_service.get_all_connections(current_user.id)


@router.patch("/connections/{connection_id}", response_model=ActiveConnection)
async def update_connection_settings(
    connection_id: str, 
    req: UpdateConnectionSettingsRequest, 
    current_user: CurrentUserDep
):
    ok = await connection_service.update_settings(current_user.id, connection_id, req.ssl_mode, req.readonly)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to apply settings.")
        
    conn_list = await connection_service.get_all_connections(current_user.id)
    updated = next((c for c in conn_list if c.id == connection_id), None)
    if not updated:
        raise HTTPException(status_code=404, detail="Connection lost after update")
    return updated


@router.delete("/connections/{connection_id}", response_model=StatusMessageResponse)
async def disconnect_database(connection_id: str, current_user: CurrentUserDep):
    success = await connection_service.disconnect(current_user.id, connection_id)
    if not success:
        raise HTTPException(status_code=404, detail="Connection not found")
    query_template_service.clear_templates_for_connection(connection_id)
    return {"message": f"Disconnected {connection_id}", "status": "disconnected"}


@router.get("/connections/{connection_id}/schema", response_model=SchemaResponse)
async def get_database_schema(connection_id: str, current_user: CurrentUserDep):
    try:
        tables = await connection_service.refresh_schema(current_user.id, connection_id)
        if tables is None:
            raise HTTPException(status_code=404, detail="Connection not found")
            
        return SchemaResponse(
            connection_id=connection_id,
            database="unknown",
            tables=tables,
        )
    except Exception as e:
        logger.error("Schema inspection failed for connection %s: %s", connection_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Schema inspection failed: {str(e)}")


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
