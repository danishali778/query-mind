"""Thread-safe cancellation token for blocking database execution."""

from __future__ import annotations

import threading


class AgentRunCancelled(RuntimeError):
    pass


class QueryCancellationToken:
    def __init__(self) -> None:
        self._cancelled = threading.Event()
        self._lock = threading.Lock()
        self._driver_connection = None

    @property
    def cancelled(self) -> bool:
        return self._cancelled.is_set()

    def register(self, sqlalchemy_connection) -> None:
        driver = getattr(getattr(sqlalchemy_connection, "connection", None), "driver_connection", None)
        with self._lock:
            self._driver_connection = driver
            already_cancelled = self._cancelled.is_set()
        if already_cancelled:
            self._cancel_driver(driver)

    def unregister(self) -> None:
        with self._lock:
            self._driver_connection = None

    def cancel(self) -> None:
        self._cancelled.set()
        with self._lock:
            driver = self._driver_connection
        self._cancel_driver(driver)

    @staticmethod
    def _cancel_driver(driver) -> None:
        cancel = getattr(driver, "cancel", None)
        if callable(cancel):
            try:
                cancel()
            except Exception:
                pass


__all__ = ["AgentRunCancelled", "QueryCancellationToken"]
