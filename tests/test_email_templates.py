"""Alert email templates: injection safety and category selection.

Deterministic, no network or API keys, so these run anywhere.
"""

from app.email_templates import CATEGORIES, category_of, render_alert_html


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
    assert "<img" not in html
    assert "&lt;img" in html


def test_javascript_href_is_neutralised():
    html = _render(url="javascript:alert(3)")
    assert "javascript:alert" not in html
    assert 'href="#"' in html


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


def test_every_category_renders_with_its_accent():
    for cat, cfg in CATEGORIES.items():
        html = render_alert_html(
            category=cat,
            callsign="PROBE-09",
            subject="s",
            body="b",
            evidence="e",
            url="https://example.com",
        )
        assert cfg["accent"] in html
        assert cfg["label"] in html
        assert "Open target" in html
