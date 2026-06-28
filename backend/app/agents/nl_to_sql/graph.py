import logging
from typing import Optional, TypedDict

from langgraph.graph import END, StateGraph

from app.agents.nl_to_sql.generator import generate_error_correction, generate_sql
from app.agents.nl_to_sql.prompts import build_conversation_prompt
from app.agents.visualization.generator import generate_visualization_blueprint
from app.query_engine.connection_pool import get_cached_engine
from app.query_engine.executor import execute_query
from app.query_engine.safety import validate_query

logger = logging.getLogger("query-mind.graph")


class ChatState(TypedDict):
    user_id: str
    connection_id: str
    session_id: str
    user_message: str
    schema_context: str
    llm_messages: list[dict]
    explanation: str
    sql: str
    column_metadata: dict
    columns: list[str]
    rows: list[dict]
    row_count: int
    execution_time_ms: float
    error: str
    retry_count: int
    max_retries: int
    chart_recommendation: Optional[dict]
    readonly: bool


def build_context(state: ChatState) -> dict:
    return {}


_DESTRUCTIVE_KEYWORDS = {"delete", "update", "insert", "drop", "truncate", "alter"}


def generate_sql_node(state: ChatState) -> dict:
    explanation, metadata, sql = generate_sql(state["llm_messages"])

    user_msg = state["user_message"].lower()
    if any(keyword in user_msg for keyword in _DESTRUCTIVE_KEYWORDS):
        explanation = (
            "query-mind is read-only. Data modification queries are not supported.\n\n"
            + explanation
        )

    return {
        "explanation": explanation,
        "column_metadata": metadata,
        "sql": sql,
        "error": "" if sql else "LLM did not generate any SQL query.",
    }


def validate_sql_node(state: ChatState) -> dict:
    sql = state["sql"]
    if not sql:
        return {"error": "No SQL query was generated."}

    is_safe, error_msg = validate_query(sql)
    if not is_safe:
        return {"error": error_msg}

    return {"error": ""}


def execute_sql_node(state: ChatState) -> dict:
    engine = get_cached_engine(state["user_id"], state["connection_id"])
    if not engine:
        return {"error": "Database connection not found."}

    result = execute_query(
        state["user_id"],
        engine,
        state["sql"],
        row_limit=500,
        connection_id=state["connection_id"],
        readonly=state.get("readonly", True),
    )

    if result.success:
        logger.info(
            "[execute_sql] Success: %d rows, %d cols",
            result.row_count,
            len(result.columns),
        )
        return {
            "columns": result.columns,
            "rows": result.rows,
            "row_count": result.row_count,
            "execution_time_ms": result.execution_time_ms,
            "error": "",
        }

    logger.warning("[execute_sql] Error: %s", result.error)
    return {"error": result.error or "Query execution failed."}


def analyze_results_node(state: ChatState) -> dict:
    columns = state.get("columns", [])
    rows = state.get("rows", [])

    if not columns or not rows:
        return {"chart_recommendation": None}

    blueprint = generate_visualization_blueprint(
        user_message=state.get("user_message", ""),
        sql=state.get("sql", ""),
        preview_rows=rows[:5],
        column_metadata=state.get("column_metadata", {}),
    )
    return {"chart_recommendation": blueprint}


def handle_error_node(state: ChatState) -> dict:
    explanation, metadata, corrected_sql = generate_error_correction(
        messages=state["llm_messages"],
        sql=state["sql"],
        error=state["error"],
    )
    retry_count = state["retry_count"] + 1
    return {
        "explanation": explanation,
        "column_metadata": metadata,
        "sql": corrected_sql,
        "retry_count": retry_count,
        "error": "" if corrected_sql else "LLM could not generate a corrected query.",
    }


def should_execute_or_retry(state: ChatState) -> str:
    if not state.get("error"):
        return "execute"
    if state["retry_count"] < state["max_retries"]:
        return "retry"
    return "give_up"


def should_finish_or_retry(state: ChatState) -> str:
    if not state.get("error"):
        return "finish"
    if state["retry_count"] < state["max_retries"]:
        return "retry"
    return "give_up"


def build_chat_graph() -> StateGraph:
    graph = StateGraph(ChatState)
    graph.add_node("build_context", build_context)
    graph.add_node("generate_sql", generate_sql_node)
    graph.add_node("validate_sql", validate_sql_node)
    graph.add_node("execute_sql", execute_sql_node)
    graph.add_node("analyze_results", analyze_results_node)
    graph.add_node("handle_error", handle_error_node)

    graph.set_entry_point("build_context")
    graph.add_edge("build_context", "generate_sql")
    graph.add_edge("generate_sql", "validate_sql")
    graph.add_conditional_edges(
        "validate_sql",
        should_execute_or_retry,
        {"execute": "execute_sql", "retry": "handle_error", "give_up": END},
    )
    graph.add_conditional_edges(
        "execute_sql",
        should_finish_or_retry,
        {"finish": "analyze_results", "retry": "handle_error", "give_up": END},
    )
    graph.add_edge("analyze_results", END)
    graph.add_edge("handle_error", "validate_sql")
    return graph.compile()


chat_graph = build_chat_graph()


def run_chat(
    user_id: str,
    connection_id: str,
    session_id: str,
    user_message: str,
    schema_context: str,
    history: list[dict],
    readonly: bool = True,
) -> ChatState:
    llm_messages = build_conversation_prompt(
        schema_context=schema_context,
        history=history,
        user_message=user_message,
    )

    initial_state: ChatState = {
        "user_id": user_id,
        "connection_id": connection_id,
        "session_id": session_id,
        "user_message": user_message,
        "schema_context": schema_context,
        "llm_messages": llm_messages,
        "explanation": "",
        "sql": "",
        "column_metadata": {},
        "columns": [],
        "rows": [],
        "row_count": 0,
        "execution_time_ms": 0.0,
        "error": "",
        "retry_count": 0,
        "max_retries": 3,
        "chart_recommendation": None,
        "readonly": readonly,
    }
    return chat_graph.invoke(initial_state)
