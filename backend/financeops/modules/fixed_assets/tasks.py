from __future__ import annotations

import calendar
import uuid
from datetime import date
from decimal import Decimal
from typing import Any, Awaitable, Callable

from celery import Task
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError, InterfaceError, OperationalError

from financeops.core.intent.context import MutationContext, governed_mutation_context
from financeops.db.models.users import IamUser
from financeops.db.rls import clear_tenant_context, set_tenant_context
from financeops.db.session import AsyncSessionLocal
from financeops.modules.accounting_layer.application.journal_service import (
    approve_journal,
    create_journal_draft,
    post_journal,
    review_journal,
    submit_journal,
)
from financeops.modules.accounting_layer.domain.schemas import JournalCreate, JournalLineCreate
from financeops.modules.fixed_assets.application.depreciation_engine import get_depreciation
from financeops.modules.fixed_assets.application.fixed_asset_service import FixedAssetService
from financeops.modules.fixed_assets.domain.exceptions import FixedAssetError
from financeops.modules.fixed_assets.models import FaAsset, FaAssetClass, FaDepreciationRun
from financeops.tasks.async_runner import run_async
from financeops.tasks.base_task import FinanceOpsTask
from financeops.tasks.celery_app import celery_app


async def _resolve_journal_actors(session, tenant_id: uuid.UUID) -> tuple[uuid.UUID, uuid.UUID]:
    users = list(
        (
            await session.execute(
                select(IamUser)
                .where(IamUser.tenant_id == tenant_id, IamUser.is_active.is_(True))
                .order_by(IamUser.created_at.asc())
                .limit(2)
            )
        ).scalars().all()
    )
    if len(users) < 2:
        raise FixedAssetError("Monthly depreciation auto-posting requires at least two active tenant users.")
    return users[0].id, users[1].id


def _parse_period(period: str) -> tuple[date, date]:
    year_text, month_text = str(period).split("-", 1)
    year = int(year_text)
    month = int(month_text)
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)


async def _post_depreciation_journal(
    session,
    *,
    tenant_id: uuid.UUID,
    asset: FaAsset,
    asset_class: FaAssetClass,
    depreciation_amount: Decimal,
    journal_reference: str,
    journal_date: date,
) -> str:
    if asset_class.coa_dep_expense_account_id is None or asset_class.coa_accum_dep_account_id is None:
        raise FixedAssetError(
            f"Asset class {asset_class.id} is missing depreciation expense or accumulated depreciation accounts."
        )

    creator_user_id, approver_user_id = await _resolve_journal_actors(session, tenant_id)
    payload = JournalCreate(
        org_entity_id=asset.entity_id,
        journal_date=journal_date,
        reference=journal_reference,
        narration=f"Monthly depreciation for asset {asset.asset_code}",
        lines=[
            JournalLineCreate(
                tenant_coa_account_id=asset_class.coa_dep_expense_account_id,
                debit=depreciation_amount,
                memo=f"Depreciation expense for {asset.asset_code}",
            ),
            JournalLineCreate(
                tenant_coa_account_id=asset_class.coa_accum_dep_account_id,
                credit=depreciation_amount,
                memo=f"Accumulated depreciation for {asset.asset_code}",
            ),
        ],
    )
    with governed_mutation_context(
        MutationContext(
            intent_id=uuid.uuid4(),
            job_id=uuid.uuid4(),
            actor_user_id=creator_user_id,
            actor_role="ACCOUNTING_SUBMITTER",
            intent_type="AUTO_POST_FIXED_ASSET_DEPRECIATION",
        )
    ):
        draft = await create_journal_draft(
            session,
            tenant_id=tenant_id,
            created_by=creator_user_id,
            payload=payload,
            source="SYSTEM",
            external_reference_id=journal_reference,
        )
        await submit_journal(
            session,
            tenant_id=tenant_id,
            journal_id=draft.id,
            acted_by=creator_user_id,
            actor_role="ACCOUNTING_SUBMITTER",
        )
        await review_journal(
            session,
            tenant_id=tenant_id,
            journal_id=draft.id,
            acted_by=approver_user_id,
            actor_role="ACCOUNTING_REVIEWER",
        )
        await approve_journal(
            session,
            tenant_id=tenant_id,
            journal_id=draft.id,
            acted_by=approver_user_id,
            actor_role="ACCOUNTING_APPROVER",
        )
        await post_journal(
            session,
            tenant_id=tenant_id,
            journal_id=draft.id,
            acted_by=approver_user_id,
            actor_role="ACCOUNTING_POSTER",
        )
    return str(draft.id)


async def _run_monthly_depreciation(
    *,
    tenant_id: str,
    period: str,
    journal_poster: Callable[..., Awaitable[str]] = _post_depreciation_journal,
    session_factory: Callable[[], Any] = AsyncSessionLocal,
) -> dict[str, Any]:
    parsed_tenant_id = uuid.UUID(str(tenant_id))
    period_start, period_end = _parse_period(period)

    async with session_factory() as session:
        try:
            await set_tenant_context(session, str(parsed_tenant_id))
            service = FixedAssetService(session)
            rows = (
                await session.execute(
                    select(FaAsset, FaAssetClass)
                    .join(FaAssetClass, FaAssetClass.id == FaAsset.asset_class_id)
                    .where(
                        FaAsset.tenant_id == parsed_tenant_id,
                        FaAsset.status.in_(["ACTIVE", "IMPAIRED", "UNDER_INSTALLATION"]),
                        FaAsset.is_active.is_(True),
                    )
                    .order_by(FaAsset.asset_code)
                )
            ).all()

            created_runs = 0
            posted_journals = 0
            skipped_runs = 0
            for asset, asset_class in rows:
                run_reference = f"{asset.entity_id}:{asset.id}:{period_start.isoformat()}:INDAS"
                existing = (
                    await session.execute(
                        select(FaDepreciationRun).where(
                            FaDepreciationRun.tenant_id == parsed_tenant_id,
                            FaDepreciationRun.run_reference == run_reference,
                        )
                    )
                ).scalar_one_or_none()
                if existing is not None:
                    skipped_runs += 1
                    continue

                opening_nbv = await service._opening_nbv(asset, "INDAS", period_start)
                depreciation_amount = get_depreciation(
                    asset=asset,
                    opening_nbv=opening_nbv,
                    period_start=period_start,
                    period_end=period_end,
                    gaap="INDAS",
                )
                residual = Decimal(str(asset.residual_value))
                closing_nbv = max(opening_nbv - depreciation_amount, residual)
                accumulated_dep = Decimal(str(asset.original_cost)) - closing_nbv

                if depreciation_amount > Decimal("0"):
                    await journal_poster(
                        session,
                        tenant_id=parsed_tenant_id,
                        asset=asset,
                        asset_class=asset_class,
                        depreciation_amount=depreciation_amount,
                        journal_reference=f"FADEP:{run_reference}",
                        journal_date=period_end,
                    )
                    posted_journals += 1

                session.add(
                    FaDepreciationRun(
                        tenant_id=parsed_tenant_id,
                        entity_id=asset.entity_id,
                        asset_id=asset.id,
                        run_date=period_end,
                        period_start=period_start,
                        period_end=period_end,
                        gaap="INDAS",
                        depreciation_method=asset.depreciation_method,
                        opening_nbv=opening_nbv,
                        depreciation_amount=depreciation_amount,
                        closing_nbv=closing_nbv,
                        accumulated_dep=accumulated_dep,
                        run_reference=run_reference,
                        is_reversal=False,
                    )
                )
                created_runs += 1

            await session.commit()
            return {
                "tenant_id": str(parsed_tenant_id),
                "period": period,
                "created_runs": created_runs,
                "posted_journals": posted_journals,
                "skipped_runs": skipped_runs,
            }
        except Exception:
            await session.rollback()
            raise
        finally:
            await clear_tenant_context(session)


@celery_app.task(
    bind=True,
    base=FinanceOpsTask,
    name="financeops.modules.fixed_assets.tasks.run_monthly_depreciation_task",
    queue="normal_q",
    max_retries=2,
)
def run_monthly_depreciation_task(self: Task, tenant_id: str, period: str) -> dict[str, Any]:
    try:
        return run_async(_run_monthly_depreciation(tenant_id=tenant_id, period=period))
    except (OperationalError, InterfaceError, DBAPIError, ConnectionError, TimeoutError, OSError) as exc:
        raise self.retry(exc=exc, countdown=60)


__all__ = ["run_monthly_depreciation_task", "_run_monthly_depreciation"]
