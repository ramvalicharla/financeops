from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.tenants import IamTenant
from financeops.modules.coa.models import (
    CoaFsClassification,
    CoaFsLineItem,
    CoaFsSchedule,
    CoaFsSubline,
    CoaGaapMapping,
    CoaLedgerAccount,
    ErpAccountMapping,
    TenantCoaAccount,
)
from financeops.services.fx import resolve_selected_rate

_BALANCE_TOLERANCE = Decimal("0.01")
_DEFAULT_REPORTING_CURRENCY = "INR"


@dataclass(frozen=True)
class RawTBLine:
    erp_account_code: str
    erp_account_name: str
    debit_amount: Decimal
    credit_amount: Decimal
    currency: str
    period_start: date | None
    period_end: date | None


@dataclass(frozen=True)
class ClassifiedTBLine:
    erp_account_code: str
    erp_account_name: str
    tenant_coa_account_id: uuid.UUID | None
    platform_account_code: str | None
    platform_account_name: str | None
    fs_classification: str | None
    fs_schedule: str | None
    fs_line_item: str | None
    fs_subline: str | None
    debit_amount: Decimal
    credit_amount: Decimal
    net_amount: Decimal
    currency: str
    is_unmapped: bool
    is_unconfirmed: bool


@dataclass(frozen=True)
class GlobalTBResult:
    entity_results: dict[uuid.UUID, list[ClassifiedTBLine]]
    consolidated: list[ClassifiedTBLine]
    unmapped_lines: list[ClassifiedTBLine]
    unconfirmed_lines: list[ClassifiedTBLine]
    total_debits: Decimal
    total_credits: Decimal
    is_balanced: bool
    unmapped_count: int
    unconfirmed_count: int


def _to_decimal(value: Any) -> Decimal:
    if value is None or value == "":
        return Decimal("0")
    return Decimal(str(value))


def _coerce_raw_line(item: RawTBLine | dict[str, Any]) -> RawTBLine:
    if isinstance(item, RawTBLine):
        return item

    erp_code = str(
        item.get("erp_account_code")
        or item.get("account_code")
        or item.get("code")
        or ""
    ).strip()
    erp_name = str(
        item.get("erp_account_name")
        or item.get("account_name")
        or item.get("name")
        or ""
    ).strip()
    amount = _to_decimal(item.get("amount"))
    is_debit = bool(item.get("is_debit", True))

    debit = item.get("debit_amount")
    credit = item.get("credit_amount")
    if debit is None and credit is None and "closing_balance" in item:
        closing = _to_decimal(item.get("closing_balance"))
        debit = closing if closing >= Decimal("0") else Decimal("0")
        credit = abs(closing) if closing < Decimal("0") else Decimal("0")
    if debit is None and credit is None and amount != Decimal("0"):
        debit = amount if is_debit else Decimal("0")
        credit = abs(amount) if not is_debit else Decimal("0")

    return RawTBLine(
        erp_account_code=erp_code,
        erp_account_name=erp_name,
        debit_amount=_to_decimal(debit),
        credit_amount=_to_decimal(credit),
        currency=str(item.get("currency") or "INR"),
        period_start=None,
        period_end=None,
    )


class GlobalTrialBalanceService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _resolve_reporting_currency(self, tenant_id: uuid.UUID) -> str:
        row = (
            await self._session.execute(
                select(IamTenant.default_currency).where(IamTenant.id == tenant_id)
            )
        ).scalar_one_or_none()
        return (row or _DEFAULT_REPORTING_CURRENCY).upper()

    async def _convert_amount(
        self,
        *,
        tenant_id: uuid.UUID,
        amount: Decimal,
        source_currency: str,
        target_currency: str,
        as_of_date: date,
    ) -> tuple[Decimal, str]:
        source = source_currency.upper()
        target = target_currency.upper()
        if source == target:
            return amount, target
        decision = await resolve_selected_rate(
            self._session,
            tenant_id=tenant_id,
            base_currency=source,
            quote_currency=target,
            as_of_date=as_of_date,
            redis_client=None,
        )
        return amount * decision.selected_rate, target

    async def classify_tb(
        self,
        tenant_id: uuid.UUID,
        entity_id: uuid.UUID,
        raw_tb: list[RawTBLine | dict[str, Any]],
        gaap: str = "INDAS",
    ) -> GlobalTBResult:
        normalized_lines = [_coerce_raw_line(line) for line in raw_tb]
        gaap_code = gaap.upper()

        mapping_rows = (
            await self._session.execute(
                select(ErpAccountMapping)
                .where(ErpAccountMapping.tenant_id == tenant_id)
                .where(ErpAccountMapping.entity_id == entity_id)
                .where(ErpAccountMapping.is_active.is_(True))
            )
        ).scalars().all()
        mapping_by_code: dict[str, ErpAccountMapping] = {}
        for row in mapping_rows:
            code = row.erp_account_code.upper()
            current = mapping_by_code.get(code)
            if current is None:
                mapping_by_code[code] = row
                continue
            if row.is_confirmed and not current.is_confirmed:
                mapping_by_code[code] = row

        tenant_account_ids = [row.tenant_coa_account_id for row in mapping_rows if row.tenant_coa_account_id]
        tenant_accounts = (
            await self._session.execute(
                select(TenantCoaAccount).where(TenantCoaAccount.id.in_(tenant_account_ids))
            )
        ).scalars().all()
        tenant_account_by_id = {account.id: account for account in tenant_accounts}

        ledger_ids = [account.ledger_account_id for account in tenant_accounts if account.ledger_account_id]
        ledgers = (
            await self._session.execute(
                select(CoaLedgerAccount).where(
                    CoaLedgerAccount.id.in_(ledger_ids),
                    or_(
                        CoaLedgerAccount.tenant_id == tenant_id,
                        CoaLedgerAccount.tenant_id.is_(None),
                    ),
                )
            )
        ).scalars().all()
        ledger_by_id = {ledger.id: ledger for ledger in ledgers}

        gaap_mappings = (
            await self._session.execute(
                select(CoaGaapMapping).where(
                    CoaGaapMapping.ledger_account_id.in_(ledger_ids),
                    CoaGaapMapping.gaap == gaap_code,
                    CoaGaapMapping.is_active.is_(True),
                )
            )
        ).scalars().all()
        gaap_by_ledger = {mapping.ledger_account_id: mapping for mapping in gaap_mappings}

        schedule_ids = [mapping.fs_schedule_id for mapping in gaap_mappings]
        line_item_ids = [mapping.fs_line_item_id for mapping in gaap_mappings]
        subline_ids = [mapping.fs_subline_id for mapping in gaap_mappings if mapping.fs_subline_id]

        schedules = (
            await self._session.execute(
                select(CoaFsSchedule).where(CoaFsSchedule.id.in_(schedule_ids))
            )
        ).scalars().all()
        schedule_by_id = {row.id: row for row in schedules}

        line_items = (
            await self._session.execute(
                select(CoaFsLineItem).where(CoaFsLineItem.id.in_(line_item_ids))
            )
        ).scalars().all()
        line_item_by_id = {row.id: row for row in line_items}

        sublines = (
            await self._session.execute(
                select(CoaFsSubline).where(CoaFsSubline.id.in_(subline_ids))
            )
        ).scalars().all()
        subline_by_id = {row.id: row for row in sublines}

        classification_ids = [schedule.fs_classification_id for schedule in schedules]
        classifications = (
            await self._session.execute(
                select(CoaFsClassification).where(CoaFsClassification.id.in_(classification_ids))
            )
        ).scalars().all()
        classification_by_id = {row.id: row for row in classifications}

        classified_lines: list[ClassifiedTBLine] = []
        unmapped_lines: list[ClassifiedTBLine] = []
        unconfirmed_lines: list[ClassifiedTBLine] = []

        total_debits = Decimal("0")
        total_credits = Decimal("0")

        for line in normalized_lines:
            total_debits += line.debit_amount
            total_credits += line.credit_amount
            mapping = mapping_by_code.get(line.erp_account_code.upper())
            tenant_account: TenantCoaAccount | None = None
            ledger: CoaLedgerAccount | None = None
            gaap_mapping: CoaGaapMapping | None = None

            is_unmapped = mapping is None or mapping.tenant_coa_account_id is None
            is_unconfirmed = mapping is not None and not mapping.is_confirmed
            if mapping is not None and mapping.tenant_coa_account_id is not None:
                tenant_account = tenant_account_by_id.get(mapping.tenant_coa_account_id)
                if tenant_account is not None and tenant_account.ledger_account_id is not None:
                    ledger = ledger_by_id.get(tenant_account.ledger_account_id)
                    if ledger is not None:
                        gaap_mapping = gaap_by_ledger.get(ledger.id)

            schedule_name: str | None = None
            line_item_name: str | None = None
            subline_name: str | None = None
            classification_name: str | None = None
            if gaap_mapping is not None:
                schedule = schedule_by_id.get(gaap_mapping.fs_schedule_id)
                line_item = line_item_by_id.get(gaap_mapping.fs_line_item_id)
                subline = subline_by_id.get(gaap_mapping.fs_subline_id) if gaap_mapping.fs_subline_id else None
                schedule_name = schedule.name if schedule is not None else None
                line_item_name = line_item.name if line_item is not None else None
                subline_name = subline.name if subline is not None else None
                if schedule is not None:
                    classification = classification_by_id.get(schedule.fs_classification_id)
                    classification_name = classification.name if classification is not None else None

            classified = ClassifiedTBLine(
                erp_account_code=line.erp_account_code,
                erp_account_name=line.erp_account_name,
                tenant_coa_account_id=tenant_account.id if tenant_account is not None else None,
                platform_account_code=tenant_account.account_code if tenant_account is not None else None,
                platform_account_name=tenant_account.display_name if tenant_account is not None else None,
                fs_classification=classification_name,
                fs_schedule=schedule_name,
                fs_line_item=line_item_name,
                fs_subline=subline_name,
                debit_amount=line.debit_amount,
                credit_amount=line.credit_amount,
                net_amount=line.debit_amount - line.credit_amount,
                currency=line.currency,
                is_unmapped=is_unmapped,
                is_unconfirmed=is_unconfirmed,
            )
            classified_lines.append(classified)
            if is_unmapped:
                unmapped_lines.append(classified)
            if is_unconfirmed:
                unconfirmed_lines.append(classified)

        reporting_currency = await self._resolve_reporting_currency(tenant_id)
        consolidated = await self._consolidate_lines(
            [line for line in classified_lines if not line.is_unmapped],
            tenant_id=tenant_id,
            reporting_currency=reporting_currency,
        )
        is_balanced = abs(total_debits - total_credits) < _BALANCE_TOLERANCE
        return GlobalTBResult(
            entity_results={entity_id: classified_lines},
            consolidated=consolidated,
            unmapped_lines=unmapped_lines,
            unconfirmed_lines=unconfirmed_lines,
            total_debits=total_debits,
            total_credits=total_credits,
            is_balanced=is_balanced,
            unmapped_count=len(unmapped_lines),
            unconfirmed_count=len(unconfirmed_lines),
        )

    async def classify_multi_entity_tb(
        self,
        tenant_id: uuid.UUID,
        entity_raw_tbs: dict[uuid.UUID, list[RawTBLine | dict[str, Any]]],
        gaap: str = "INDAS",
    ) -> GlobalTBResult:
        entity_results: dict[uuid.UUID, list[ClassifiedTBLine]] = {}
        all_classified: list[ClassifiedTBLine] = []
        unmapped_lines: list[ClassifiedTBLine] = []
        unconfirmed_lines: list[ClassifiedTBLine] = []
        total_debits = Decimal("0")
        total_credits = Decimal("0")

        for entity_id, raw_tb in entity_raw_tbs.items():
            result = await self.classify_tb(
                tenant_id=tenant_id,
                entity_id=entity_id,
                raw_tb=raw_tb,
                gaap=gaap,
            )
            entity_results[entity_id] = result.entity_results.get(entity_id, [])
            all_classified.extend(entity_results[entity_id])
            unmapped_lines.extend(result.unmapped_lines)
            unconfirmed_lines.extend(result.unconfirmed_lines)
            total_debits += result.total_debits
            total_credits += result.total_credits

        reporting_currency = await self._resolve_reporting_currency(tenant_id)
        consolidated = await self._consolidate_lines(
            [line for line in all_classified if not line.is_unmapped],
            tenant_id=tenant_id,
            reporting_currency=reporting_currency,
        )
        return GlobalTBResult(
            entity_results=entity_results,
            consolidated=consolidated,
            unmapped_lines=unmapped_lines,
            unconfirmed_lines=unconfirmed_lines,
            total_debits=total_debits,
            total_credits=total_credits,
            is_balanced=abs(total_debits - total_credits) < _BALANCE_TOLERANCE,
            unmapped_count=len(unmapped_lines),
            unconfirmed_count=len(unconfirmed_lines),
        )

    async def _consolidate_lines(
        self,
        lines: list[ClassifiedTBLine],
        *,
        tenant_id: uuid.UUID,
        reporting_currency: str,
    ) -> list[ClassifiedTBLine]:
        grouped: dict[tuple[str | None, str | None, str | None, str | None, str | None, str], ClassifiedTBLine] = {}
        as_of_date = date.today()
        for line in lines:
            debit_amount = line.debit_amount
            credit_amount = line.credit_amount
            currency = line.currency
            if line.currency.upper() != reporting_currency:
                try:
                    debit_amount, currency = await self._convert_amount(
                        tenant_id=tenant_id,
                        amount=line.debit_amount,
                        source_currency=line.currency,
                        target_currency=reporting_currency,
                        as_of_date=as_of_date,
                    )
                    credit_amount, currency = await self._convert_amount(
                        tenant_id=tenant_id,
                        amount=line.credit_amount,
                        source_currency=line.currency,
                        target_currency=reporting_currency,
                        as_of_date=as_of_date,
                    )
                except Exception:  # noqa: BLE001
                    debit_amount = line.debit_amount
                    credit_amount = line.credit_amount
                    currency = line.currency
            key = (
                line.platform_account_code,
                line.fs_classification,
                line.fs_schedule,
                line.fs_line_item,
                line.fs_subline,
                currency,
            )
            existing = grouped.get(key)
            if existing is None:
                grouped[key] = ClassifiedTBLine(
                    erp_account_code=line.erp_account_code,
                    erp_account_name=line.erp_account_name,
                    tenant_coa_account_id=line.tenant_coa_account_id,
                    platform_account_code=line.platform_account_code,
                    platform_account_name=line.platform_account_name,
                    fs_classification=line.fs_classification,
                    fs_schedule=line.fs_schedule,
                    fs_line_item=line.fs_line_item,
                    fs_subline=line.fs_subline,
                    debit_amount=debit_amount,
                    credit_amount=credit_amount,
                    net_amount=debit_amount - credit_amount,
                    currency=currency,
                    is_unmapped=False,
                    is_unconfirmed=line.is_unconfirmed,
                )
                continue
            grouped[key] = ClassifiedTBLine(
                erp_account_code=existing.erp_account_code,
                erp_account_name=existing.erp_account_name,
                tenant_coa_account_id=existing.tenant_coa_account_id,
                platform_account_code=existing.platform_account_code,
                platform_account_name=existing.platform_account_name,
                fs_classification=existing.fs_classification,
                fs_schedule=existing.fs_schedule,
                fs_line_item=existing.fs_line_item,
                fs_subline=existing.fs_subline,
                debit_amount=existing.debit_amount + debit_amount,
                credit_amount=existing.credit_amount + credit_amount,
                net_amount=(existing.debit_amount + debit_amount) - (existing.credit_amount + credit_amount),
                currency=existing.currency,
                is_unmapped=False,
                is_unconfirmed=existing.is_unconfirmed or line.is_unconfirmed,
            )
        return sorted(
            grouped.values(),
            key=lambda row: (row.fs_classification or "", row.fs_schedule or "", row.platform_account_code or ""),
        )
