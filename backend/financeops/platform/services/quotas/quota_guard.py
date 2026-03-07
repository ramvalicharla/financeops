from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from financeops.platform.services.quotas.usage_service import check_and_record_usage


@dataclass(frozen=True)
class QuotaGuardRequest:
    tenant_id: uuid.UUID
    quota_type: str
    usage_delta: int
    operation_id: uuid.UUID
    idempotency_key: str
    request_fingerprint: str
    source_layer: str
    actor_user_id: uuid.UUID | None
    correlation_id: str


class QuotaGuard:
    @staticmethod
    async def check_and_record(session: AsyncSession, request: QuotaGuardRequest) -> dict:
        return await check_and_record_usage(
            session,
            tenant_id=request.tenant_id,
            quota_type=request.quota_type,
            usage_delta=request.usage_delta,
            operation_id=request.operation_id,
            idempotency_key=request.idempotency_key,
            request_fingerprint=request.request_fingerprint,
            source_layer=request.source_layer,
            actor_user_id=request.actor_user_id,
            correlation_id=request.correlation_id,
        )
