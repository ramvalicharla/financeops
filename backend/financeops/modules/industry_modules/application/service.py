from __future__ import annotations

import calendar
import logging
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from math import pow

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import NotFoundError, ValidationError
from financeops.core.intent.enums import IntentSourceChannel, IntentType
from financeops.core.intent.journal_pipeline import (
    GovernedJournalMutationResult,
    submit_governed_journal_intent,
)
from financeops.db.models.industry_modules import (
    FinanceModule,
    IndustryAccrualSchedule,
    IndustryAssetSchedule,
    IndustryContract,
    IndustryFixedAsset,
    IndustryJournalLink,
    IndustryLease,
    IndustryLeaseSchedule,
    IndustryPerformanceObligation,
    IndustryPrepaidSchedule,
    IndustryRevenueSchedule,
)
from financeops.modules.accounting_layer.domain.schemas import JournalCreate
from financeops.modules.coa.models import TenantCoaAccount
from financeops.modules.industry_modules.schemas import (
    AccrualCreateRequest,
    AssetScheduleRow,
    FixedAssetCreateRequest,
    FixedAssetCreateResponse,
    LeaseCreateRequest,
    LeaseCreateResponse,
    LeaseScheduleRow,
    ModuleResponse,
    ModuleStatus,
    PrepaidCreateRequest,
    RevenueContractCreateRequest,
    RevenueContractCreateResponse,
    RevenueScheduleRow,
    ScheduleBatchCreateResponse,
)

logger = logging.getLogger(__name__)

_SUPPORTED_MODULES = {
    "LEASE",
    "REVENUE",
    "ASSETS",
    "PREPAID",
    "ACCRUAL",
    "SUBSCRIPTION",
}
_ENABLED = "ENABLED"
_DISABLED = "DISABLED"
_ROUNDING = Decimal("0.0001")


@dataclass(frozen=True)
class _AccountPair:
    debit_account_code: str
    credit_account_code: str


@dataclass(frozen=True)
class LeaseProjectionRow:
    period_number: int
    opening_liability: Decimal
    interest_expense: Decimal
    lease_payment: Decimal
    closing_liability: Decimal
    rou_asset_value: Decimal
    depreciation: Decimal


@dataclass(frozen=True)
class AssetProjectionRow:
    period_number: int
    depreciation: Decimal
    net_book_value: Decimal


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _q(value: Decimal) -> Decimal:
    return Decimal(value).quantize(_ROUNDING)


def _months_between_inclusive(start_date: date, end_date: date) -> list[date]:
    if end_date < start_date:
        raise ValidationError("End date cannot be before start date.")

    out: list[date] = []
    cursor = start_date
    while cursor <= end_date:
        out.append(cursor)
        next_month = cursor.month + 1
        next_year = cursor.year
        if next_month == 13:
            next_month = 1
            next_year += 1
        day = min(cursor.day, calendar.monthrange(next_year, next_month)[1])
        cursor = date(next_year, next_month, day)

        if len(out) > 600:
            raise ValidationError("Schedule horizon too long. Max supported periods: 600.")
    return out


def split_evenly(total: Decimal, parts: int) -> list[Decimal]:
    if parts <= 0:
        raise ValidationError("parts must be >= 1")
    per_part = _q(total / Decimal(parts))
    rows = [per_part for _ in range(parts)]
    allocated = per_part * Decimal(parts)
    remainder = _q(total - allocated)
    if remainder != 0:
        rows[0] = _q(rows[0] + remainder)
    return rows


def build_lease_projection(
    *,
    lease_payment: Decimal,
    annual_discount_rate: Decimal,
    period_count: int,
) -> tuple[Decimal, list[LeaseProjectionRow]]:
    if period_count <= 0:
        raise ValidationError("period_count must be >= 1")

    payment = _q(lease_payment)
    monthly_rate = _q(annual_discount_rate / Decimal("12")) if annual_discount_rate > 0 else Decimal("0.0000")
    if monthly_rate > 0:
        pv_factor = (Decimal("1") - (Decimal("1") + monthly_rate) ** Decimal(-period_count)) / monthly_rate
        present_value = _q(payment * pv_factor)
    else:
        present_value = _q(payment * Decimal(period_count))

    rows: list[LeaseProjectionRow] = []
    opening_liability = present_value
    rou_value = present_value
    depreciation = _q(present_value / Decimal(period_count))
    for index in range(1, period_count + 1):
        interest = _q(opening_liability * monthly_rate)
        closing = _q(opening_liability + interest - payment)
        if index == period_count:
            closing = Decimal("0.0000")
        rows.append(
            LeaseProjectionRow(
                period_number=index,
                opening_liability=opening_liability,
                interest_expense=interest,
                lease_payment=payment,
                closing_liability=max(closing, Decimal("0.0000")),
                rou_asset_value=rou_value,
                depreciation=depreciation,
            )
        )
        opening_liability = max(closing, Decimal("0.0000"))
        rou_value = max(_q(rou_value - depreciation), Decimal("0.0000"))
    return present_value, rows


def build_asset_projection(
    *,
    cost: Decimal,
    residual_value: Decimal,
    period_count: int,
    depreciation_method: str,
) -> list[AssetProjectionRow]:
    if period_count <= 0:
        raise ValidationError("period_count must be >= 1")
    if residual_value > cost:
        raise ValidationError("residual_value cannot exceed cost")

    rows: list[AssetProjectionRow] = []
    nbv = _q(cost)
    residual = _q(residual_value)
    method = depreciation_method.upper()

    if method == "SLM":
        plan = split_evenly(cost - residual_value, period_count)
        for idx in range(1, period_count + 1):
            depreciation = plan[idx - 1]
            if idx == period_count:
                depreciation = _q(nbv - residual)
            nbv = _q(nbv - depreciation)
            rows.append(
                AssetProjectionRow(
                    period_number=idx,
                    depreciation=depreciation,
                    net_book_value=max(nbv, residual),
                )
            )
        return rows

    if method == "WDV":
        residual_target = residual_value if residual_value > 0 else Decimal("0.01")
        rate = Decimal(str(1 - pow(float(residual_target / cost), 1 / period_count)))
        for idx in range(1, period_count + 1):
            depreciation = _q(nbv * rate)
            if idx == period_count:
                depreciation = _q(nbv - residual)
            nbv = _q(nbv - depreciation)
            rows.append(
                AssetProjectionRow(
                    period_number=idx,
                    depreciation=depreciation,
                    net_book_value=max(nbv, residual),
                )
            )
        return rows

    raise ValidationError("depreciation_method must be SLM or WDV")


def _as_module_status(raw: str) -> ModuleStatus:
    value = raw.upper()
    if value not in {_ENABLED, _DISABLED}:
        raise ValidationError(f"Invalid module status '{raw}'.")
    return value  # type: ignore[return-value]


async def list_modules(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
) -> list[ModuleResponse]:
    stmt = (
        select(FinanceModule)
        .where(FinanceModule.tenant_id == tenant_id)
        .order_by(FinanceModule.module_name.asc())
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [
        ModuleResponse(
            module_name=row.module_name,
            status=_as_module_status(row.status),
            configuration_json=dict(row.configuration_json or {}),
            updated_at=row.updated_at,
        )
        for row in rows
    ]


async def set_module_status(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    module_name: str,
    status: ModuleStatus,
    configuration_json: dict[str, object] | None,
) -> ModuleResponse:
    normalized_module = module_name.strip().upper()
    if normalized_module not in _SUPPORTED_MODULES:
        raise ValidationError(f"Unsupported module '{module_name}'.")

    stmt = select(FinanceModule).where(
        FinanceModule.tenant_id == tenant_id,
        FinanceModule.module_name == normalized_module,
    )
    existing = (await db.execute(stmt)).scalar_one_or_none()
    now = _utcnow()
    if existing is None:
        existing = FinanceModule(
            tenant_id=tenant_id,
            module_name=normalized_module,
            status=status,
            configuration_json=configuration_json or {},
            created_by=actor_user_id,
            updated_at=now,
        )
        db.add(existing)
    else:
        existing.status = status
        if configuration_json is not None:
            existing.configuration_json = configuration_json
        existing.updated_at = now

    await db.flush()
    return ModuleResponse(
        module_name=existing.module_name,
        status=_as_module_status(existing.status),
        configuration_json=dict(existing.configuration_json or {}),
        updated_at=existing.updated_at,
    )


async def _ensure_module_enabled(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    module_name: str,
) -> None:
    normalized_module = module_name.strip().upper()
    stmt = select(FinanceModule).where(
        FinanceModule.tenant_id == tenant_id,
        FinanceModule.module_name == normalized_module,
    )
    module = (await db.execute(stmt)).scalar_one_or_none()
    if module is None or module.status.upper() != _ENABLED:
        raise ValidationError(
            f"Module '{normalized_module}' is disabled. Enable it from /api/v1/modules first."
        )


async def _resolve_account_pair(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    debit_code: str | None,
    credit_code: str | None,
) -> _AccountPair:
    if debit_code and credit_code and debit_code.strip().upper() == credit_code.strip().upper():
        raise ValidationError("Debit and credit account codes must be distinct.")

    if debit_code and credit_code:
        return _AccountPair(
            debit_account_code=debit_code.strip().upper(),
            credit_account_code=credit_code.strip().upper(),
        )

    stmt: Select[tuple[TenantCoaAccount]] = (
        select(TenantCoaAccount)
        .where(
            TenantCoaAccount.tenant_id == tenant_id,
            TenantCoaAccount.is_active.is_(True),
        )
        .order_by(TenantCoaAccount.account_code.asc())
        .limit(10)
    )
    accounts = (await db.execute(stmt)).scalars().all()
    if len(accounts) < 2:
        raise ValidationError(
            "At least two active CoA accounts are required to generate draft journals."
        )

    debit = debit_code.strip().upper() if debit_code else accounts[0].account_code
    credit = credit_code.strip().upper() if credit_code else accounts[1].account_code
    if debit == credit:
        for account in accounts:
            if account.account_code != debit:
                credit = account.account_code
                break
    if debit == credit:
        raise ValidationError("Unable to resolve distinct debit and credit accounts.")
    return _AccountPair(debit_account_code=debit, credit_account_code=credit)


async def _create_module_draft_journal(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    actor_role: str,
    org_entity_id: uuid.UUID,
    journal_date: date,
    reference: str,
    narration: str,
    amount: Decimal,
    debit_account_code: str,
    credit_account_code: str,
) -> GovernedJournalMutationResult:
    if amount <= 0:
        raise ValidationError("Draft journal amount must be greater than zero.")

    payload = JournalCreate(
        org_entity_id=org_entity_id,
        journal_date=journal_date,
        reference=reference,
        narration=narration,
        lines=[
            {"account_code": debit_account_code, "debit": _q(amount), "credit": Decimal("0")},
            {"account_code": credit_account_code, "debit": Decimal("0"), "credit": _q(amount)},
        ],
    )
    intent_payload = payload.model_dump(mode="json")
    intent_payload["source"] = "MODULE"
    intent_payload["external_reference_id"] = reference
    return await submit_governed_journal_intent(
        db,
        intent_type=IntentType.CREATE_JOURNAL,
        tenant_id=tenant_id,
        user_id=actor_user_id,
        actor_role=actor_role,
        source_channel=IntentSourceChannel.API.value,
        namespace=f"industry_module_create:{reference}",
        payload=intent_payload,
    )


async def create_lease(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    actor_role: str,
    payload: LeaseCreateRequest,
) -> LeaseCreateResponse:
    await _ensure_module_enabled(db, tenant_id=tenant_id, module_name="LEASE")

    periods = _months_between_inclusive(payload.lease_start_date, payload.lease_end_date)
    period_count = len(periods)
    present_value, projection = build_lease_projection(
        lease_payment=payload.lease_payment,
        annual_discount_rate=payload.discount_rate,
        period_count=period_count,
    )

    lease = IndustryLease(
        tenant_id=tenant_id,
        entity_id=payload.entity_id,
        lease_start_date=payload.lease_start_date,
        lease_end_date=payload.lease_end_date,
        lease_payment=_q(payload.lease_payment),
        discount_rate=_q(payload.discount_rate),
        lease_type=payload.lease_type,
        currency=payload.currency.upper(),
        created_by=actor_user_id,
    )
    db.add(lease)
    await db.flush()

    for row, period_date in zip(projection, periods, strict=False):
        db.add(
            IndustryLeaseSchedule(
                tenant_id=tenant_id,
                lease_id=lease.id,
                period_number=row.period_number,
                period_date=period_date,
                opening_liability=row.opening_liability,
                interest_expense=row.interest_expense,
                lease_payment=row.lease_payment,
                closing_liability=row.closing_liability,
                rou_asset_value=row.rou_asset_value,
                depreciation=row.depreciation,
            )
        )

    accounts = await _resolve_account_pair(
        db,
        tenant_id=tenant_id,
        debit_code=payload.rou_asset_account_code,
        credit_code=payload.lease_liability_account_code,
    )
    journal_mutation = await _create_module_draft_journal(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        actor_role=actor_role,
        org_entity_id=payload.entity_id,
        journal_date=payload.lease_start_date,
        reference=f"LEASE:{lease.id}",
        narration=f"Lease initial recognition ({payload.lease_type})",
        amount=present_value,
        debit_account_code=accounts.debit_account_code,
        credit_account_code=accounts.credit_account_code,
    )
    draft_journal_id = journal_mutation.require_journal_id()
    db.add(
        IndustryJournalLink(
            tenant_id=tenant_id,
            module_name="LEASE",
            module_record_id=lease.id,
            journal_id=draft_journal_id,
            note="Initial lease recognition draft",
        )
    )

    logger.info(
        "Lease module run created",
        extra={
            "tenant_id": str(tenant_id),
            "lease_id": str(lease.id),
            "draft_journal_id": str(draft_journal_id),
            "periods": period_count,
        },
    )
    return LeaseCreateResponse(
        lease_id=lease.id,
        draft_journal_id=draft_journal_id,
        intent_id=journal_mutation.intent_id,
        job_id=journal_mutation.job_id,
        record_refs=journal_mutation.record_refs,
        periods=period_count,
    )


async def get_lease_schedule(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    lease_id: uuid.UUID,
) -> list[LeaseScheduleRow]:
    lease_stmt = select(IndustryLease.id).where(
        IndustryLease.id == lease_id,
        IndustryLease.tenant_id == tenant_id,
    )
    if (await db.execute(lease_stmt)).scalar_one_or_none() is None:
        raise NotFoundError("Lease not found")

    stmt = (
        select(IndustryLeaseSchedule)
        .where(
            IndustryLeaseSchedule.tenant_id == tenant_id,
            IndustryLeaseSchedule.lease_id == lease_id,
        )
        .order_by(IndustryLeaseSchedule.period_number.asc())
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [
        LeaseScheduleRow(
            period_number=row.period_number,
            period_date=row.period_date,
            opening_liability=row.opening_liability,
            interest_expense=row.interest_expense,
            lease_payment=row.lease_payment,
            closing_liability=row.closing_liability,
            rou_asset_value=row.rou_asset_value,
            depreciation=row.depreciation,
        )
        for row in rows
    ]


async def create_revenue_contract(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    actor_role: str,
    payload: RevenueContractCreateRequest,
) -> RevenueContractCreateResponse:
    await _ensure_module_enabled(db, tenant_id=tenant_id, module_name="REVENUE")

    periods = _months_between_inclusive(payload.contract_start_date, payload.contract_end_date)
    period_count = len(periods)

    contract = IndustryContract(
        tenant_id=tenant_id,
        entity_id=payload.entity_id,
        customer_id=payload.customer_id,
        contract_start_date=payload.contract_start_date,
        contract_end_date=payload.contract_end_date,
        contract_value=_q(payload.contract_value),
        created_by=actor_user_id,
    )
    db.add(contract)
    await db.flush()

    first_period_total = Decimal("0")
    for obligation_input in payload.obligations:
        obligation = IndustryPerformanceObligation(
            tenant_id=tenant_id,
            contract_id=contract.id,
            obligation_type=obligation_input.obligation_type,
            allocation_value=_q(obligation_input.allocation_value),
        )
        db.add(obligation)
        await db.flush()

        per_period_amounts = split_evenly(obligation.allocation_value, period_count)
        for idx, period_date in enumerate(periods, start=1):
            revenue_amount = per_period_amounts[idx - 1]
            if idx == 1:
                first_period_total = _q(first_period_total + revenue_amount)
            db.add(
                IndustryRevenueSchedule(
                    tenant_id=tenant_id,
                    obligation_id=obligation.id,
                    period_number=idx,
                    recognition_date=period_date,
                    revenue_amount=revenue_amount,
                )
            )

    accounts = await _resolve_account_pair(
        db,
        tenant_id=tenant_id,
        debit_code=payload.receivable_account_code,
        credit_code=payload.revenue_account_code,
    )
    journal_mutation = await _create_module_draft_journal(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        actor_role=actor_role,
        org_entity_id=payload.entity_id,
        journal_date=payload.contract_start_date,
        reference=f"REVENUE:{contract.id}",
        narration="Revenue contract initial recognition (draft only)",
        amount=first_period_total,
        debit_account_code=accounts.debit_account_code,
        credit_account_code=accounts.credit_account_code,
    )
    draft_journal_id = journal_mutation.require_journal_id()
    db.add(
        IndustryJournalLink(
            tenant_id=tenant_id,
            module_name="REVENUE",
            module_record_id=contract.id,
            journal_id=draft_journal_id,
            note="Revenue first-period draft",
        )
    )
    return RevenueContractCreateResponse(
        contract_id=contract.id,
        draft_journal_id=draft_journal_id,
        intent_id=journal_mutation.intent_id,
        job_id=journal_mutation.job_id,
        record_refs=journal_mutation.record_refs,
        periods=period_count,
    )


async def get_revenue_schedule(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    contract_id: uuid.UUID,
) -> list[RevenueScheduleRow]:
    contract_stmt = select(IndustryContract.id).where(
        IndustryContract.id == contract_id,
        IndustryContract.tenant_id == tenant_id,
    )
    if (await db.execute(contract_stmt)).scalar_one_or_none() is None:
        raise NotFoundError("Contract not found")

    stmt = (
        select(IndustryRevenueSchedule, IndustryPerformanceObligation.obligation_type)
        .join(
            IndustryPerformanceObligation,
            IndustryPerformanceObligation.id == IndustryRevenueSchedule.obligation_id,
        )
        .where(
            IndustryRevenueSchedule.tenant_id == tenant_id,
            IndustryPerformanceObligation.contract_id == contract_id,
        )
        .order_by(
            IndustryRevenueSchedule.period_number.asc(),
            IndustryPerformanceObligation.obligation_type.asc(),
        )
    )
    rows = (await db.execute(stmt)).all()
    return [
        RevenueScheduleRow(
            obligation_type=obligation_type,
            period_number=schedule.period_number,
            recognition_date=schedule.recognition_date,
            revenue_amount=schedule.revenue_amount,
        )
        for schedule, obligation_type in rows
    ]


async def create_fixed_asset(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    actor_role: str,
    payload: FixedAssetCreateRequest,
) -> FixedAssetCreateResponse:
    await _ensure_module_enabled(db, tenant_id=tenant_id, module_name="ASSETS")

    period_count = payload.useful_life_years * 12
    periods = _months_between_inclusive(date.today(), date.today().replace(year=date.today().year + payload.useful_life_years))
    periods = periods[:period_count]
    asset = IndustryFixedAsset(
        tenant_id=tenant_id,
        entity_id=payload.entity_id,
        asset_name=payload.asset_name,
        cost=_q(payload.cost),
        useful_life_years=payload.useful_life_years,
        depreciation_method=payload.depreciation_method,
        residual_value=_q(payload.residual_value),
        created_by=actor_user_id,
    )
    db.add(asset)
    await db.flush()

    projection = build_asset_projection(
        cost=payload.cost,
        residual_value=payload.residual_value,
        period_count=period_count,
        depreciation_method=payload.depreciation_method,
    )
    for row, period_date in zip(projection, periods, strict=False):
        db.add(
            IndustryAssetSchedule(
                tenant_id=tenant_id,
                asset_id=asset.id,
                period_number=row.period_number,
                period_date=period_date,
                depreciation=row.depreciation,
                net_book_value=row.net_book_value,
            )
        )

    accounts = await _resolve_account_pair(
        db,
        tenant_id=tenant_id,
        debit_code=payload.asset_account_code,
        credit_code=payload.payable_account_code,
    )
    journal_mutation = await _create_module_draft_journal(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        actor_role=actor_role,
        org_entity_id=payload.entity_id,
        journal_date=date.today(),
        reference=f"ASSET:{asset.id}",
        narration="Fixed asset capitalization (draft only)",
        amount=payload.cost,
        debit_account_code=accounts.debit_account_code,
        credit_account_code=accounts.credit_account_code,
    )
    draft_journal_id = journal_mutation.require_journal_id()
    db.add(
        IndustryJournalLink(
            tenant_id=tenant_id,
            module_name="ASSETS",
            module_record_id=asset.id,
            journal_id=draft_journal_id,
            note="Asset capitalization draft",
        )
    )
    return FixedAssetCreateResponse(
        asset_id=asset.id,
        draft_journal_id=draft_journal_id,
        intent_id=journal_mutation.intent_id,
        job_id=journal_mutation.job_id,
        record_refs=journal_mutation.record_refs,
        periods=period_count,
    )


async def get_asset_schedule(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    asset_id: uuid.UUID,
) -> list[AssetScheduleRow]:
    asset_stmt = select(IndustryFixedAsset.id).where(
        IndustryFixedAsset.id == asset_id,
        IndustryFixedAsset.tenant_id == tenant_id,
    )
    if (await db.execute(asset_stmt)).scalar_one_or_none() is None:
        raise NotFoundError("Asset not found")

    stmt = (
        select(IndustryAssetSchedule)
        .where(
            IndustryAssetSchedule.tenant_id == tenant_id,
            IndustryAssetSchedule.asset_id == asset_id,
        )
        .order_by(IndustryAssetSchedule.period_number.asc())
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [
        AssetScheduleRow(
            period_number=row.period_number,
            period_date=row.period_date,
            depreciation=row.depreciation,
            net_book_value=row.net_book_value,
        )
        for row in rows
    ]


async def create_prepaid_schedule(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    actor_role: str,
    payload: PrepaidCreateRequest,
) -> ScheduleBatchCreateResponse:
    await _ensure_module_enabled(db, tenant_id=tenant_id, module_name="PREPAID")

    periods = _months_between_inclusive(payload.start_date, payload.end_date)
    period_count = len(periods)
    batch_id = uuid.uuid4()
    amortization_plan = split_evenly(payload.total_amount, period_count)

    remaining = _q(payload.total_amount)
    first_period_amount = Decimal("0.0000")
    for idx, period_date in enumerate(periods, start=1):
        amortization = amortization_plan[idx - 1]
        if idx == 1:
            first_period_amount = amortization
        remaining = _q(remaining - amortization)
        db.add(
            IndustryPrepaidSchedule(
                tenant_id=tenant_id,
                entity_id=payload.entity_id,
                schedule_batch_id=batch_id,
                prepaid_name=payload.prepaid_name,
                period_number=idx,
                period_date=period_date,
                amortization_amount=amortization,
                remaining_balance=max(remaining, Decimal("0.0000")),
            )
        )

    accounts = await _resolve_account_pair(
        db,
        tenant_id=tenant_id,
        debit_code=payload.prepaid_account_code,
        credit_code=payload.cash_account_code,
    )
    journal_mutation = await _create_module_draft_journal(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        actor_role=actor_role,
        org_entity_id=payload.entity_id,
        journal_date=payload.start_date,
        reference=f"PREPAID:{batch_id}",
        narration="Prepaid initial recognition (draft only)",
        amount=first_period_amount,
        debit_account_code=accounts.debit_account_code,
        credit_account_code=accounts.credit_account_code,
    )
    draft_journal_id = journal_mutation.require_journal_id()
    db.add(
        IndustryJournalLink(
            tenant_id=tenant_id,
            module_name="PREPAID",
            module_record_id=batch_id,
            journal_id=draft_journal_id,
            note="Prepaid first-period draft",
        )
    )
    return ScheduleBatchCreateResponse(
        schedule_batch_id=batch_id,
        draft_journal_id=draft_journal_id,
        intent_id=journal_mutation.intent_id,
        job_id=journal_mutation.job_id,
        record_refs=journal_mutation.record_refs,
        periods=period_count,
    )


async def create_accrual_schedule(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    actor_role: str,
    payload: AccrualCreateRequest,
) -> ScheduleBatchCreateResponse:
    await _ensure_module_enabled(db, tenant_id=tenant_id, module_name="ACCRUAL")

    periods = _months_between_inclusive(payload.start_date, payload.end_date)
    period_count = len(periods)
    batch_id = uuid.uuid4()
    accrual_plan = split_evenly(payload.total_amount, period_count)

    remaining = _q(payload.total_amount)
    first_period_amount = Decimal("0.0000")
    for idx, period_date in enumerate(periods, start=1):
        accrual_amount = accrual_plan[idx - 1]
        if idx == 1:
            first_period_amount = accrual_amount
        remaining = _q(remaining - accrual_amount)
        db.add(
            IndustryAccrualSchedule(
                tenant_id=tenant_id,
                entity_id=payload.entity_id,
                schedule_batch_id=batch_id,
                accrual_name=payload.accrual_name,
                period_number=idx,
                period_date=period_date,
                accrual_amount=accrual_amount,
                remaining_balance=max(remaining, Decimal("0.0000")),
            )
        )

    accounts = await _resolve_account_pair(
        db,
        tenant_id=tenant_id,
        debit_code=payload.expense_account_code,
        credit_code=payload.accrued_liability_account_code,
    )
    journal_mutation = await _create_module_draft_journal(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        actor_role=actor_role,
        org_entity_id=payload.entity_id,
        journal_date=payload.start_date,
        reference=f"ACCRUAL:{batch_id}",
        narration="Accrual first-period recognition (draft only)",
        amount=first_period_amount,
        debit_account_code=accounts.debit_account_code,
        credit_account_code=accounts.credit_account_code,
    )
    draft_journal_id = journal_mutation.require_journal_id()
    db.add(
        IndustryJournalLink(
            tenant_id=tenant_id,
            module_name="ACCRUAL",
            module_record_id=batch_id,
            journal_id=draft_journal_id,
            note="Accrual first-period draft",
        )
    )
    return ScheduleBatchCreateResponse(
        schedule_batch_id=batch_id,
        draft_journal_id=draft_journal_id,
        intent_id=journal_mutation.intent_id,
        job_id=journal_mutation.job_id,
        record_refs=journal_mutation.record_refs,
        periods=period_count,
    )
