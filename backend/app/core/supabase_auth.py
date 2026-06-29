from __future__ import annotations

from fastapi import Response

from app.core.config import settings


ACCESS_TOKEN_COOKIE_NAME = "qm_access_token"
REFRESH_TOKEN_COOKIE_NAME = "qm_refresh_token"
DEFAULT_ACCESS_TOKEN_MAX_AGE = 3600
DEFAULT_REFRESH_TOKEN_MAX_AGE = 60 * 60 * 24 * 30


def supabase_auth_base_url() -> str:
    return settings.require("supabase_url").rstrip("/")


def supabase_signup_url() -> str:
    return f"{supabase_auth_base_url()}/auth/v1/signup"


def supabase_password_login_url() -> str:
    return f"{supabase_auth_base_url()}/auth/v1/token?grant_type=password"


def supabase_refresh_url() -> str:
    return f"{supabase_auth_base_url()}/auth/v1/token?grant_type=refresh_token"


def supabase_logout_url() -> str:
    return f"{supabase_auth_base_url()}/auth/v1/logout"


def supabase_public_headers() -> dict[str, str]:
    return {
        "apikey": settings.require("supabase_anon_key"),
        "Content-Type": "application/json",
    }


def supabase_auth_headers(access_token: str | None = None) -> dict[str, str]:
    headers = supabase_public_headers()
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    return headers


def auth_cookie_settings() -> dict[str, object]:
    cookie_settings: dict[str, object] = {
        "httponly": True,
        "secure": settings.resolved_auth_cookie_secure,
        "samesite": settings.auth_cookie_samesite.lower(),
        "path": "/",
    }
    if settings.auth_cookie_domain:
        cookie_settings["domain"] = settings.auth_cookie_domain
    return cookie_settings


def set_auth_cookies(
    response: Response,
    *,
    access_token: str,
    refresh_token: str,
    expires_in: int | None = None,
) -> None:
    cookie_kwargs = auth_cookie_settings()
    response.set_cookie(
        ACCESS_TOKEN_COOKIE_NAME,
        access_token,
        max_age=expires_in or DEFAULT_ACCESS_TOKEN_MAX_AGE,
        **cookie_kwargs,
    )
    response.set_cookie(
        REFRESH_TOKEN_COOKIE_NAME,
        refresh_token,
        max_age=DEFAULT_REFRESH_TOKEN_MAX_AGE,
        **cookie_kwargs,
    )


def clear_auth_cookies(response: Response) -> None:
    cookie_kwargs = auth_cookie_settings()
    response.delete_cookie(ACCESS_TOKEN_COOKIE_NAME, **cookie_kwargs)
    response.delete_cookie(REFRESH_TOKEN_COOKIE_NAME, **cookie_kwargs)


__all__ = [
    "ACCESS_TOKEN_COOKIE_NAME",
    "REFRESH_TOKEN_COOKIE_NAME",
    "DEFAULT_ACCESS_TOKEN_MAX_AGE",
    "DEFAULT_REFRESH_TOKEN_MAX_AGE",
    "supabase_signup_url",
    "supabase_password_login_url",
    "supabase_refresh_url",
    "supabase_logout_url",
    "supabase_public_headers",
    "supabase_auth_headers",
    "auth_cookie_settings",
    "set_auth_cookies",
    "clear_auth_cookies",
]
