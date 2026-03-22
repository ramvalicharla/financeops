from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Iterable
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.fixed_assets import Asset
from financeops.services.accounting_common.supersession_validator import (
    SupersessionNode,
    ensure_append_targets_terminal,
    validate_linear_chain,
)
from financeops.schemas.fixed_assets import AssetDisposalInput, AssetImpairmentInput, FixedAssetInput
from financeops.services.accounting_common.quantization_policy import quantize_persisted_amount
from financeops.services.audit_writer import AuditEvent, AuditWriter


@dataclass(frozen=True)
class RegisteredAsset:
    asset_id: UUID
    asset_code: str
    description: str
    entity_id: str
    asset_class: str
    asset_currency: str
    reporting_currency: str
    capitalization_date: datetime.date
    in_service_date: datetime.date
    capitalized_amount_asset_currency: Decimal
    depreciation_method: str
    useful_life_months: int | None
    reducing_balance_rate_annual: Decimal | None
    residual_value_reporting_currency: Decimal
    rate_mode: str
    source_acquisition_reference: str
    parent_reference_id: UUID | None
    source_reference_id: UUID | None
    impairments: list[AssetImpairmentInput]
    disposals: list[AssetDisposalInput]


async def register_assets(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    user_id: UUID,
    correlation_id: str,
    accepted_at: datetime,
    assets: Iterable[FixedAssetInput],
) -> list[RegisteredAsset]:
    registered: list[RegisteredAsset] = []

    for asset in assets:
        same_request_result = await session.execute(
            select(Asset)
            .where(
                Asset.tenant_id == tenant_id,
                Asset.asset_code == asset.asset_code,
                Asset.source_acquisition_reference == asset.source_acquisition_reference,
                Asset.correlation_id == correlation_id,
            )
            .order_by(desc(Asset.created_at))
            .limit(1)
        )
        existing = same_request_result.scalar_one_or_none()

        if existing is None:
            chain_rows = (
                await session.execute(
                    select(Asset)
                    .where(
                        Asset.tenant_id == tenant_id,
                        Asset.asset_code == asset.asset_code,
                        Asset.source_acquisition_reference == asset.source_acquisition_reference,
                    )
                    .order_by(Asset.created_at, Asset.id)
                )
            ).scalars().all()
            chain_nodes = [
                SupersessionNode(
                    id=row.id,
                    tenant_id=row.tenant_id,
                    created_at=row.created_at,
                    supersedes_id=row.supersedes_id,
                )
                for row in chain_rows
            ]
            validate_linear_chain(nodes=chain_nodes, tenant_id=tenant_id)

            latest_result = await session.execute(
                select(Asset)
                .where(
                    Asset.tenant_id == tenant_id,
                    Asset.asset_code == asset.asset_code,
                    Asset.source_acquisition_reference == asset.source_acquisition_reference,
                )
                .order_by(desc(Asset.created_at), desc(Asset.id))
                .limit(1)
            )
            latest = latest_result.scalar_one_or_none()
            ensure_append_targets_terminal(
                nodes=chain_nodes,
                tenant_id=tenant_id,
                supersedes_id=latest.id if latest else None,
            )

            existing = await AuditWriter.insert_financial_record(
                session,
                model_class=Asset,
                tenant_id=tenant_id,
                record_data={
                    "asset_code": asset.asset_code,
                    "source_acquisition_reference": asset.source_acquisition_reference,
                    "depreciation_method": asset.depreciation_method.value,
                    "rate_mode": asset.rate_mode.value,
                },
                values={
                    "created_at": accepted_at,
                    "asset_code": asset.asset_code,
                    "description": asset.description,
                    "entity_id": asset.entity_id,
                    "asset_class": asset.asset_class,
                    "asset_currency": asset.asset_currency,
                    "reporting_currency": asset.reporting_currency,
                    "capitalization_date": asset.capitalization_date,
                    "in_service_date": asset.in_service_date,
                    "capitalized_amount_asset_currency": quantize_persisted_amount(
                        asset.capitalized_amount_asset_currency
                    ),
                    "depreciation_method": asset.depreciation_method.value,
                    "useful_life_months": asset.useful_life_months,
                    "reducing_balance_rate_annual": asset.reducing_balance_rate_annual,
                    "residual_value_reporting_currency": quantize_persisted_amount(
                        asset.residual_value_reporting_currency
                    ),
                    "rate_mode": asset.rate_mode.value,
                    "source_acquisition_reference": asset.source_acquisition_reference,
                    "parent_reference_id": asset.parent_reference_id,
                    "source_reference_id": asset.source_reference_id,
                    "correlation_id": correlation_id,
                    "supersedes_id": latest.id if latest else None,
                },
                audit=AuditEvent(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    action="fixed_assets.registry.created",
                    resource_type="asset",
                    new_value={
                        "asset_code": asset.asset_code,
                        "source_acquisition_reference": asset.source_acquisition_reference,
                        "correlation_id": correlation_id,
                    },
                ),
            )

        registered.append(
            RegisteredAsset(
                asset_id=existing.id,
                asset_code=existing.asset_code,
                description=existing.description,
                entity_id=existing.entity_id,
                asset_class=existing.asset_class,
                asset_currency=existing.asset_currency,
                reporting_currency=existing.reporting_currency,
                capitalization_date=existing.capitalization_date,
                in_service_date=existing.in_service_date,
                capitalized_amount_asset_currency=existing.capitalized_amount_asset_currency,
                depreciation_method=existing.depreciation_method,
                useful_life_months=existing.useful_life_months,
                reducing_balance_rate_annual=existing.reducing_balance_rate_annual,
                residual_value_reporting_currency=existing.residual_value_reporting_currency,
                rate_mode=existing.rate_mode,
                source_acquisition_reference=existing.source_acquisition_reference,
                parent_reference_id=existing.parent_reference_id,
                source_reference_id=existing.source_reference_id,
                impairments=sorted(asset.impairments, key=lambda row: (row.impairment_date, row.idempotency_key)),
                disposals=sorted(asset.disposals, key=lambda row: (row.disposal_date, row.idempotency_key)),
            )
        )

    registered.sort(key=lambda row: (row.asset_code, str(row.asset_id)))
    return registered

