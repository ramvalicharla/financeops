from __future__ import annotations

import asyncio
import hmac
import json
import logging
import smtplib
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from email.message import EmailMessage
from hashlib import sha256
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.config import settings
from financeops.core.security import decrypt_field
from financeops.db.models.scheduled_delivery import DeliveryLog, DeliverySchedule
from financeops.modules.scheduled_delivery.domain.enums import (
    ChannelType,
    DeliveryStatus,
    ScheduleType,
)
from financeops.modules.scheduled_delivery.infrastructure.repository import (
    DeliveryRepository,
)

if TYPE_CHECKING:
    from financeops.modules.board_pack_generator.infrastructure.repository import (
        BoardPackRepository,
    )
    from financeops.modules.custom_report_builder.infrastructure.repository import (
        ReportRepository,
    )

log = logging.getLogger(__name__)


class DeliveryConfigurationError(ValueError):
    pass


def _assert_smtp_configured() -> None:
    """Raise immediately if SMTP is required but not configured."""
    if not settings.SMTP_REQUIRED:
        return

    missing: list[str] = []
    smtp_host = str(getattr(settings, "SMTP_HOST", "") or "")
    if not smtp_host or smtp_host.strip().lower() == "localhost":
        missing.append("SMTP_HOST")
    if not str(getattr(settings, "SMTP_USER", "") or "").strip():
        missing.append("SMTP_USER")
    if not str(getattr(settings, "SMTP_PASSWORD", "") or "").strip():
        missing.append("SMTP_PASSWORD")

    if missing:
        raise RuntimeError(
            "SMTP_REQUIRED=True but SMTP not configured. "
            f"Missing or default: {', '.join(missing)}. "
            "Set real SMTP credentials or set SMTP_REQUIRED=False."
        )


@dataclass(slots=True)
class SourceRunInfo:
    source_run_id: uuid.UUID
    source_type: ScheduleType


class DeliveryService:
    def __init__(
        self,
        *,
        delivery_repository: DeliveryRepository | None = None,
        board_pack_repository: "BoardPackRepository | None" = None,
        report_repository: "ReportRepository | None" = None,
    ) -> None:
        self._delivery_repository = delivery_repository or DeliveryRepository()
        self._board_pack_repository = board_pack_repository
        self._report_repository = report_repository

    async def trigger_schedule(
        self,
        db: AsyncSession,
        schedule_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> list[DeliveryLog]:
        """
        1. Load schedule from DB
        2. Determine source type (BOARD_PACK or REPORT)
        3. Trigger a new generate/run on the source
           (call board_pack_generator or custom_report_builder
            Celery tasks to produce fresh output)
        4. For each recipient in schedule.recipients:
           a. Create DeliveryLog row (PENDING)
           b. Dispatch to correct channel
           c. Update log → DELIVERED or FAILED (append new row)
        5. Update schedule.last_triggered_at + next_run_at
        6. Return list of DeliveryLog rows created
        """
        schedule = await self._delivery_repository.get_schedule(
            db=db,
            tenant_id=tenant_id,
            schedule_id=schedule_id,
        )
        if schedule is None:
            raise DeliveryConfigurationError("Delivery schedule not found")
        if not schedule.is_active:
            raise DeliveryConfigurationError("Delivery schedule is inactive")

        source_run = await self._trigger_source_run(
            db=db,
            schedule=schedule,
            tenant_id=tenant_id,
        )

        final_logs: list[DeliveryLog] = []
        for recipient in list(schedule.recipients or []):
            recipient_type = str(recipient.get("type", "")).strip().lower()
            recipient_address = str(recipient.get("address", "")).strip()
            if recipient_type not in {"email", "webhook"}:
                raise DeliveryConfigurationError(f"Unsupported recipient type: {recipient_type}")
            if not recipient_address:
                raise DeliveryConfigurationError("recipient address is required")

            channel_type = (
                ChannelType.EMAIL
                if recipient_type == "email"
                else ChannelType.WEBHOOK
            )
            pending_log = await self._delivery_repository.create_log(
                db=db,
                tenant_id=tenant_id,
                schedule_id=schedule.id,
                channel_type=channel_type.value,
                recipient_address=recipient_address,
                source_run_id=source_run.source_run_id,
                status=DeliveryStatus.PENDING.value,
                response_metadata={
                    "schedule_type": source_run.source_type.value,
                    "schedule_name": schedule.name,
                },
            )

            try:
                if channel_type == ChannelType.EMAIL:
                    await self._dispatch_email(
                        recipient=recipient_address,
                        subject=f"Scheduled delivery: {schedule.name}",
                        body="Your scheduled FinanceOps export is ready.",
                        attachment=self._build_attachment_bytes(schedule, source_run),
                        filename=self._build_attachment_filename(schedule, source_run),
                    )
                else:
                    await self._dispatch_webhook(
                        url=recipient_address,
                        payload=self._build_webhook_payload(schedule, source_run, pending_log),
                        secret=self._webhook_secret(schedule),
                    )

                delivered_log = await self._delivery_repository.create_log(
                    db=db,
                    tenant_id=tenant_id,
                    schedule_id=schedule.id,
                    channel_type=channel_type.value,
                    recipient_address=recipient_address,
                    source_run_id=source_run.source_run_id,
                    status=DeliveryStatus.DELIVERED.value,
                    completed_at=datetime.now(UTC),
                    retry_count=pending_log.retry_count,
                    response_metadata={
                        "previous_log_id": str(pending_log.id),
                        "delivery": "ok",
                    },
                )
                final_logs.append(delivered_log)
            except Exception as exc:
                failed_log = await self._delivery_repository.create_log(
                    db=db,
                    tenant_id=tenant_id,
                    schedule_id=schedule.id,
                    channel_type=channel_type.value,
                    recipient_address=recipient_address,
                    source_run_id=source_run.source_run_id,
                    status=DeliveryStatus.FAILED.value,
                    completed_at=datetime.now(UTC),
                    error_message=str(exc)[:2000],
                    retry_count=pending_log.retry_count + 1,
                    response_metadata={
                        "previous_log_id": str(pending_log.id),
                        "delivery": "failed",
                    },
                )
                final_logs.append(failed_log)

        now = datetime.now(UTC)
        await self._delivery_repository.update_schedule(
            db=db,
            tenant_id=tenant_id,
            schedule_id=schedule.id,
            updates={
                "last_triggered_at": now,
                "next_run_at": self._compute_next_run_at(
                    cron_expression=schedule.cron_expression,
                    timezone=schedule.timezone,
                    from_time=now,
                ),
            },
        )
        return final_logs

    async def _trigger_source_run(
        self,
        *,
        db: AsyncSession,
        schedule: DeliverySchedule,
        tenant_id: uuid.UUID,
    ) -> SourceRunInfo:
        # Import source modules lazily to avoid cross-module model side effects
        # during app startup/test collection.
        from financeops.modules.board_pack_generator.infrastructure.repository import (
            BoardPackRepository,
        )
        from financeops.modules.board_pack_generator.tasks import generate_board_pack_task
        from financeops.modules.custom_report_builder.infrastructure.repository import (
            ReportRepository,
        )
        from financeops.modules.custom_report_builder.tasks import run_custom_report_task

        schedule_type = ScheduleType(schedule.schedule_type)
        board_pack_repository = self._board_pack_repository or BoardPackRepository()
        report_repository = self._report_repository or ReportRepository()
        if schedule_type == ScheduleType.BOARD_PACK:
            definition = await board_pack_repository.get_definition(
                db=db,
                tenant_id=tenant_id,
                definition_id=schedule.source_definition_id,
            )
            if definition is None or not definition.is_active:
                raise DeliveryConfigurationError("Board pack definition not found or inactive")

            period_start, period_end = self._current_month_period()
            run = await board_pack_repository.create_run(
                db=db,
                tenant_id=tenant_id,
                definition_id=schedule.source_definition_id,
                period_start=period_start,
                period_end=period_end,
                triggered_by=schedule.created_by,
            )
            generate_board_pack_task.delay(str(run.id), str(tenant_id))
            return SourceRunInfo(source_run_id=run.id, source_type=schedule_type)

        if schedule_type == ScheduleType.REPORT:
            definition = await report_repository.get_definition(
                db=db,
                tenant_id=tenant_id,
                definition_id=schedule.source_definition_id,
            )
            if definition is None or not definition.is_active:
                raise DeliveryConfigurationError("Report definition not found or inactive")

            run = await report_repository.create_run(
                db=db,
                tenant_id=tenant_id,
                definition_id=schedule.source_definition_id,
                triggered_by=schedule.created_by,
            )
            run_custom_report_task.delay(str(run.id), str(tenant_id))
            return SourceRunInfo(source_run_id=run.id, source_type=schedule_type)

        raise DeliveryConfigurationError(f"Unsupported schedule type: {schedule.schedule_type}")

    async def _dispatch_email(
        self,
        recipient: str,
        subject: str,
        body: str,
        attachment: bytes,
        filename: str,
    ) -> None:
        """
        Send via SMTP using settings:
          SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD
          (read from settings — add to settings if missing,
           with safe defaults: host=localhost, port=587)
        If SMTP not configured: log warning, do not raise
        (fail-open for email in dev — fail-closed in prod
         controlled by SMTP_REQUIRED setting, default False)
        """

        _assert_smtp_configured()

        def _send() -> None:
            message = EmailMessage()
            message["Subject"] = subject
            message["From"] = str(getattr(settings, "SMTP_USER", "")) or "no-reply@financeops.local"
            message["To"] = recipient
            message.set_content(body)
            message.add_attachment(
                attachment,
                maintype="application",
                subtype="octet-stream",
                filename=filename,
            )

            host = str(getattr(settings, "SMTP_HOST", "localhost") or "localhost")
            port = int(getattr(settings, "SMTP_PORT", 587) or 587)
            user = str(getattr(settings, "SMTP_USER", "") or "")
            password = str(getattr(settings, "SMTP_PASSWORD", "") or "")

            with smtplib.SMTP(host=host, port=port, timeout=30) as smtp:
                smtp.ehlo()
                try:
                    smtp.starttls()
                    smtp.ehlo()
                except smtplib.SMTPException:
                    pass
                if user and password:
                    smtp.login(user, password)
                smtp.send_message(message)

        try:
            await asyncio.to_thread(_send)
        except Exception as exc:
            if bool(getattr(settings, "SMTP_REQUIRED", False)):
                raise
            log.warning("SMTP delivery skipped/fail-open for recipient %s: %s", recipient, exc)

    async def _dispatch_webhook(
        self,
        url: str,
        payload: dict,
        secret: str | None = None,
    ) -> None:
        """
        POST payload as JSON to url.
        If secret provided: add X-Signature-256 header
          = "sha256=" + HMAC-SHA256(secret, json_body)
        Use httpx (already in deps) with timeout=30s
        Raise on non-2xx response
        """
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if secret:
            digest = hmac.new(secret.encode("utf-8"), body, sha256).hexdigest()
            headers["X-Signature-256"] = f"sha256={digest}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url=url, content=body, headers=headers)
            response.raise_for_status()

    def _current_month_period(self) -> tuple[date, date]:
        now = datetime.now(UTC).date()
        period_start = now.replace(day=1)
        if period_start.month == 12:
            next_month = period_start.replace(year=period_start.year + 1, month=1, day=1)
        else:
            next_month = period_start.replace(month=period_start.month + 1, day=1)
        period_end = next_month - timedelta(days=1)
        return period_start, period_end

    def _compute_next_run_at(
        self,
        *,
        cron_expression: str,
        timezone: str,
        from_time: datetime,
    ) -> datetime:
        fields = cron_expression.split()
        if len(fields) != 5:
            return from_time + timedelta(minutes=1)

        minute_field, hour_field, day_field, month_field, weekday_field = fields
        try:
            tz = ZoneInfo(timezone or "UTC")
        except Exception:
            tz = ZoneInfo("UTC")
        current = from_time.astimezone(tz).replace(second=0, microsecond=0) + timedelta(minutes=1)
        for _ in range(0, 60 * 24 * 370):
            if (
                self._cron_match(minute_field, current.minute)
                and self._cron_match(hour_field, current.hour)
                and self._cron_match(day_field, current.day)
                and self._cron_match(month_field, current.month)
                and self._cron_match(weekday_field, (current.weekday() + 1) % 7)
            ):
                return current.astimezone(UTC)
            current += timedelta(minutes=1)
        return from_time + timedelta(minutes=1)

    def _cron_match(self, field: str, value: int) -> bool:
        if field == "*":
            return True
        if field.startswith("*/"):
            try:
                step = int(field[2:])
            except ValueError:
                return False
            return step > 0 and value % step == 0
        if "," in field:
            return any(self._cron_match(part.strip(), value) for part in field.split(","))
        try:
            return int(field) == value
        except ValueError:
            return False

    def _build_attachment_filename(
        self,
        schedule: DeliverySchedule,
        source_run: SourceRunInfo,
    ) -> str:
        fmt = (schedule.export_format or "PDF").lower()
        extension = "xlsx" if fmt == "excel" else ("csv" if fmt == "csv" else "pdf")
        return f"{schedule.schedule_type.lower()}_{source_run.source_run_id}.{extension}"

    def _build_attachment_bytes(
        self,
        schedule: DeliverySchedule,
        source_run: SourceRunInfo,
    ) -> bytes:
        payload = {
            "schedule_id": str(schedule.id),
            "schedule_type": source_run.source_type.value,
            "source_run_id": str(source_run.source_run_id),
            "export_format": schedule.export_format,
            "generated_at": datetime.now(UTC).isoformat(),
        }
        return json.dumps(payload, sort_keys=True).encode("utf-8")

    def _build_webhook_payload(
        self,
        schedule: DeliverySchedule,
        source_run: SourceRunInfo,
        pending_log: DeliveryLog,
    ) -> dict:
        return {
            "schedule_id": str(schedule.id),
            "schedule_name": schedule.name,
            "schedule_type": source_run.source_type.value,
            "source_run_id": str(source_run.source_run_id),
            "log_id": str(pending_log.id),
            "export_format": schedule.export_format,
            "triggered_at": pending_log.triggered_at.isoformat(),
        }

    def _webhook_secret(self, schedule: DeliverySchedule) -> str | None:
        config = schedule.config if isinstance(schedule.config, dict) else {}
        encrypted = str(config.get("webhook_secret_enc") or "").strip()
        if encrypted:
            try:
                return decrypt_field(encrypted)
            except Exception:
                log.warning("Failed to decrypt webhook secret; falling back to legacy key")
        secret = config.get("webhook_secret")
        return str(secret) if secret else None


__all__ = ["DeliveryConfigurationError", "DeliveryService", "_assert_smtp_configured"]
