import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from app.agents.db_agent.output import ChatAgentOutcome, parse_agent_outcome
from app.agents.db_agent.trace import TraceRecorder
from app.agents.schema_context.scoring import score_tables
from app.agents.schema_context.types import CatalogColumn, CatalogTable, SchemaCatalog
from app.agents.schema_context.user_semantics import SemanticContext, SemanticContextEntry
from app.core.secret_detection import detect_secret, redact_secrets
from app.services import chat_run_service
from app.services.chat_input_guard import ChatInputDecision, ChatInputGuard, ChatInputRejected
from app.services.question_intent_service import (
    analyze_question_intent,
    bounded_follow_up_history,
    explicit_follow_up,
)


def _catalog() -> SchemaCatalog:
    return SchemaCatalog(
        connection_id="connection-1",
        db_type="postgresql",
        schema_hash="schema-1",
        captured_at="2026-07-15T00:00:00Z",
        tables=[
            CatalogTable(
                name="orders",
                importance_score=1.0,
                columns=[
                    CatalogColumn(name="customer_id", type="uuid"),
                    CatalogColumn(name="created_at", type="timestamp", semantic_type="datetime"),
                ],
            ),
            CatalogTable(
                name="payments",
                importance_score=1.0,
                columns=[CatalogColumn(name="amount", type="numeric", semantic_type="currency")],
            ),
        ],
    )


@pytest.mark.parametrize(
    ("category", "value"),
    [
        ("google_api_key", "AIza" + "A1_b" * 8 + "XYZ"),
        ("openai_api_key", "sk-proj-" + "aB3_" * 8),
        ("github_token", "ghp_" + "A1" * 20),
        ("aws_access_key", "AKIA" + "A1B2" * 4),
        ("slack_token", "xoxb-" + "1234567890-" * 3),
        ("stripe_key", "sk_live_" + "Ab12" * 6),
        ("jwt", "eyJ" + "a" * 10 + "." + "b" * 10 + "." + "c" * 10),
        ("bearer_token", "Bearer " + "opaque-token-value-123456"),
        ("private_key", "-----BEGIN PRIVATE KEY-----\nsynthetic\n-----END PRIVATE KEY-----"),
        ("assigned_secret", "api_key=synthetic-secret-value"),
    ],
)
def test_synthetic_credential_shapes_are_rejected_and_redacted(category, value):
    finding = detect_secret(value)
    assert finding is not None
    assert finding.category == category
    with pytest.raises(ChatInputRejected) as exc_info:
        ChatInputGuard.enforce(value)
    assert exc_info.value.code == "chat_sensitive_input_detected"
    assert value not in exc_info.value.message
    assert value not in redact_secrets(value)


def test_noise_guard_rejects_opaque_and_punctuation_but_preserves_short_questions():
    assert ChatInputGuard.inspect("!?!?!!!").decision == ChatInputDecision.REJECT_NOISE
    assert ChatInputGuard.inspect("Z9f_xQ2mP7vL4kN8sR1tW6yB3cD0").decision == ChatInputDecision.REJECT_NOISE
    assert ChatInputGuard.inspect("orders?").decision == ChatInputDecision.ACCEPT
    assert ChatInputGuard.inspect("MRR").decision == ChatInputDecision.ACCEPT
    assert ChatInputGuard.inspect("top customers").decision == ChatInputDecision.ACCEPT


def test_secret_guard_runs_before_durable_persistence(monkeypatch):
    repository_call = AsyncMock()
    monkeypatch.setattr(chat_run_service.chat_run_repository, "get_run_by_client_request", repository_call)
    request = SimpleNamespace(
        message="AIza" + "Z9_x" * 8 + "XYZ",
        connection_id="connection-1",
        session_id=None,
        client_request_id="00000000-0000-0000-0000-000000000001",
    )

    with pytest.raises(ChatInputRejected):
        asyncio.run(chat_run_service.start_run("user-1", request))

    repository_call.assert_not_awaited()


def test_catalog_grounding_never_makes_the_user_facing_decision():
    ambiguous = analyze_question_intent(
        "Please help me with this thing",
        catalog=_catalog(),
        semantic_context=None,
        history=[],
    )
    assert ambiguous.decision == "analyze"
    assert ambiguous.reason_code == "agent_decision_required"
    assert ambiguous.matched_tables == []

    analytical = analyze_question_intent(
        "top orders by customer",
        catalog=_catalog(),
        semantic_context=None,
        history=[],
    )
    assert analytical.decision == "analyze"
    assert "orders" in analytical.matched_tables

    substring_only = analyze_question_intent(
        "identify something useful",
        catalog=_catalog(),
        semantic_context=None,
        history=[],
    )
    assert substring_only.decision == "analyze"
    assert substring_only.reason_code == "agent_decision_required"


def test_semantic_description_overlap_does_not_create_analytical_intent():
    context = SemanticContext(
        schema_hash="schema-1",
        definitions=[
            SemanticContextEntry(
                definition_id="definition-1",
                version_id="version-1",
                reference="sem_metric_revenue_v1",
                kind="metric",
                key="revenue",
                display_name="Revenue",
                description="Use this helpful metric for finance reporting.",
                version=1,
                payload={"required_tables": ["payments"]},
            )
        ],
    )

    ambiguous = analyze_question_intent(
        "Can you be helpful?",
        catalog=_catalog(),
        semantic_context=context,
        history=[],
    )
    assert ambiguous.decision == "analyze"
    assert ambiguous.matched_semantic_refs == []

    explicit = analyze_question_intent(
        "Show revenue",
        catalog=_catalog(),
        semantic_context=context,
        history=[],
    )
    assert explicit.decision == "analyze"
    assert explicit.matched_semantic_refs == ["sem_metric_revenue_v1"]
    assert explicit.matched_tables == ["payments"]


def test_bounded_history_keeps_latest_three_completed_pairs_with_metadata():
    history = []
    for index in range(5):
        user_id = f"u-{index}"
        history.extend(
            [
                {"id": user_id, "role": "user", "content": f"question {index}"},
                {
                    "id": f"a-{index}",
                    "role": "assistant",
                    "parent_id": user_id,
                    "content": f"answer {index}",
                    "sql": "SELECT 1",
                    "error": None,
                    "run_status": "completed",
                    "response_kind": "answer",
                    "answer_metadata": {
                        "method": "bounded method",
                        "evidence": [{"claim": f"evidence {index}"}],
                        "limitations": [],
                    },
                },
            ]
        )
    history.append({"id": "placeholder", "role": "assistant", "content": "", "run_status": "running"})

    assert explicit_follow_up("Show orders", history) is False
    assert bounded_follow_up_history(history, include=False) == []
    assert explicit_follow_up("What about last month?", history) is True
    bounded = bounded_follow_up_history(history, include=True)
    assert len(bounded) == 6
    assert bounded[0]["content"] == "question 2"
    assert "Method: bounded method" in bounded[1]["content"]
    assert "Evidence: evidence 2" in bounded[1]["content"]


def test_zero_overlap_schema_search_ignores_table_importance():
    assert score_tables("completely unrelated prose", _catalog()) == []


def test_agent_outcome_contract_distinguishes_analysis_and_clarification():
    analysis = ChatAgentOutcome(
        response_type="data_analysis",
        answer="Customer one has the most orders.",
        result_ref="result_1",
        presentation={"kind": "table", "chart": None},
        evidence=[{
            "claim": "Customer one is first.",
            "result_ref": "result_1",
            "columns": ["customer_id", "order_count"],
            "row_indexes": [0],
        }],
        relevant_tables=["orders"],
        relevant_columns=["orders.customer_id"],
    )
    assert analysis.response_type == "data_analysis"

    clarification = ChatAgentOutcome(
        response_type="clarification",
        answer="Which metric should I analyze?",
        clarification_context={
            "reason_code": "missing_metric",
            "expected_input": "metric",
        },
        presentation={"kind": "none", "chart": None},
    )
    assert clarification.result_ref is None

    with pytest.raises(ValidationError):
        ChatAgentOutcome(
            response_type="clarification",
            answer="Which metric?",
            clarification_context={"reason_code": "missing_metric", "expected_input": "metric"},
            result_ref="result_1",
        )
    with pytest.raises(Exception):
        parse_agent_outcome(json.dumps({**analysis.model_dump(), "unknown": True}))

    with pytest.raises(ValidationError):
        ChatAgentOutcome(
            response_type="direct_answer",
            answer="Unsafe generated answer sk-proj-" + "Ab3_" * 8,
        )


def test_trace_recorder_redacts_credentials_before_persistence():
    synthetic = "sk-proj-" + "Ab3_" * 8
    trace = TraceRecorder()
    trace.record("note", synthetic, 1, "ok", output_summary=f"value={synthetic}")
    serialized = json.dumps(trace.to_list())
    assert synthetic not in serialized
    assert "[REDACTED]" in serialized


def test_private_key_redaction_removes_the_complete_block():
    value = "-----BEGIN PRIVATE KEY-----\nsynthetic-private-material\n-----END PRIVATE KEY-----"
    redacted = redact_secrets(value)
    assert "synthetic-private-material" not in redacted
    assert redacted == "[REDACTED]"
