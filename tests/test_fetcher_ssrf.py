"""The SSRF guard: only public http(s) targets are allowed.

Uses loopback and link-local addresses, which resolve locally, so no internet
is required.
"""

import pytest

from app.fetcher import UnsafeUrlError, assert_safe_url


@pytest.mark.parametrize(
    "url",
    [
        "ftp://example.com",
        "file:///etc/passwd",
        "javascript:alert(1)",
        "not-a-url",
        "http://",
    ],
)
def test_bad_scheme_or_host_rejected(url):
    with pytest.raises(UnsafeUrlError):
        assert_safe_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/admin",
        "http://localhost:8000/",
        "http://169.254.169.254/latest/meta-data/",  # cloud metadata
    ],
)
def test_internal_addresses_blocked(url):
    with pytest.raises(UnsafeUrlError):
        assert_safe_url(url)
