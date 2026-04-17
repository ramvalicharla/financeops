from __future__ import annotations

import logging
from email.message import EmailMessage

from financeops.config import settings
from financeops.modules.notifications.models import NotificationEvent
from financeops.modules.notifications.templates.emails import (
    auditor_access_email,
    board_pack_ready_email,
    covenant_breach_email,
    signoff_request_email,
    user_invited_email,
)
from financeops.services.network_runtime import send_smtp_message

log = logging.getLogger(__name__)


def _smtp_configured() -> bool:
    if bool(settings.SMTP_REQUIRED):
        return True
    host = str(settings.SMTP_HOST or "").strip()
    user = str(settings.SMTP_USER or "").strip()
    password = str(settings.SMTP_PASSWORD or "").strip()
    return bool(host and user and password)


def _render_notification(notification_event: NotificationEvent) -> tuple[str, str]:
    data = notification_event.metadata_json or {}
    if not isinstance(data, dict):
        data = {}

    ntype = str(notification_event.notification_type or "")
    if ntype == "board_pack_ready":
        return board_pack_ready_email(
            recipient_name=str(data.get("recipient_name", "")),
            period=str(data.get("period", "")),
            entity_name=str(data.get("entity_name", "")),
            board_pack_url=str(data.get("board_pack_url", notification_event.action_url or "#")),
            unsubscribe_url=str(data.get("unsubscribe_url", "#")),
        )
    if ntype in {"covenant_breach", "system_alert"}:
        return covenant_breach_email(
            recipient_name=str(data.get("recipient_name", "")),
            covenant_label=str(data.get("covenant_label", notification_event.title)),
            facility_name=str(data.get("facility_name", "")),
            actual_value=str(data.get("actual_value", "")),
            threshold_value=str(data.get("threshold_value", "")),
            breach_type=str(data.get("breach_type", "near_breach")),
            covenants_url=str(data.get("covenants_url", notification_event.action_url or "#")),
            unsubscribe_url=str(data.get("unsubscribe_url", "#")),
        )
    if ntype in {"signoff_requested", "digital_signoff"}:
        return signoff_request_email(
            signatory_name=str(data.get("signatory_name", "")),
            document_reference=str(data.get("document_reference", notification_event.title)),
            period=str(data.get("period", "")),
            signoff_url=str(data.get("signoff_url", notification_event.action_url or "#")),
            unsubscribe_url=str(data.get("unsubscribe_url", "#")),
        )
    if ntype == "auditor_access":
        return auditor_access_email(
            auditor_name=str(data.get("auditor_name", "")),
            engagement_name=str(data.get("engagement_name", "")),
            portal_url=str(data.get("portal_url", notification_event.action_url or "#")),
            access_token=str(data.get("access_token", "")),
            valid_until=str(data.get("valid_until", "")),
            unsubscribe_url=str(data.get("unsubscribe_url", "#")),
        )
    if ntype == "user_invited":
        return user_invited_email(
            invitee_name=str(data.get("invitee_name", "")),
            inviter_name=str(data.get("inviter_name", "")),
            company_name=str(data.get("company_name", "FinanceOps")),
            invite_url=str(data.get("invite_url", notification_event.action_url or "#")),
            unsubscribe_url=str(data.get("unsubscribe_url", "#")),
        )

    html = (
        "<html><body style=\"font-family:Arial,sans-serif;background:#0b1220;color:#e5e7eb\">"
        "<div style=\"max-width:620px;margin:0 auto;padding:20px\">"
        f"<h1 style=\"font-size:20px;margin:0 0 8px\">{notification_event.title}</h1>"
        f"<p style=\"line-height:1.5\">{notification_event.body}</p>"
        "</div></body></html>"
    )
    return notification_event.title, html


async def send_direct(
    *,
    to: str,
    subject: str,
    html_body: str,
    text_body: str | None = None,
) -> bool:
    if not _smtp_configured():
        log.warning("notification_email_skipped reason=smtp_not_configured recipient=%s", to)
        return False

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.SMTP_USER or "no-reply@financeops.local"
    message["To"] = to
    message.set_content(text_body or "FinanceOps notification")
    message.add_alternative(html_body, subtype="html")

    try:
        await send_smtp_message(
            message,
            host=str(settings.SMTP_HOST),
            port=int(settings.SMTP_PORT),
            user=str(settings.SMTP_USER or ""),
            password=str(settings.SMTP_PASSWORD or ""),
            timeout=30,
        )
        return True
    except Exception as exc:  # noqa: BLE001
        log.warning("notification_email_send_failed recipient=%s error=%s", to, exc)
        return False


async def send_email(
    notification_event: NotificationEvent,
    recipient_email: str,
    *,
    brand_name: str | None = None,
) -> bool:
    del brand_name
    subject, html = _render_notification(notification_event)
    return await send_direct(
        to=recipient_email,
        subject=subject,
        html_body=html,
        text_body=notification_event.body,
    )


__all__ = ["send_email", "send_direct"]
