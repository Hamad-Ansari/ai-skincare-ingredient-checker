"""Minimal SMTP adapter for verification and password-reset email messages."""

from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage

from backend.app.core.config import Settings


class AuthEmailDeliveryError(Exception):
    """A safe, transport-agnostic email delivery failure."""


def send_auth_email(settings: Settings, recipient: str, subject: str, body: str) -> None:
    """Send a text-only account email without logging its token or message body."""
    if not settings.mail_is_configured or not settings.mail_host or not settings.mail_from:
        if settings.app_env in {"development", "test"} and settings.auth_expose_dev_tokens:
            return
        raise AuthEmailDeliveryError("Email delivery is not configured")

    message = EmailMessage()
    message["From"] = str(settings.mail_from)
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)

    try:
        with smtplib.SMTP(settings.mail_host, settings.mail_port, timeout=10) as smtp:
            smtp.ehlo()
            if settings.mail_starttls:
                smtp.starttls(context=ssl.create_default_context())
                smtp.ehlo()
            if settings.mail_username and settings.mail_password:
                smtp.login(settings.mail_username, settings.mail_password.get_secret_value())
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        raise AuthEmailDeliveryError("Account email could not be delivered") from exc
