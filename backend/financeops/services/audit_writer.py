from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.base import FinancialBase
from financeops.services.audit_service import log_action
from financeops.utils.chain_hash import compute_chain_hash, get_previous_hash

TAnyModel = TypeVar("TAnyModel")
TFinancialModel = TypeVar("TFinancialModel", bound=FinancialBase)


@dataclass(frozen=True)
class AuditEvent:
    tenant_id: uuid.UUID
    action: str
    resource_type: str
    user_id: uuid.UUID | None = None
    resource_id: str | None = None
    resource_name: str | None = None
    old_value: Any = None
    new_value: Any = None
    ip_address: str | None = None
    user_agent: str | None = None


class AuditWriter:
    """
    Central write path for domain persistence.
    - FinancialBase writes: computes and persists hash-chain fields.
    - Generic writes: inserts row and optionally records an audit entry.
    """

    @staticmethod
    async def insert_record(
        session: AsyncSession,
        *,
        record: TAnyModel,
        audit: AuditEvent | None = None,
    ) -> TAnyModel:
        session.add(record)
        await session.flush()
        if audit is not None:
            await log_action(
                session,
                tenant_id=audit.tenant_id,
                user_id=audit.user_id,
                action=audit.action,
                resource_type=audit.resource_type,
                resource_id=audit.resource_id or str(getattr(record, "id", "")),
                resource_name=audit.resource_name,
                old_value=audit.old_value,
                new_value=audit.new_value,
                ip_address=audit.ip_address,
                user_agent=audit.user_agent,
            )
        return record

    @staticmethod
    async def flush_with_audit(
        session: AsyncSession,
        *,
        audit: AuditEvent,
    ) -> None:
        await session.flush()
        await log_action(
            session,
            tenant_id=audit.tenant_id,
            user_id=audit.user_id,
            action=audit.action,
            resource_type=audit.resource_type,
            resource_id=audit.resource_id,
            resource_name=audit.resource_name,
            old_value=audit.old_value,
            new_value=audit.new_value,
            ip_address=audit.ip_address,
            user_agent=audit.user_agent,
        )

    @staticmethod
    async def insert_financial_record(
        session: AsyncSession,
        *,
        model_class: type[TFinancialModel],
        tenant_id: uuid.UUID,
        record_data: Mapping[str, Any],
        values: Mapping[str, Any],
        audit: AuditEvent | None = None,
    ) -> TFinancialModel:
        previous_hash = await get_previous_hash(session, model_class, tenant_id)
        chain_hash = compute_chain_hash(dict(record_data), previous_hash)

        payload = dict(values)
        payload["tenant_id"] = tenant_id
        payload["chain_hash"] = chain_hash
        payload["previous_hash"] = previous_hash

        record = model_class(**payload)
        return await AuditWriter.insert_record(session, record=record, audit=audit)
