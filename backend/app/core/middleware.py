from collections.abc import Iterable
from urllib.parse import urlparse

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.core.supabase_auth import ACCESS_TOKEN_COOKIE_NAME, REFRESH_TOKEN_COOKIE_NAME


_UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
_LOCAL_ORIGINS = {
    "http://localhost:5173",
    "http://127.0.0.1:5174",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
}


class CookieOriginMiddleware(BaseHTTPMiddleware):
    """Require an allow-listed Origin for unsafe cookie-authenticated requests."""

    def __init__(self, app, *, allowed_origins: set[str]) -> None:
        super().__init__(app)
        self.allowed_origins = allowed_origins

    async def dispatch(self, request: Request, call_next):
        has_auth_cookie = any(
            request.cookies.get(cookie_name)
            for cookie_name in (ACCESS_TOKEN_COOKIE_NAME, REFRESH_TOKEN_COOKIE_NAME)
        )
        if request.method in _UNSAFE_METHODS and has_auth_cookie:
            origin = request.headers.get("origin")
            if origin not in self.allowed_origins:
                return JSONResponse(
                    status_code=403,
                    content={
                        "error": {
                            "code": "csrf_origin_invalid",
                            "message": "Cookie-authenticated requests require an allowed Origin.",
                            "details": None,
                        }
                    },
                )
        return await call_next(request)


def _validate_production_origins(origins: list[str]) -> None:
    if not origins:
        raise RuntimeError("ALLOWED_ORIGINS must contain at least one HTTPS origin in production.")
    for origin in origins:
        parsed = urlparse(origin)
        if origin == "*" or parsed.scheme != "https" or not parsed.hostname:
            raise RuntimeError("ALLOWED_ORIGINS must contain only explicit HTTPS origins in production.")
        if parsed.hostname.lower() == "localhost" or parsed.hostname.startswith("127."):
            raise RuntimeError("ALLOWED_ORIGINS cannot include loopback origins in production.")


def configure_cors(
    app: FastAPI,
    origins: Iterable[str],
    *,
    is_production: bool | None = None,
) -> list[str]:
    production = settings.is_production if is_production is None else is_production
    normalized = list(dict.fromkeys(origin.rstrip("/") for origin in origins if origin.strip()))
    if "*" in normalized:
        raise RuntimeError(
            "Security configuration error: ALLOWED_ORIGINS cannot contain '*' when allow_credentials=True."
        )
    if production:
        _validate_production_origins(normalized)
    else:
        normalized = list(dict.fromkeys([*normalized, *_LOCAL_ORIGINS]))

    app.add_middleware(CookieOriginMiddleware, allowed_origins=set(normalized))
    app.add_middleware(
        CORSMiddleware,
        allow_origins=normalized,
        allow_headers=["*"],
        allow_methods=["*"],
        allow_credentials=True,
    )
    return normalized


__all__ = ["CookieOriginMiddleware", "configure_cors"]
