"""Over-long pages: keep the part the watch is about. No network or keys.

A result sheet or merit list is far longer than the readable cap, and the row
that matters is almost never in the first 32,000 characters. Chopping at the
front turns "is my roll number listed" into a confident, wrong "no".
"""

from app.fetcher import MAX_TEXT_CHARS, TRUNCATION_NOTE, _cap, _focus_windows


def _long_page(target_row: str, target_index: int = 3860, rows: int = 4000) -> str:
    body = [f"Roll {100000 + i} Candidate {i} Marks {50 + i % 50} Passed." for i in range(rows)]
    body[target_index] = target_row
    return "MERIT LIST 2026. Published 24 July 2026.\n" + "\n".join(body)


def test_short_pages_are_untouched():
    text = "a short page"
    assert _cap(text) == text
    assert _cap(text, "some focus") == text


def test_plain_truncation_marks_itself():
    capped = _cap("x" * (MAX_TEXT_CHARS + 500))
    assert capped.endswith(TRUNCATION_NOTE)
    assert len(capped) == MAX_TEXT_CHARS + len(TRUNCATION_NOTE)


def test_plain_truncation_loses_a_late_row():
    page = _long_page("Roll 103860 AHSAN ULLAH Marks 91 Passed.")
    assert "AHSAN ULLAH" not in _cap(page)


def test_focus_keeps_the_row_that_matters():
    page = _long_page("Roll 103860 AHSAN ULLAH Marks 91 Passed.")
    focused = _cap(page, "Is roll number 103860 listed as passed?")
    assert "AHSAN ULLAH" in focused
    assert len(focused) <= MAX_TEXT_CHARS + len(TRUNCATION_NOTE)


def test_focus_keeps_the_opening_for_context():
    page = _long_page("Roll 103860 AHSAN ULLAH Marks 91 Passed.")
    focused = _cap(page, "Is roll number 103860 listed as passed?")
    assert "MERIT LIST 2026" in focused


def test_focus_still_admits_it_dropped_text():
    page = _long_page("Roll 103860 AHSAN ULLAH Marks 91 Passed.")
    assert _cap(page, "roll 103860").endswith(TRUNCATION_NOTE)


def test_focus_of_only_stopwords_falls_back_to_plain():
    page = _long_page("Roll 103860 AHSAN ULLAH Marks 91 Passed.")
    # Nothing here can locate anything, so it must not pretend otherwise.
    assert _cap(page, "has the page been listed for you now").startswith("MERIT LIST")


def test_focus_windows_ignores_common_words():
    text = "the quick brown fox " * 50
    kept = _focus_windows(text, "the and for brown")
    assert "brown" in kept


def test_missing_term_still_returns_the_opening():
    page = _long_page("Roll 103860 AHSAN ULLAH Marks 91 Passed.")
    focused = _cap(page, "roll 999999 nowhere in this document")
    assert "MERIT LIST 2026" in focused
    assert focused.endswith(TRUNCATION_NOTE)
