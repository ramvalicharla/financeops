from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.accounting_jv import AccountingJVAggregate, JVStatus
from financeops.db.models.erp_sync import (
    ErpAccountExternalRef,
    ExternalConnection,
    ExternalPeriodLock,
)
from financeops.modules.erp_sync.application.connection_service import resolve_connection_runtime_state
from financeops.modules.erp_sync.domain.enums import DatasetType


class GateFailure(Exception):
    """Raised when a pre-push validation gate fails."""

    def __init__(self, gate: str, reason: str) -> None:
        self.gate = gate
        self.reason = reason
        super().__init__(f"[{gate}] {reason}")


def _period_key(fiscal_year: int, fiscal_period: int) -> str:
    return f"{fiscal_year:04d}-{fiscal_period:02d}"


async def gate_jv_approved(jv: AccountingJVAggregate) -> None:
    if jv.status != JVStatus.APPROVED:
        raise GateFailure(
            "JV_STATUS",
            f"JV must be APPROVED before push. Current status: '{jv.status}'",
        )


async def gate_period_open(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    fiscal_year: int,
    fiscal_period: int,
) -> None:
    result = await db.execute(
        select(ExternalPeriodLock).where(
            ExternalPeriodLock.tenant_id == tenant_id,
            ExternalPeriodLock.entity_id == entity_id,
            ExternalPeriodLock.dataset_type == DatasetType.GENERAL_LEDGER.value,
            ExternalPeriodLock.period_key == _period_key(fiscal_year, fiscal_period),
            ExternalPeriodLock.lock_status == "locked",
        )
    )
    if result.scalar_one_or_none() is not None:
        raise GateFailure(
            "PERIOD_LOCKED",
            f"Period {fiscal_year}/{fiscal_period:02d} is locked for entity {entity_id}.",
        )


async def gate_account_mappings_complete(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    connector_type: str,
    account_codes: list[str],
) -> None:
    if not account_codes:
        raise GateFailure("ACCOUNT_MAPPING", "JV has no account codes to validate.")

    normalized_connector = connector_type.lower()
    result = await db.execute(
        select(ErpAccountExternalRef).where(
            ErpAccountExternalRef.tenant_id == tenant_id,
            ErpAccountExternalRef.connector_type == normalized_connector,
            ErpAccountExternalRef.internal_account_code.in_(account_codes),
            ErpAccountExternalRef.is_active.is_(True),
            ErpAccountExternalRef.is_stale.is_(False),
        )
    )
    mapped_codes = {row.internal_account_code for row in result.scalars().all()}
    missing = sorted(set(account_codes) - mapped_codes)
    if missing:
        raise GateFailure(
            "ACCOUNT_MAPPING",
            f"Missing active account mappings for connector '{normalized_connector}': {missing}",
        )


async def gate_no_stale_mappings(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    connector_type: str,
    account_codes: list[str],
) -> None:
    normalized_connector = connector_type.lower()
    result = await db.execute(
        select(ErpAccountExternalRef).where(
            ErpAccountExternalRef.tenant_id == tenant_id,
            ErpAccountExternalRef.connector_type == normalized_connector,
            ErpAccountExternalRef.internal_account_code.in_(account_codes),
            ErpAccountExternalRef.is_stale.is_(True),
        )
    )
    stale_codes = sorted({row.internal_account_code for row in result.scalars().all()})
    if stale_codes:
        raise GateFailure(
            "STALE_MAPPING",
            f"Stale account mappings found for connector '{normalized_connector}': {stale_codes}",
        )


async def gate_entity_config_complete(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    connector_type: str,
) -> None:
    normalized_connector = connector_type.lower()
    result = await db.execute(
        select(ExternalConnection).where(
            ExternalConnection.organisation_id == tenant_id,
            ExternalConnection.entity_id == entity_id,
            ExternalConnection.connector_type == normalized_connector,
        )
    )
    rows: list[ExternalConnection]
    try:
        scalar_rows = result.scalars().all()
        rows = scalar_rows if isinstance(scalar_rows, list) else []
    except Exception:
        rows = []
    if not rows and hasattr(result, "scalar_one_or_none"):
        single_row = result.scalar_one_or_none()
        if single_row is not None:
            rows = [single_row]
    has_active_connection = False
    for row in rows:
        _, runtime_state = await resolve_connection_runtime_state(
            db,
            connection=row,
        )
        if str(runtime_state.get("connection_status") or row.connection_status).strip().lower() == "active":
            has_active_connection = True
            break

    if not has_active_connection:
        raise GateFailure(
            "ENTITY_CONFIG",
            f"No active '{normalized_connector}' ERP connection found for entity {entity_id}.",
        )


async def run_all_push_gates(
    db: AsyncSession,
    *,
    jv: AccountingJVAggregate,
    connector_type: str,
    tenant_id: uuid.UUID,
) -> None:
    await gate_jv_approved(jv)

    await gate_period_open(
        db,
        tenant_id=tenant_id,
        entity_id=jv.entity_id,
        fiscal_year=jv.fiscal_year,
        fiscal_period=jv.fiscal_period,
    )

    account_codes = sorted(
        {
            line.account_code
            for line in jv.lines
            if line.jv_version == jv.version
        }
    )

    await gate_account_mappings_complete(
        db,
        tenant_id=tenant_id,
        connector_type=connector_type,
        account_codes=account_codes,
    )

    await gate_no_stale_mappings(
        db,
        tenant_id=tenant_id,
        connector_type=connector_type,
        account_codes=account_codes,
    )

    await gate_entity_config_complete(
        db,
        tenant_id=tenant_id,
        entity_id=jv.entity_id,
        connector_type=connector_type,
    )
