"""SMTP mailer — no-op when SMTP keys missing."""
from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage
from typing import Optional

from app.config import get_settings
from package.logger import get_logger

logger = get_logger(__name__)


def send_email(to: str, subject: str, html: str, text: Optional[str] = None) -> bool:
    settings = get_settings()
    if settings.is_dev and not settings.mail_configured:
        return False
    if not settings.mail_configured:
        logger.warning("Mail not configured — skip send to %s", to)
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"{settings.mail_from_name} <{settings.mail_from_email}>"
    msg["To"] = to
    msg["Reply-To"] = settings.mail_from_email
    msg.set_content(text or "Please view this email in an HTML-capable client.")
    msg.add_alternative(html, subtype="html")

    try:
        context = ssl.create_default_context()
        timeout = 8
        if settings.smtp_port == 465:
            with smtplib.SMTP_SSL(
                settings.smtp_host, settings.smtp_port, context=context, timeout=timeout
            ) as smtp:
                smtp.login(settings.smtp_user, settings.smtp_pass)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=timeout) as smtp:
                smtp.ehlo()
                smtp.starttls(context=context)
                smtp.ehlo()
                smtp.login(settings.smtp_user, settings.smtp_pass)
                smtp.send_message(msg)
        logger.info("Email sent to %s (%s)", to, subject)
        return True
    except Exception:
        logger.exception("Failed to send email to %s", to)
        return False


def send_otp_email(to: str, code: str, purpose: str = "login") -> bool:
    settings = get_settings()
    brand = settings.bakery_name
    subject = f"{brand} · verification code"
    text = f"{brand} verification code: {code}\nValid for {settings.otp_expire_minutes} minutes."
    html = f"<p>{text}</p><p>Purpose: {purpose}</p>"
    return send_email(to, subject, html, text=text)


def send_admin_confirm_email(to: str, code: str, name: str | None = None) -> bool:
    settings = get_settings()
    brand = settings.bakery_name
    who = name or "Owner"
    subject = f"Confirm your {brand} admin account"
    text = (
        f"Hi {who},\n\n"
        f"Your {brand} admin confirmation code is: {code}\n"
        f"Valid for {settings.otp_expire_minutes} minutes.\n"
    )
    html = f"<p>{text.replace(chr(10), '<br>')}</p>"
    return send_email(to, subject, html, text=text)


def send_login_notice(to: str, name: str | None = None) -> bool:
    settings = get_settings()
    if not settings.auth_mail_notify_on_login:
        return False
    brand = settings.bakery_name
    who = name or "there"
    text = f"Hi {who},\n\nA new sign-in to your {brand} account just succeeded.\n"
    html = f"<p>{text.replace(chr(10), '<br>')}</p>"
    return send_email(to, f"New sign-in · {brand}", html, text=text)
