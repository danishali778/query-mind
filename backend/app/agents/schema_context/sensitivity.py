"""Sensitive column detection and safe sample filtering."""

import re

SENSITIVE_NAME_PATTERNS = (
    r"email",
    r"phone",
    r"mobile",
    r"address",
    r"token",
    r"secret",
    r"password",
    r"passwd",
    r"ssn",
    r"iban",
    r"card",
    r"dob",
    r"birth",
    r"salary",
    r"api_key",
    r"auth_key",
)

# Match whole tokens or suffixes like customer_name, first_name
_SENSITIVE_RE = re.compile(
    r"(?:^|_)(?:" + "|".join(SENSITIVE_NAME_PATTERNS) + r")(?:$|_)",
    re.IGNORECASE,
)


def is_sensitive_column(name: str, semantic_type: str) -> bool:
    """Return True if column should not expose sample values."""
    if semantic_type in {"email", "phone", "name", "address", "free_text"}:
        return True
    if _SENSITIVE_RE.search(name):
        return True
    if semantic_type == "identifier" and any(
        token in name.lower() for token in ("uuid", "guid", "token", "hash")
    ):
        return True
    return False


def filter_sample_values(
    name: str,
    semantic_type: str,
    sample_values: list[str],
    *,
    max_values: int = 15,
) -> tuple[list[str], bool]:
    """
    Filter sample values for catalog storage.

    Returns (filtered_values, is_sensitive).
    """
    if is_sensitive_column(name, semantic_type):
        return [], True
    if not sample_values:
        return [], False
    if len(sample_values) > max_values:
        return [], False
    return sample_values[:max_values], False


__all__ = ["SENSITIVE_NAME_PATTERNS", "is_sensitive_column", "filter_sample_values"]
