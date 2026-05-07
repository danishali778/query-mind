import logging
import logging.handlers
import os
import re
from datetime import datetime
from pathlib import Path


LOG_FILE = "startup_debug.log"
DEFAULT_LOG_LEVEL = os.getenv("APP_LOG_LEVEL", "INFO").upper()
NOISY_LOGGERS = (
    "httpx",
    "httpcore",
    "hpack",
    "postgrest",
    "supabase",
    "gotrue",
    "realtime",
)

_BEARER_RE = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._\-+/=]+")
_AUTH_HEADER_RE = re.compile(r"(?i)\b(authorization)\b\s*[:=]\s*([^\s,;]+(?:\s+[^\s,;]+)?)")
_APIKEY_RE = re.compile(r"(?i)\b(apikey)\b\s*[:=]\s*([^\s,;]+)")
_TOKEN_VALUE_RE = re.compile(r"(?i)\b(access_token|refresh_token|id_token|service_role_key|anon_key)\b\s*[:=]\s*([^\s,;]+)")


class SecretRedactionFilter(logging.Filter):
    """Redact sensitive header/token values before they reach handlers."""

    @classmethod
    def _redact_value(cls, value):
        if isinstance(value, str):
            return cls.redact_text(value)
        if isinstance(value, bytes):
            return cls.redact_text(value.decode("utf-8", errors="replace"))
        return value

    @staticmethod
    def redact_text(text: str) -> str:
        redacted = _BEARER_RE.sub("Bearer [REDACTED]", text)
        redacted = _AUTH_HEADER_RE.sub(r"\1=[REDACTED]", redacted)
        redacted = _APIKEY_RE.sub(r"\1=[REDACTED]", redacted)
        redacted = _TOKEN_VALUE_RE.sub(r"\1=[REDACTED]", redacted)
        return redacted

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = self.redact_text(str(record.msg))
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: self._redact_value(v) for k, v in record.args.items()}
            else:
                record.args = tuple(self._redact_value(arg) for arg in record.args)
        return True


def _resolve_log_level() -> int:
    return getattr(logging, DEFAULT_LOG_LEVEL, logging.INFO)


def _configure_noisy_loggers() -> None:
    for logger_name in NOISY_LOGGERS:
        noisy_logger = logging.getLogger(logger_name)
        noisy_logger.setLevel(logging.WARNING)


def _quarantine_existing_log(log_path: Path) -> None:
    if not log_path.exists():
        return

    quarantine_name = (
        f"{log_path.stem}.compromised.{datetime.now().strftime('%Y%m%d%H%M%S')}{log_path.suffix}"
    )
    quarantine_path = log_path.with_name(quarantine_name)
    try:
        log_path.rename(quarantine_path)
    except OSError:
        # If the file is locked, fall back to a fresh path instead of crashing startup.
        pass


def _build_file_handler(base_log_path: Path, formatter: logging.Formatter) -> logging.Handler:
    _quarantine_existing_log(base_log_path)

    handler_path = base_log_path
    try:
        handler = logging.handlers.RotatingFileHandler(
            handler_path,
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
    except OSError:
        fallback_name = f"{base_log_path.stem}.{os.getpid()}{base_log_path.suffix}"
        handler_path = base_log_path.with_name(fallback_name)
        handler = logging.handlers.RotatingFileHandler(
            handler_path,
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )

    handler.setLevel(_resolve_log_level())
    handler.setFormatter(formatter)
    handler.addFilter(SecretRedactionFilter())
    return handler


def configure_logging() -> None:
    """Configure process-wide logging once, with safe defaults and redaction."""
    root_logger = logging.getLogger()
    root_logger.setLevel(_resolve_log_level())

    if root_logger.handlers:
        _configure_noisy_loggers()
        return

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = _build_file_handler(Path(LOG_FILE), formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(formatter)
    stream_handler.addFilter(SecretRedactionFilter())

    root_logger.addHandler(file_handler)
    root_logger.addHandler(stream_handler)
    _configure_noisy_loggers()


__all__ = [
    "DEFAULT_LOG_LEVEL",
    "LOG_FILE",
    "NOISY_LOGGERS",
    "SecretRedactionFilter",
    "configure_logging",
]
