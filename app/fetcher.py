"""Fetch a user-supplied URL safely and extract readable text.

Because URLs come from users and are fetched server-side, this module guards
against SSRF: only http/https, no private/loopback/link-local hosts, and
redirects are followed manually so EVERY hop is re-validated (an auto-follow
client would happily chase a public URL that 302s to an internal address).
Responses are streamed and cut off at a hard byte cap so a huge page cannot
exhaust the instance's memory. The extracted text feeds the Watcher.
"""

import ipaddress
import logging
import socket
from urllib.parse import urljoin, urlparse

import httpx
import trafilatura

logger = logging.getLogger("argus.fetcher")

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
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


class UnsafeUrlError(Exception):
    pass


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


def _fetch(url: str, verify: bool = True) -> str:
    """Fetch with manual, re-validated redirects. Returns raw HTML text."""
    current = url
    with httpx.Client(
        follow_redirects=False,
        timeout=TIMEOUT,
        verify=verify,
        headers={
            "User-Agent": BROWSER_UA,
            "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        },
    ) as client:
        for _ in range(MAX_REDIRECTS + 1):
            assert_safe_url(current)  # EVERY hop, not just the first
            resp = _stream_capped(client, current)
            if resp.is_redirect:
                location = resp.headers.get("location")
                if not location:
                    raise UnsafeUrlError("redirect with no location header")
                current = urljoin(current, location)
                continue
            resp.raise_for_status()
            return resp.text
    raise UnsafeUrlError(f"more than {MAX_REDIRECTS} redirects")


def _fetch_via_renderer(url: str) -> str:
    """Last-resort fetch through the r.jina.ai rendering proxy.

    Returns extracted text, or an empty string if the proxy cannot help
    either. Never raises: by the time this runs, the primary fetch has
    already failed, and the caller wants the best text available.
    """
    try:
        resp = httpx.get(
            f"{JINA_PREFIX}{url}",
            timeout=JINA_TIMEOUT,
            headers={"X-Return-Format": "text", "User-Agent": BROWSER_UA},
        )
        if resp.status_code != 200:
            return ""
        return resp.text.strip()[:MAX_TEXT_CHARS]
    except httpx.HTTPError as exc:
        logger.info("renderer fallback failed for %s: %s", url, exc)
        return ""


def fetch_readable_text(url: str) -> str:
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
    try:
        html = _fetch(url, verify=True)
        text = (trafilatura.extract(html) or "").strip()
    except UnsafeUrlError:
        raise
    except httpx.ConnectError as exc:
        message = str(exc).lower()
        if "certificate" not in message:
            primary_error = exc
        else:
            logger.warning("TLS verification failed for %s, retrying unverified", url)
            try:
                html = _fetch(url, verify=False)
                text = (trafilatura.extract(html) or "").strip()
            except UnsafeUrlError:
                raise
            except httpx.HTTPError as exc2:
                primary_error = exc2
    except httpx.HTTPError as exc:
        primary_error = exc

    if len(text) >= MIN_USEFUL_CHARS:
        return text[:MAX_TEXT_CHARS]

    rendered = _fetch_via_renderer(url)
    if len(rendered) > len(text):
        logger.info("using renderer fallback for %s (%d chars)", url, len(rendered))
        return rendered

    if primary_error is not None:
        raise primary_error
    return text[:MAX_TEXT_CHARS]
