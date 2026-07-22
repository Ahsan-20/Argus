"""Email delivery via SMTP (e.g. Gmail with an App Password).

A single shared sender account delivers alerts to whatever address the user
set on their watcher, so notifications actually reach the intended person (no
verified domain needed). Every sent alert is also rendered inside the app.
"""

import smtplib
import ssl
from email.message import EmailMessage

from .config import get_settings

settings = get_settings()


def send_alert(
    *, to: str, subject: str, body: str, html: str | None = None
) -> dict:
    """Send an alert email and return a small result dict for the event log.

    Falls back to a non-sending preview (so the trigger flow stays testable)
    when SMTP credentials are not configured yet.
    """
    recipient = to or settings.owner_email
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
    msg.set_content(body)
    if html:
        msg.add_alternative(html, subtype="html")

    _send(msg)
    return {"sent": True, "to": recipient, "subject": subject, "body": body}


def _send(msg: EmailMessage) -> None:
    """Deliver over SSL (port 465) or STARTTLS (port 587, Gmail's default)."""
    context = ssl.create_default_context()
    if settings.smtp_port == 465:
        with smtplib.SMTP_SSL(
            settings.smtp_host, settings.smtp_port, context=context
        ) as server:
            server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)
    else:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.starttls(context=context)
            server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)
