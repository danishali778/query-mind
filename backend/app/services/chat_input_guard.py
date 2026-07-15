"""Pre-persistence validation for chat input."""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from enum import Enum

from app.core.errors import AppError
from app.core.secret_detection import detect_secret
from app.core import chat_guard_metrics


class ChatInputDecision(str, Enum):
    ACCEPT = "accept"
    REJECT_SENSITIVE = "reject_sensitive"
    REJECT_NOISE = "reject_noise"


@dataclass(frozen=True)
class ChatInputGuardResult:
    decision: ChatInputDecision
    reason_code: str
    character_count: int


class ChatInputRejected(AppError):
    pass


_OPAQUE_TOKEN_RE = re.compile(r"^[A-Za-z0-9_+./=-]{24,}$")
_LANGUAGE_WORD_RE = re.compile(r"[A-Za-z]{2,}")


def _entropy(value: str) -> float:
    if not value:
        return 0.0
    counts = Counter(value)
    length = len(value)
    return -sum((count / length) * math.log2(count / length) for count in counts.values())


def _looks_like_noise(value: str, *, expects_identifier: bool) -> bool:
    printable = "".join(ch for ch in value if ch.isprintable()).strip()
    if not printable:
        return True
    if not any(ch.isalnum() for ch in printable):
        return True
    compact = re.sub(r"\s+", "", printable)
    if len(compact) >= 8 and len(set(compact.casefold())) <= 2:
        return True
    if expects_identifier:
        return False
    if _OPAQUE_TOKEN_RE.fullmatch(compact):
        words = _LANGUAGE_WORD_RE.findall(printable)
        has_language_structure = bool(re.search(r"\s", printable)) and len(words) >= 2
        mixed_classes = sum(
            bool(pattern.search(compact))
            for pattern in (re.compile(r"[a-z]"), re.compile(r"[A-Z]"), re.compile(r"\d"), re.compile(r"[_+./=-]"))
        )
        if not has_language_structure and mixed_classes >= 2 and _entropy(compact) >= 3.5:
            return True
    return False


class ChatInputGuard:
    """Reject secrets and obvious noise without echoing submitted content."""

    @staticmethod
    def inspect(message: str, *, expects_identifier: bool = False) -> ChatInputGuardResult:
        if detect_secret(message):
            return ChatInputGuardResult(
                ChatInputDecision.REJECT_SENSITIVE,
                "credential_shape_detected",
                len(message),
            )
        if _looks_like_noise(message, expects_identifier=expects_identifier):
            return ChatInputGuardResult(
                ChatInputDecision.REJECT_NOISE,
                "unintelligible_input",
                len(message),
            )
        return ChatInputGuardResult(ChatInputDecision.ACCEPT, "accepted", len(message))

    @staticmethod
    def enforce_sensitive(message: str) -> None:
        """Run the history-independent secret check before any other service work."""
        finding = detect_secret(message)
        if finding:
            chat_guard_metrics.increment("sensitive_inputs_rejected")
            chat_guard_metrics.increment(f"sensitive_{finding.category}")
            chat_guard_metrics.increment("prevented_llm_calls")
            chat_guard_metrics.increment("prevented_sql_executions")
            raise ChatInputRejected(
                "Remove the credential from your message and rotate it before continuing.",
                code="chat_sensitive_input_detected",
                status_code=422,
            )

    @classmethod
    def enforce(cls, message: str, *, expects_identifier: bool = False) -> ChatInputGuardResult:
        cls.enforce_sensitive(message)
        result = cls.inspect(message, expects_identifier=expects_identifier)
        if result.decision == ChatInputDecision.REJECT_NOISE:
            chat_guard_metrics.increment("noise_inputs_rejected")
            chat_guard_metrics.increment("prevented_llm_calls")
            chat_guard_metrics.increment("prevented_sql_executions")
            raise ChatInputRejected(
                "Enter a database question using a metric, table, or business outcome.",
                code="chat_input_unintelligible",
                status_code=422,
            )
        return result


__all__ = [
    "ChatInputDecision",
    "ChatInputGuard",
    "ChatInputGuardResult",
    "ChatInputRejected",
]
