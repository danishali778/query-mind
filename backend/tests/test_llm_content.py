"""Tests for LLM content normalization."""

from app.agents._llm_content import content_to_text, log_llm_output


def test_content_to_text_string():
    assert content_to_text("hello") == "hello"


def test_content_to_text_list_of_strings():
    assert content_to_text(["a", "b"]) == "ab"


def test_content_to_text_list_of_dict_blocks():
    blocks = [{"type": "text", "text": '{"sql": "SELECT 1"}'}]
    assert content_to_text(blocks) == '{"sql": "SELECT 1"}'


def test_log_llm_output_truncates(caplog):
    import logging

    logger = logging.getLogger("test.llm")
    long_text = "x" * 100
    with caplog.at_level(logging.INFO):
        result = log_llm_output(logger, "test", long_text, max_chars=20)
    assert result == long_text
    assert "[llm-output] test" in caplog.text
