"""Normalize and log raw LLM message content."""

from __future__ import annotations

import logging


def content_to_text(content: object) -> str:
    """Convert LangChain/Gemini message content to plain text."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
                continue
            if isinstance(block, dict):
                if block.get("type") == "text" and block.get("text"):
                    parts.append(str(block["text"]))
                elif block.get("text"):
                    parts.append(str(block["text"]))
                continue
            text = getattr(block, "text", None)
            if text:
                parts.append(str(text))
        return "".join(parts)
    return str(content)


def log_llm_output(logger: logging.Logger, label: str, content: object, *, max_chars: int = 6000) -> str:
    """Log normalized model output and return the normalized text."""
    text = content_to_text(content).strip()
    if len(text) <= max_chars:
        logged = text
    else:
        logged = f"{text[:max_chars]}... [truncated {len(text) - max_chars} chars]"
    logger.info("[llm-output] %s (%d chars): %s", label, len(text), logged or "<empty>")
    return text


__all__ = ["content_to_text", "log_llm_output"]
