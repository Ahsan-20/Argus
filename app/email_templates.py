"""HTML alert emails, styled as a mission-control transmission.

Deep Space Mission Control brand: near-black, a single phosphor-amber accent
with verdict-green used sparingly, thin hairline borders, monospace for all
telemetry and labels, and a terse mission-control voice. The layout is a
data-dense dossier (console header, status line, telemetry readout, evidence
quote, outline CTA), deliberately NOT a soft centred SaaS card.

Security first: every dynamic value is HTML-escaped, hrefs are scheme-checked
so a model-supplied "javascript:" URL can never render as a live link, and
subjects are stripped of newlines by the mailer to prevent header injection.
Layout is table-based with inline styles, the only thing email clients render
reliably.
"""

import html
from urllib.parse import urlparse

from .branding import LOGO_CID

# Category is metadata only. The brand uses one accent (amber); the verdict is
# signalled in green. No per-category rainbow, which reads more disciplined.
CATEGORIES: dict[str, dict[str, str]] = {
    "availability": {"label": "AVAILABILITY", "status": "NOW AVAILABLE"},
    "price": {"label": "PRICE", "status": "PRICE CHANGE DETECTED"},
    "release": {"label": "RELEASE", "status": "NEW RELEASE DETECTED"},
    "status": {"label": "STATUS", "status": "STATUS CHANGE DETECTED"},
    "generic": {"label": "ALERT", "status": "CONDITION MET"},
}
FALLBACK = "generic"

# Palette
PAGE = "#05070d"      # outer background
CARD = "#0B0E1A"      # console body
LINE = "#20263a"      # hairline
PANEL = "#0e1424"     # inset panels
AMBER = "#FFB000"     # the one accent
GREEN = "#3DDC84"     # verdict / positive, used sparingly
WHITE = "#f4f7ff"
TEXT = "#c2cae0"
MUTE = "#616b86"

MONO = "'JetBrains Mono','SFMono-Regular',Consolas,'Liberation Mono','Courier New',monospace"
DISP = "'Space Grotesk','Helvetica Neue',Helvetica,Arial,sans-serif"


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
            f'<p style="margin:0 0 12px;color:{TEXT};font-family:{DISP};'
            f'font-size:15px;line-height:1.65">{_esc(block).replace(chr(10), "<br>")}</p>'
        )
    return "".join(parts) or (
        f'<p style="margin:0;color:{TEXT};font-family:{DISP};font-size:15px">'
        "Your watched condition is now met.</p>"
    )


def _label(text: str) -> str:
    """A `// SECTION` marker in amber monospace."""
    return (
        f'<div style="color:{AMBER};font-family:{MONO};font-size:11px;'
        f'letter-spacing:2px;font-weight:bold">// {_esc(text)}</div>'
    )


def _telemetry_rows(rows: list[tuple[str, str, bool]]) -> str:
    """rows: list of (label, value, highlight). Rendered as key:value lines."""
    out = []
    for i, (label, value, highlight) in enumerate(rows):
        border = "" if i == 0 else f"border-top:1px solid {LINE};"
        val_color = AMBER if highlight else WHITE
        val_size = "15px" if highlight else "13px"
        out.append(
            f'<tr><td style="{border}padding:9px 14px;font-family:{MONO};'
            f'font-size:11px;letter-spacing:1px;color:{MUTE};'
            f'white-space:nowrap;vertical-align:middle">{_esc(label)}</td>'
            f'<td style="{border}padding:9px 14px;font-family:{MONO};'
            f'font-size:{val_size};color:{val_color};text-align:right;'
            f'vertical-align:middle;word-break:break-all">{_esc(value)}</td></tr>'
        )
    return "".join(out)


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
    confidence: int | None = None,
    stamp: str | None = None,
) -> str:
    """Build a self-contained, injection-safe mission-control alert email."""
    cat = CATEGORIES[category_of(category)]
    href = _safe_href(url)
    # http(s) only reaches real watchers; fall back to a neutral label rather
    # than echoing an unexpected scheme into the telemetry readout.
    host = urlparse(url).hostname or "target"
    stamp = stamp or "--"

    # Telemetry readout rows.
    rows: list[tuple[str, str, bool]] = [("PROBE", callsign, False)]
    if confidence is not None:
        rows.append(("CONFIDENCE", f"{confidence}%", False))
    if tracked_label and tracked_value and tracked_value.strip():
        rows.append((tracked_label.upper()[:40], tracked_value.strip(), True))
    rows.append(("TARGET", host, False))
    rows.append(("CLASS", cat["label"], False))

    evidence_section = ""
    if (evidence or "").strip():
        evidence_section = (
            f'<tr><td style="padding:22px 30px 0">{_label("EVIDENCE")}'
            f'<div style="margin-top:10px;border:1px solid {LINE};'
            f'border-left:3px solid {AMBER};background:{PANEL};padding:12px 16px;'
            f'font-family:{MONO};font-size:13px;line-height:1.6;color:#aeb8cc">'
            f'&ldquo;{_esc(evidence.strip())}&rdquo;</div></td></tr>'
        )

    parts = [
        f'<div style="background:{PAGE};padding:28px 12px;margin:0">',
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0">',
        '<tr><td align="center">',
        '<table role="presentation" width="600" cellpadding="0" cellspacing="0" '
        f'style="max-width:600px;width:100%;background:{CARD};border:1px solid {LINE}">',

        # top amber rule
        f'<tr><td style="height:3px;background:{AMBER};line-height:3px;font-size:0">'
        '&nbsp;</td></tr>',

        # console header: logo + wordmark ........ // PROBE REPORT
        '<tr><td style="padding:22px 30px 16px">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>'
        f'<td width="40" style="vertical-align:middle">'
        f'<img src="cid:{LOGO_CID}" width="34" height="34" alt="Argus" '
        'style="display:block;border:0"></td>'
        '<td style="vertical-align:middle;padding-left:12px">'
        f'<div style="color:{WHITE};font-family:{DISP};font-size:16px;'
        'font-weight:700;letter-spacing:4px;line-height:1">ARGUS</div>'
        f'<div style="color:{MUTE};font-family:{MONO};font-size:9px;'
        'letter-spacing:3px;margin-top:3px">MISSION CONTROL</div></td>'
        f'<td style="vertical-align:middle;text-align:right;color:{MUTE};'
        f'font-family:{MONO};font-size:10px;letter-spacing:2px">// PROBE REPORT</td>'
        '</tr></table></td></tr>',

        # hairline
        f'<tr><td style="padding:0 30px"><div style="border-top:1px solid {LINE}">'
        '</div></td></tr>',

        # transmission line
        f'<tr><td style="padding:16px 30px 0;color:{MUTE};font-family:{MONO};'
        f'font-size:11px;letter-spacing:1px">{_esc(callsign)} REPORTING '
        f'&middot; {_esc(stamp)}</td></tr>',

        # status line (verdict green, left rule)
        '<tr><td style="padding:12px 30px 0">'
        f'<table role="presentation" cellpadding="0" cellspacing="0"><tr>'
        f'<td style="border-left:3px solid {GREEN};padding:2px 0 2px 12px;'
        f'color:{GREEN};font-family:{MONO};font-size:15px;font-weight:bold;'
        f'letter-spacing:2px">&#9679; {_esc(cat["status"])}</td>'
        '</tr></table></td></tr>',

        # subject
        f'<tr><td style="padding:16px 30px 0"><h1 style="margin:0;color:{WHITE};'
        f'font-family:{DISP};font-size:22px;font-weight:700;line-height:1.3">'
        f'{_esc(subject)}</h1></td></tr>',

        # body
        f'<tr><td style="padding:14px 30px 0">{_body_html(body)}</td></tr>',

        # telemetry
        f'<tr><td style="padding:22px 30px 0">{_label("TELEMETRY")}'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="margin-top:10px;border:1px solid {LINE};background:{PANEL}">'
        f'{_telemetry_rows(rows)}</table></td></tr>',

        # evidence
        evidence_section,

        # CTA: outline button, monospace
        '<tr><td style="padding:26px 30px 6px">'
        f'<a href="{href}" style="display:inline-block;border:1px solid {AMBER};'
        f'color:{AMBER};text-decoration:none;font-family:{MONO};font-size:13px;'
        'font-weight:bold;letter-spacing:2px;padding:12px 22px">'
        'OPEN TARGET &nbsp;&rarr;</a></td></tr>',

        # footer
        f'<tr><td style="padding:24px 30px;margin-top:6px">'
        f'<div style="border-top:1px solid {LINE};padding-top:16px;color:{MUTE};'
        f'font-family:{MONO};font-size:10px;letter-spacing:1px;line-height:1.7">'
        'ARGUS MISSION CONTROL &middot; AUTOMATED WATCH REPORT<br>'
        'You are receiving this transmission because you launched this probe.'
        '</div></td></tr>',

        '</table></td></tr></table></div>',
    ]
    return "".join(parts)
