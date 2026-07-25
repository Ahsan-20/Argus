"""Being a good guest on other people's servers. No network, no keys.

Argus polls the same page over and over, which is the traffic pattern most
likely to annoy a site owner into blocking us. These lock in the habits that
prevent that: honest identification, obeying robots.txt, spacing out requests,
and asking whether anything changed before asking for the page again.
"""

import time
from urllib.robotparser import RobotFileParser

import pytest

from app import fetcher
from app.fetcher import (
    UA_TOKEN,
    BlockedByRobotsError,
    Fetched,
    _retry_after_seconds,
    _robots_check,
    _throttle,
    user_agent,
)


class _Resp:
    def __init__(self, headers):
        self.headers = headers


# ---- identification --------------------------------------------------------
def test_identifies_itself_rather_than_faking_a_browser():
    ua = user_agent()
    assert UA_TOKEN in ua           # says what it is
    assert "+http" in ua            # says where to complain
    assert "Chrome/" not in ua      # does not pretend to be a person
    assert "Safari/" not in ua


def test_user_agent_is_overridable(monkeypatch):
    monkeypatch.setattr(fetcher.settings, "user_agent", "CustomBot/2.0 (+mail@x.io)")
    assert user_agent() == "CustomBot/2.0 (+mail@x.io)"


# ---- robots.txt ------------------------------------------------------------
def _robots(body: str):
    rp = RobotFileParser()
    rp.parse(body.splitlines())
    return rp


def test_disallowed_path_is_refused(monkeypatch):
    monkeypatch.setattr(
        fetcher, "_robots_for", lambda origin: _robots("User-agent: *\nDisallow: /private")
    )
    with pytest.raises(BlockedByRobotsError):
        _robots_check("https://example.com/private/thing")


def test_allowed_path_passes(monkeypatch):
    monkeypatch.setattr(
        fetcher, "_robots_for", lambda origin: _robots("User-agent: *\nDisallow: /private")
    )
    assert _robots_check("https://example.com/public") >= 0


def test_crawl_delay_is_honoured(monkeypatch):
    monkeypatch.setattr(
        fetcher, "_robots_for",
        lambda origin: _robots("User-agent: *\nCrawl-delay: 12\nDisallow:"),
    )
    assert _robots_check("https://example.com/") == 12.0


def test_absurd_crawl_delay_is_capped(monkeypatch):
    monkeypatch.setattr(
        fetcher, "_robots_for",
        lambda origin: _robots("User-agent: *\nCrawl-delay: 9999\nDisallow:"),
    )
    assert _robots_check("https://example.com/") == fetcher.settings.max_crawl_delay_seconds


def test_missing_robots_means_allowed(monkeypatch):
    monkeypatch.setattr(fetcher, "_robots_for", lambda origin: None)
    assert _robots_check("https://example.com/anything") >= 0


def test_robots_can_be_switched_off(monkeypatch):
    monkeypatch.setattr(fetcher.settings, "respect_robots", False)
    monkeypatch.setattr(
        fetcher, "_robots_for", lambda origin: _robots("User-agent: *\nDisallow: /")
    )
    assert _robots_check("https://example.com/private") >= 0


# ---- spacing requests out --------------------------------------------------
def test_second_hit_on_a_host_waits():
    fetcher._last_hit.pop("spacing.test", None)
    start = time.time()
    _throttle("spacing.test", 0.4)
    _throttle("spacing.test", 0.4)
    assert time.time() - start >= 0.35


def test_different_hosts_do_not_block_each_other():
    fetcher._last_hit.pop("a.test", None)
    fetcher._last_hit.pop("b.test", None)
    start = time.time()
    _throttle("a.test", 5.0)
    _throttle("b.test", 5.0)
    assert time.time() - start < 1.0


# ---- backing off when asked ------------------------------------------------
def test_retry_after_seconds_is_used():
    assert _retry_after_seconds(_Resp({"retry-after": "20"})) == 20.0


def test_retry_after_is_capped():
    assert _retry_after_seconds(_Resp({"retry-after": "9999"})) == 60.0


def test_missing_retry_after_still_pauses():
    assert _retry_after_seconds(_Resp({})) > 0


# ---- conditional requests --------------------------------------------------
def test_not_modified_carries_no_body_but_keeps_validators():
    f = Fetched(not_modified=True, etag='W/"abc"', last_modified="Fri, 25 Jul 2026 06:00:00 GMT")
    assert f.not_modified
    assert f.text == ""
    assert f.etag == 'W/"abc"'
