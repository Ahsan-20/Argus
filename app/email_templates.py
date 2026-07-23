"""HTML alert templates, one visual style per alert category.

Security first: every dynamic value is HTML-escaped, hrefs are scheme-checked
so a model-supplied "javascript:" URL can never render as a live link, and
subjects are stripped of newlines by the mailer to prevent header injection.
Layout is table-based with inline styles, the only thing email clients render
reliably.
"""

import html
from urllib.parse import urlparse

from .branding import LOGO_DATA_URI

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


MONO = "'Courier New',monospace"
SANS = "Arial,Helvetica,sans-serif"


def _header(accent: str, callsign: str) -> str:
    """Logo emblem + ARGUS wordmark + callsign, as an email-safe table row."""
    return (
        '<tr><td style="padding:24px 28px 0">'
        '<table role="presentation" cellpadding="0" cellspacing="0"><tr>'
        f'<td style="padding-right:14px;vertical-align:middle">'
        f'<img src="{LOGO_DATA_URI}" width="40" height="40" alt="Argus" '
        'style="display:block;border:0"></td>'
        '<td style="vertical-align:middle">'
        f'<div style="color:#ffffff;font-family:{SANS};font-size:18px;'
        'font-weight:bold;letter-spacing:3px;line-height:1">ARGUS</div>'
        f'<div style="color:{MUTE};font-family:{MONO};font-size:10px;'
        f'letter-spacing:2px;margin-top:3px">MISSION CONTROL &nbsp;//&nbsp; '
        f'{_esc(callsign)}</div>'
        '</td></tr></table></td></tr>'
    )


def _pill(accent: str, label: str) -> str:
    return (
        '<tr><td style="padding:18px 28px 0">'
        f'<span style="display:inline-block;background:{INK_2};color:{accent};'
        f'border:1px solid {accent};border-radius:999px;padding:4px 13px;'
        f'font-family:{MONO};font-size:11px;letter-spacing:1px">'
        f'&#9679; {_esc(label)}</span></td></tr>'
    )


def _tracked_block(accent: str, label: str, value: str) -> str:
    return (
        '<tr><td style="padding:16px 28px 0">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>'
        f'<td style="background:{INK_2};border:1px solid {LINE};border-radius:8px;'
        'padding:12px 16px">'
        f'<div style="color:{MUTE};font-family:{MONO};font-size:10px;'
        f'letter-spacing:1px;text-transform:uppercase">Tracking &middot; {_esc(label)}</div>'
        f'<div style="color:{accent};font-family:{MONO};font-size:22px;'
        f'font-weight:bold;margin-top:4px">{_esc(value)}</div>'
        '</td></tr></table></td></tr>'
    )


def _evidence_block(accent: str, evidence: str) -> str:
    return (
        '<tr><td style="padding:16px 28px 0">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>'
        f'<td style="border-left:3px solid {accent};background:{INK_2};'
        f'padding:10px 16px;color:#aeb8cc;font-family:{MONO};font-size:13px;'
        f'line-height:1.6">&ldquo;{_esc(evidence.strip())}&rdquo;</td>'
        '</tr></table></td></tr>'
    )


def render_alert_html(
    *,
    category: str,
    callsign: str,
    subject: str,
    body: str,
    evidence: str | None,
    url: str,
    tracked_label: str | None = None,
    tracked_value: str | None = None,
) -> str:
    """Build a self-contained, injection-safe, branded HTML alert."""
    cat = CATEGORIES[category_of(category)]
    accent = cat["accent"]
    href = _safe_href(url)

    tracked = ""
    if tracked_label and tracked_value and tracked_value.strip():
        tracked = _tracked_block(accent, tracked_label, tracked_value)
    evidence_html = _evidence_block(accent, evidence) if (evidence or "").strip() else ""

    parts = [
        '<div style="background:#05070f;padding:24px 12px;margin:0">',
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0">',
        '<tr><td align="center">',
        '<table role="presentation" width="600" cellpadding="0" cellspacing="0" '
        f'style="max-width:600px;width:100%;background:{INK};border:1px solid {LINE};'
        'border-radius:14px;overflow:hidden">',
        f'<tr><td style="height:4px;background:{accent};line-height:4px;font-size:0">'
        '&nbsp;</td></tr>',
        _header(accent, callsign),
        _pill(accent, cat["label"]),
        '<tr><td style="padding:14px 28px 0">'
        f'<h1 style="margin:0;color:#ffffff;font-family:{SANS};font-size:21px;'
        f'line-height:1.35">{_esc(subject)}</h1></td></tr>',
        f'<tr><td style="padding:14px 28px 0">{_body_html(body)}</td></tr>',
        tracked,
        evidence_html,
        '<tr><td style="padding:24px 28px 8px">'
        f'<a href="{href}" style="display:inline-block;background:{accent};'
        f'color:#06110a;text-decoration:none;font-family:{SANS};font-weight:bold;'
        'font-size:14px;padding:13px 26px;border-radius:7px">Open target &rarr;</a>'
        '</td></tr>',
        '<tr><td style="padding:22px 28px;border-top:1px solid '
        f'{LINE};color:{MUTE};font-family:{MONO};font-size:11px;line-height:1.6">'
        'Argus Mission Control &middot; automated watch report<br>'
        'You are receiving this because you launched this probe.</td></tr>',
        '</table></td></tr></table></div>',
    ]
    return "".join(parts)
