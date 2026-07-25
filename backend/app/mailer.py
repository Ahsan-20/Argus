"""Email delivery, over an HTTP API where one is configured, otherwise SMTP.

A single shared sender account delivers alerts to whatever address the user set
on their watcher, so notifications reach the intended person with no verified
domain needed. Every sent alert is also rendered inside the app, so a message
is never only in an inbox.

**Why there are two transports.** SMTP is the simpler one and needs no third
party, but hosting providers routinely block outbound SMTP ports to stop their
address ranges being used for spam, and a blocked port does not refuse the
connection, it swallows it. The symptom is not an error, it is a request that
never returns. Measured on the deployed host: 20 seconds to a timeout, every
time.

An HTTP mail API goes out over 443 like any other request, so it is unaffected.
Set BREVO_API_KEY and mail goes that way; leave it blank and nothing changes.
"""

import base64
import logging
import smtplib
import ssl
from email.message import EmailMessage

import httpx

from .branding import LOGO_CID, LOGO_DATA_URI
from .config import get_settings

settings = get_settings()
logger = logging.getLogger("argus.mailer")

# Raw logo bytes, embedded inline as a CID attachment. Email clients (Gmail in
# particular) strip `data:` image URLs, so the logo must be a real attached
# part referenced by `cid:` to actually render in a received email.
_LOGO_BYTES = base64.b64decode(LOGO_DATA_URI.split(",", 1)[1])


def _one_line(value: str) -> str:
    """Collapse newlines so a crafted subject/recipient cannot inject headers.

    An attacker-controlled value with a CR/LF could otherwise smuggle extra
    SMTP headers (a Bcc, a second body). Header values are single line by
    definition, so flattening them is both safe and lossless here.
    """
    return " ".join((value or "").splitlines()).strip()


def send_alert(
    *, to: str, subject: str, body: str, html: str | None = None
) -> dict:
    """Send an alert email and return a small result dict for the event log.

    Falls back to a non-sending preview (so the trigger flow stays testable)
    when SMTP credentials are not configured yet.
    """
    recipient = _one_line(to or settings.owner_email)
    subject = _one_line(subject)[:200] or "Argus alert"
    if not settings.smtp_user or not settings.smtp_password:
        return {
            "sent": False,
            "to": recipient,
            "subject": subject,
            "body": body,
            "note": "SMTP not configured",
        }

    msg = EmailMessage()
    msg["From"] = f"{settings.smtp_from_name} <{settings.smtp_user}>"
    msg["To"] = recipient
    msg["Subject"] = subject
    msg.set_content(body)  # plain-text part
    if html:
        msg.add_alternative(html, subtype="html")  # preferred part
        # Attach the logo inline, related to the HTML part, referenced by cid.
        html_part = msg.get_payload()[1]
        html_part.add_related(
            _LOGO_BYTES, maintype="image", subtype="png", cid=LOGO_CID
        )

    if settings.brevo_api_key:
        _send_http(recipient, subject, body, html)
    else:
        _send(msg)
    return {"sent": True, "to": recipient, "subject": subject, "body": body}


BREVO_URL = "https://api.brevo.com/v3/smtp/email"
HTTP_TIMEOUT = 20


def _send_http(to: str, subject: str, body: str, html: str | None) -> None:
    """Send over Brevo's HTTP API, which leaves on 443 like any other request.

    The logo travels as a real attachment with a content id, exactly as it does
    over SMTP, because Gmail strips `data:` image URLs and would otherwise show
    a broken image in place of the mark.

    Raises on failure rather than swallowing it. Every caller either runs
    outside the request or already handles the error, and a send that quietly
    reports success is worse than one that fails loudly.
    """
    payload: dict = {
        "sender": {
            "email": settings.smtp_user,
            "name": settings.smtp_from_name or "Argus",
        },
        "to": [{"email": to}],
        "subject": subject,
        "textContent": body,
    }
    if html:
        payload["htmlContent"] = html
        payload["attachment"] = [
            {
                "content": base64.b64encode(_LOGO_BYTES).decode(),
                "name": "argus.png",
                # Brevo maps this to a cid: reference, so the same
                # cid:LOGO_CID in the HTML resolves on both transports.
                "contentId": LOGO_CID,
            }
        ]

    resp = httpx.post(
        BREVO_URL,
        json=payload,
        headers={"api-key": settings.brevo_api_key, "accept": "application/json"},
        timeout=HTTP_TIMEOUT,
    )
    if resp.status_code >= 300:
        logger.warning("brevo send failed %s: %s", resp.status_code, resp.text[:200])
        raise RuntimeError(f"mail API returned {resp.status_code}")


# Without this, smtplib inherits the global default socket timeout, which is
# None, meaning wait forever. Hosting providers routinely block outbound SMTP
# to stop their address ranges being used for spam, and a blocked port does not
# refuse the connection, it swallows it. The result is a request that never
# returns rather than an error anyone can see or handle: signing up hung
# indefinitely on a deployment where everything else worked.
SMTP_TIMEOUT = 20


def _send(msg: EmailMessage) -> None:
    """Deliver over SSL (port 465) or STARTTLS (port 587, Gmail's default)."""
    context = ssl.create_default_context()
    if settings.smtp_port == 465:
        with smtplib.SMTP_SSL(
            settings.smtp_host,
            settings.smtp_port,
            context=context,
            timeout=SMTP_TIMEOUT,
        ) as server:
            server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)
    else:
        with smtplib.SMTP(
            settings.smtp_host, settings.smtp_port, timeout=SMTP_TIMEOUT
        ) as server:
            server.starttls(context=context)
            server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)
