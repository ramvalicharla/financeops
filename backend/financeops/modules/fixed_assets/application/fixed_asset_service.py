from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import NotFoundError, ValidationError
from financeops.modules.fixed_assets.application.depreciation_engine import get_depreciation
from financeops.modules.fixed_assets.application.impairment_engine import (
    calculate_impairment_loss,
    calculate_recoverable_amount,
)
from financeops.modules.fixed_assets.application.revaluation_engine import (
    apply_elimination_method,
    apply_proportional_method,
)
from financeops.modules.fixed_assets.models import (
    FaAsset,
    FaAssetClass,
    FaDepreciationRun,
    FaImpairment,
    FaRevaluation,
)


class FixedAssetService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _limit(limit: int) -> int:
        return max(1, min(limit, 1000))

    async def _get_asset_or_404(self, tenant_id: uuid.UUID, asset_id: uuid.UUID) -> FaAsset:
        asset = (
            await self._session.execute(
                select(FaAsset).where(FaAsset.id == asset_id, FaAsset.tenant_id == tenant_id)
            )
        ).scalar_one_or_none()
        if asset is None:
            raise NotFoundError("Asset not found")
        return asset

    async def _asset_accum_dep(
        self,
        tenant_id: uuid.UUID,
        asset_id: uuid.UUID,
        gaap: str,
        as_of: date | None = None,
    ) -> Decimal:
        stmt = select(func.coalesce(func.sum(FaDepreciationRun.depreciation_amount), Decimal("0"))).where(
            FaDepreciationRun.tenant_id == tenant_id,
            FaDepreciationRun.asset_id == asset_id,
            FaDepreciationRun.gaap == gaap,
        )
        if as_of is not None:
            stmt = stmt.where(FaDepreciationRun.run_date <= as_of)
        value = (await self._session.execute(stmt)).scalar_one()
        return Decimal(str(value or "0"))

    async def _opening_nbv(
        self,
        asset: FaAsset,
        gaap: str,
        period_start: date,
    ) -> Decimal:
        accum = await self._asset_accum_dep(asset.tenant_id, asset.id, gaap, as_of=period_start)
        opening = Decimal(str(asset.original_cost)) - accum
        return max(opening, Decimal(str(asset.residual_value)))

    async def create_asset_class(
        self,
        tenant_id: uuid.UUID,
        entity_id: uuid.UUID,
        data: dict[str, Any],
    ) -> FaAssetClass:
        row = FaAssetClass(
            tenant_id=tenant_id,
            entity_id=entity_id,
            name=str(data["name"]).strip(),
            asset_type=str(data["asset_type"]).upper(),
            default_method=str(data["default_method"]).upper(),
            default_useful_life_years=data.get("default_useful_life_years"),
            default_residual_pct=data.get("default_residual_pct"),
            it_act_block_number=data.get("it_act_block_number"),
            it_act_depreciation_rate=data.get("it_act_depreciation_rate"),
            coa_asset_account_id=data.get("coa_asset_account_id"),
            coa_accum_dep_account_id=data.get("coa_accum_dep_account_id"),
            coa_dep_expense_account_id=data.get("coa_dep_expense_account_id"),
            is_active=bool(data.get("is_active", True)),
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def update_asset_class(
        self,
        tenant_id: uuid.UUID,
        class_id: uuid.UUID,
        data: dict[str, Any],
    ) -> FaAssetClass:
        row = (
            await self._session.execute(
                select(FaAssetClass).where(FaAssetClass.id == class_id, FaAssetClass.tenant_id == tenant_id)
            )
        ).scalar_one_or_none()
        if row is None:
            raise NotFoundError("Asset class not found")

        for key in [
            "name",
            "asset_type",
            "default_method",
            "default_useful_life_years",
            "default_residual_pct",
            "it_act_block_number",
            "it_act_depreciation_rate",
            "coa_asset_account_id",
            "coa_accum_dep_account_id",
            "coa_dep_expense_account_id",
            "is_active",
        ]:
            if key in data:
                setattr(row, key, data[key])

        await self._session.flush()
        return row

    async def get_asset_classes(
        self,
        tenant_id: uuid.UUID,
        entity_id: uuid.UUID,
        skip: int,
        limit: int,
    ) -> dict[str, Any]:
        effective_limit = self._limit(limit)
        total = int(
            (
                await self._session.execute(
                    select(func.count()).select_from(FaAssetClass).where(
                        FaAssetClass.tenant_id == tenant_id,
                        FaAssetClass.entity_id == entity_id,
                    )
                )
            ).scalar_one()
        )
        rows = (
            await self._session.execute(
                select(FaAssetClass)
                .where(FaAssetClass.tenant_id == tenant_id, FaAssetClass.entity_id == entity_id)
                .order_by(FaAssetClass.name)
                .offset(skip)
                .limit(effective_limit)
            )
        ).scalars().all()
        return {
            "items": list(rows),
            "total": total,
            "skip": skip,
            "limit": effective_limit,
            "has_more": (skip + len(rows)) < total,
        }

    async def create_asset(
        self,
        tenant_id: uuid.UUID,
        entity_id: uuid.UUID,
        data: dict[str, Any],
    ) -> FaAsset:
        existing = (
            await self._session.execute(
                select(FaAsset.id).where(
                    FaAsset.tenant_id == tenant_id,
                    FaAsset.entity_id == entity_id,
                    FaAsset.asset_code == str(data["asset_code"]),
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            raise ValidationError("asset_code already exists for entity")

        row = FaAsset(
            tenant_id=tenant_id,
            entity_id=entity_id,
            asset_class_id=data["asset_class_id"],
            asset_code=str(data["asset_code"]),
            asset_name=str(data["asset_name"]),
            description=data.get("description"),
            location=data.get("location"),
            serial_number=data.get("serial_number"),
            purchase_date=data["purchase_date"],
            capitalisation_date=data["capitalisation_date"],
            original_cost=Decimal(str(data["original_cost"])),
            residual_value=Decimal(str(data.get("residual_value", "0"))),
            useful_life_years=Decimal(str(data["useful_life_years"])),
            depreciation_method=str(data["depreciation_method"]).upper(),
            it_act_block_number=data.get("it_act_block_number"),
            status=str(data.get("status", "ACTIVE")).upper(),
            gaap_overrides=data.get("gaap_overrides"),
            is_active=bool(data.get("is_active", True)),
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def update_asset(
        self,
        tenant_id: uuid.UUID,
        asset_id: uuid.UUID,
        data: dict[str, Any],
    ) -> FaAsset:
        row = await self._get_asset_or_404(tenant_id, asset_id)
        allowed = {
            "asset_name",
            "description",
            "location",
            "serial_number",
            "status",
            "gaap_overrides",
            "is_active",
            "disposal_date",
            "disposal_proceeds",
        }
        for key, value in data.items():
            if key in allowed:
                setattr(row, key, value)
        await self._session.flush()
        return row

    async def get_assets(
        self,
        tenant_id: uuid.UUID,
        entity_id: uuid.UUID,
        skip: int,
        limit: int,
        status: str | None = None,
    ) -> dict[str, Any]:
        effective_limit = self._limit(limit)
        stmt = select(FaAsset).where(FaAsset.tenant_id == tenant_id, FaAsset.entity_id == entity_id)
        if status:
            stmt = stmt.where(FaAsset.status == status)

        total = int((await self._session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one())
        rows = (
            await self._session.execute(
                stmt.order_by(FaAsset.capitalisation_date.desc(), FaAsset.asset_code)
                .offset(skip)
                .limit(effective_limit)
            )
        ).scalars().all()
        return {
            "items": list(rows),
            "total": total,
            "skip": skip,
            "limit": effective_limit,
            "has_more": (skip + len(rows)) < total,
        }

    async def get_asset(self, tenant_id: uuid.UUID, asset_id: uuid.UUID) -> FaAsset:
        return await self._get_asset_or_404(tenant_id, asset_id)

    async def run_depreciation(
        self,
        tenant_id: uuid.UUID,
        entity_id: uuid.UUID,
        period_start: date,
        period_end: date,
        gaap: str = "INDAS",
    ) -> list[FaDepreciationRun]:
        gaap_key = gaap.upper()
        assets = (
            await self._session.execute(
                select(FaAsset)
                .where(
                    FaAsset.tenant_id == tenant_id,
                    FaAsset.entity_id == entity_id,
                    FaAsset.status.in_(["ACTIVE", "IMPAIRED", "UNDER_INSTALLATION"]),
                    FaAsset.is_active.is_(True),
                )
                .order_by(FaAsset.asset_code)
            )
        ).scalars().all()

        runs: list[FaDepreciationRun] = []
        for asset in assets:
            run_reference = f"{entity_id}:{asset.id}:{period_start.isoformat()}:{gaap_key}"
            existing = (
                await self._session.execute(
                    select(FaDepreciationRun).where(
                        FaDepreciationRun.tenant_id == tenant_id,
                        FaDepreciationRun.run_reference == run_reference,
                    )
                )
            ).scalar_one_or_none()
            if existing is not None:
                runs.append(existing)
                continue

            opening_nbv = await self._opening_nbv(asset, gaap_key, period_start)
            depreciation_amount = get_depreciation(
                asset=asset,
                opening_nbv=opening_nbv,
                period_start=period_start,
                period_end=period_end,
                gaap=gaap_key,
            )
            residual = Decimal(str(asset.residual_value))
            closing_nbv = max(opening_nbv - depreciation_amount, residual)
            accumulated_dep = Decimal(str(asset.original_cost)) - closing_nbv

            row = FaDepreciationRun(
                tenant_id=tenant_id,
                entity_id=entity_id,
                asset_id=asset.id,
                run_date=period_end,
                period_start=period_start,
                period_end=period_end,
                gaap=gaap_key,
                depreciation_method=asset.depreciation_method,
                opening_nbv=opening_nbv,
                depreciation_amount=depreciation_amount,
                closing_nbv=closing_nbv,
                accumulated_dep=accumulated_dep,
                run_reference=run_reference,
                is_reversal=False,
            )
            self._session.add(row)
            runs.append(row)

        await self._session.flush()
        return runs

    async def run_asset_depreciation(
        self,
        tenant_id: uuid.UUID,
        asset_id: uuid.UUID,
        period_start: date,
        period_end: date,
        gaap: str = "INDAS",
    ) -> FaDepreciationRun:
        asset = await self._get_asset_or_404(tenant_id, asset_id)
        rows = await self.run_depreciation(
            tenant_id=tenant_id,
            entity_id=asset.entity_id,
            period_start=period_start,
            period_end=period_end,
            gaap=gaap,
        )
        for row in rows:
            if row.asset_id == asset_id:
                return row
        raise NotFoundError("Depreciation run not found")

    async def get_depreciation_history(
        self,
        tenant_id: uuid.UUID,
        asset_id: uuid.UUID,
        skip: int,
        limit: int,
    ) -> dict[str, Any]:
        effective_limit = self._limit(limit)
        total = int(
            (
                await self._session.execute(
                    select(func.count()).select_from(FaDepreciationRun).where(
                        FaDepreciationRun.tenant_id == tenant_id,
                        FaDepreciationRun.asset_id == asset_id,
                    )
                )
            ).scalar_one()
        )
        rows = (
            await self._session.execute(
                select(FaDepreciationRun)
                .where(FaDepreciationRun.tenant_id == tenant_id, FaDepreciationRun.asset_id == asset_id)
                .order_by(FaDepreciationRun.period_end.desc(), FaDepreciationRun.created_at.desc())
                .offset(skip)
                .limit(effective_limit)
            )
        ).scalars().all()
        return {
            "items": list(rows),
            "total": total,
            "skip": skip,
            "limit": effective_limit,
            "has_more": (skip + len(rows)) < total,
        }

    async def post_revaluation(
        self,
        tenant_id: uuid.UUID,
        asset_id: uuid.UUID,
        fair_value: Decimal,
        method: str,
        revaluation_date: date,
    ) -> FaRevaluation:
        asset = await self._get_asset_or_404(tenant_id, asset_id)
        accum_dep = await self._asset_accum_dep(tenant_id, asset.id, "INDAS", as_of=revaluation_date)
        pre_cost = Decimal(str(asset.original_cost))
        pre_nbv = pre_cost - accum_dep

        method_upper = method.upper()
        if method_upper == "PROPORTIONAL":
            result = apply_proportional_method(asset, Decimal(str(fair_value)), revaluation_date)
        elif method_upper == "ELIMINATION":
            result = apply_elimination_method(asset, Decimal(str(fair_value)), revaluation_date)
        else:
            raise ValidationError("Invalid revaluation method")

        row = FaRevaluation(
            tenant_id=tenant_id,
            entity_id=asset.entity_id,
            asset_id=asset.id,
            revaluation_date=revaluation_date,
            pre_revaluation_cost=pre_cost,
            pre_revaluation_accum_dep=accum_dep,
            pre_revaluation_nbv=pre_nbv,
            fair_value=Decimal(str(fair_value)),
            revaluation_surplus=Decimal(str(result["surplus"])),
            method=method_upper,
        )
        self._session.add(row)

        gaap_overrides = dict(asset.gaap_overrides or {})
        gaap_overrides["_accumulated_dep"] = str(result["new_accum_dep"])
        asset.gaap_overrides = gaap_overrides
        asset.original_cost = Decimal(str(result["new_cost"]))

        await self._session.flush()
        return row

    async def get_revaluation_history(
        self,
        tenant_id: uuid.UUID,
        asset_id: uuid.UUID,
    ) -> list[FaRevaluation]:
        rows = (
            await self._session.execute(
                select(FaRevaluation)
                .where(FaRevaluation.tenant_id == tenant_id, FaRevaluation.asset_id == asset_id)
                .order_by(FaRevaluation.revaluation_date.desc(), FaRevaluation.created_at.desc())
            )
        ).scalars().all()
        return list(rows)

    async def post_impairment(
        self,
        tenant_id: uuid.UUID,
        asset_id: uuid.UUID,
        value_in_use: Decimal | None,
        fvlcts: Decimal | None,
        discount_rate: Decimal | None,
        impairment_date: date,
    ) -> FaImpairment:
        asset = await self._get_asset_or_404(tenant_id, asset_id)
        accum_dep = await self._asset_accum_dep(tenant_id, asset.id, "INDAS", as_of=impairment_date)
        nbv = Decimal(str(asset.original_cost)) - accum_dep

        if value_in_use is None and fvlcts is None:
            raise ValidationError("Either value_in_use or fvlcts is required")

        viu = Decimal(str(value_in_use if value_in_use is not None else "0"))
        fvlcts_value = Decimal(str(fvlcts if fvlcts is not None else "0"))
        recoverable = calculate_recoverable_amount(viu, fvlcts_value)
        impairment_loss = calculate_impairment_loss(nbv, recoverable)

        row = FaImpairment(
            tenant_id=tenant_id,
            entity_id=asset.entity_id,
            asset_id=asset.id,
            impairment_date=impairment_date,
            pre_impairment_nbv=nbv,
            recoverable_amount=recoverable,
            value_in_use=value_in_use,
            fvlcts=fvlcts,
            impairment_loss=impairment_loss,
            discount_rate=discount_rate,
        )
        self._session.add(row)

        if impairment_loss > Decimal("0"):
            asset.status = "IMPAIRED"

        await self._session.flush()
        return row

    async def get_impairment_history(
        self,
        tenant_id: uuid.UUID,
        asset_id: uuid.UUID,
    ) -> list[FaImpairment]:
        rows = (
            await self._session.execute(
                select(FaImpairment)
                .where(FaImpairment.tenant_id == tenant_id, FaImpairment.asset_id == asset_id)
                .order_by(FaImpairment.impairment_date.desc(), FaImpairment.created_at.desc())
            )
        ).scalars().all()
        return list(rows)

    async def get_fixed_asset_register(
        self,
        tenant_id: uuid.UUID,
        entity_id: uuid.UUID,
        as_of_date: date,
        gaap: str = "INDAS",
    ) -> list[dict[str, Any]]:
        gaap_key = gaap.upper()
        assets = (
            await self._session.execute(
                select(FaAsset, FaAssetClass)
                .join(FaAssetClass, FaAssetClass.id == FaAsset.asset_class_id)
                .where(FaAsset.tenant_id == tenant_id, FaAsset.entity_id == entity_id)
                .order_by(FaAsset.asset_code)
            )
        ).all()

        lines: list[dict[str, Any]] = []
        for asset, asset_class in assets:
            accumulated_dep = await self._asset_accum_dep(tenant_id, asset.id, gaap_key, as_of=as_of_date)
            ytd_dep = Decimal(
                str(
                    (
                        await self._session.execute(
                            select(func.coalesce(func.sum(FaDepreciationRun.depreciation_amount), Decimal("0"))).where(
                                FaDepreciationRun.tenant_id == tenant_id,
                                FaDepreciationRun.asset_id == asset.id,
                                FaDepreciationRun.gaap == gaap_key,
                                func.date_part("year", FaDepreciationRun.run_date) == as_of_date.year,
                            )
                        )
                    ).scalar_one()
                )
            )
            nbv = Decimal(str(asset.original_cost)) - accumulated_dep
            lines.append(
                {
                    "asset_code": asset.asset_code,
                    "asset_name": asset.asset_name,
                    "class_name": asset_class.name,
                    "purchase_date": asset.purchase_date,
                    "capitalisation_date": asset.capitalisation_date,
                    "original_cost": Decimal(str(asset.original_cost)),
                    "accumulated_dep": accumulated_dep,
                    "nbv": nbv,
                    "ytd_depreciation": ytd_dep,
                    "status": asset.status,
                }
            )
        return lines

    async def dispose_asset(
        self,
        tenant_id: uuid.UUID,
        asset_id: uuid.UUID,
        disposal_date: date,
        proceeds: Decimal,
    ) -> FaAsset:
        asset = await self._get_asset_or_404(tenant_id, asset_id)
        accum_dep = await self._asset_accum_dep(tenant_id, asset.id, "INDAS", as_of=disposal_date)
        nbv = Decimal(str(asset.original_cost)) - accum_dep
        gain_loss = Decimal(str(proceeds)) - nbv

        asset.status = "DISPOSED"
        asset.disposal_date = disposal_date
        asset.disposal_proceeds = Decimal(str(proceeds))
        overrides = dict(asset.gaap_overrides or {})
        overrides["disposal_gain_loss"] = str(gain_loss)
        asset.gaap_overrides = overrides

        await self._session.flush()
        return asset


__all__ = ["FixedAssetService"]
