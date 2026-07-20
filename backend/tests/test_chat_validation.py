import pytest
from pydantic import ValidationError

from app.api.v1.schemas.chat import (
    CHAT_MESSAGE_MAX_LENGTH,
    EDIT_SQL_MAX_LENGTH,
    ChatRequest,
    EditSqlRequest,
)
from app.services.chat_input_guard import ChatInputDecision, ChatInputGuard


def test_chat_request_strips_valid_message_and_connection_id():
    request = ChatRequest(connection_id=" conn_1 ", session_id=" session_1 ", message="  Show users  ")

    assert request.connection_id == "conn_1"
    assert request.session_id == "session_1"
    assert request.message == "Show users"


def test_chat_request_converts_blank_session_id_to_none():
    request = ChatRequest(connection_id="conn_1", session_id="   ", message="Show users")

    assert request.session_id is None


@pytest.mark.parametrize(
    "payload",
    [
        {"connection_id": "conn_1", "message": ""},
        {"connection_id": "conn_1", "message": "   "},
        {"connection_id": "", "message": "Show users"},
        {"connection_id": "   ", "message": "Show users"},
    ],
)
def test_chat_request_rejects_empty_required_fields(payload):
    with pytest.raises(ValidationError):
        ChatRequest(**payload)


def test_chat_request_rejects_over_limit_message():
    with pytest.raises(ValidationError):
        ChatRequest(connection_id="conn_1", message="x" * (CHAT_MESSAGE_MAX_LENGTH + 1))


def test_edit_sql_request_strips_valid_sql_and_connection_id():
    request = EditSqlRequest(connection_id=" conn_1 ", sql="  SELECT 1  ")

    assert request.connection_id == "conn_1"
    assert request.sql == "SELECT 1"


@pytest.mark.parametrize(
    "payload",
    [
        {"connection_id": "conn_1", "sql": ""},
        {"connection_id": "conn_1", "sql": "   "},
        {"connection_id": "", "sql": "SELECT 1"},
        {"connection_id": "   ", "sql": "SELECT 1"},
    ],
)
def test_edit_sql_request_rejects_empty_required_fields(payload):
    with pytest.raises(ValidationError):
        EditSqlRequest(**payload)


def test_edit_sql_request_rejects_over_limit_sql():
    with pytest.raises(ValidationError):
        EditSqlRequest(connection_id="conn_1", sql="x" * (EDIT_SQL_MAX_LENGTH + 1))


@pytest.mark.parametrize(
    "message",
    [
        "sjsajijjklkammklalkjsldsasan",
        "sjakiuejlajlkjsldlsjslk",
    ],
)
def test_chat_input_guard_rejects_long_alphabetic_keyboard_smash(message):
    assert ChatInputGuard.inspect(message).decision == ChatInputDecision.REJECT_NOISE


@pytest.mark.parametrize("message", ["profitability", "customertransactionhistory", "top customers"])
def test_chat_input_guard_preserves_real_database_language(message):
    assert ChatInputGuard.inspect(message).decision == ChatInputDecision.ACCEPT
