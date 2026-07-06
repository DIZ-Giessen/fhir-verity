"""Transactional email notifications via SMTP (implicit SSL, port 465).

smtplib is synchronous; every send is offloaded to a worker thread via
asyncio.to_thread so the validation task's event loop is never blocked.
Failures are swallowed and logged: a notification must never affect run state.
"""

import asyncio
import logging
import smtplib
import ssl
from email.message import EmailMessage

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def _send_sync(to_address: str, subject: str, body: str) -> None:
    """Blocking SMTP send. Runs inside a worker thread.

    Supports both transports: implicit SSL (EMAIL_USE_SSL=True, typically the
    original meaning of port 465) and STARTTLS (EMAIL_USE_SSL=False, typical for
    587 and for 465-servers configured for explicit TLS).
    """
    msg = EmailMessage()
    msg["From"] = settings.EMAIL_ADDRESS
    msg["To"] = to_address
    msg["Subject"] = subject
    msg.set_content(body)

    context = ssl.create_default_context()
    if not settings.EMAIL_VERIFY_CERT:
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

    if settings.EMAIL_USE_SSL:
        with smtplib.SMTP_SSL(
            settings.EMAIL_HOST, settings.EMAIL_HOST_PORT, context=context, timeout=30
        ) as server:
            server.login(settings.EMAIL_USER, settings.EMAIL_PASSWORD)
            server.send_message(msg)
    else:
        with smtplib.SMTP(
            settings.EMAIL_HOST, settings.EMAIL_HOST_PORT, timeout=30
        ) as server:
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            server.login(settings.EMAIL_USER, settings.EMAIL_PASSWORD)
            server.send_message(msg)


async def send_email(to_address: str, subject: str, body: str) -> None:
    """Fire-and-forget email. Never raises; logs on failure."""
    if not settings.EMAIL_ENABLED:
        return
    if not settings.EMAIL_HOST or not to_address:
        return
    try:
        await asyncio.to_thread(_send_sync, to_address, subject, body)
        logger.info("Notification email sent to %s", to_address)
    except Exception as exc:
        logger.error("Failed to send email to %s: %s", to_address, exc)


def build_run_notification(
    *,
    recipient_name: str | None,
    status: str,
    server_name: str,
    total_processed: int,
    total_invalid: int,
    run_url: str,
    error_message: str | None = None,
) -> tuple[str, str]:
    """Return (subject, body) for a finished validation run."""
    greeting = f"Hallo {recipient_name}," if recipient_name else "Hallo,"

    if status == "completed":
        subject = f"Validierung abgeschlossen — {server_name}"
        outcome = (
            f"Die Validierung auf '{server_name}' wurde erfolgreich abgeschlossen.\n\n"
            f"Geprüfte Ressourcen: {total_processed}\n"
            f"Invalide Ressourcen: {total_invalid}"
        )
    else:  # failed
        subject = f"Validierung fehlgeschlagen — {server_name}"
        outcome = (
            f"Die Validierung auf '{server_name}' ist fehlgeschlagen.\n\n"
            f"Fehler: {error_message or 'unbekannt'}"
        )

    body = (
        f"{greeting}\n\n"
        f"{outcome}\n\n"
        f"Details ansehen: {run_url}\n\n"
        f"Diese Nachricht wurde automatisch von FHIR Verity gesendet."
    )
    return subject, body
