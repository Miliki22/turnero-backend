"""Email sending helpers."""

from datetime import datetime
from email.message import EmailMessage
import logging
import smtplib
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.core.config import settings

logger = logging.getLogger(__name__)


def _send_email(to_email: str, subject: str, body: str) -> None:
    """Send an email through configured SMTP server."""
    if not settings.email_enabled:
        logger.info("EMAIL_ENABLED=false, skipping email to %s", to_email)
        return

    message = EmailMessage()
    message["From"] = settings.email_from
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(body)

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
        smtp.send_message(message)


def _to_app_tz(dt: datetime) -> datetime:
    """Normalize a datetime to application timezone."""
    try:
        app_tz = ZoneInfo(settings.tz)
    except ZoneInfoNotFoundError:
        logger.warning("Invalid TZ=%s, falling back to America/Argentina/Buenos_Aires", settings.tz)
        app_tz = ZoneInfo("America/Argentina/Buenos_Aires")

    if dt.tzinfo is None:
        return dt.replace(tzinfo=app_tz)
    return dt.astimezone(app_tz)


def send_password_reset_email(to_email: str, token: str) -> None:
    """Send password reset link to user email."""
    reset_link = f"{settings.frontend_url.rstrip('/')}/reset-password?token={token}"
    subject = "Recuperar contraseña"
    body = (
        "Recibimos una solicitud para restablecer tu contraseña.\n\n"
        f"Usá este enlace para continuar:\n{reset_link}\n\n"
        "Si no solicitaste este cambio, podés ignorar este mensaje."
    )
    _send_email(to_email=to_email, subject=subject, body=body)


def send_appointment_confirmation_email(
    client_email: str,
    admin_email: str,
    client_name: str,
    service_name: str,
    start_at: datetime,
    end_at: datetime | None,
) -> None:
    """Send appointment confirmation to client and admin."""
    start_local = _to_app_tz(start_at)
    end_local = _to_app_tz(end_at) if end_at is not None else None
    date_str = start_local.strftime("%d/%m/%Y")
    start_time_str = start_local.strftime("%H:%M")
    subject = "Turno confirmado"
    body = "\n".join(
        [
            "Turno confirmado",
            "",
            f"Cliente: {client_name}",
            f"Servicio: {service_name}",
            f"Fecha: {date_str}",
            f"Hora: {start_time_str}",
            f"Fin: {end_local.strftime('%H:%M')}" if end_local is not None else "",
        ]
    ).rstrip()
    _send_email(to_email=client_email, subject=subject, body=body)
    if admin_email and admin_email != client_email:
        _send_email(to_email=admin_email, subject=subject, body=body)
