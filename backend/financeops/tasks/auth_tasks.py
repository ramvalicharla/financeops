from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, datetime

import sentry_sdk
from sqlalchemy.exc import DBAPIError, InterfaceError, OperationalError

from financeops.config import settings
from financeops.db.models.auth_tokens import PasswordResetToken
from financeops.db.models.users import IamUser
from financeops.db.session import AsyncSessionLocal
from financeops.modules.notifications.channels.email_channel import send_direct
from financeops.tasks.async_runner import run_async
from financeops.tasks.celery_app import celery_app

log = logging.getLogger(__name__)


def _password_reset_email(*, full_name: str | None, reset_url: str) -> tuple[str, str, str]:
    recipient_name = (full_name or "").strip() or "there"
    subject = "Reset your FinanceOps password"
    text_body = (
        f"Hi {recipient_name},\n\n"
        "We received a request to reset your FinanceOps password.\n"
        f"Use this link to continue: {reset_url}\n\n"
        "If you did not request this, you can ignore this email."
    )
    html_body = (
        "<html><body style=\"font-family:Arial,sans-serif;color:#111827\">"
        f"<p>Hi {recipient_name},</p>"
        "<p>We received a request to reset your FinanceOps password.</p>"
        f"<p><a href=\"{reset_url}\">Reset your password</a></p>"
        "<p>If you did not request this, you can ignore this email.</p>"
        "</body></html>"
    )
    return subject, html_body, text_body


@celery_app.task(
    name="auth.send_password_reset_email",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
)
def send_password_reset_email_task(
    self,
    password_reset_token_id: str,
    plain_token: str,
) -> dict[str, str | int]:
    async def _run() -> dict[str, str | int]:
        token_id = uuid.UUID(str(password_reset_token_id))
        frontend_base = str(getattr(settings, "FRONTEND_URL", "http://localhost:3000")).rstrip("/")
        reset_url = f"{frontend_base}/reset-password?token={plain_token}"

        async with AsyncSessionLocal() as session:
            async with session.begin():
                token = await session.get(PasswordResetToken, token_id)
                if token is None:
                    return {"status": "missing", "password_reset_token_id": str(token_id)}
                if token.used_at is not None:
                    return {"status": "used", "password_reset_token_id": str(token_id)}
                if token.expires_at < datetime.now(UTC):
                    return {"status": "expired", "password_reset_token_id": str(token_id)}

                user = await session.get(IamUser, token.user_id)
                if user is None:
                    return {"status": "missing_user", "password_reset_token_id": str(token_id)}

                if token.reset_attempt_count >= 3:
                    await asyncio.sleep(30)

                token.reset_attempt_count += 1
                await session.flush()

                subject, html_body, text_body = _password_reset_email(
                    full_name=user.full_name,
                    reset_url=reset_url,
                )
                sent = await send_direct(
                    to=user.email,
                    subject=subject,
                    html_body=html_body,
                    text_body=text_body,
                )
                return {
                    "status": "sent" if sent else "skipped",
                    "password_reset_token_id": str(token_id),
                    "reset_attempt_count": token.reset_attempt_count,
                }

    try:
        return run_async(_run())
    except (OperationalError, InterfaceError, DBAPIError, ConnectionError, TimeoutError, OSError) as exc:
        raise self.retry(exc=exc)
    except Exception as exc:
        sentry_sdk.capture_exception(exc)
        log.exception("password_reset_email_task_failed token_id=%s", password_reset_token_id)
        raise


__all__ = ["send_password_reset_email_task"]
