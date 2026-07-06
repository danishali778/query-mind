"""Keyword scoring for search_schema tool."""

from __future__ import annotations

import re

from app.agents.schema_context.types import SchemaCatalog, ScoredTable

DEFAULT_SYNONYMS: dict[str, list[str]] = {
    "revenue": ["sales", "income", "gross", "paid", "amount", "payment"],
    "customer": ["client", "buyer", "account", "user"],
    "user": ["member", "account", "profile"],
    "order": ["purchase", "transaction", "sale"],
    "product": ["item", "sku", "goods"],
    "date": ["time", "created", "timestamp", "month", "week", "year"],
    "churn": ["cancellation", "inactive", "lost", "stopped"],
    "subscription": ["plan", "membership"],
}

_PRESERVE_TERMS = {"mrr", "arr", "ltv", "gmv", "cac", "kpi", "id"}


def tokenize(text: str) -> list[str]:
    """Normalize question text into search tokens."""
    text = text.lower()
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    text = text.replace("_", " ").replace("-", " ")
    raw = re.findall(r"[a-z0-9]+", text)
    tokens: list[str] = []
    for token in raw:
        if token in _PRESERVE_TERMS:
            tokens.append(token)
            continue
        tokens.append(token)
        if token.endswith("ies") and len(token) > 4:
            tokens.append(token[:-3] + "y")
        elif token.endswith("es") and len(token) > 3:
            tokens.append(token[:-2])
        elif token.endswith("s") and len(token) > 3 and not token.endswith("ss"):
            tokens.append(token[:-1])
    return list(dict.fromkeys(tokens))


def _expand_terms(tokens: list[str]) -> set[str]:
    expanded = set(tokens)
    for token in tokens:
        for canonical, synonyms in DEFAULT_SYNONYMS.items():
            if token == canonical or token in synonyms:
                expanded.add(canonical)
                expanded.update(synonyms)
    return expanded


def _table_tokens(table_name: str) -> set[str]:
    base = table_name.split(".")[-1].lower()
    parts = re.findall(r"[a-z0-9]+", base.replace("_", " "))
    return set(parts)


def score_tables(query: str, catalog: SchemaCatalog, *, top_k: int = 8) -> list[ScoredTable]:
    """Score catalog tables against a natural-language query."""
    terms = _expand_terms(tokenize(query))
    scored: list[ScoredTable] = []

    for table in catalog.tables:
        score = 0.0
        reasons: list[str] = []
        matched_columns: list[str] = []

        table_tokens = _table_tokens(table.name)
        if table.name.lower() in query.lower():
            score += 3.0
            reasons.append("exact table name")

        overlap = terms & table_tokens
        if overlap:
            score += 1.5 * len(overlap)
            reasons.append(f"table tokens: {', '.join(sorted(overlap))}")

        for col in table.columns:
            col_tokens = set(re.findall(r"[a-z0-9]+", col.name.lower()))
            col_overlap = terms & col_tokens
            if col_overlap:
                score += 1.0
                matched_columns.append(col.name)
            if col.semantic_type in terms or any(
                col.semantic_type == syn for syn in terms if col.semantic_type != "unknown"
            ):
                score += 0.5

        for canonical, synonyms in DEFAULT_SYNONYMS.items():
            if canonical in terms or terms & set(synonyms):
                if table_tokens & ({canonical} | set(synonyms)):
                    score += 1.0
                    reasons.append(f"synonym: {canonical}")

        score += table.importance_score * 0.5
        if table.is_internal:
            score -= 2.0
            reasons.append("internal penalty")

        if score > 0:
            scored.append(
                ScoredTable(
                    name=table.name,
                    score=round(score, 2),
                    reason="; ".join(reasons) if reasons else "match",
                    matched_columns=matched_columns[:5],
                )
            )

    scored.sort(key=lambda s: -s.score)
    return scored[:top_k]


__all__ = ["DEFAULT_SYNONYMS", "tokenize", "score_tables"]
