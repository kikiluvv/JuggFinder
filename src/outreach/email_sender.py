"""
SMTP email sender for outreach automation.

Runs blocking SMTP calls in a thread so API handlers stay async-friendly.
"""

from __future__ import annotations

import asyncio
import smtplib
from email.message import EmailMessage
from email.utils import formataddr

from src.config.settings import settings
from src.utils.logging import get_logger

logger = get_logger(__name__)


class OutreachEmailError(Exception):
    """Raised when outreach email sending cannot be completed safely."""


def _build_message(*, to_email: str, subject: str, body: str) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = formataddr((settings.outreach_sender_name, settings.outreach_sender_email))
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body.strip())
    return msg


def _validate_send_configuration() -> None:
    required = {
        "OUTREACH_SENDER_EMAIL": settings.outreach_sender_email,
        "SMTP_HOST": settings.smtp_host,
        "SMTP_USERNAME": settings.smtp_username,
        "SMTP_PASSWORD": settings.smtp_password,
    }
    missing = [k for k, v in required.items() if not v.strip()]
    if missing:
        raise OutreachEmailError(
            f"Missing SMTP configuration: {', '.join(missing)}. Check your .env."
        )


def _send_blocking(*, to_email: str, subject: str, body: str) -> str | None:
    _validate_send_configuration()
    msg = _build_message(to_email=to_email, subject=subject, body=body)

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as server:
        if settings.smtp_use_tls:
            server.starttls()
        server.login(settings.smtp_username, settings.smtp_password)
        result = server.send_message(msg)
        # send_message returns a dict of failed recipients; empty means success.
        if result:
            raise OutreachEmailError(f"SMTP rejected recipient(s): {result}")
    return msg.get("Message-ID")


async def send_outreach_email(*, to_email: str, subject: str, body: str) -> str | None:
    """
    Send one outreach email. Returns Message-ID when available.
    Raises OutreachEmailError for expected configuration/delivery failures.
    """
    try:
        message_id = await asyncio.to_thread(
            _send_blocking,
            to_email=to_email,
            subject=subject,
            body=body,
        )
        logger.info(f"Outreach email sent to {to_email}")
        return message_id
    except OutreachEmailError:
        raise
    except Exception as e:
        logger.error(f"Unexpected SMTP send failure to {to_email}: {e}")
        raise OutreachEmailError(str(e)) from e
