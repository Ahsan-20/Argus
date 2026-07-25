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

# Each category is its own kind of star: a distinct accent, glyph and status
# line, so an alert is recognisable in the inbox before a word is read.
#
# The split of duties matters. The ACCENT owns the news (top rule, status
# line, the tracked value, the evidence rule, the lit star). Amber stays the
# interface colour (section labels, the action button), so every alert still
# reads as Argus. Two colours per email, never a rainbow.
#
#   accent  the category's hue, chosen to be legible on near black
#   band    a very dark tint of that hue, for the header sky
#   glyph   a widely supported symbol, so no client falls back to a box
CATEGORIES: dict[str, dict[str, str]] = {
    "availability": {
        "label": "AVAILABILITY",
        "status": "NOW AVAILABLE",
        "accent": "#3DDC84",  # green: something opened up
        "band": "#10241c",
        "glyph": "&#10003;",  # check
    },
    "price": {
        "label": "PRICE",
        "status": "PRICE CHANGED",
        "accent": "#FFB000",  # gold: money
        "band": "#241c0c",
        "glyph": "&#9670;",  # diamond
    },
    "release": {
        "label": "RELEASE",
        "status": "NEW RELEASE",
        "accent": "#8FB8FF",  # blue white: the hottest, newest star
        "band": "#141d33",
        "glyph": "&#9733;",  # star
    },
    "status": {
        "label": "STATUS",
        "status": "STATUS CHANGED",
        "accent": "#B9A0FF",  # violet: a change of state
        "band": "#1e1830",
        "glyph": "&#9654;",  # play, something moved forward
    },
    "generic": {
        "label": "ALERT",
        "status": "FOUND IT",
        "accent": "#C2CAE0",  # neutral starlight: no special category
        "band": "#161b2b",
        "glyph": "&#9679;",  # dot
    },
    # Not something the Herald ever picks. Used for the system's own notice
    # that a watcher has stopped being able to read its page.
    "trouble": {
        "label": "TROUBLE",
        "status": "NEEDS ATTENTION",
        "accent": "#FF6B81",  # red: this one is about a problem
        "band": "#2a1620",
        "glyph": "&#9888;",  # warning
    },
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

# Phone rules. The layout is already fluid (max-width with width:100%), which
# is what carries Outlook and anything that ignores media queries. This adds
# the finishing touches for clients that do honour them: tighter gutters, type
# that does not overflow a 320px screen, and the header tagline dropped rather
# than crushed. !important is required because email styling is inline.
RESPONSIVE_STYLE = """\
<style>
@media only screen and (max-width:620px){
  .px{padding-left:18px!important;padding-right:18px!important}
  .subject{font-size:19px!important;line-height:1.3!important}
  .readout{font-size:22px!important}
  .stamp{font-size:10px!important;letter-spacing:0.5px!important}
  .status{font-size:13px!important;letter-spacing:1px!important}
  .cta{display:block!important;text-align:center!important}
  .hide-sm{display:none!important}
  .tel-label{font-size:10px!important}
  .tel-value{font-size:12px!important}
}
</style>"""


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


def _preheader(text: str) -> str:
    """The inbox preview line, hidden inside the email itself.

    Without this, clients preview whatever text comes first (the wordmark and
    section labels), which reads as noise in the inbox list. The trailing
    invisible characters stop body copy from leaking in after it.
    """
    filler = "&#847;&zwnj;&nbsp;" * 60
    return (
        '<div style="display:none;max-height:0;overflow:hidden;opacity:0;'
        'color:transparent;height:0;width:0;mso-hide:all">'
        f"{_esc(text[:140])}{filler}</div>"
    )


def _constellation(accent: str = AMBER) -> str:
    """A small run of stars with one lit, used as a section divider.

    Pure characters, so it renders identically in every client, unlike the
    gradients and rounded shapes email clients disagree about. The lit star
    takes the category's colour.
    """
    dot = f'<span style="color:{LINE}">&middot;</span>'
    star = f'<span style="color:{accent}">&#9679;</span>'
    gap = "&nbsp;&nbsp;&nbsp;"
    return (
        f'<div style="text-align:center;font-size:11px;line-height:1">'
        f"{dot}{gap}{dot}{gap}{star}{gap}{dot}{gap}{dot}</div>"
    )


def _readout(label: str, value: str, accent: str = AMBER) -> str:
    """The tracked value as a large instrument readout, the email's hero."""
    return (
        f'<tr><td class="px" style="padding:22px 30px 0">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="border:1px solid {LINE};background:{PANEL}">'
        f'<tr><td style="padding:14px 18px 16px;border-left:3px solid {accent}">'
        f'<div style="color:{MUTE};font-family:{MONO};font-size:10px;'
        f'letter-spacing:2px;text-transform:uppercase">{_esc(label)[:48]}</div>'
        f'<div class="readout" style="margin-top:6px;color:{accent};'
        f'font-family:{MONO};font-size:28px;line-height:1.15;font-weight:bold;'
        f'word-break:break-word">{_esc(value)}</div>'
        "</td></tr></table></td></tr>"
    )


def _telemetry_rows(
    rows: list[tuple[str, str, bool]], accent: str = AMBER
) -> str:
    """rows: list of (label, value, highlight). Rendered as key:value lines."""
    out = []
    for i, (label, value, highlight) in enumerate(rows):
        border = "" if i == 0 else f"border-top:1px solid {LINE};"
        val_color = accent if highlight else WHITE
        val_size = "15px" if highlight else "13px"
        out.append(
            f'<tr><td class="tel-label" style="{border}padding:9px 14px;'
            f'font-family:{MONO};font-size:11px;letter-spacing:1px;color:{MUTE};'
            f'white-space:nowrap;vertical-align:middle">{_esc(label)}</td>'
            f'<td class="tel-value" style="{border}padding:9px 14px;'
            f'font-family:{MONO};font-size:{val_size};color:{val_color};'
            f'text-align:right;vertical-align:middle;word-break:break-word">'
            f"{_esc(value)}</td></tr>"
        )
    return "".join(out)


def render_account_html(
    *,
    heading: str,
    body: str,
    cta_label: str,
    cta_url: str,
    footnote: str,
    expiry_note: str | None = None,
) -> str:
    """An account email: verify your address, or reset your password.

    Same sky as an alert but deliberately quieter. No category colour, no
    telemetry, no evidence: this is not a report about a page, it is one
    instruction with one button, and anything else competing with that button
    is working against the person trying to get back into their account.

    The link is also printed as text underneath, because a good number of mail
    clients strip or rewrite buttons, and "the link did nothing" with no way
    to recover is how people give up on an account.
    """
    href = _safe_href(cta_url)
    parts = [
        RESPONSIVE_STYLE,
        _preheader(" ".join((body or heading).split())),
        f'<div style="background:{PAGE};padding:28px 12px;margin:0">',
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0">',
        '<tr><td align="center">',
        '<table role="presentation" width="600" cellpadding="0" cellspacing="0" '
        f'style="max-width:600px;width:100%;background:{CARD};border:1px solid {LINE}">',

        f'<tr><td style="height:3px;background:{AMBER};background-image:'
        f'linear-gradient(90deg,{AMBER} 0%,{AMBER} 45%,{LINE} 100%);'
        'line-height:3px;font-size:0">&nbsp;</td></tr>',

        f'<tr><td class="px" style="padding:22px 30px 18px">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>'
        f'<td width="40" style="vertical-align:middle">'
        f'<img src="cid:{LOGO_CID}" width="34" height="34" alt="Argus" '
        'style="display:block;border:0"></td>'
        '<td style="vertical-align:middle;padding-left:12px">'
        f'<div style="color:{WHITE};font-family:{DISP};font-size:16px;'
        'font-weight:700;letter-spacing:4px;line-height:1">ARGUS</div>'
        f'<div style="color:{MUTE};font-family:{MONO};font-size:9px;'
        'letter-spacing:3px;margin-top:3px">MISSION CONTROL</div></td>'
        '</tr></table></td></tr>',

        f'<tr><td class="px" style="padding:6px 30px 0">'
        f"{_constellation(AMBER)}</td></tr>",

        f'<tr><td class="px" style="padding:20px 30px 0;text-align:center">'
        f'<h1 class="subject" style="margin:0;color:{WHITE};font-family:{DISP};'
        f'font-size:23px;font-weight:700;line-height:1.32">'
        f"{_esc(heading)}</h1></td></tr>",

        f'<tr><td class="px" style="padding:14px 30px 0;text-align:center">'
        f"{_body_html(body)}</td></tr>",

        '<tr><td class="px" style="padding:26px 30px 0;text-align:center">'
        f'<a class="cta" href="{href}" style="display:inline-block;'
        f'background:{AMBER};border:1px solid {AMBER};color:#151007;'
        f'text-decoration:none;font-family:{MONO};font-size:13px;'
        'font-weight:bold;letter-spacing:2px;padding:14px 30px">'
        f"{_esc(cta_label.upper())}</a></td></tr>",

        # The same link in plain text. Not decoration: it is the fallback when
        # the button is stripped, so it has to be selectable and complete.
        f'<tr><td class="px" style="padding:16px 30px 0;text-align:center">'
        f'<div style="color:{MUTE};font-family:{MONO};font-size:10px;'
        'letter-spacing:1px;line-height:1.7">OR PASTE THIS INTO YOUR BROWSER</div>'
        f'<div style="margin-top:7px;word-break:break-all;color:{TEXT};'
        f'font-family:{MONO};font-size:11px;line-height:1.6">{_esc(cta_url)}</div>'
        "</td></tr>",

        (
            f'<tr><td class="px" style="padding:18px 30px 0;text-align:center">'
            f'<div style="color:{MUTE};font-family:{MONO};font-size:11px;'
            f'letter-spacing:1px">{_esc(expiry_note)}</div></td></tr>'
            if expiry_note
            else ""
        ),

        f'<tr><td class="px" style="padding:26px 30px 24px">'
        f'<div style="border-top:1px solid {LINE};padding-top:18px">'
        f"{_constellation(AMBER)}"
        f'<div style="margin-top:12px;text-align:center;color:{MUTE};'
        f'font-family:{MONO};font-size:10px;letter-spacing:1px;line-height:1.8">'
        f"{_esc(footnote)}</div></div></td></tr>",

        '</table></td></tr></table></div>',
    ]
    return "".join(parts)


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
    accent = cat["accent"]
    href = _safe_href(url)
    # http(s) only reaches real watchers; fall back to a neutral label rather
    # than echoing an unexpected scheme into the telemetry readout.
    host = urlparse(url).hostname or "target"
    stamp = stamp or "--"

    # The tracked value is promoted to a large readout of its own, so the
    # telemetry block stays a quiet list of context rather than burying it.
    has_readout = bool(tracked_label and tracked_value and tracked_value.strip())

    rows: list[tuple[str, str, bool]] = [("PROBE", callsign, False)]
    if confidence is not None:
        rows.append(("CONFIDENCE", f"{confidence}%", False))
    if not has_readout and tracked_value and tracked_value.strip():
        rows.append(("VALUE", tracked_value.strip(), True))
    rows.append(("TARGET", host, False))
    rows.append(("CLASS", cat["label"], True))  # tinted: it names the category

    evidence_section = ""
    if (evidence or "").strip():
        evidence_section = (
            f'<tr><td class="px" style="padding:22px 30px 0">{_label("EVIDENCE")}'
            f'<div style="margin-top:10px;border:1px solid {LINE};'
            f'border-left:3px solid {accent};background:{PANEL};padding:12px 16px;'
            f'font-family:{MONO};font-size:13px;line-height:1.6;color:#aeb8cc">'
            f'&ldquo;{_esc(evidence.strip())}&rdquo;</div></td></tr>'
        )

    # Preview line: the news itself, not the wordmark.
    preview = " ".join((body or subject or "").split())

    parts = [
        RESPONSIVE_STYLE,
        _preheader(preview),
        f'<div style="background:{PAGE};padding:28px 12px;margin:0">',
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0">',
        '<tr><td align="center">',
        '<table role="presentation" width="600" cellpadding="0" cellspacing="0" '
        f'style="max-width:600px;width:100%;background:{CARD};border:1px solid {LINE}">',

        # top rule: the category's colour fading toward deep space
        f'<tr><td style="height:3px;background:{accent};background-image:'
        f'linear-gradient(90deg,{accent} 0%,{accent} 45%,{LINE} 100%);'
        'line-height:3px;font-size:0">&nbsp;</td></tr>',

        # header band: a lit corner of the night sky, tinted by the category
        f'<tr><td class="px" style="background:{cat["band"]};background-image:'
        f'linear-gradient(135deg,{cat["band"]} 0%,{CARD} 62%);padding:22px 30px 18px">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>'
        f'<td width="40" style="vertical-align:middle">'
        f'<img src="cid:{LOGO_CID}" width="34" height="34" alt="Argus" '
        'style="display:block;border:0"></td>'
        '<td style="vertical-align:middle;padding-left:12px">'
        f'<div style="color:{WHITE};font-family:{DISP};font-size:16px;'
        'font-weight:700;letter-spacing:4px;line-height:1">ARGUS</div>'
        f'<div style="color:{MUTE};font-family:{MONO};font-size:9px;'
        'letter-spacing:3px;margin-top:3px">MISSION CONTROL</div></td>'
        f'<td class="hide-sm" style="vertical-align:middle;text-align:right;'
        f'color:{MUTE};font-family:{MONO};font-size:10px;letter-spacing:2px">'
        "// PROBE REPORT</td>"
        '</tr></table></td></tr>',

        # constellation divider
        f'<tr><td class="px" style="padding:14px 30px 0">'
        f"{_constellation(accent)}</td></tr>",

        # transmission line
        f'<tr><td class="px stamp" style="padding:14px 30px 0;text-align:center;'
        f'color:{MUTE};font-family:{MONO};font-size:11px;letter-spacing:1px">'
        f'{_esc(callsign)} REPORTING &middot; {_esc(stamp)}</td></tr>',

        # status line: the category's glyph and colour, the strongest signal
        f'<tr><td class="px status" style="padding:10px 30px 0;text-align:center;'
        f'color:{accent};font-family:{MONO};font-size:15px;font-weight:bold;'
        f'letter-spacing:2px">{cat["glyph"]} {_esc(cat["status"])}</td></tr>',

        # subject
        f'<tr><td class="px" style="padding:14px 30px 0;text-align:center">'
        f'<h1 class="subject" style="margin:0;color:{WHITE};font-family:{DISP};'
        f'font-size:23px;font-weight:700;line-height:1.32">'
        f"{_esc(subject)}</h1></td></tr>",

        # body
        f'<tr><td class="px" style="padding:14px 30px 0;text-align:center">'
        f"{_body_html(body)}</td></tr>",

        # the tracked value, as a large readout
        _readout(tracked_label, tracked_value.strip(), accent) if has_readout else "",

        # evidence
        evidence_section,

        # telemetry
        f'<tr><td class="px" style="padding:22px 30px 0">{_label("TELEMETRY")}'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="margin-top:10px;border:1px solid {LINE};background:{PANEL}">'
        f"{_telemetry_rows(rows, accent)}</table></td></tr>",

        # CTA: outline button, monospace
        '<tr><td class="px" style="padding:26px 30px 6px;text-align:center">'
        f'<a class="cta" href="{href}" style="display:inline-block;'
        f'border:1px solid {AMBER};color:{AMBER};text-decoration:none;'
        f'font-family:{MONO};font-size:13px;font-weight:bold;letter-spacing:2px;'
        'padding:13px 26px">OPEN THE PAGE &nbsp;&rarr;</a></td></tr>',

        # footer, closed by the same constellation that opened the report
        f'<tr><td class="px" style="padding:26px 30px 24px">'
        f'<div style="border-top:1px solid {LINE};padding-top:18px">'
        f"{_constellation(accent)}"
        f'<div style="margin-top:12px;text-align:center;color:{MUTE};'
        f'font-family:{MONO};font-size:10px;letter-spacing:1px;line-height:1.8">'
        'ARGUS MISSION CONTROL &middot; AUTOMATIC ALERT<br>'
        'You are getting this because you asked Argus to watch this page.'
        '</div></div></td></tr>',

        '</table></td></tr></table></div>',
    ]
    return "".join(parts)
