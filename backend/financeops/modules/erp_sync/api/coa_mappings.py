from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, require_finance_team
from financeops.db.models.erp_sync import (
    ErpAccountExternalRef,
    ExternalConnection,
    ExternalMappingDefinition,
)
from financeops.db.models.users import IamUser
from financeops.modules.erp_sync.application.mapping_service import MappingService
from financeops.shared_kernel.response import ok

router = APIRouter()


async def _resolve_or_create_coa_mapping(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    connection: ExternalConnection,
    created_by: uuid.UUID,
) -> ExternalMappingDefinition:
    """Find or create an active COA mapping definition for this connection's org."""
    definition = (
        await session.execute(
            select(ExternalMappingDefinition)
            .where(
                ExternalMappingDefinition.tenant_id == tenant_id,
                ExternalMappingDefinition.organisation_id == connection.organisation_id,
                ExternalMappingDefinition.dataset_type == "chart_of_accounts",
                ExternalMappingDefinition.mapping_status == "active",
            )
            .order_by(ExternalMappingDefinition.created_at.desc(), ExternalMappingDefinition.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    if definition is not None:
        return definition

    mapping_service = MappingService(session)
    definition = await mapping_service.create_mapping_definition(
        tenant_id=tenant_id,
        organisation_id=connection.organisation_id,
        mapping_code=f"coa-{str(connection.id)[:8]}",
        mapping_name="Chart of Accounts mapping",
        dataset_type="chart_of_accounts",
        created_by=created_by,
        status="active",
    )
    await mapping_service.create_mapping_version(
        tenant_id=tenant_id,
        mapping_definition_id=definition.id,
        mapping_payload_json={},
        created_by=created_by,
        activate=True,
    )
    return definition


@router.post("/mappings/coa", status_code=status.HTTP_200_OK)
async def upsert_coa_mappings(
    request: Request,
    body: dict[str, Any],
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> dict[str, Any]:
    """Upsert COA account mappings for the tenant.

    Body:
        connection_id: UUID of the ERP connection
        accounts: list of {external_account_id, internal_account_code,
                           external_account_code?, external_account_name?}
    """
    connection_id = uuid.UUID(str(body["connection_id"]))
    accounts: list[dict[str, Any]] = list(body.get("accounts", []))
    if not accounts:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="accounts must be non-empty")

    connection = (
        await session.execute(
            select(ExternalConnection).where(
                ExternalConnection.tenant_id == user.tenant_id,
                ExternalConnection.id == connection_id,
            )
        )
    ).scalar_one_or_none()
    if connection is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="connection_not_found")

    definition = await _resolve_or_create_coa_mapping(
        session,
        tenant_id=user.tenant_id,
        connection=connection,
        created_by=user.id,
    )

    now = datetime.now(UTC)
    upserted = 0
    for acct in accounts:
        external_account_id = str(acct["external_account_id"])
        internal_account_code = str(acct["internal_account_code"])

        existing = (
            await session.execute(
                select(ErpAccountExternalRef).where(
                    ErpAccountExternalRef.tenant_id == user.tenant_id,
                    ErpAccountExternalRef.mapping_id == definition.id,
                    ErpAccountExternalRef.connector_type == connection.connector_type,
                    ErpAccountExternalRef.external_account_id == external_account_id,
                )
            )
        ).scalar_one_or_none()

        if existing is not None:
            existing.internal_account_code = internal_account_code
            existing.external_account_code = str(acct.get("external_account_code") or existing.external_account_code or "")
            existing.external_account_name = str(acct.get("external_account_name") or existing.external_account_name or "")
            existing.is_active = True
            existing.updated_at = now
            session.add(existing)
        else:
            ref = ErpAccountExternalRef(
                id=uuid.uuid4(),
                tenant_id=user.tenant_id,
                mapping_id=definition.id,
                connector_type=connection.connector_type,
                external_account_id=external_account_id,
                external_account_code=str(acct.get("external_account_code") or ""),
                external_account_name=str(acct.get("external_account_name") or ""),
                internal_account_code=internal_account_code,
                is_active=True,
                updated_at=now,
            )
            session.add(ref)
        upserted += 1

    await session.flush()
    return ok(
        {"upserted": upserted, "mapping_definition_id": str(definition.id)},
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")
