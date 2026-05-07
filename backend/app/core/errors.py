"""Canonical error handling registration."""

import logging
import uuid
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


logger = logging.getLogger(__name__)


class AppError(Exception):
    """Application-level error with a stable API-facing shape."""

    def __init__(
        self,
        message: str,
        *,
        code: str,
        status_code: int,
        details: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details


class NotFoundError(AppError):
    def __init__(self, message: str = "Resource not found.") -> None:
        super().__init__(message, code="not_found", status_code=status.HTTP_404_NOT_FOUND)


class BadRequestError(AppError):
    def __init__(self, message: str = "Invalid request.") -> None:
        super().__init__(message, code="bad_request", status_code=status.HTTP_400_BAD_REQUEST)


class ServiceUnavailableError(AppError):
    def __init__(self, message: str = "Service temporarily unavailable.") -> None:
        super().__init__(
            message,
            code="service_unavailable",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


def _normalize_http_detail(detail: object) -> tuple[str, list[dict] | None]:
    if isinstance(detail, dict):
        message = str(detail.get("message") or detail.get("detail") or "Request failed.")
        details = detail.get("details")
        return message, details if isinstance(details, list) else None
    if isinstance(detail, list):
        return "Request failed.", detail if all(isinstance(item, dict) for item in detail) else None
    if isinstance(detail, str):
        return detail, None
    return "Request failed.", None


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_exception_handler(_: Request, exc: AppError):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                }
            },
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_: Request, exc: HTTPException):
        message, details = _normalize_http_detail(exc.detail)
        code = f"http_{exc.status_code}"
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": code,
                    "message": message,
                    "details": details,
                }
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(_: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "Request validation failed.",
                    "details": exc.errors(),
                }
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        correlation_id = str(uuid.uuid4())
        logger.exception(
            "Unhandled exception [correlation_id=%s] on %s %s",
            correlation_id,
            request.method,
            request.url.path,
            exc_info=exc,
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "internal_server_error",
                    "message": "An unexpected error occurred. Please contact support if this persists.",
                    "correlation_id": correlation_id,
                }
            },
        )


__all__ = [
    "AppError",
    "BadRequestError",
    "NotFoundError",
    "ServiceUnavailableError",
    "register_exception_handlers",
]
