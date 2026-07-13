"""Safe deterministic suggestion generation using metadata only."""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict

from app.agents.question_suggestions.context import SuggestionEvidence, SuggestionGenerationContext
from app.db.models.question_suggestions import (
    DEFAULT_SURFACE_LIMITS,
    QuestionSuggestion,
    SURFACES,
    SuggestionCategory,
    SuggestionSurface,
)


_DATE_HINT = re.compile(r"date|time|month|year|created|updated", re.IGNORECASE)
_NUMBER_HINT = re.compile(r"int|numeric|decimal|float|double|real|money", re.IGNORECASE)


def suggestion_id(fingerprint: str, surface: str, prompt: str) -> str:
    normalized = " ".join(prompt.casefold().split())
    digest = hashlib.sha256(f"{fingerprint}|{surface}|{normalized}".encode()).hexdigest()
    return f"qs_{digest[:16]}"


def _item(
    context: SuggestionGenerationContext,
    surface: SuggestionSurface,
    title: str,
    prompt: str,
    rationale: str,
    category: SuggestionCategory,
    labels: list[str],
) -> QuestionSuggestion:
    return QuestionSuggestion(
        id=suggestion_id(context.context_fingerprint, surface, prompt),
        surface=surface,
        title=title,
        prompt=prompt,
        rationale=rationale,
        category=category,
        source="deterministic",
        based_on=list(dict.fromkeys(labels))[:5],
    )


def _semantic_items(context: SuggestionGenerationContext) -> list[tuple[str, str, str]]:
    metrics = [item for item in context.evidence if item.kind == "metric"]
    dates = [item for item in context.evidence if item.kind == "date_policy"]
    dimensions = [item for item in context.evidence if item.kind in {"dimension", "entity"}]
    results: list[tuple[str, str, str]] = []
    for metric in metrics[:3]:
        date = dates[0] if dates else None
        dimension = dimensions[0] if dimensions else None
        results.append((metric.label, date.label if date else "month", dimension.label if dimension else "category"))
    return results


def _physical_candidates(context: SuggestionGenerationContext):
    by_table: dict[str, list[SuggestionEvidence]] = defaultdict(list)
    for evidence in context.evidence:
        if evidence.kind == "physical_column":
            by_table[str(evidence.payload.get("table_name"))].append(evidence)
    candidates = []
    for table in context.catalog.tables:
        if table.is_internal:
            continue
        columns = by_table.get(table.name, [])
        dates = [c for c in columns if _DATE_HINT.search(str(c.payload.get("data_type", "")) + c.label)]
        numbers = [c for c in columns if _NUMBER_HINT.search(str(c.payload.get("data_type", "")))]
        categories = [c for c in columns if c not in dates and c not in numbers]
        candidates.append((table.name, dates, numbers, categories))
    return candidates


def _surface_prompts(context: SuggestionGenerationContext, surface: SuggestionSurface):
    output: list[QuestionSuggestion] = []
    semantics = _semantic_items(context)
    for metric, date, dimension in semantics:
        if surface == "dashboard":
            output.append(_item(context, surface, f"{metric} performance", f"Build a {metric} performance dashboard with trends over {date}, comparisons by {dimension}, top contributors, and unusual changes.", f"Verified definitions for {metric}, {date}, and {dimension} are available.", "trend", [metric, date, dimension]))
        else:
            output.extend([
                _item(context, surface, f"{metric} trend", f"Show the {metric} trend over {date} for the latest available periods.", f"A verified {metric} definition and date policy are available.", "trend", [metric, date]),
                _item(context, surface, f"Top {dimension} by {metric}", f"Rank the top {dimension} by {metric} and compare their contribution.", f"Verified metric and grouping definitions are available.", "ranking", [metric, dimension]),
                _item(context, surface, f"{metric} summary", f"Summarize the current {metric} and compare it with the previous period.", f"A verified {metric} definition is available.", "kpi", [metric]),
            ])

    for table, dates, numbers, categories in _physical_candidates(context)[:4]:
        date = dates[0].payload.get("column_name") if dates else None
        number = numbers[0].payload.get("column_name") if numbers else None
        category = categories[0].payload.get("column_name") if categories else None
        if surface == "dashboard":
            prompt = f"Build an exploration dashboard for {table} with record volume, distributions, rankings, and trends"
            if date:
                prompt += f" over {date}"
            prompt += "."
            output.append(_item(context, surface, f"Explore {table}", prompt, "This source contains safe analytical fields that can support a dashboard.", "segmentation", [table]))
        else:
            output.append(_item(context, surface, f"Explore {table}", f"Give me an analytical overview of {table}, including record counts and useful breakdowns.", "This table is available in the current connection scope.", "segmentation", [table]))
            if date:
                measure = f"{number} totals" if number else "record volume"
                output.append(_item(context, surface, f"{table} over time", f"Show how {measure} in {table} changes over {date}.", "A date-like field is available for trend analysis.", "trend", [table, str(date), *([str(number)] if number else [])]))
            if category:
                output.append(_item(context, surface, f"Compare {category}", f"Compare record counts in {table} by {category} and rank the largest groups.", "A categorical field is available for comparison.", "comparison", [table, str(category)]))

    if not output:
        output.append(_item(context, surface, "Explore the database", "Describe the available tables and suggest useful read-only analyses I can run.", "No verified business definitions are available yet, so this starts with schema discovery.", "segmentation", []))
    output.append(_item(context, surface, "Investigate unusual changes", "Identify unusual changes or outliers in the safest useful numeric measures over time.", "An anomaly scan can reveal unexpected behavior without exposing raw sensitive values.", "anomaly", []))
    return output


def generate_deterministic_bundle(context: SuggestionGenerationContext) -> dict[str, list[dict]]:
    bundle: dict[str, list[dict]] = {}
    for surface in SURFACES:
        seen: set[str] = set()
        diverse: list[QuestionSuggestion] = []
        by_category: dict[str, list[QuestionSuggestion]] = defaultdict(list)
        for item in _surface_prompts(context, surface):
            normalized = " ".join(item.prompt.casefold().split())
            if normalized not in seen:
                seen.add(normalized)
                by_category[item.category].append(item)
        while len(diverse) < DEFAULT_SURFACE_LIMITS[surface] and any(by_category.values()):
            for category in ("kpi", "trend", "comparison", "ranking", "segmentation", "anomaly"):
                if by_category[category] and len(diverse) < DEFAULT_SURFACE_LIMITS[surface]:
                    diverse.append(by_category[category].pop(0))
        bundle[surface] = [item.model_dump(mode="json") for item in diverse]
    return bundle


__all__ = ["generate_deterministic_bundle", "suggestion_id"]
