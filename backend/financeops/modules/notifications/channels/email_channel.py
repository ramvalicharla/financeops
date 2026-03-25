from __future__ import annotations

import asyncio
import logging
import smtplib
from concurrent.futures import ThreadPoolExecutor
from email.message import EmailMessage

from financeops.config import settings
from financeops.modules.notifications.models import NotificationEvent

log = logging.getLogger(__name__)
_smtp_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="smtp")


def _smtp_configured() -> bool:
    if bool(settings.SMTP_REQUIRED):
        return True
    host = str(settings.SMTP_HOST or "").strip()
    user = str(settings.SMTP_USER or "").strip()
    password = str(settings.SMTP_PASSWORD or "").strip()
    return bool(host and user and password)


async def send_email(
    notification_event: NotificationEvent,
    recipient_email: str,
    *,
    brand_name: str | None = None,
) -> bool:
    """
    Send a notification email and fail open when SMTP is not configured.
    """
    if not _smtp_configured():
        log.warning("notification_email_skipped reason=smtp_not_configured recipient=%s", recipient_email)
        return False

    safe_brand = (brand_name or "FinanceOps").strip() or "FinanceOps"
    action_html = ""
    if notification_event.action_url:
        action_html = (
            "<p style=\"margin-top:20px\">"
            f"<a href=\"{notification_event.action_url}\" "
            "style=\"display:inline-block;padding:10px 14px;background:#3b82f6;"
            "color:#fff;text-decoration:none;border-radius:6px\">Open in Platform</a>"
            "</p>"
        )

    html = (
        "<html><body style=\"font-family:Arial,sans-serif;background:#0b1220;color:#e5e7eb\">"
        "<div style=\"max-width:620px;margin:0 auto;padding:20px\">"
        f"<h2 style=\"margin:0 0 12px\">{safe_brand}</h2>"
        f"<h1 style=\"font-size:20px;margin:0 0 8px\">{notification_event.title}</h1>"
        f"<p style=\"line-height:1.5\">{notification_event.body}</p>"
        f"{action_html}"
        "<p style=\"margin-top:24px;font-size:12px;color:#94a3b8\">"
        "You can manage notification preferences in Settings."
        "</p>"
        "</div></body></html>"
    )

    message = EmailMessage()
    message["Subject"] = f"[{safe_brand}] {notification_event.title}"
    message["From"] = settings.SMTP_USER or "no-reply@financeops.local"
    message["To"] = recipient_email
    message.set_content(notification_event.body)
    message.add_alternative(html, subtype="html")

    def _send_smtp_blocking(email_message: EmailMessage) -> None:
        with smtplib.SMTP(
            host=settings.SMTP_HOST,
            port=int(settings.SMTP_PORT),
            timeout=30,
        ) as smtp:
            smtp.ehlo()
            try:
                smtp.starttls()
                smtp.ehlo()
            except smtplib.SMTPException:
                pass
            if settings.SMTP_USER and settings.SMTP_PASSWORD:
                smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            smtp.send_message(email_message)

    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(_smtp_executor, _send_smtp_blocking, message)
        return True
    except Exception as exc:  # noqa: BLE001
        log.warning("notification_email_send_failed recipient=%s error=%s", recipient_email, exc)
        return False


__all__ = ["send_email"]
