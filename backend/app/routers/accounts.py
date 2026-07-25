"""Accounts: sign up, sign in, verify an address, reset a forgotten password.

Two rules shape most of the decisions here.

**Never confirm whether an address has an account.** Sign up, sign in and
"forgot password" all answer the same way whether or not the address is known.
An endpoint that says "no such user" is a free membership check, and people
reuse passwords across sites, so leaking who is registered here is a favour to
whoever turns up with a list of credentials from somewhere else.

**A new account works immediately.** Verification matters, but demanding it
before the first look costs you the person who was only half interested. So a
new account is usable for a grace period, is nagged about it in the app, and
only then has to verify. That also means someone can be handed the link and
try the thing without a detour through their inbox.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth import (
    email_looks_valid,
    hash_password,
    normalise_email,
    password_problem,
    read_token,
    reset_token,
    session_token,
    verify_password,
    verify_token,
)
from ..config import get_settings
from ..db import get_db
from ..deps import current_user, optional_user
from ..email_templates import render_account_html
from ..mailer import send_alert
from ..models import User

logger = logging.getLogger("argus.accounts")
settings = get_settings()
router = APIRouter(prefix="/auth", tags=["auth"])

# Guessing defences. Lock briefly rather than forever: an attacker must not be
# able to lock a real person out of their own account by getting it wrong on
# purpose, so the lock always expires by itself.
MAX_FAILED_LOGINS = 8
LOCKOUT_MINUTES = 15
# Stops the resend button being used as a way to post mail to a stranger.
RESEND_COOLDOWN_SECONDS = 60


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime | None) -> datetime | None:
    """Postgres hands these back timezone aware, SQLite does not. Comparing an
    aware and a naive datetime raises, which would turn a cosmetic difference
    between environments into a 500 on the login path."""
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _link(path: str, token: str) -> str:
    base = (settings.frontend_base_url or "").rstrip("/")
    return f"{base}{path}?token={token}"


# --------------------------------------------------------------------------
# Outgoing mail
# --------------------------------------------------------------------------
def _send_verification(user: User) -> None:
    url = _link("/verify", verify_token(user.email))
    hours = settings.verify_grace_hours
    body = (
        "Confirm this is your address and your account is yours for good. "
        f"Until you do, Argus keeps working for {hours} hours, then pauses "
        "until it is confirmed."
    )
    send_alert(
        to=user.email,
        subject="Confirm your Argus account",
        body=body,
        html=render_account_html(
            heading="Confirm your email",
            body=body,
            cta_label="Confirm my email",
            cta_url=url,
            expiry_note="This link works for 14 days.",
            footnote=(
                "You are getting this because someone signed up to Argus with "
                "this address. If that was not you, ignore this email and "
                "nothing will happen."
            ),
        ),
    )


def _send_reset(user: User) -> None:
    url = _link("/reset", reset_token(user.email))
    body = (
        "Pick a new password and you are back in. If you did not ask for "
        "this, nothing has changed and you can ignore this email."
    )
    send_alert(
        to=user.email,
        subject="Reset your Argus password",
        body=body,
        html=render_account_html(
            heading="Reset your password",
            body=body,
            cta_label="Choose a new password",
            cta_url=url,
            expiry_note=(
                f"This link works for {settings.reset_token_hours} hour and "
                "once only."
            ),
            footnote=(
                "You are getting this because a password reset was requested "
                "for this address on Argus."
            ),
        ),
    )


# --------------------------------------------------------------------------
# Shapes
# --------------------------------------------------------------------------
class Credentials(BaseModel):
    email: str
    password: str


class EmailOnly(BaseModel):
    email: str


class TokenOnly(BaseModel):
    token: str


class NewPassword(BaseModel):
    token: str
    password: str


def _account_state(user: User) -> dict:
    """What the frontend needs to decide between letting someone in, nagging
    them, or sending them to the verify wall."""
    deadline = _aware(user.created_at) + timedelta(hours=settings.verify_grace_hours)
    remaining = (deadline - _now()).total_seconds()
    return {
        "email": user.email,
        "is_verified": user.is_verified,
        "grace_hours_left": max(0, round(remaining / 3600, 1)),
        "grace_expired": (not user.is_verified) and remaining <= 0,
    }


def _signed_in(user: User) -> dict:
    return {"token": session_token(user.email), "user": _account_state(user)}


# --------------------------------------------------------------------------
# Endpoints
# --------------------------------------------------------------------------
@router.post("/signup")
def signup(payload: Credentials, db: Session = Depends(get_db)) -> dict:
    email = normalise_email(payload.email)
    if not email_looks_valid(email):
        raise HTTPException(400, "That does not look like an email address")
    problem = password_problem(payload.password or "")
    if problem:
        raise HTTPException(400, problem)

    existing = db.query(User).filter(User.email == email).one_or_none()
    if existing:
        # Deliberately the same wording the sign in page uses for a wrong
        # password, and deliberately not "that email is taken". Someone who
        # already has an account is told to sign in, which is what they need
        # to hear, without confirming the account exists to a stranger.
        raise HTTPException(409, "That address already has an account. Try signing in.")

    user = User(email=email, password_hash=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)

    # A mail server having a bad day must not cost someone their account: it
    # exists, they are signed in, and they can ask for the email again.
    try:
        _send_verification(user)
        user.verify_sent_at = _now()
        db.commit()
    except Exception as exc:
        logger.warning("verification email failed for %s: %s", email, exc)

    return _signed_in(user)


@router.post("/login")
def login(payload: Credentials, db: Session = Depends(get_db)) -> dict:
    email = normalise_email(payload.email)
    user = db.query(User).filter(User.email == email).one_or_none()

    # One message for "no such account" and for "wrong password". Which of the
    # two it was is exactly what an attacker wants to know.
    wrong = HTTPException(401, "Email or password is not right")

    if not user:
        raise wrong

    locked = _aware(user.locked_until)
    if locked and locked > _now():
        wait = max(1, round((locked - _now()).total_seconds() / 60))
        raise HTTPException(
            429, f"Too many attempts. Try again in about {wait} minutes."
        )

    if not verify_password(payload.password or "", user.password_hash):
        user.failed_logins = (user.failed_logins or 0) + 1
        if user.failed_logins >= MAX_FAILED_LOGINS:
            user.locked_until = _now() + timedelta(minutes=LOCKOUT_MINUTES)
            user.failed_logins = 0
        db.commit()
        raise wrong

    user.failed_logins = 0
    user.locked_until = None
    user.last_login_at = _now()
    db.commit()
    return _signed_in(user)


@router.get("/me")
def me(user: User = Depends(current_user)) -> dict:
    return _account_state(user)


@router.post("/verify")
def verify(payload: TokenOnly, db: Session = Depends(get_db)) -> dict:
    email = read_token(payload.token, kind="verify")
    if not email:
        raise HTTPException(400, "That link is not valid or has expired")
    user = db.query(User).filter(User.email == email).one_or_none()
    if not user:
        raise HTTPException(400, "That link is not valid or has expired")

    # Clicking an old link again is not an error worth showing anyone.
    if not user.is_verified:
        user.is_verified = True
        user.verified_at = _now()
        db.commit()

    # A token is returned so someone who verified from the link on a different
    # device lands signed in rather than at a login form.
    return _signed_in(user)


@router.post("/resend")
def resend(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    if user.is_verified:
        return {"sent": False, "detail": "Already confirmed"}

    last = _aware(user.verify_sent_at)
    if last and (_now() - last).total_seconds() < RESEND_COOLDOWN_SECONDS:
        wait = RESEND_COOLDOWN_SECONDS - int((_now() - last).total_seconds())
        raise HTTPException(429, f"Just sent one. Try again in {wait} seconds.")

    try:
        _send_verification(user)
    except Exception as exc:
        # A mail server having a moment is not the pusher's fault. Say so
        # plainly, and leave verify_sent_at alone so the cooldown does not
        # start on an email that never went anywhere: they can press again
        # immediately rather than waiting a minute for nothing.
        logger.warning("resend failed for %s: %s", user.email, exc)
        raise HTTPException(
            502, "Could not send it just now. Try again in a moment."
        )

    user.verify_sent_at = _now()
    db.commit()
    return {"sent": True}


@router.post("/forgot")
def forgot(payload: EmailOnly, db: Session = Depends(get_db)) -> dict:
    """Always the same answer, whether or not the address is known.

    Anything else turns this into a way to ask "does this person have an
    account here?" and get a straight answer, thousands of times an hour.
    """
    email = normalise_email(payload.email)
    if email_looks_valid(email):
        user = db.query(User).filter(User.email == email).one_or_none()
        if user:
            try:
                _send_reset(user)
                user.reset_requested_at = _now()
                # Any reset link issued earlier stops working now.
                user.reset_used_at = None
                db.commit()
            except Exception as exc:
                logger.warning("reset email failed for %s: %s", email, exc)
    return {"ok": True}


@router.post("/reset")
def reset(payload: NewPassword, db: Session = Depends(get_db)) -> dict:
    email = read_token(payload.token, kind="reset")
    if not email:
        raise HTTPException(400, "That reset link is not valid or has expired")
    problem = password_problem(payload.password or "")
    if problem:
        raise HTTPException(400, problem)

    user = db.query(User).filter(User.email == email).one_or_none()
    if not user:
        raise HTTPException(400, "That reset link is not valid or has expired")

    # Single use. The token is still inside its expiry window, so without this
    # the same link in a forwarded email would keep working.
    requested = _aware(user.reset_requested_at)
    used = _aware(user.reset_used_at)
    if not requested or (used and used >= requested):
        raise HTTPException(400, "That reset link has already been used")

    user.password_hash = hash_password(payload.password)
    user.reset_used_at = _now()
    user.failed_logins = 0
    user.locked_until = None
    # Getting into the inbox proves the address, which is what verification
    # was asking for anyway.
    if not user.is_verified:
        user.is_verified = True
        user.verified_at = _now()
    db.commit()
    return _signed_in(user)


@router.get("/state")
def state(user: User | None = Depends(optional_user)) -> dict:
    """Cheap "am I still signed in" for app boot. Never 401s, so the landing
    page can ask without a stale token bouncing a first time visitor."""
    return {"signed_in": bool(user), "user": _account_state(user) if user else None}
