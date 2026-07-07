from collections.abc import Iterable

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


def configure_cors(app: FastAPI, origins: Iterable[str]) -> list[str]:
    normalized = list(origins)
    if "*" in normalized:
        raise RuntimeError(
            "Security configuration error: ALLOWED_ORIGINS cannot contain '*' "
            "when allow_credentials=True."
        )

    for local_origin in [
        "http://localhost:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ]:
        if local_origin not in normalized:
            normalized.append(local_origin)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=normalized,
        allow_headers=["*"],
        allow_methods=["*"],
        allow_credentials=True,
    )
    return normalized


__all__ = ["configure_cors"]
