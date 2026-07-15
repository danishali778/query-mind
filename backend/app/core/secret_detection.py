"""Centralized credential detection and redaction.

Patterns intentionally identify credential *shapes* only. Callers must never
log the matched text or persist it for diagnostics.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class SecretFinding:
    category: str
    start: int
    end: int


_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "private_key",
        re.compile(
            r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----[\s\S]*?"
            r"-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
            re.I,
        ),
    ),
    ("bearer_token", re.compile(r"\bBearer\s+[A-Za-z0-9._~+\-/=]{16,}", re.I)),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")),
    ("google_api_key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("openai_api_key", re.compile(r"\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{20,}\b")),
    ("github_token", re.compile(r"\bgh(?:p|o|u|s|r)_[A-Za-z0-9]{30,}\b")),
    ("aws_access_key", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("slack_token", re.compile(r"\bxox(?:b|p|a|r|s)-[A-Za-z0-9-]{20,}\b")),
    ("stripe_key", re.compile(r"\b(?:sk|rk)_(?:live|test)_[A-Za-z0-9]{16,}\b")),
    (
        "assigned_secret",
        re.compile(
            r"(?i)\b(?:api[_-]?key|authorization|access[_-]?token|refresh[_-]?token|"
            r"secret|password)\b\s*[:=]\s*['\"]?[^\s,'\"]{8,}"
        ),
    ),
)


def detect_secret(text: str) -> SecretFinding | None:
    """Return the first high-confidence credential-shaped match."""
    for category, pattern in _PATTERNS:
        match = pattern.search(text)
        if match:
            return SecretFinding(category=category, start=match.start(), end=match.end())
    return None


def redact_secrets(text: str) -> str:
    """Redact every recognized credential without exposing its category."""
    redacted = text
    for _category, pattern in _PATTERNS:
        redacted = pattern.sub("[REDACTED]", redacted)
    return redacted


__all__ = ["SecretFinding", "detect_secret", "redact_secrets"]
