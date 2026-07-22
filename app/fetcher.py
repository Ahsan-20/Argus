"""Fetch a user-supplied URL safely and extract readable text.

Because URLs come from users and are fetched server-side, this module guards
against SSRF: only http/https, no private/loopback/link-local hosts, capped
redirects and response size. The extracted text feeds the Watcher.
"""

import ipaddress
import socket
from urllib.parse import urlparse

import httpx
import trafilatura

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
MAX_BYTES = 1_000_000  # 1 MB response cap
MAX_TEXT_CHARS = 32_000  # ~8k tokens, truncated before the Watcher sees it
TIMEOUT = 10.0


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


def fetch_readable_text(url: str) -> str:
    """Fetch the URL and return cleaned, truncated readable text.

    Raises UnsafeUrlError for blocked targets; lets httpx errors propagate so
    the caller records an honest error run.
    """
    assert_safe_url(url)
    with httpx.Client(
        follow_redirects=True,
        max_redirects=3,
        timeout=TIMEOUT,
        headers={"User-Agent": BROWSER_UA},
    ) as client:
        resp = client.get(url)
        resp.raise_for_status()
        html = resp.text[:MAX_BYTES]

    text = trafilatura.extract(html) or ""
    return text[:MAX_TEXT_CHARS]
