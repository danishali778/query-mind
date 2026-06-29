from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response, status

from app.api.deps import UncheckedUserDep
from app.api.v1.schemas.auth import (
    AuthCredentialsRequest,
    AuthSessionResponse,
    AuthUserResponse,
)
from app.api.v1.schemas.common import StatusMessageResponse
from app.core.supabase_auth import (
    ACCESS_TOKEN_COOKIE_NAME,
    REFRESH_TOKEN_COOKIE_NAME,
    clear_auth_cookies,
    set_auth_cookies,
)
from app.services import auth as auth_service


router = APIRouter(prefix="/api/auth", tags=["Auth"])


def _session_response(result: auth_service.AuthSessionResult) -> AuthSessionResponse:
    user = None
    if result.user_id:
        user = AuthUserResponse(id=result.user_id, email=result.email)
    return AuthSessionResponse(
        authenticated=result.authenticated,
        user=user,
        message=result.message,
    )


def _maybe_set_auth_cookies(response: Response, result: auth_service.AuthSessionResult) -> None:
    if result.access_token and result.refresh_token:
        set_auth_cookies(
            response,
            access_token=result.access_token,
            refresh_token=result.refresh_token,
            expires_in=result.expires_in,
        )


def _request_access_token(request: Request) -> str | None:
    cookie_token = request.cookies.get(ACCESS_TOKEN_COOKIE_NAME)
    if cookie_token:
        return cookie_token

    authorization = request.headers.get("authorization", "")
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None


@router.post("/signup", response_model=AuthSessionResponse)
def signup(payload: AuthCredentialsRequest, response: Response):
    try:
        result = auth_service.signup(payload.email, payload.password)
    except auth_service.AuthServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    _maybe_set_auth_cookies(response, result)
    return _session_response(result)


@router.post("/login", response_model=AuthSessionResponse)
def login(payload: AuthCredentialsRequest, response: Response):
    try:
        result = auth_service.login(payload.email, payload.password)
    except auth_service.AuthServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    _maybe_set_auth_cookies(response, result)
    return _session_response(result)


@router.post("/refresh", response_model=AuthSessionResponse)
def refresh_session(request: Request, response: Response):
    refresh_token = request.cookies.get(REFRESH_TOKEN_COOKIE_NAME)
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No refresh session is available.")

    try:
        result = auth_service.refresh_session(refresh_token)
    except auth_service.AuthServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    _maybe_set_auth_cookies(response, result)
    return _session_response(result)


@router.post("/logout", response_model=StatusMessageResponse)
def logout(request: Request, response: Response):
    auth_service.logout(_request_access_token(request))
    clear_auth_cookies(response)
    return {"message": "Signed out.", "status": "signed_out"}


@router.get("/session", response_model=AuthSessionResponse)
def get_session(current_user: UncheckedUserDep):
    result = auth_service.build_active_session(current_user.id, current_user.email)
    return _session_response(result)


__all__ = ["router"]
