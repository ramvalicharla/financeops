from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal, ROUND_HALF_UP
from difflib import SequenceMatcher
from typing import Any

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import NotFoundError
from financeops.modules.coa.models import CoaLedgerAccount, ErpAccountMapping, TenantCoaAccount

_CONFIDENCE_SCALE = Decimal("0.0001")


def _to_confidence(value: float) -> Decimal:
    return Decimal(str(round(value, 4))).quantize(_CONFIDENCE_SCALE, rounding=ROUND_HALF_UP)


def _normalize_code(value: str) -> str:
    return value.strip().upper()


def _normalize_name(value: str) -> str:
    return " ".join(value.strip().lower().split())


class ErpMappingService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def auto_suggest_mappings(
        self,
        tenant_id: uuid.UUID,
        entity_id: uuid.UUID,
        erp_connector_type: str,
        erp_accounts: list[dict[str, Any]],
    ) -> list[ErpAccountMapping]:
        account_rows = (
            await self._session.execute(
                select(TenantCoaAccount, CoaLedgerAccount)
                .outerjoin(CoaLedgerAccount, CoaLedgerAccount.id == TenantCoaAccount.ledger_account_id)
                .where(TenantCoaAccount.tenant_id == tenant_id)
                .where(TenantCoaAccount.is_active.is_(True))
                .where(
                    or_(
                        CoaLedgerAccount.id.is_(None),
                        CoaLedgerAccount.tenant_id == tenant_id,
                        CoaLedgerAccount.tenant_id.is_(None),
                    )
                )
            )
        ).all()

        by_exact_code: dict[str, tuple[TenantCoaAccount, CoaLedgerAccount | None]] = {}
        for tenant_account, ledger_account in account_rows:
            by_exact_code[_normalize_code(tenant_account.account_code)] = (
                tenant_account,
                ledger_account,
            )

        existing_rows = (
            await self._session.execute(
                select(ErpAccountMapping).where(
                    ErpAccountMapping.tenant_id == tenant_id,
                    ErpAccountMapping.entity_id == entity_id,
                    ErpAccountMapping.erp_connector_type == erp_connector_type,
                    ErpAccountMapping.erp_account_code.in_(
                        [_normalize_code(str(item.get("code", ""))) for item in erp_accounts]
                    ),
                )
            )
        ).scalars().all()
        existing_by_code = {row.erp_account_code: row for row in existing_rows}

        result_rows: list[ErpAccountMapping] = []
        for item in erp_accounts:
            erp_code = _normalize_code(str(item.get("code", "")))
            erp_name = str(item.get("name", "")).strip()
            erp_type = str(item.get("type", "") or "").strip()

            existing = existing_by_code.get(erp_code)
            if existing is not None and existing.is_confirmed and existing.tenant_coa_account_id is not None:
                result_rows.append(existing)
                continue

            suggested_account_id: uuid.UUID | None = None
            confidence = Decimal("0.0000")

            exact = by_exact_code.get(erp_code)
            if exact is not None:
                suggested_account_id = exact[0].id
                confidence = Decimal("1.0000")
            else:
                normalized_erp_name = _normalize_name(erp_name)
                best_ratio = 0.0
                best_account: TenantCoaAccount | None = None
                for tenant_account, ledger_account in account_rows:
                    base_name = _normalize_name(tenant_account.display_name)
                    ratio = SequenceMatcher(a=normalized_erp_name, b=base_name).ratio()
                    if erp_type and ledger_account is not None:
                        hint = erp_type.lower()
                        flag = (ledger_account.bs_pl_flag or "").lower()
                        if ("asset" in hint and flag == "asset") or ("liab" in hint and flag == "liability"):
                            ratio += 0.05
                        if ("income" in hint or "revenue" in hint) and flag == "revenue":
                            ratio += 0.05
                        if ("expense" in hint or "cost" in hint) and flag == "expense":
                            ratio += 0.05
                    if ratio > best_ratio:
                        best_ratio = ratio
                        best_account = tenant_account
                if best_account is not None:
                    suggested_account_id = best_account.id
                    confidence = _to_confidence(best_ratio if best_ratio <= 1 else 1.0)

            values = {
                "tenant_id": tenant_id,
                "entity_id": entity_id,
                "erp_connector_type": erp_connector_type,
                "erp_account_code": erp_code,
                "erp_account_name": erp_name,
                "erp_account_type": erp_type or None,
                "tenant_coa_account_id": suggested_account_id,
                "mapping_confidence": confidence,
                "is_auto_mapped": True,
                "is_confirmed": False,
                "confirmed_by": None,
                "confirmed_at": None,
                "is_active": True,
            }
            stmt = insert(ErpAccountMapping).values(values)
            stmt = stmt.on_conflict_do_update(
                constraint="uq_erp_account_mappings_scope_code",
                set_={
                    "erp_account_name": stmt.excluded.erp_account_name,
                    "erp_account_type": stmt.excluded.erp_account_type,
                    "tenant_coa_account_id": stmt.excluded.tenant_coa_account_id,
                    "mapping_confidence": stmt.excluded.mapping_confidence,
                    "is_auto_mapped": stmt.excluded.is_auto_mapped,
                    "is_confirmed": False,
                    "confirmed_by": None,
                    "confirmed_at": None,
                    "updated_at": func.now(),
                },
            )
            await self._session.execute(stmt)

        refreshed = (
            await self._session.execute(
                select(ErpAccountMapping).where(
                    ErpAccountMapping.tenant_id == tenant_id,
                    ErpAccountMapping.entity_id == entity_id,
                    ErpAccountMapping.erp_connector_type == erp_connector_type,
                    ErpAccountMapping.erp_account_code.in_(
                        [_normalize_code(str(item.get("code", ""))) for item in erp_accounts]
                    ),
                )
            )
        ).scalars().all()
        result_rows.extend([row for row in refreshed if row not in result_rows])
        return result_rows

    async def confirm_mapping(
        self,
        tenant_id: uuid.UUID,
        mapping_id: uuid.UUID,
        tenant_coa_account_id: uuid.UUID,
        confirmed_by: uuid.UUID,
    ) -> ErpAccountMapping:
        row = (
            await self._session.execute(
                select(ErpAccountMapping).where(
                    ErpAccountMapping.id == mapping_id,
                    ErpAccountMapping.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        if row is None:
            raise NotFoundError("ERP mapping not found")
        row.tenant_coa_account_id = tenant_coa_account_id
        row.is_confirmed = True
        row.confirmed_by = confirmed_by
        row.confirmed_at = datetime.now(UTC)
        row.is_active = True
        await self._session.flush()
        return row

    async def bulk_confirm_mappings(
        self,
        tenant_id: uuid.UUID,
        mapping_ids: list[uuid.UUID],
        confirmed_by: uuid.UUID,
    ) -> int:
        if not mapping_ids:
            return 0
        result = await self._session.execute(
            update(ErpAccountMapping)
            .where(ErpAccountMapping.tenant_id == tenant_id)
            .where(ErpAccountMapping.id.in_(mapping_ids))
            .where(ErpAccountMapping.tenant_coa_account_id.is_not(None))
            .where(ErpAccountMapping.is_confirmed.is_(False))
            .values(
                is_confirmed=True,
                confirmed_by=confirmed_by,
                confirmed_at=datetime.now(UTC),
                updated_at=func.now(),
            )
        )
        return int(result.rowcount or 0)

    async def get_unmapped_accounts(
        self,
        tenant_id: uuid.UUID,
        entity_id: uuid.UUID,
        erp_connector_type: str | None = None,
    ) -> list[ErpAccountMapping]:
        stmt = select(ErpAccountMapping).where(
            ErpAccountMapping.tenant_id == tenant_id,
            ErpAccountMapping.entity_id == entity_id,
            or_(
                ErpAccountMapping.tenant_coa_account_id.is_(None),
                ErpAccountMapping.is_confirmed.is_(False),
            ),
        )
        if erp_connector_type:
            stmt = stmt.where(ErpAccountMapping.erp_connector_type == erp_connector_type)
        rows = (await self._session.execute(stmt.order_by(ErpAccountMapping.erp_account_code))).scalars().all()
        return list(rows)

    async def get_mapping_summary(
        self,
        tenant_id: uuid.UUID,
        entity_id: uuid.UUID,
        erp_connector_type: str | None = None,
    ) -> dict[str, Decimal | int]:
        base_filters = [
            ErpAccountMapping.tenant_id == tenant_id,
            ErpAccountMapping.entity_id == entity_id,
        ]
        if erp_connector_type:
            base_filters.append(ErpAccountMapping.erp_connector_type == erp_connector_type)

        total = int(
            (
                await self._session.execute(
                    select(func.count()).select_from(ErpAccountMapping).where(*base_filters)
                )
            ).scalar_one()
        )
        mapped = int(
            (
                await self._session.execute(
                    select(func.count())
                    .select_from(ErpAccountMapping)
                    .where(*base_filters)
                    .where(ErpAccountMapping.tenant_coa_account_id.is_not(None))
                )
            ).scalar_one()
        )
        confirmed = int(
            (
                await self._session.execute(
                    select(func.count())
                    .select_from(ErpAccountMapping)
                    .where(*base_filters)
                    .where(ErpAccountMapping.tenant_coa_account_id.is_not(None))
                    .where(ErpAccountMapping.is_confirmed.is_(True))
                )
            ).scalar_one()
        )
        avg_confidence_raw = (
            await self._session.execute(
                select(func.avg(ErpAccountMapping.mapping_confidence))
                .where(*base_filters)
                .where(ErpAccountMapping.mapping_confidence.is_not(None))
            )
        ).scalar_one_or_none()
        avg_confidence = Decimal(str(avg_confidence_raw or "0")).quantize(_CONFIDENCE_SCALE)
        return {
            "total": total,
            "mapped": mapped,
            "confirmed": confirmed,
            "unmapped": total - confirmed,
            "confidence_avg": avg_confidence,
        }
