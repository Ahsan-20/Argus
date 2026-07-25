"""Shared FastAPI dependencies.

Identity used to be whatever the client put in an X-Operator-Email header,
behind one shared passphrase everybody knew. That meant any signed in person
could read or delete anyone else's watchers by editing a header, because the
server had no way to tell the difference between "this is who I am" and "this
is who I say I am".

Identity now comes out of a signed session token and nothing else. The client
cannot claim to be someone else without the signing secret, so ownership
checks elsewhere in the app are finally worth something.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from .auth import read_token
from .config import get_settings
from .db import get_db
from .models import User

settings = get_settings()


def _bearer(header: str) -> str:
    value = (header or "").strip()
    if value.lower().startswith("bearer "):
        return value[7:].strip()
    return value


def _load(token: str, db: Session) -> User | None:
    email = read_token(token, kind="session")
    if not email:
        return None
    return db.query(User).filter(User.email == email).one_or_none()


def optional_user(
    authorization: str = Header(default=""),
    db: Session = Depends(get_db),
) -> User | None:
    """The signed in user, or None. For endpoints that are public but richer
    when they know who is asking, such as the landing page statistics."""
    return _load(_bearer(authorization), db)


def current_user(
    authorization: str = Header(default=""),
    db: Session = Depends(get_db),
) -> User:
    """The signed in user, or 401.

    Does not enforce verification: the grace period is deliberately generous
    and is checked separately, so that a brand new account can do everything
    from the first minute.
    """
    user = _load(_bearer(authorization), db)
    if not user:
        raise HTTPException(status_code=401, detail="Please sign in")
    return user


def current_email(user: User = Depends(current_user)) -> str:
    """Just the address, for the many places that only need to know whose."""
    return user.email


def verified_user(user: User = Depends(current_user)) -> User:
    """A user whose grace period has not run out unverified.

    Guards the endpoints that create work: making watchers, running checks,
    sending mail. Reading stays open on a lapsed account so nobody is locked
    out of their own data by an email they never received, and the distinct
    error code lets the frontend route to the verify screen rather than
    showing a dead end.
    """
    if user.is_verified:
        return user
    created = user.created_at
    if created and not created.tzinfo:
        created = created.replace(tzinfo=timezone.utc)
    deadline = created + timedelta(hours=settings.verify_grace_hours)
    if datetime.now(timezone.utc) > deadline:
        raise HTTPException(
            status_code=403,
            detail="verification_required",
        )
    return user


def verified_email(user: User = Depends(verified_user)) -> str:
    return user.email
