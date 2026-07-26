"""Build the wide architecture overview shown at the top of the README.

Hand written SVG rather than a Mermaid block, for three reasons: real brand
logos, exact control over spacing, and a single file that renders identically
everywhere GitHub shows an image.

Two versions are produced, light and dark, and the README picks between them
with a <picture> element so the diagram suits whichever theme the reader uses.
A single dark diagram looks like a hole punched in a light page.

Logo paths come from Simple Icons (CC0). They are cached in docs/icons.json and
fetched only if that file is missing, so a rebuild needs no network. Each icon
is a single path on a 24x24 grid, so drawing one is a translate and a scale.

    python docs/build_overview.py
"""

import json
import pathlib
import re

HERE = pathlib.Path(__file__).parent
CACHE = HERE / "icons.json"
NAMES = [
    "react", "python", "fastapi", "vercel",
    "render", "googlegemini", "supabase", "gmail",
]


def load_icons() -> dict:
    if CACHE.exists():
        return json.loads(CACHE.read_text())

    import urllib.request

    print("  fetching logos from the Simple Icons CDN")
    icons = {}
    for name in NAMES:
        url = f"https://cdn.jsdelivr.net/npm/simple-icons@latest/icons/{name}.svg"
        svg = urllib.request.urlopen(url, timeout=20).read().decode()
        icons[name] = re.search(r'<path\s+d="([^"]+)"', svg).group(1)
    CACHE.write_text(json.dumps(icons, indent=1))
    return icons


ICONS = load_icons()

W, H = 1180, 470

# Two palettes, same geometry. Brand colours stay put in both, because a
# recoloured logo is not the logo.
THEMES = {
    "light": {
        "bg": "#ffffff", "panel": "#f6f7fb", "stroke": "#d8dce8",
        "title": "#0b0f1e", "text": "#3d4560", "muted": "#767f99",
        "wire": "#b9c0d2", "band": "#eef0f7", "bandtext": "#5a6480",
        "accent": "#d98a00",
    },
    "dark": {
        "bg": "#0b0f1e", "panel": "#131829", "stroke": "#262e47",
        "title": "#f5f7ff", "text": "#c7cde0", "muted": "#8a93ac",
        "wire": "#35405f", "band": "#0e1424", "bandtext": "#98a1bc",
        "accent": "#ffb000",
    },
}

# Official brand colours. Vercel's mark is near black, so it alone follows the
# theme; every other logo keeps its own colour, because a recoloured logo is not
# the logo.
BRAND = {
    "react": "#61DAFB", "python": "#3776AB", "fastapi": "#009688",
    "vercel": None, "render": "#46E3B7", "googlegemini": "#8E75B2",
    "supabase": "#3FCF8E", "gmail": "#EA4335",
}

FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif"
MONO = "ui-monospace,'SF Mono',Menlo,Consolas,monospace"


def icon(name: str, x: float, y: float, size: float, t: dict) -> str:
    colour = BRAND.get(name) or t["title"]
    s = size / 24
    return (
        f'<g transform="translate({x},{y}) scale({s})">'
        f'<path d="{ICONS[name]}" fill="{colour}"/></g>'
    )


def box(x, y, w, h, t, dashed=False):
    dash = ' stroke-dasharray="5 4"' if dashed else ""
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" '
        f'fill="{t["panel"]}" stroke="{t["stroke"]}" stroke-width="1.5"{dash}/>'
    )


def text(x, y, s, t, size=13, weight=400, fill=None, anchor="start", mono=False):
    return (
        f'<text x="{x}" y="{y}" font-family="{MONO if mono else FONT}" '
        f'font-size="{size}" font-weight="{weight}" fill="{fill or t["text"]}" '
        f'text-anchor="{anchor}">{s}</text>'
    )


def arrow(x1, y1, x2, y2, t, label=None, dashed=False):
    dash = ' stroke-dasharray="4 4"' if dashed else ""
    out = (
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{t["wire"]}" '
        f'stroke-width="1.6" marker-end="url(#head)"{dash}/>'
    )
    if label:
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        out += text(mx, my - 7, label, t, size=10.5, fill=t["muted"], anchor="middle")
    return out


def build(theme: str) -> str:
    t = THEMES[theme]
    p = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
        f'width="{W}" height="{H}" font-family="{FONT}">',
        f'<defs>'
        f'<marker id="head" markerWidth="9" markerHeight="9" refX="7" refY="3" '
        f'orient="auto"><path d="M0,0 L7,3 L0,6 z" fill="{t["wire"]}"/></marker>'
        # The return leg is drawn in the accent colour, so it needs its own
        # arrowhead; markers do not inherit the stroke of the line they end.
        f'<marker id="head-accent" markerWidth="9" markerHeight="9" refX="7" refY="3" '
        f'orient="auto"><path d="M0,0 L7,3 L0,6 z" fill="{t["accent"]}"/></marker>'
        f'</defs>',
        f'<rect width="{W}" height="{H}" fill="{t["bg"]}"/>',
        text(40, 44, "How Argus works", t, size=21, weight=700, fill=t["title"]),
        text(40, 68, "One sentence becomes a watcher. It reads the page on a schedule, "
                     "judges it, and emails you when your thing happens.", t, size=13,
             fill=t["muted"]),
    ]

    # ---- row 1: the browser, the frontend, the backend -------------------
    y = 106
    p += [
        box(40, y, 210, 112, t),
        icon("react", 64, y + 22, 26, t),
        text(100, y + 34, "Browser", t, size=14.5, weight=600, fill=t["title"]),
        text(64, y + 62, "React 19, Vite, Tailwind", t, size=11.5, fill=t["muted"]),
        icon("vercel", 64, y + 79, 12, t),
        text(83, y + 89, "hosted on Vercel", t, size=11, fill=t["muted"]),
    ]

    p += [
        box(330, y, 250, 112, t),
        icon("fastapi", 354, y + 22, 26, t),
        text(390, y + 34, "Argus API", t, size=14.5, weight=600, fill=t["title"]),
        text(354, y + 62, "FastAPI, scheduler inside", t, size=11.5, fill=t["muted"]),
        icon("render", 354, y + 79, 12, t),
        text(373, y + 89, "Render", t, size=11, fill=t["muted"]),
        icon("python", 442, y + 79, 12, t),
        text(461, y + 89, "Python 3.12", t, size=11, fill=t["muted"]),
    ]

    p.append(arrow(250, y + 56, 328, y + 56, t, "signed token"))

    # ---- the three AI roles ---------------------------------------------
    p += [
        box(660, y, 250, 112, t),
        icon("googlegemini", 684, y + 21, 22, t),
        text(714, y + 34, "Three AI roles", t, size=14.5, weight=600, fill=t["title"]),
        text(684, y + 60, "Commissioner, reads your sentence", t, size=10.5, fill=t["muted"]),
        text(684, y + 76, "Watcher, judges the page", t, size=10.5, fill=t["muted"]),
        text(684, y + 92, "Herald, writes the alert", t, size=10.5, fill=t["muted"]),
    ]
    p.append(arrow(580, y + 56, 658, y + 56, t))

    # ---- storage ---------------------------------------------------------
    p += [
        box(990, y, 150, 112, t),
        icon("supabase", 1014, y + 21, 22, t),
        text(1044, y + 34, "Supabase", t, size=14.5, weight=600, fill=t["title"]),
        text(1014, y + 62, "Postgres: watchers,", t, size=11, fill=t["muted"]),
        text(1014, y + 78, "runs, accounts, alerts", t, size=11, fill=t["muted"]),
    ]
    p.append(arrow(910, y + 56, 988, y + 56, t))

    # ---- row 2: what it watches, and how the alert gets out --------------
    y2 = 274
    p += [
        box(330, y2, 250, 96, t),
        text(354, y2 + 30, "Target web pages", t, size=13.5, weight=600, fill=t["title"]),
        text(354, y2 + 52, "robots.txt, throttled, SSRF", t, size=11, fill=t["muted"]),
        text(354, y2 + 70, "guarded, conditional GETs", t, size=11, fill=t["muted"]),
    ]
    p.append(arrow(455, y + 112, 455, y2 - 2, t, "every 60s: anything due?"))

    # The mail path, drawn as its own hop because that is the interesting part.
    p += [
        box(660, y2, 250, 96, t, dashed=True),
        text(684, y2 + 28, "Apps Script relay", t, size=13.5, weight=600, fill=t["accent"]),
        text(684, y2 + 50, "over HTTPS, because the", t, size=11, fill=t["muted"]),
        text(684, y2 + 66, "host blocks SMTP ports", t, size=11, fill=t["muted"]),
    ]
    p.append(arrow(580, y2 + 48, 658, y2 + 48, t, "alert found"))

    p += [
        box(990, y2, 150, 96, t),
        icon("gmail", 1014, y2 + 24, 20, t),
        text(1042, y2 + 34, "Your inbox", t, size=14, weight=600, fill=t["title"]),
        text(1014, y2 + 62, "Gmail sends it, so", t, size=11, fill=t["muted"]),
        text(1014, y2 + 78, "it authenticates", t, size=11, fill=t["muted"]),
    ]
    p.append(arrow(910, y2 + 48, 988, y2 + 48, t))

    # The alert coming back to the person, which is the whole point.
    p.append(
        f'<path d="M1065,{y2 + 96} L1065,{y2 + 122} L145,{y2 + 122} L145,{y + 114}" '
        f'fill="none" stroke="{t["accent"]}" stroke-width="1.6" '
        f'stroke-dasharray="4 4" marker-end="url(#head-accent)"/>'
    )
    p.append(text(600, y2 + 116, "the alert reaches you", t, size=11,
                  fill=t["accent"], anchor="middle"))

    p.append(f'<rect x="0" y="{H-34}" width="{W}" height="34" fill="{t["band"]}"/>')
    p.append(text(40, H - 13, "Every check is recorded with its verdict, confidence, "
                              "and a quote from the page.", t, size=11.5, fill=t["bandtext"]))
    p.append("</svg>")
    return "\n".join(p)


for name in ("light", "dark"):
    path = HERE / f"architecture-{name}.svg"
    path.write_text(build(name), encoding="utf8")
    print(f"  wrote {path.name}  ({path.stat().st_size:,} bytes)")
