"""Celery execution for durable interactive chat runs."""

from __future__ import annotations

import asyncio
import logging
import threading

from app.core.config import settings
from app.core.errors import AppError
from app.db.repositories import chat_run_repository
from app.services import chat_service
from app.services.chat_progress import AgentRunCancelled, ProgressReporter, cancel_signalled, publish_event
from app.workers.celery_app import celery_app


logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="app.workers.jobs.run_chat_agent.run_chat_agent_task",
    queue=settings.celery_interactive_queue,
    acks_late=True,
    reject_on_worker_lost=True,
)
def run_chat_agent_task(self, run_id: str) -> None:
    run = chat_run_repository.claim_run(run_id)
    if not run:
        return
    progress = ProgressReporter(run_id)
    watcher_stop = threading.Event()

    def _watch_for_cancel() -> None:
        while not watcher_stop.wait(0.25):
            if cancel_signalled(run_id):
                progress.cancellation_token.cancel()
                return

    watcher = threading.Thread(target=_watch_for_cancel, name=f"chat-cancel-{run_id}", daemon=True)
    watcher.start()
    publish_event(run_id, "run.started", "Analyzing your question", stage="preparing")
    try:
        triggering_message = chat_run_repository.get_triggering_user_message(run_id)
        question = triggering_message.content if triggering_message else ""
        result = asyncio.run(
            chat_service.execute_prepared_turn(
                user_id=run.owner_id,
                connection_id=run.connection_id,
                session_id=run.session_id,
                message=question,
                history=None,
                progress=progress,
                run_id=run_id,
            )
        )
        progress.check_cancelled()
        progress.stage_started("saving", "Saving the verified answer")
        updates = {
            "content": result.get("explanation", ""),
            "sql": result.get("sql"),
            "results": {
                "rows": result.get("rows", []),
                "row_count": result.get("row_count", 0),
                "execution_time_ms": result.get("execution_time_ms", 0.0),
                "truncated": result.get("truncated", False),
                "column_metadata": result.get("column_metadata", {}),
            },
            "columns": result.get("columns", []),
            "chart_recommendation": result.get("chart_recommendation"),
            "error": result.get("error"),
            "agent_trace": result.get("trace", []),
            "agent_tier": result.get("tier"),
            "semantic_lineage": result.get("semantic_lineage", []),
            "response_kind": result.get("response_kind", "answer"),
            "clarification_context": result.get("clarification_context"),
            "presentation_kind": result.get("presentation_kind"),
            "answer_metadata": result.get("answer_metadata"),
            "_conversation_memory": result.get("memory_update"),
        }
        if not chat_run_repository.finalize_run(run_id, status="completed", message_updates=updates):
            raise AgentRunCancelled("Cancellation won before final persistence.")
        message = chat_run_repository.get_assistant_message(run_id)
        publish_event(
            run_id,
            "run.completed",
            "Answer ready",
            stage="completed",
            metadata={"message_id": message.id if message else ""},
        )
    except AgentRunCancelled:
        chat_run_repository.finalize_run(
            run_id,
            status="cancelled",
            failure_code="cancelled_by_user",
            failure_message="Response stopped by user.",
            message_updates={"error": "Response stopped by user."},
        )
        publish_event(run_id, "run.cancelled", "Response stopped")
    except AppError as exc:
        logger.warning("Durable chat run %s failed code=%s", run_id, exc.code)
        chat_run_repository.finalize_run(
            run_id,
            status="failed",
            failure_code=exc.code,
            failure_message=exc.message,
            message_updates={"error": exc.message},
        )
        publish_event(run_id, "run.failed", exc.message)
    except Exception:
        logger.exception("Durable chat run %s failed", run_id)
        chat_run_repository.finalize_run(
            run_id,
            status="failed",
            failure_code="agent_run_failed",
            failure_message="AI processing failed for this request.",
            message_updates={"error": "AI processing failed for this request."},
        )
        publish_event(run_id, "run.failed", "Response failed")
    finally:
        watcher_stop.set()
        watcher.join(timeout=1)


__all__ = ["run_chat_agent_task"]
