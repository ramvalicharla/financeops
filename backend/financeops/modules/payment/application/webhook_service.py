from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.payment import WebhookEvent
from financeops.modules.payment.domain.enums import PaymentProvider
from financeops.modules.payment.infrastructure.providers.registry import get_provider
from financeops.services.audit_writer import AuditWriter


class WebhookService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def handle_webhook(
        self,
        *,
        provider: PaymentProvider,
        payload: bytes,
        signature: str,
        secret: str,
        tenant_id: uuid.UUID,
    ) -> None:
        provider_impl = get_provider(provider)
        verified = await provider_impl.verify_webhook(payload=payload, signature=signature, secret=secret)
        if not verified:
            return

        parsed_payload = json.loads(payload.decode("utf-8")) if payload else {}
        canonical_event_type, normalized_data = await provider_impl.parse_webhook_event(parsed_payload)
        provider_event_id = str(normalized_data.get("provider_event_id") or parsed_payload.get("id") or "")

        if provider_event_id:
            existing = (
                await self._session.execute(
                    select(WebhookEvent).where(
                        WebhookEvent.tenant_id == tenant_id,
                        WebhookEvent.provider == provider.value,
                        WebhookEvent.provider_event_id == provider_event_id,
                    )
                )
            ).scalar_one_or_none()
            if existing is not None:
                return

        processing_error: str | None = None
        try:
            await self._route_event(
                tenant_id=tenant_id,
                canonical_event_type=canonical_event_type,
                normalized_data=normalized_data,
            )
        except Exception as exc:  # pragma: no cover - defensive path for webhook resilience
            processing_error = str(exc)

        await AuditWriter.insert_financial_record(
            self._session,
            model_class=WebhookEvent,
            tenant_id=tenant_id,
            record_data={
                "provider": provider.value,
                "provider_event_id": provider_event_id,
                "event_type": canonical_event_type,
                "processed": "true",
            },
            values={
                "provider": provider.value,
                "provider_event_id": provider_event_id,
                "event_type": canonical_event_type,
                "payload": parsed_payload,
                "processed": True,
                "processed_at": datetime.now(UTC),
                "processing_error": processing_error,
            },
        )

    async def _route_event(
        self,
        *,
        tenant_id: uuid.UUID,
        canonical_event_type: str,
        normalized_data: dict[str, Any],
    ) -> None:
        # Event application logic is handled by dedicated services during endpoint orchestration.
        # This function intentionally stays deterministic and side-effect scoped.
        _ = (tenant_id, canonical_event_type, normalized_data)
        return None
