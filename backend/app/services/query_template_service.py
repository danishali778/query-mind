"""AI query-template workflows."""

from app.db.repositories import template_repository
from app.workers.jobs.generate_library_templates import enqueue_template_generation


def get_generation_status(user_id: str, connection_id: str) -> str:
    state = template_repository.get_generation_state(user_id, connection_id)
    return state.status if state else "not_started"


def list_templates(user_id: str, connection_id: str):
    return template_repository.list_templates(user_id, connection_id)


def get_template(user_id: str, template_id: str):
    return template_repository.get_template(user_id, template_id)


def start_template_generation(user_id: str, connection_id: str, schema_text: str, db_type: str) -> None:
    enqueue_template_generation(connection_id, user_id, schema_text, db_type)


__all__ = [
    "get_generation_status",
    "list_templates",
    "get_template",
    "start_template_generation",
]
