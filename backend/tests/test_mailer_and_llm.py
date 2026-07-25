"""Header-injection defence and JSON parsing. No network or keys."""

import pytest

from app.llm import LLMError, _safe_parse
from app.mailer import _one_line


def test_header_injection_is_flattened():
    out = _one_line("Subject\r\nBcc: victim@evil.com\r\nX-Hack: 1")
    assert "\n" not in out and "\r" not in out
    assert "Bcc:" in out  # content preserved, just single-lined


def test_one_line_trims():
    assert _one_line("  hi  ") == "hi"


def test_safe_parse_plain_json():
    assert _safe_parse('{"a": 1}') == {"a": 1}


def test_safe_parse_code_fence():
    assert _safe_parse('```json\n{"a": 2}\n```') == {"a": 2}


def test_safe_parse_invalid_raises():
    with pytest.raises(LLMError):
        _safe_parse("not json at all")
