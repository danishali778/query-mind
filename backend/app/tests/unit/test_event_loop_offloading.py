"""Behavioral checks for blocking work at async service boundaries."""

import asyncio
import threading
from types import SimpleNamespace

from app.services import billing_service, dashboard_service


def test_dashboard_insight_runs_llm_off_event_loop(monkeypatch):
    loop_thread = threading.get_ident()
    worker_threads: list[int] = []

    async def fake_get_widget(_user_id, _widget_id):
        return SimpleNamespace(
            title="Revenue",
            viz_type="bar",
            rows=[{"value": 10}],
            dashboard_id="dashboard-1",
        )

    async def fake_get_dashboard(_user_id, _dashboard_id):
        return SimpleNamespace(filters={})

    def fake_generate(*_args):
        worker_threads.append(threading.get_ident())
        return "insight"

    monkeypatch.setattr(dashboard_service, "get_widget", fake_get_widget)
    monkeypatch.setattr(dashboard_service, "get_dashboard", fake_get_dashboard)
    monkeypatch.setattr(dashboard_service, "generate_widget_insight", fake_generate)

    result = asyncio.run(dashboard_service.build_widget_insight("user-1", "widget-1"))

    assert result == "insight"
    assert worker_threads and worker_threads[0] != loop_thread


def test_async_billing_upgrade_runs_off_event_loop(monkeypatch):
    loop_thread = threading.get_ident()
    worker_threads: list[int] = []

    def fake_upgrade(user_id):
        worker_threads.append(threading.get_ident())
        return SimpleNamespace(owner_id=user_id)

    monkeypatch.setattr(billing_service, "upgrade_to_pro", fake_upgrade)

    result = asyncio.run(billing_service.upgrade_to_pro_async("user-1"))

    assert result.owner_id == "user-1"
    assert worker_threads and worker_threads[0] != loop_thread


def test_connection_release_runs_off_event_loop(monkeypatch):
    from app.db import connection_manager

    loop_thread = threading.get_ident()
    worker_threads: list[int] = []

    def fake_release(_user_id, _connection_id):
        worker_threads.append(threading.get_ident())

    async def fake_delete(_user_id, _connection_id):
        return True

    monkeypatch.setattr(connection_manager.connection_pool, "release_connection", fake_release)
    monkeypatch.setattr(connection_manager.connection_repository, "delete_connection", fake_delete)

    result = asyncio.run(connection_manager.disconnect("user-1", "connection-1"))

    assert result is True
    assert worker_threads and worker_threads[0] != loop_thread
