"""Alert email templates: injection safety and category selection.

Deterministic, no network or API keys, so these run anywhere.
"""

from app.email_templates import AMBER, CATEGORIES, category_of, render_alert_html


def _render(**over):
    args = dict(
        category="generic",
        callsign="PROBE-01",
        subject="hello",
        body="a body",
        evidence="some evidence",
        url="https://example.com",
    )
    args.update(over)
    return render_alert_html(**args)


def test_script_tag_is_escaped():
    html = _render(subject="<script>alert(1)</script>")
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_img_onerror_is_escaped():
    html = _render(body="<img src=x onerror=alert(2)>")
    # The injected tag must be escaped (inert)...
    assert "&lt;img" in html
    assert "<img src=x onerror" not in html
    # ...while the only live <img> is our own logo, referenced by cid.
    assert html.count("<img") == 1
    assert 'src="cid:argus-logo"' in html


def test_tracked_value_is_escaped_and_shown():
    html = _render(tracked_label="the price", tracked_value="<b>$5</b>")
    assert "&lt;b&gt;$5&lt;/b&gt;" in html
    assert "// TELEMETRY" in html


def test_javascript_href_is_neutralised():
    html = _render(url="javascript:alert(3)")
    assert "javascript:alert" not in html
    assert 'href="#"' in html


def test_telemetry_and_sections_present():
    html = _render(
        confidence=88,
        tracked_label="the price",
        tracked_value="$479",
        stamp="2026-07-24 20:00 UTC",
    )
    assert "// TELEMETRY" in html
    assert "// EVIDENCE" in html
    assert "OPEN THE PAGE" in html
    assert "88%" in html
    assert "$479" in html
    assert "REPORTING" in html


def test_mobile_rules_and_fluid_shell_present():
    """Phones: fluid width for every client, media query for those that honour it."""
    html = _render(tracked_label="the price", tracked_value="$479")
    assert "max-width:600px;width:100%" in html  # fluid even without CSS support
    assert "@media only screen and (max-width:620px)" in html
    assert 'class="px"' in html  # gutters tighten
    assert 'class="subject"' in html  # headline scales down
    assert 'class="readout"' in html  # big value scales down
    assert 'class="hide-sm"' in html  # header tagline drops rather than crushes


def test_preheader_carries_the_news():
    html = _render(body="Slots are open for August.")
    assert "mso-hide:all" in html
    assert "Slots are open for August." in html


def test_http_href_survives():
    html = _render(url="https://example.com/path?q=1")
    assert 'href="https://example.com/path?q=1"' in html


def test_ampersand_escaped():
    html = _render(subject="Tom & Jerry")
    assert "Tom &amp; Jerry" in html


def test_category_coercion():
    assert category_of("PRICE") == "price"
    assert category_of("Availability") == "availability"
    assert category_of("nonsense") == "generic"
    assert category_of(None) == "generic"
    assert category_of("") == "generic"


def test_every_category_renders_with_its_status():
    for cat, cfg in CATEGORIES.items():
        html = render_alert_html(
            category=cat,
            callsign="PROBE-09",
            subject="s",
            body="b",
            evidence="e",
            url="https://example.com",
        )
        assert cfg["label"] in html   # CLASS metadata
        assert cfg["status"] in html  # status line
        assert cfg["accent"] in html  # the category's own colour
        assert cfg["glyph"] in html   # and its own glyph
        assert "OPEN THE PAGE" in html


def test_categories_are_visually_distinct():
    """Each category owns a unique accent and glyph, so alerts differ at a glance."""
    accents = [c["accent"] for c in CATEGORIES.values()]
    glyphs = [c["glyph"] for c in CATEGORIES.values()]
    assert len(set(accents)) == len(accents)
    assert len(set(glyphs)) == len(glyphs)


def test_amber_stays_the_interface_colour():
    """The action button stays Argus amber even when the news is another hue."""
    html = render_alert_html(
        category="release",  # blue accent
        callsign="PROBE-09",
        subject="s",
        body="b",
        evidence="e",
        url="https://example.com",
    )
    assert CATEGORIES["release"]["accent"] in html
    # the CTA border and section labels remain amber
    assert f"border:1px solid {AMBER}" in html
    assert f"color:{AMBER};font-family:" in html
