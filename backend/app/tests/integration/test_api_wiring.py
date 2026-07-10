import os

os.environ.setdefault("ENCRYPTION_KEY", "TZZoA4e_0aRy3zO0u7FzjHwBq2L8y6b9R9oV8XmQ_Jw=")
os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "service-role-key")
os.environ.setdefault("SUPABASE_JWT_SECRET", "jwt-secret")
os.environ.setdefault("GROQ_API_KEY", "groq-test-key")

from app.api.router import api_router
from app.main import app, health_check


def test_health_check_payload_shape():
    payload = health_check()
    assert payload["status"] == "ok"
    assert payload["service"] == "query-mind API"


def test_api_router_contains_expected_prefixes():
    api_paths = {route.path for route in app.routes if route.path.startswith("/api")}
    expected = {
        "/api/health",
        "/api/chat",
        "/api/database/connect",
        "/api/query/execute",
        "/api/dashboard/dashboards",
        "/api/library/queries",
        "/api/settings",
    }
    assert expected.issubset(api_paths)


def test_api_route_count_has_not_collapsed():
    api_route_count = sum(1 for route in app.routes if route.path.startswith("/api"))
    assert api_route_count >= 59


def test_top_level_api_router_is_registered():
    assert api_router is not None
