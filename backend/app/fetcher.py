"""Fetch a user-supplied URL safely and extract readable text.

Because URLs come from users and are fetched server-side, this module guards
against SSRF: only http/https, no private/loopback/link-local hosts, and
redirects are followed manually so EVERY hop is re-validated (an auto-follow
client would happily chase a public URL that 302s to an internal address).
Responses are streamed and cut off at a hard byte cap so a huge page cannot
exhaust the instance's memory. The extracted text feeds the Watcher.

Known residual risk, accepted at this scope: the safety check resolves DNS
and the fetch then resolves it again, so a hostile authoritative DNS server
could answer differently each time (rebinding) and slip one GET past the
check. Closing it needs a resolve-once, connect-by-IP transport; not worth
the complexity for a read-only fetcher on a host with no internal services.
"""

import ipaddress
import logging
import re
import socket
import threading
import time
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx
import trafilatura

from .config import get_settings

logger = logging.getLogger("argus.fetcher")
settings = get_settings()

# The name a site's robots.txt can address us by.
UA_TOKEN = "ArgusWatcher"


def user_agent() -> str:
    """How Argus introduces itself.

    Honest identification, not browser impersonation: the site owner can see
    what is calling and where to complain. Overridable so a deployment can put
    its own contact URL in.
    """
    if settings.user_agent:
        return settings.user_agent
    contact = (settings.public_base_url or "https://argus.local").rstrip("/")
    return f"Mozilla/5.0 (compatible; {UA_TOKEN}/1.0; +{contact})"


def _headers(extra: dict | None = None) -> dict:
    h = {
        "User-Agent": user_agent(),
        "Accept": "text/html,application/xhtml+xml,application/pdf,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "close",
    }
    if extra:
        h.update({k: v for k, v in extra.items() if v})
    return h
MAX_BYTES = 1_000_000  # hard download cap, enforced while streaming
MAX_TEXT_CHARS = 32_000  # ~8k tokens, truncated before the Watcher sees it
MAX_REDIRECTS = 3
TIMEOUT = 15.0
MIN_USEFUL_CHARS = 200  # below this, try the rendering fallback

# r.jina.ai renders pages (including JS) and returns plain text, free and
# keyless at ~20 requests/minute, far above our 5-runs-per-tick pace. Measured
# 2026-07-23: it rescued NADRA (WAF 403 -> 5k chars of real content) but not
# Amazon or NTS, so it is strictly a fallback, never the primary.
JINA_PREFIX = "https://r.jina.ai/"
JINA_TIMEOUT = 30.0


# Appended when a page is longer than the cap. Without it the extra text is
# dropped silently, the model answers from a partial page, and a "not found"
# on a long results list looks identical to a genuine one. The Watcher prompt
# tells the model to distrust a negative verdict when it sees this.
TRUNCATION_NOTE = (
    "\n\n[PAGE CUT OFF: this page was longer than could be read, and the text "
    "beyond this point was not included. Anything you are looking for may be "
    "in the part that was cut.]"
)


class UnsafeUrlError(Exception):
    pass


class BlockedByRobotsError(Exception):
    """The site's robots.txt asks us not to fetch this path."""


@dataclass
class Fetched:
    """One fetch: the readable text, plus what lets us ask again politely."""

    text: str = ""
    etag: str | None = None
    last_modified: str | None = None
    not_modified: bool = False  # server said nothing changed, body omitted


# ---------------------------------------------------------------------------
# Being a good guest: robots.txt, and never crowding one host
# ---------------------------------------------------------------------------
_robots_cache: dict[str, tuple[float, RobotFileParser | None]] = {}
_ROBOTS_TTL = 3600.0
_last_hit: dict[str, float] = {}
_hit_lock = threading.Lock()


def _robots_for(origin: str) -> RobotFileParser | None:
    """Fetch and cache a host's robots.txt. None means no usable rules.

    A missing or unreadable robots.txt means allowed, which is the convention.
    Fetched with our own client rather than RobotFileParser.read() so it gets
    the same timeout and identification as everything else.
    """
    now = time.time()
    cached = _robots_cache.get(origin)
    if cached and now - cached[0] < _ROBOTS_TTL:
        return cached[1]

    parser: RobotFileParser | None = None
    try:
        resp = httpx.get(
            f"{origin}/robots.txt",
            timeout=8.0,
            headers=_headers(),
            follow_redirects=True,
        )
        if resp.status_code == 200 and resp.text.strip():
            parser = RobotFileParser()
            parser.parse(resp.text.splitlines())
    except httpx.HTTPError as exc:
        logger.info("no robots.txt for %s: %s", origin, exc)
    _robots_cache[origin] = (now, parser)
    return parser


def _robots_check(url: str) -> float:
    """Refuse paths robots.txt disallows. Returns the delay to respect."""
    floor = settings.crawl_delay_seconds
    if not settings.respect_robots:
        return floor
    parsed = urlparse(url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    parser = _robots_for(origin)
    if parser is None:
        return floor
    if not parser.can_fetch(UA_TOKEN, url):
        raise BlockedByRobotsError(
            "this site's robots.txt asks automated visitors not to read this page"
        )
    stated = parser.crawl_delay(UA_TOKEN)
    if stated:
        # Honour the site's wishes, but do not let one hostile value stall a
        # worker for minutes.
        return min(max(float(stated), floor), settings.max_crawl_delay_seconds)
    return floor


def _throttle(host: str, delay: float) -> None:
    """Space out requests so one host never sees a burst from us."""
    with _hit_lock:
        wait = delay - (time.time() - _last_hit.get(host, 0.0))
        if wait > 0:
            logger.info("waiting %.1fs before hitting %s again", wait, host)
            time.sleep(wait)
        _last_hit[host] = time.time()


def _cap(text: str, focus: str | None = None) -> str:
    """Trim to the readable limit, saying so when anything was dropped.

    With `focus` (the watch condition and tracked field), a page that is too
    long is not simply chopped at the front. The distinctive terms from the
    watch are located in the full text and a window around each is kept, after
    an opening slice for context. That is what makes "is my roll number in
    this list" work on a result sheet with thousands of rows, where the answer
    is almost never in the first 32,000 characters.
    """
    if len(text) <= MAX_TEXT_CHARS:
        return text

    logger.info("page text over the cap at %d chars", len(text))
    if focus:
        windows = _focus_windows(text, focus)
        if windows:
            return windows + TRUNCATION_NOTE
    return text[:MAX_TEXT_CHARS] + TRUNCATION_NOTE


# Terms this short or this common carry no locating power.
_STOPWORDS = {
    "the", "and", "for", "any", "has", "have", "been", "with", "that", "this",
    "from", "are", "was", "were", "does", "did", "not", "yet", "its", "his",
    "her", "there", "shown", "show", "page", "listed", "list", "available",
    "since", "previous", "check", "than", "more", "less", "when", "what",
    "number", "current", "still", "your", "you", "new", "now",
}
HEAD_CHARS = 6_000  # opening slice: headings, dates, table captions
WINDOW = 1_200  # kept either side of a match
MAX_SPANS = 40  # windows to gather before calling it enough
COMMON_TERM_LIMIT = 40  # above this a term is page furniture, not a landmark


def _focus_windows(text: str, focus: str) -> str:
    """Keep the opening plus the neighbourhood of each distinctive focus term.

    Rarest terms are used first. On a merit list the words "roll" and "passed"
    appear on every one of four thousand rows and locate nothing, while the
    roll number appears once and locates everything. Working through terms in
    document order let the common ones exhaust the window budget before the
    distinctive one was ever looked up.
    """
    terms = {
        t
        for t in re.findall(r"[A-Za-z0-9][A-Za-z0-9._-]{2,}", focus.lower())
        if t not in _STOPWORDS
    }
    if not terms:
        return ""

    lowered = text.lower()
    counts = {t: lowered.count(t) for t in terms}
    useful = sorted((t for t in terms if counts[t]), key=lambda t: counts[t])
    if not useful:
        return ""

    spans: list[tuple[int, int]] = [(0, HEAD_CHARS)]
    for term in useful:
        # Skip page furniture once something better has been found.
        if counts[term] > COMMON_TERM_LIMIT and len(spans) > 1:
            continue
        start = 0
        while len(spans) < MAX_SPANS:
            i = lowered.find(term, start)
            if i == -1:
                break
            spans.append((max(0, i - WINDOW), min(len(text), i + WINDOW)))
            start = i + len(term)
        if len(spans) >= MAX_SPANS:
            break

    spans.sort()
    merged: list[list[int]] = []
    for lo, hi in spans:
        if merged and lo <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], hi)
        else:
            merged.append([lo, hi])

    out, used = [], 0
    for lo, hi in merged:
        chunk = text[lo : hi]
        if used + len(chunk) > MAX_TEXT_CHARS:
            chunk = chunk[: MAX_TEXT_CHARS - used]
        if not chunk:
            break
        out.append(chunk)
        used += len(chunk)
        if used >= MAX_TEXT_CHARS:
            break
    logger.info("focused extraction kept %d chars around %d terms", used, len(terms))
    return "\n[...]\n".join(out)


def assert_safe_url(url: str) -> None:
    """Validate a target URL without fetching it.

    Public so watcher creation can reject unsafe targets up front, rather than
    only discovering them on the first run. This is the real guard: the API has
    no auth, so /watchers/confirm must not accept internal addresses.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise UnsafeUrlError("only http and https URLs are allowed")
    host = parsed.hostname
    if not host:
        raise UnsafeUrlError("URL has no host")
    # Reject any resolved address that is private, loopback, or link-local.
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise UnsafeUrlError(f"cannot resolve host: {host}") from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise UnsafeUrlError(f"host resolves to a blocked address: {ip}")


def _stream_capped(client: httpx.Client, url: str) -> httpx.Response:
    """GET without auto-redirects, streaming the body up to MAX_BYTES."""
    with client.stream("GET", url) as resp:
        if resp.is_redirect:
            # Body irrelevant for redirects; return with headers only.
            resp.read()
            return resp
        chunks: list[bytes] = []
        total = 0
        for chunk in resp.iter_bytes():
            chunks.append(chunk)
            total += len(chunk)
            if total >= MAX_BYTES:
                logger.info("response for %s cut off at %d bytes", url, total)
                break
        resp._content = b"".join(chunks)[:MAX_BYTES]  # make .text/.content usable
        return resp


def _retry_after_seconds(resp: httpx.Response) -> float:
    """How long the server asked us to wait, clamped to something sane."""
    raw = (resp.headers.get("retry-after") or "").strip()
    if raw.isdigit():
        return min(float(raw), 60.0)
    return 5.0  # asked to back off without saying how long


def _fetch(
    url: str,
    verify: bool = True,
    etag: str | None = None,
    last_modified: str | None = None,
) -> httpx.Response:
    """Fetch with manual, re-validated redirects, politely.

    robots.txt is consulted, requests to one host are spaced out, and a server
    that answers 429 or 503 is given the pause it asked for and tried once
    more rather than being hammered. Conditional headers are sent when we have
    them, so an unchanged page can come back as an empty 304.
    """
    delay = _robots_check(url)
    current = url
    conditional = {"If-None-Match": etag, "If-Modified-Since": last_modified}

    with httpx.Client(
        follow_redirects=False,
        timeout=TIMEOUT,
        verify=verify,
        headers=_headers(conditional),
    ) as client:
        for _ in range(MAX_REDIRECTS + 1):
            assert_safe_url(current)  # EVERY hop, not just the first
            host = urlparse(current).hostname or ""
            _throttle(host, delay)

            resp = _stream_capped(client, current)

            # Rate limited or briefly unavailable: wait as asked, try once.
            if resp.status_code in (429, 503):
                pause = _retry_after_seconds(resp)
                logger.info(
                    "%s said %s, waiting %.0fs before one retry",
                    host, resp.status_code, pause,
                )
                time.sleep(pause)
                _throttle(host, delay)
                resp = _stream_capped(client, current)

            if resp.status_code == 304:
                return resp  # unchanged, and it cost the server almost nothing

            if resp.is_redirect:
                location = resp.headers.get("location")
                if not location:
                    raise UnsafeUrlError("redirect with no location header")
                current = urljoin(current, location)
                continue

            resp.raise_for_status()
            return resp
    raise UnsafeUrlError(f"more than {MAX_REDIRECTS} redirects")


def _fetch_via_renderer(url: str) -> str:
    """Fetch through the r.jina.ai rendering proxy (it executes JavaScript).

    Returns extracted text, or an empty string if the proxy cannot help.
    Never raises: callers treat rendered text as best-effort.

    Deliberately sends NO User-Agent: r.jina.ai sits behind Cloudflare, which
    challenges browser-looking agents with a 403 "Just a moment" page while a
    plain client passes. Found live on 2026-07-24; with BROWSER_UA this
    fallback had been silently returning nothing.
    """
    try:
        resp = httpx.get(
            f"{JINA_PREFIX}{url}",
            timeout=JINA_TIMEOUT,
            headers={"X-Return-Format": "text"},  # deliberately no UA, see above
        )
        if resp.status_code != 200:
            logger.info("renderer returned %s for %s", resp.status_code, url)
            return ""
        return _cap(resp.text.strip())
    except httpx.HTTPError as exc:
        logger.info("renderer fallback failed for %s: %s", url, exc)
        return ""


def fetch_rendered_text(url: str) -> str:
    """Fetch a page through the JS renderer, for targets whose data only
    exists after scripts run (countdowns, client-rendered prices/listings).

    Validates the target and checks robots.txt first, so neither an internal
    address nor a path the site asked us to leave alone reaches the proxy.
    Returns "" when the renderer cannot help; never raises for fetch trouble.
    """
    assert_safe_url(url)
    _robots_check(url)
    return _fetch_via_renderer(url)


def fetch_readable_text(
    url: str,
    focus: str | None = None,
    etag: str | None = None,
    last_modified: str | None = None,
) -> Fetched:
    """Fetch the URL and return cleaned, truncated readable text.

    Escalation, mirroring the LLM client's philosophy:
    1. Direct fetch with TLS verification.
    2. On a certificate failure only, retry unverified. Old government and
       university sites frequently run misconfigured TLS, and for a read-only
       monitor of public pages this equals what any browser user clicking
       through the warning would see. The retry is logged.
    3. If the fetch fails outright (WAF 403, timeout) or yields too little
       text to judge (JS-rendered page), try the rendering proxy.

    Raises UnsafeUrlError for blocked targets; those never reach step 3, so
    internal addresses are never sent to the proxy either. Other errors
    propagate only if the proxy also produced nothing, so the caller records
    an honest error run.
    """
    primary_error: Exception | None = None
    text = ""
    tag: str | None = None
    modified: str | None = None

    def absorb(resp: httpx.Response) -> str:
        """Keep the caching headers, hand back the body."""
        nonlocal tag, modified
        tag = resp.headers.get("etag") or None
        modified = resp.headers.get("last-modified") or None
        return (trafilatura.extract(resp.text) or "").strip()

    try:
        resp = _fetch(url, verify=True, etag=etag, last_modified=last_modified)
        if resp.status_code == 304:
            # The server says nothing has changed. Nothing was transferred and
            # nothing needs reading.
            return Fetched(not_modified=True, etag=etag, last_modified=last_modified)
        text = absorb(resp)
    except (UnsafeUrlError, BlockedByRobotsError):
        raise
    except httpx.ConnectError as exc:
        message = str(exc).lower()
        if "certificate" not in message:
            primary_error = exc
        else:
            logger.warning("TLS verification failed for %s, retrying unverified", url)
            try:
                resp = _fetch(url, verify=False, etag=etag, last_modified=last_modified)
                if resp.status_code == 304:
                    return Fetched(
                        not_modified=True, etag=etag, last_modified=last_modified
                    )
                text = absorb(resp)
            except (UnsafeUrlError, BlockedByRobotsError):
                raise
            except httpx.HTTPError as exc2:
                primary_error = exc2
    except httpx.HTTPError as exc:
        primary_error = exc

    if len(text) >= MIN_USEFUL_CHARS:
        return Fetched(text=_cap(text, focus), etag=tag, last_modified=modified)

    rendered = _fetch_via_renderer(url)
    if len(rendered) > len(text):
        logger.info("using renderer fallback for %s (%d chars)", url, len(rendered))
        return Fetched(text=rendered)

    if primary_error is not None:
        raise primary_error
    return Fetched(text=_cap(text, focus), etag=tag, last_modified=modified)
