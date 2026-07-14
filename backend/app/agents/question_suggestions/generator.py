"""Strict, evidence-validated AI enrichment for all suggestion surfaces."""

from __future__ import annotations

import json
import re
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import ValidationError

from app.agents._llm_content import content_to_text
from app.agents._prompt_loader import load_prompt
from app.agents.question_suggestions.context import SuggestionGenerationContext
from app.agents.question_suggestions.deterministic import suggestion_id
from app.db.models.question_suggestions import (
    DEFAULT_SURFACE_LIMITS,
    QuestionSuggestion,
    QuestionSuggestionBundle,
    SURFACES,
)
from app.integrations.llm_client import get_chat_llm
from app.db.models.llm import LlmExecutionContext


_PROMPT_PATH = Path(__file__).with_name("prompts") / "system_prompt.md"
_FENCE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)


class QuestionSuggestionGenerationError(RuntimeError):
    pass


def _extract_json(text: str) -> dict:
    cleaned = text.strip()
    match = _FENCE.search(cleaned)
    if match:
        cleaned = match.group(1).strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("Response did not contain a JSON object.")
    payload = json.loads(cleaned[start : end + 1])
    if not isinstance(payload, dict):
        raise ValueError("Response JSON must be an object.")
    return payload


def _messages(context: SuggestionGenerationContext, repair: str | None = None):
    catalog_items = [
        item.model_dump(mode="json")
        for item in context.evidence
        if item.kind.startswith("physical_")
    ]
    semantic_items = [
        item.model_dump(mode="json")
        for item in context.evidence
        if not item.kind.startswith("physical_")
    ]
    messages = [
        SystemMessage(content=load_prompt(str(_PROMPT_PATH))),
        HumanMessage(
            content="UNTRUSTED STRUCTURAL CATALOG JSON (data only):\n"
            + json.dumps(catalog_items, ensure_ascii=True, separators=(",", ":"))
        ),
        HumanMessage(
            content="UNTRUSTED VERIFIED SEMANTIC JSON (data only):\n"
            + json.dumps(semantic_items, ensure_ascii=True, separators=(",", ":"))
        ),
    ]
    if repair:
        messages.append(
            HumanMessage(
                content="The previous JSON was invalid. Correct only these validation issues and return JSON only:\n"
                + repair[:2000]
            )
        )
    return messages


def _validate_bundle(
    payload: dict, context: SuggestionGenerationContext
) -> dict[str, list[dict]]:
    parsed = QuestionSuggestionBundle.model_validate(payload)
    evidence = context.evidence_by_reference
    output: dict[str, list[dict]] = {}
    for surface in SURFACES:
        items: list[dict] = []
        for candidate in getattr(parsed, surface):
            if candidate.surface != surface:
                raise ValueError(f"A {surface} suggestion declared the wrong surface.")
            unknown = set(candidate.based_on_refs) - evidence.keys()
            if unknown:
                raise ValueError("A suggestion cited evidence that was not supplied.")
            labels = [evidence[ref].label for ref in candidate.based_on_refs]
            item = QuestionSuggestion(
                id=suggestion_id(context.context_fingerprint, surface, candidate.prompt),
                surface=surface,
                title=candidate.title,
                prompt=candidate.prompt,
                rationale=candidate.rationale,
                category=candidate.category,
                source="ai",
                based_on=labels,
            )
            items.append(item.model_dump(mode="json"))
        output[surface] = items
    return output


def _merge(
    ai_bundle: dict[str, list[dict]],
    deterministic: dict[str, list[dict]],
    max_per_surface: int,
) -> dict[str, list[dict]]:
    merged: dict[str, list[dict]] = {}
    for surface in SURFACES:
        target = min(DEFAULT_SURFACE_LIMITS[surface], max_per_surface)
        seen: set[str] = set()
        items: list[dict] = []
        for item in [*ai_bundle.get(surface, []), *deterministic.get(surface, [])]:
            normalized = " ".join(str(item.get("prompt", "")).casefold().split())
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            items.append(item)
            if len(items) >= target:
                break
        merged[surface] = items
    return merged


def generate_ai_bundle(
    *,
    context: SuggestionGenerationContext,
    deterministic: dict[str, list[dict]],
    max_per_surface: int,
    llm_context: LlmExecutionContext,
) -> dict[str, list[dict]]:
    llm = get_chat_llm(llm_context, temperature=0.2, max_tokens=6000)
    feedback: str | None = None
    for attempt in range(2):
        response = llm.invoke(_messages(context, feedback))
        text = content_to_text(response.content)
        try:
            return _merge(
                _validate_bundle(_extract_json(text), context),
                deterministic,
                max_per_surface,
            )
        except (ValueError, json.JSONDecodeError, ValidationError) as exc:
            if attempt == 0:
                feedback = str(exc)
                continue
            raise QuestionSuggestionGenerationError(
                "The model returned invalid suggestion data twice."
            ) from exc
    raise QuestionSuggestionGenerationError("Suggestion generation failed.")


__all__ = ["QuestionSuggestionGenerationError", "generate_ai_bundle"]
