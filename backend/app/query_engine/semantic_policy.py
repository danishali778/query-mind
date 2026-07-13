"""AI-only SQL policy enforcement derived from verified semantic metadata."""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlglot import exp, parse_one
from sqlglot.errors import ParseError

from app.agents.schema_context.user_semantics import SemanticContext


@dataclass
class SemanticPolicyResult:
    allowed: bool
    reason: str | None = None
    enforced_references: list[str] = field(default_factory=list)


def validate_ai_semantic_policy(sql: str, context: SemanticContext) -> SemanticPolicyResult:
    """Reject AI SQL that violates verified visibility or classification rules."""
    if not (
        context.policy.hidden_tables
        or context.policy.restricted_columns
        or context.policy.sensitive_columns
    ):
        return SemanticPolicyResult(allowed=True)
    try:
        tree = parse_one(sql)
    except ParseError:
        return SemanticPolicyResult(False, "SQL could not be parsed for semantic policy checks.")

    aliases: dict[str, str] = {}
    physical_tables: set[str] = set()
    for table in tree.find_all(exp.Table):
        name = table.name.casefold()
        db = (table.db or "").casefold()
        qualified = f"{db}.{name}" if db else name
        physical_tables.update({name, qualified})
        aliases[(table.alias_or_name or name).casefold()] = qualified
        hidden_reference = _lookup_table(context.policy.hidden_tables, qualified)
        if hidden_reference:
            return SemanticPolicyResult(
                False,
                "AI-generated SQL referenced a table hidden by the semantic policy.",
                [hidden_reference],
            )

    enforced: set[str] = set()
    for column in tree.find_all(exp.Column):
        column_name = column.name.casefold()
        qualifier = (column.table or "").casefold()
        table_name = aliases.get(qualifier, qualifier) if qualifier else ""
        candidate_keys = _candidate_column_keys(table_name, column_name, physical_tables)

        restricted_reference = _lookup_column(context.policy.restricted_columns, candidate_keys)
        if restricted_reference:
            return SemanticPolicyResult(
                False,
                "AI-generated SQL referenced a restricted column.",
                [restricted_reference],
            )

        sensitive_reference = _lookup_column(context.policy.sensitive_columns, candidate_keys)
        if sensitive_reference:
            if column.find_ancestor(exp.AggFunc) is None:
                return SemanticPolicyResult(
                    False,
                    "AI-generated SQL attempted to expose raw sensitive values.",
                    [sensitive_reference],
                )
            enforced.add(sensitive_reference)

    return SemanticPolicyResult(True, enforced_references=sorted(enforced))


def _lookup_table(policies: dict[str, str], table_name: str) -> str | None:
    return policies.get(table_name) or policies.get(table_name.split(".")[-1])


def _candidate_column_keys(
    table_name: str, column_name: str, physical_tables: set[str]
) -> set[str]:
    if table_name:
        return {
            f"{table_name}.{column_name}",
            f"{table_name.split('.')[-1]}.{column_name}",
        }
    return {
        f"{table}.{column_name}"
        for table in physical_tables
    }


def _lookup_column(policies: dict[str, str], keys: set[str]) -> str | None:
    matches = {policies[key] for key in keys if key in policies}
    return next(iter(matches)) if len(matches) == 1 else None


__all__ = ["SemanticPolicyResult", "validate_ai_semantic_policy"]
