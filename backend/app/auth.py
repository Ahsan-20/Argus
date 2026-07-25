"""Passwords, session tokens, and email checking.

Deliberately stdlib only. bcrypt and argon2 ship compiled wheels and PyJWT is
one more thing to remember to install on the host; none of them buy anything
here that hashlib and hmac do not already provide correctly. Fewer moving
parts is worth real money when the app has to come up first time on a machine
you cannot debug.

Two primitives:

  * Passwords are stretched with PBKDF2-HMAC-SHA256 over a per user random
    salt. Never stored, never logged, never recoverable: a forgotten password
    is replaced, not looked up.
  * Session and reset tokens are payloads signed with HMAC-SHA256. The user
    can read their own token, which is fine, but cannot change a single byte
    of it without the secret. Every comparison is constant time.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import secrets
import time

from .config import get_settings

settings = get_settings()

# Cost of checking one password. Enough to make guessing expensive, small
# enough that a real login stays instant. Stored per hash, so this can be
# raised later without invalidating anyone: old hashes keep verifying at the
# number they were written with.
PBKDF2_ROUNDS = 240_000
SALT_BYTES = 16
MIN_PASSWORD = 8
MAX_PASSWORD = 200  # a megabyte password is a denial of service, not security

# Deliberately boring. Exotic but technically legal addresses are rarer than
# typos, and the verification email is the real proof that an address exists.
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
MAX_EMAIL = 254  # RFC 5321


# A blank secret in development gets a random one per boot rather than a
# constant. Tokens then die on restart, which is a visible annoyance instead
# of an invisible hole: nobody can ship a guessable signing key by accident.
_FALLBACK_SECRET = secrets.token_urlsafe(48)


def _secret() -> bytes:
    return (settings.secret_key or _FALLBACK_SECRET).encode()


# --------------------------------------------------------------------------
# Email
# --------------------------------------------------------------------------
def normalise_email(raw: str) -> str:
    """Trim and lowercase. Addresses are case insensitive in practice, and
    storing them one way stops Ali@x.com and ali@x.com becoming two accounts."""
    return (raw or "").strip().lower()


def email_looks_valid(email: str) -> bool:
    return bool(email) and len(email) <= MAX_EMAIL and bool(EMAIL_RE.match(email))


# --------------------------------------------------------------------------
# Passwords
# --------------------------------------------------------------------------
def password_problem(password: str) -> str | None:
    """Why this password is unacceptable, or None if it is fine.

    Length only. Forced symbol and digit rules push people towards Passw0rd!
    and a sticky note, which is worse than a long thing they can remember.
    """
    if not password or len(password) < MIN_PASSWORD:
        return f"Use at least {MIN_PASSWORD} characters"
    if len(password) > MAX_PASSWORD:
        return "That password is too long"
    return None


def hash_password(password: str, *, rounds: int = PBKDF2_ROUNDS) -> str:
    """Store as algorithm$rounds$salt$hash, so the parameters travel with the
    hash and can be changed later without stranding existing accounts."""
    salt = secrets.token_bytes(SALT_BYTES)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, rounds)
    return "$".join(
        [
            "pbkdf2_sha256",
            str(rounds),
            base64.b64encode(salt).decode(),
            base64.b64encode(digest).decode(),
        ]
    )


def verify_password(password: str, stored: str) -> bool:
    """Constant time check. Any malformed stored value fails closed."""
    try:
        algo, rounds_s, salt_b64, hash_b64 = (stored or "").split("$")
        if algo != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode(),
            base64.b64decode(salt_b64),
            int(rounds_s),
        )
        return hmac.compare_digest(digest, base64.b64decode(hash_b64))
    except Exception:
        return False


# --------------------------------------------------------------------------
# Signed tokens
# --------------------------------------------------------------------------
def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def make_token(subject: str, *, kind: str, seconds: int) -> str:
    """A signed, self expiring token. `kind` stops one being used as another:
    a password reset link cannot be replayed as a session."""
    payload = {"sub": subject, "kind": kind, "exp": int(time.time()) + seconds}
    body = _b64(json.dumps(payload, separators=(",", ":")).encode())
    sig = hmac.new(_secret(), body.encode(), hashlib.sha256).digest()
    return f"{body}.{_b64(sig)}"


def read_token(token: str, *, kind: str) -> str | None:
    """The subject if the token is genuine, unexpired and of the right kind.

    Signature is checked before the payload is trusted for anything, and with
    compare_digest so a near miss cannot be walked towards a hit by timing.
    """
    try:
        body, sig = (token or "").split(".")
        expected = hmac.new(_secret(), body.encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(_unb64(sig), expected):
            return None
        payload = json.loads(_unb64(body))
        if payload.get("kind") != kind:
            return None
        if int(payload.get("exp", 0)) < time.time():
            return None
        return payload.get("sub") or None
    except Exception:
        return None


def session_token(email: str) -> str:
    return make_token(email, kind="session", seconds=settings.session_days * 86400)


def reset_token(email: str) -> str:
    return make_token(email, kind="reset", seconds=settings.reset_token_hours * 3600)


def verify_token(email: str) -> str:
    """Verification links stay valid well past the grace period, so a link
    found in an inbox a week later still works instead of dead ending."""
    return make_token(email, kind="verify", seconds=14 * 86400)
