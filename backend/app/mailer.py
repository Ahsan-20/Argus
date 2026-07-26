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

    used = _deliver(msg, recipient, subject, body, html)
    return {
        "sent": True,
        "to": recipient,
        "subject": subject,
        "body": body,
        "via": used,
    }


def _deliver(msg: EmailMessage, to: str, subject: str, body: str, html: str | None) -> str:
    """Try each configured transport in turn, and return the one that worked.

    Order, and the reasoning. The Apps Script relay is best: it is reached over
    HTTPS so no host blocks it, and Gmail itself does the sending, so the mail
    authenticates and reaches inboxes. Brevo also avoids the port block but
    sends on our behalf, which fails SPF and DKIM alignment for a @gmail.com
    sender and invites the spam folder. Plain SMTP authenticates properly but
    many hosts block the ports outright.

    Genuinely falling through on failure, not just picking one and hoping. A
    relay can be deleted, hit its daily quota, or be down, and on a host where
    SMTP does work it is better to be slow than silent. Every attempt is
    bounded by its own timeout and sending happens after the response, so
    nobody is left waiting on the retries.

    Only configured transports are attempted, so this changes nothing for a
    deployment that has set up exactly one.
    """
    attempts: list[tuple[str, object]] = []
    if settings.apps_script_mail_enabled:
        attempts.append(("apps-script", lambda: _send_apps_script(to, subject, body, html)))
    if settings.brevo_api_key:
        attempts.append(("brevo", lambda: _send_http(to, subject, body, html)))
    if settings.smtp_user and settings.smtp_password:
        attempts.append(("smtp", lambda: _send(msg)))

    if not attempts:
        raise RuntimeError("no email transport is configured")

    last: Exception | None = None
    for name, send in attempts:
        try:
            send()
            if last is not None:
                logger.info("mail sent via %s after an earlier transport failed", name)
            return name
        except Exception as exc:
            last = exc
            logger.warning("mail transport %s failed: %s", name, str(exc)[:200])

    raise last


BREVO_URL = "https://api.brevo.com/v3/smtp/email"
HTTP_TIMEOUT = 20


def _send_apps_script(to: str, subject: str, body: str, html: str | None) -> None:
    """Hand the message to a Google Apps Script web app, which sends it.

    follow_redirects matters: an Apps Script web app answers with a 302 to
    script.googleusercontent.com and does the work there. Without following it
    every send would look like it failed while having quietly succeeded.

    The script answers 200 with {"ok": false} on its own errors rather than an
    HTTP error code, so the body has to be read. A transport that reports
    success because the status line looked fine is worse than one that fails.
    """
    payload = {
        "secret": settings.apps_script_mail_secret,
        "to": to,
        "subject": subject,
        "text": body,
        "fromName": settings.smtp_from_name or "Argus",
    }
    if html:
        payload["html"] = html
        payload["logoBase64"] = base64.b64encode(_LOGO_BYTES).decode()
        payload["logoCid"] = LOGO_CID

    resp = httpx.post(
        settings.apps_script_mail_url,
        json=payload,
        timeout=HTTP_TIMEOUT,
        follow_redirects=True,
    )
    if resp.status_code >= 300:
        logger.warning("apps script relay HTTP %s: %s", resp.status_code, resp.text[:200])
        raise RuntimeError(f"mail relay returned {resp.status_code}")
    try:
        result = resp.json()
    except Exception:
        logger.warning("apps script relay gave non-JSON: %s", resp.text[:200])
        raise RuntimeError("mail relay gave an unexpected response")
    if not result.get("ok"):
        logger.warning("apps script relay refused: %s", result)
        raise RuntimeError(f"mail relay refused: {result.get('error')}")


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
            # MAIL_FROM when set, else the SMTP username. An HTTP provider
            # only sends from an address it has verified, which is often not
            # the mailbox whose password happens to be in SMTP_USER.
            "email": settings.mail_from or settings.smtp_user,
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


# Deliberately short. Without any timeout smtplib inherits the global default of
# None and waits forever, but a long one is nearly as bad: where the port is
# blocked the connection is swallowed rather than refused, so the full timeout
# is spent every single time, and this transport sits at the end of a fallback
# chain that only reaches it after something else has already failed. A healthy
# SMTP server answers in under two seconds, so eight is generous for the case
# that works and cheap for the case that never will. Hosting providers routinely block outbound SMTP
# to stop their address ranges being used for spam, and a blocked port does not
# refuse the connection, it swallows it. The result is a request that never
# returns rather than an error anyone can see or handle: signing up hung
# indefinitely on a deployment where everything else worked.
SMTP_TIMEOUT = 8


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
