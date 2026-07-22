"""Shared FastAPI dependencies."""

from fastapi import Header, HTTPException

from .config import get_settings

settings = get_settings()


def require_access(x_access_code: str = Header(default="")) -> None:
    """Gate an endpoint behind the shared access code.

    If ACCESS_CODE is unset (local dev), the gate is open. In production it is
    set, and the frontend sends it as the X-Access-Code header after the user
    enters the passphrase once.
    """
    if settings.access_code and x_access_code != settings.access_code:
        raise HTTPException(status_code=401, detail="invalid or missing access code")
