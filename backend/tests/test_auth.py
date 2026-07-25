"""Passwords and signed tokens. No network, no database, no keys.

These are the parts where a quiet mistake is invisible until it is exploited:
a hash that is not salted, a token whose signature is not really checked, an
expiry that is parsed but never compared. Each test below is one of those
failures, written down so it cannot come back.
"""

import time

from app.auth import (
    MIN_PASSWORD,
    email_looks_valid,
    hash_password,
    make_token,
    normalise_email,
    password_problem,
    read_token,
    verify_password,
)


# ---------------------------------------------------------------------------
# Passwords
# ---------------------------------------------------------------------------
def test_password_roundtrip():
    stored = hash_password("correct horse battery")
    assert verify_password("correct horse battery", stored)
    assert not verify_password("correct horse batteru", stored)


def test_hash_never_contains_the_password():
    """The obvious catastrophe: storing something reversible."""
    stored = hash_password("hunter2-and-then-some")
    assert "hunter2" not in stored


def test_same_password_hashes_differently():
    """Per user salt. Without it, identical passwords produce identical hashes
    and one leaked table tells you who shares a password with whom."""
    assert hash_password("same-password") != hash_password("same-password")


def test_verify_fails_closed_on_junk():
    for junk in ["", "not-a-hash", "pbkdf2_sha256$notanint$x$y", "a$b$c$d$e"]:
        assert not verify_password("anything", junk)


def test_hash_records_its_own_cost():
    """Rounds travel with the hash, so raising the cost later does not lock
    out everyone who signed up before the change."""
    cheap = hash_password("portable", rounds=1000)
    assert cheap.split("$")[1] == "1000"
    assert verify_password("portable", cheap)


def test_password_length_rules():
    assert password_problem("a" * (MIN_PASSWORD - 1))
    assert password_problem("")
    assert password_problem("a" * 5000)
    assert password_problem("a" * MIN_PASSWORD) is None


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------
def test_email_is_normalised_so_one_person_gets_one_account():
    assert normalise_email("  Sam.Rivera@EXAMPLE.com ") == "sam.rivera@example.com"


def test_email_shape():
    assert email_looks_valid("a@b.co")
    for bad in ["", "no-at-sign", "bad@", "@bad.com", "a b@c.com", "a@b"]:
        assert not email_looks_valid(bad), bad
    assert not email_looks_valid("x" * 250 + "@example.com")


# ---------------------------------------------------------------------------
# Tokens
# ---------------------------------------------------------------------------
def test_token_roundtrip():
    token = make_token("a@b.com", kind="session", seconds=60)
    assert read_token(token, kind="session") == "a@b.com"


def test_token_of_one_kind_cannot_be_used_as_another():
    """A password reset link must not double as a session, or an emailed link
    would be a permanent skeleton key."""
    reset = make_token("a@b.com", kind="reset", seconds=60)
    assert read_token(reset, kind="session") is None


def test_expired_token_is_refused():
    assert read_token(make_token("a@b.com", kind="session", seconds=-1), kind="session") is None


def test_tampered_payload_is_refused():
    """The real attack: edit the payload to claim to be someone else. Without
    a genuine signature check this is trivial, so prove it fails."""
    import base64, json

    forged = base64.urlsafe_b64encode(
        json.dumps({"sub": "victim@b.com", "kind": "session", "exp": int(time.time()) + 600}).encode()
    ).decode().rstrip("=")
    genuine = make_token("attacker@b.com", kind="session", seconds=600)
    signature = genuine.split(".")[1]
    assert read_token(f"{forged}.{signature}", kind="session") is None


def test_tampered_signature_is_refused():
    token = make_token("a@b.com", kind="session", seconds=60)
    body, sig = token.split(".")
    assert read_token(f"{body}.{sig[:-2]}zz", kind="session") is None


def test_malformed_tokens_never_raise():
    """Anything can arrive in a URL. None of it should reach a traceback."""
    for junk in ["", "no-dot", "a.b.c", "....", "!!!.???", None]:
        assert read_token(junk, kind="session") is None


# ---------------------------------------------------------------------------
# Endpoints an uptime monitor watches
# ---------------------------------------------------------------------------
def test_monitored_paths_answer_head_as_well_as_get():
    """Uptime monitors commonly probe with HEAD, not GET, because it costs a
    fraction of the bandwidth.

    FastAPI's @app.get registers GET alone, unlike plain Starlette which adds
    HEAD alongside it. That difference had the deployed service returning 405
    Method Not Allowed to every probe and being reported as down while it was
    serving traffic perfectly well. The response time graph was the giveaway:
    it kept recording times right through the supposed outage.
    """
    from fastapi.testclient import TestClient

    from app.main import app

    # No lifespan: this asserts routing only, and starting it would reach for
    # a database and a scheduler that these tests deliberately do without.
    client = TestClient(app)
    for path in ("/", "/health"):
        assert client.get(path).status_code == 200, path
        assert client.head(path).status_code == 200, path
