"""Alert delivery across channels.

One place decides how an alert reaches the user. Email is always on. WhatsApp
(via CallMeBot) turns on automatically once WHATSAPP_PHONE and WHATSAPP_APIKEY
are set, so adding it later is a config change, not a code change.

Every channel is exception-isolated: one failing channel never breaks a run or
blocks the others, and its error is returned for the mission log.
"""

import logging

import httpx

from .config import get_settings
from .mailer import send_alert as _send_email

logger = logging.getLogger("argus.notify")
settings = get_settings()

CALLMEBOT_URL = "https://api.callmebot.com/whatsapp.php"


def deliver_alert(*, email: str, subject: str, body: str, html: str | None = None) -> dict:
    """Send an alert on every enabled channel. Returns per-channel results."""
    results: dict[str, dict] = {}

    try:
        results["email"] = _send_email(to=email, subject=subject, body=body, html=html)
    except Exception as exc:  # a bad SMTP send must not crash the run
        logger.warning("email channel failed: %s", exc)
        results["email"] = {"sent": False, "error": str(exc)[:300]}

    if settings.whatsapp_enabled:
        results["whatsapp"] = _send_whatsapp(f"{subject}\n\n{body}")

    return results


def _send_whatsapp(text: str) -> dict:
    """Send via CallMeBot. Free, keyless setup, opt-in recipients only.

    Implemented and ready; stays dormant until the two WHATSAPP_ env vars are
    set, at which point deliver_alert starts including it with no other change.
    """
    try:
        resp = httpx.get(
            CALLMEBOT_URL,
            params={
                "phone": settings.whatsapp_phone,
                "text": text[:900],  # CallMeBot truncates very long messages
                "apikey": settings.whatsapp_apikey,
            },
            timeout=20,
        )
        ok = resp.status_code == 200
        if not ok:
            logger.warning("whatsapp channel HTTP %s: %s", resp.status_code, resp.text[:150])
        return {"sent": ok, "to": settings.whatsapp_phone, "status": resp.status_code}
    except Exception as exc:
        logger.warning("whatsapp channel failed: %s", exc)
        return {"sent": False, "error": str(exc)[:300]}
