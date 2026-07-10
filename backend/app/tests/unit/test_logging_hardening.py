import logging
from pathlib import Path

from app.core import logging as app_logging


def test_secret_redaction_filter_scrubs_sensitive_values():
    text = (
        "Authorization: Bearer abc.def.ghi "
        "apikey=super-secret "
        "access_token=token-123 "
        "refresh_token=token-456"
    )

    redacted = app_logging.SecretRedactionFilter.redact_text(text)

    assert "abc.def.ghi" not in redacted
    assert "super-secret" not in redacted
    assert "token-123" not in redacted
    assert "token-456" not in redacted
    assert "[REDACTED]" in redacted


def test_configure_logging_suppresses_noisy_libraries(monkeypatch, tmp_path):
    root_logger = logging.getLogger()
    original_handlers = list(root_logger.handlers)
    original_level = root_logger.level

    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)
        handler.close()

    monkeypatch.setattr(app_logging, "LOG_FILE", str(tmp_path / "runtime.log"))
    monkeypatch.setattr(app_logging, "DEFAULT_LOG_LEVEL", "INFO")

    try:
        app_logging.configure_logging()

        assert logging.getLogger("httpx").level == logging.WARNING
        assert logging.getLogger("httpcore").level == logging.WARNING
        assert logging.getLogger("hpack").level == logging.WARNING
        assert root_logger.level == logging.INFO
    finally:
        for handler in list(root_logger.handlers):
            root_logger.removeHandler(handler)
            handler.close()
        for handler in original_handlers:
            root_logger.addHandler(handler)
        root_logger.setLevel(original_level)


def test_configure_logging_writes_redacted_values_to_file(monkeypatch, tmp_path):
    root_logger = logging.getLogger()
    original_handlers = list(root_logger.handlers)
    original_level = root_logger.level

    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)
        handler.close()

    log_path = tmp_path / "runtime.log"
    monkeypatch.setattr(app_logging, "LOG_FILE", str(log_path))
    monkeypatch.setattr(app_logging, "DEFAULT_LOG_LEVEL", "INFO")

    try:
        app_logging.configure_logging()
        logger = logging.getLogger("test.logging")
        logger.info("Authorization: Bearer very-secret-token apikey=another-secret")

        for handler in root_logger.handlers:
            handler.flush()

        contents = Path(log_path).read_text(encoding="utf-8")
        assert "very-secret-token" not in contents
        assert "another-secret" not in contents
        assert "[REDACTED]" in contents
    finally:
        for handler in list(root_logger.handlers):
            root_logger.removeHandler(handler)
            handler.close()
        for handler in original_handlers:
            root_logger.addHandler(handler)
        root_logger.setLevel(original_level)


def test_quarantine_cap_removes_oldest_logs(monkeypatch, tmp_path):
    monkeypatch.setattr(app_logging, "MAX_QUARANTINED_LOGS", 3)
    log_path = tmp_path / "startup_debug.log"
    for index in range(6):
        stale = tmp_path / f"startup_debug.compromised.2026010100000{index}.log"
        stale.write_text("old run", encoding="utf-8")
    log_path.write_text("previous run", encoding="utf-8")

    app_logging._quarantine_existing_log(log_path)
    app_logging._prune_quarantined_logs(log_path)

    remaining = sorted(tmp_path.glob("startup_debug.compromised.*.log"))
    assert len(remaining) == 3
    assert not log_path.exists()
    # The just-quarantined log (newest timestamp) must survive the prune.
    assert remaining[-1].read_text(encoding="utf-8") == "previous run"


def test_secret_redaction_filter_preserves_numeric_log_args():
    logger = logging.getLogger("test.logging.numeric")
    record = logger.makeRecord(
        name=logger.name,
        level=logging.WARNING,
        fn=__file__,
        lno=1,
        msg="attempt %d/%d failed: %s",
        args=(1, 3, "Authorization: Bearer very-secret-token"),
        exc_info=None,
    )

    accepted = app_logging.SecretRedactionFilter().filter(record)

    assert accepted is True
    assert record.args[0] == 1
    assert record.args[1] == 3
    assert "very-secret-token" not in record.args[2]
    assert "[REDACTED]" in record.args[2]
