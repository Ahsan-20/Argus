"""House style: no em or en dashes in copy Argus writes. No DB or network."""

from app.tick import plain_dashes


def test_em_dash_becomes_a_comma():
    assert plain_dashes("Slots are open — book now") == "Slots are open, book now"


def test_em_dash_without_spaces():
    assert plain_dashes("Found it—finally") == "Found it, finally"


def test_en_dash_between_digits_is_a_range():
    assert plain_dashes("Draw runs 15–20 August") == "Draw runs 15-20 August"


def test_en_dash_between_words_becomes_a_comma():
    assert plain_dashes("Price dropped – a lot") == "Price dropped, a lot"


def test_dash_next_to_existing_punctuation_does_not_double_up():
    assert plain_dashes("Ready, — set") == "Ready, set"


def test_dash_before_punctuation_leaves_no_gap():
    assert plain_dashes("It is open — .") == "It is open,."


def test_plain_text_is_untouched():
    text = "The next Rs. 1,500 draw is listed for August 15, 2026."
    assert plain_dashes(text) == text


def test_hyphens_and_ranges_survive():
    assert plain_dashes("well-known 10-20 range") == "well-known 10-20 range"


def test_handles_empty_and_none():
    assert plain_dashes("") == ""
    assert plain_dashes(None) == ""


def test_multiple_dashes_in_one_string():
    assert (
        plain_dashes("One — two — three")
        == "One, two, three"
    )
