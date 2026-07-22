"""HTML alert templates, one visual style per alert category.

Security first: every dynamic value is HTML-escaped, hrefs are scheme-checked
so a model-supplied "javascript:" URL can never render as a live link, and
subjects are stripped of newlines by the mailer to prevent header injection.
Layout is table-based with inline styles, the only thing email clients render
reliably.
"""

import html
from urllib.parse import urlparse

# Category -> visual identity. Amber is the house accent; green signals "go".
CATEGORIES: dict[str, dict[str, str]] = {
    "availability": {"accent": "#3DDC84", "label": "AVAILABILITY", "tag": "Now available"},
    "price": {"accent": "#FFB000", "label": "PRICE", "tag": "Price change"},
    "release": {"accent": "#38BDF8", "label": "RELEASE", "tag": "New release"},
    "status": {"accent": "#F5A524", "label": "STATUS", "tag": "Status change"},
    "generic": {"accent": "#FFB000", "label": "ALERT", "tag": "Condition met"},
}
FALLBACK = "generic"

INK = "#0B0E1A"
INK_2 = "#10152a"
LINE = "#1c2233"
TEXT = "#c9d1e3"
MUTE = "#6b7488"


def category_of(value: str | None) -> str:
    """Coerce anything (including a hallucinated label) to a known category."""
    v = (value or "").strip().lower()
    return v if v in CATEGORIES else FALLBACK


def _esc(value: str) -> str:
    return html.escape(value or "", quote=True)


def _safe_href(url: str) -> str:
    """Only http(s) links become live; anything else is neutralised to '#'."""
    try:
        scheme = urlparse((url or "").strip()).scheme.lower()
    except ValueError:
        return "#"
    return _esc(url) if scheme in ("http", "https") else "#"


def _body_html(body: str) -> str:
    """Escape, then turn blank lines into paragraphs and newlines into breaks."""
    blocks = [b.strip() for b in (body or "").split("\n\n") if b.strip()]
    parts = []
    for block in blocks:
        parts.append(
            '<p style="margin:0 0 14px;color:%s;font-size:14px;line-height:1.7">%s</p>'
            % (TEXT, _esc(block).replace("\n", "<br>"))
        )
    return "".join(parts) or (
        '<p style="margin:0 0 14px;color:%s">Your watched condition is now met.</p>'
        % TEXT
    )


def render_alert_html(
    *,
    category: str,
    callsign: str,
    subject: str,
    body: str,
    evidence: str | None,
    url: str,
) -> str:
    """Build a self-contained, injection-safe HTML alert for one category."""
    cat = CATEGORIES[category_of(category)]
    accent = cat["accent"]
    href = _safe_href(url)

    evidence_block = ""
    if evidence and evidence.strip():
        evidence_block = (
            '<tr><td style="padding:4px 28px 0">'
            '<table role="presentation" width="100%%" cellpadding="0" cellspacing="0"><tr>'
            '<td style="border-left:3px solid %s;background:%s;padding:10px 16px;'
            'color:#aeb8cc;font-family:\'Courier New\',monospace;font-size:13px;'
            'line-height:1.6">&ldquo;%s&rdquo;</td></tr></table></td></tr>'
            % (accent, INK_2, _esc(evidence.strip()))
        )

    # Dark accent bar, eyebrow, category pill, subject, body, evidence, CTA, footer.
    return (
        '<div style="background:#05070f;padding:24px 12px;margin:0">'
        '<table role="presentation" width="100%%" cellpadding="0" cellspacing="0">'
        '<tr><td align="center">'
        '<table role="presentation" width="600" cellpadding="0" cellspacing="0" '
        'style="max-width:600px;width:100%%;background:%s;border:1px solid %s;'
        'border-radius:12px;overflow:hidden">'
        # accent bar
        '<tr><td style="height:4px;background:%s;line-height:4px;font-size:0">&nbsp;</td></tr>'
        # eyebrow + pill
        '<tr><td style="padding:22px 28px 0">'
        '<span style="color:%s;font-family:\'Courier New\',monospace;font-size:11px;'
        'letter-spacing:2px">ARGUS &nbsp;//&nbsp; %s</span>'
        '<div style="margin-top:12px">'
        '<span style="display:inline-block;background:%s;color:%s;border:1px solid %s;'
        'border-radius:999px;padding:3px 12px;font-family:\'Courier New\',monospace;'
        'font-size:11px;letter-spacing:1px">&#9679; %s</span></div></td></tr>'
        # subject
        '<tr><td style="padding:14px 28px 0">'
        '<h1 style="margin:0;color:#ffffff;font-family:Arial,Helvetica,sans-serif;'
        'font-size:20px;line-height:1.35">%s</h1></td></tr>'
        # body
        '<tr><td style="padding:14px 28px 0">%s</td></tr>'
        # evidence
        '%s'
        # CTA
        '<tr><td style="padding:22px 28px 6px">'
        '<a href="%s" style="display:inline-block;background:%s;color:#06110a;'
        'text-decoration:none;font-family:Arial,Helvetica,sans-serif;font-weight:bold;'
        'font-size:14px;padding:12px 24px;border-radius:6px">Open target &rarr;</a></td></tr>'
        # footer
        '<tr><td style="padding:22px 28px;margin-top:8px;border-top:1px solid %s;'
        'color:%s;font-family:\'Courier New\',monospace;font-size:11px;line-height:1.6">'
        'Argus Mission Control &middot; automated watch report<br>'
        'You are receiving this because you launched this probe.</td></tr>'
        '</table></td></tr></table></div>'
    ) % (
        INK, LINE,
        accent,
        accent, _esc(callsign),
        INK_2, accent, accent, _esc(cat["label"]),
        _esc(subject),
        _body_html(body),
        evidence_block,
        href, accent,
        LINE, MUTE,
    )
