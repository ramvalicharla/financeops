from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from time import perf_counter

from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.accounting_jv import AccountingJVAggregate
from financeops.db.models.custom_report_builder import ReportDefinition, ReportRun
from financeops.db.models.users import IamUser, UserRole
from financeops.modules.expense_management.models import ExpenseClaim
from financeops.modules.search.schemas import (
    SearchModule,
    UnifiedSearchItem,
    UnifiedSearchMeta,
    UnifiedSearchResponse,
)
from financeops.platform.db.models.entities import CpEntity
from financeops.platform.services.rbac.evaluator import evaluate_permission
from financeops.platform.services.rbac.permission_engine import has_permission
from financeops.platform.services.tenancy.entity_access import get_entities_for_user

_ALL_ENTITY_ROLES = {
    UserRole.finance_leader,
    UserRole.platform_owner,
    UserRole.platform_admin,
    UserRole.super_admin,
}
_FINANCE_REVIEWER_ROLES = _ALL_ENTITY_ROLES | {
    UserRole.finance_team,
}
_TENANT_USER_SEARCH_FALLBACK_ROLES = {
    UserRole.super_admin,
    UserRole.platform_owner,
    UserRole.platform_admin,
    UserRole.finance_leader,
}
_DYNAMIC_PERMISSION_FALLBACK_REASONS = {
    "permission_not_defined",
    "no_role_assignments",
    "no_matching_permissions",
    "no_effective_permission",
}


@dataclass(frozen=True)
class _SearchCandidate:
    id: str
    module: SearchModule
    title: str
    subtitle: str | None
    href: str
    status: str | None
    amount: Decimal | None
    currency: str | None
    created_at: datetime
    match_priority: int


def _match_priority_expr(
    *,
    primary_text,
    search_lower: str,
    prefix_pattern: str,
    fallback_match,
):
    return case(
        (func.lower(primary_text) == search_lower, 0),
        (primary_text.ilike(prefix_pattern), 1),
        (fallback_match, 2),
        else_=3,
    )


def _serialize_amount(value: Decimal | None) -> float | None:
    if value is None:
        return None
    return float(value)


def _candidate_to_item(candidate: _SearchCandidate) -> UnifiedSearchItem:
    return UnifiedSearchItem(
        id=candidate.id,
        module=candidate.module,
        title=candidate.title,
        subtitle=candidate.subtitle,
        href=candidate.href,
        status=candidate.status,
        amount=_serialize_amount(candidate.amount),
        currency=candidate.currency,
        created_at=(
            candidate.created_at
            if candidate.created_at.tzinfo is not None
            else candidate.created_at.replace(tzinfo=UTC)
        ),
    )


def _candidate_sort_key(candidate: _SearchCandidate) -> tuple[int, float, str]:
    return (
        candidate.match_priority,
        -candidate.created_at.timestamp(),
        candidate.id,
    )


async def _resolve_entity_scope(
    session: AsyncSession,
    user: IamUser,
) -> tuple[bool, set[uuid.UUID]]:
    entities = await get_entities_for_user(
        session=session,
        tenant_id=user.tenant_id,
        user_id=user.id,
        user_role=user.role,
    )
    return user.role in _ALL_ENTITY_ROLES, {entity.id for entity in entities}


async def _can_search_users(session: AsyncSession, user: IamUser) -> bool:
    evaluation = await evaluate_permission(
        session,
        tenant_id=user.tenant_id,
        user_id=user.id,
        resource_type="tenant_user",
        action="manage",
        context_scope={"tenant": user.tenant_id},
        execution_timestamp=datetime.now(UTC),
    )
    if evaluation.allowed:
        return True
    if evaluation.reason == "deny_over_allow":
        return False
    if evaluation.reason not in _DYNAMIC_PERMISSION_FALLBACK_REASONS:
        return False
    return user.role in _TENANT_USER_SEARCH_FALLBACK_ROLES


async def _search_journals(
    session: AsyncSession,
    user: IamUser,
    *,
    query_text: str,
    fetch_size: int,
    all_entity_access: bool,
    accessible_entity_ids: set[uuid.UUID],
) -> tuple[int, list[_SearchCandidate]]:
    allowed = await has_permission(user, "journal.view", {"session": session})
    if not allowed:
        return 0, []
    if not all_entity_access and not accessible_entity_ids:
        return 0, []

    pattern = f"%{query_text}%"
    prefix_pattern = f"{query_text}%"
    lower_q = query_text.lower()
    match_filter = or_(
        AccountingJVAggregate.jv_number.ilike(pattern),
        func.coalesce(AccountingJVAggregate.description, "").ilike(pattern),
        func.coalesce(AccountingJVAggregate.reference, "").ilike(pattern),
    )
    base_filters = [
        AccountingJVAggregate.tenant_id == user.tenant_id,
        match_filter,
    ]
    if not all_entity_access:
        base_filters.append(AccountingJVAggregate.entity_id.in_(list(accessible_entity_ids)))

    rank_expr = _match_priority_expr(
        primary_text=AccountingJVAggregate.jv_number,
        search_lower=lower_q,
        prefix_pattern=prefix_pattern,
        fallback_match=match_filter,
    ).label("match_priority")

    total = int(
        (
            await session.execute(
                select(func.count()).select_from(
                    select(AccountingJVAggregate.id).where(*base_filters).subquery()
                )
            )
        ).scalar_one()
    )
    rows = (
        await session.execute(
            select(AccountingJVAggregate, rank_expr)
            .where(*base_filters)
            .order_by(rank_expr.asc(), AccountingJVAggregate.created_at.desc(), AccountingJVAggregate.id.desc())
            .limit(fetch_size)
        )
    ).all()
    return total, [
        _SearchCandidate(
            id=str(journal.id),
            module="journal",
            title=journal.jv_number,
            subtitle=journal.description,
            href=f"/accounting/journals/{journal.id}",
            status=journal.status,
            amount=journal.total_debit,
            currency=journal.currency,
            created_at=journal.created_at,
            match_priority=int(rank),
        )
        for journal, rank in rows
    ]


async def _search_expenses(
    session: AsyncSession,
    user: IamUser,
    *,
    query_text: str,
    fetch_size: int,
    all_entity_access: bool,
    accessible_entity_ids: set[uuid.UUID],
) -> tuple[int, list[_SearchCandidate]]:
    pattern = f"%{query_text}%"
    prefix_pattern = f"{query_text}%"
    lower_q = query_text.lower()
    match_filter = or_(
        ExpenseClaim.vendor_name.ilike(pattern),
        ExpenseClaim.description.ilike(pattern),
    )
    base_filters = [
        ExpenseClaim.tenant_id == user.tenant_id,
        match_filter,
    ]
    if user.role not in {UserRole.finance_leader, UserRole.super_admin}:
        base_filters.append(ExpenseClaim.submitted_by == user.id)
    if not all_entity_access:
        if not accessible_entity_ids:
            return 0, []
        base_filters.append(ExpenseClaim.entity_id.in_(list(accessible_entity_ids)))

    rank_expr = _match_priority_expr(
        primary_text=ExpenseClaim.vendor_name,
        search_lower=lower_q,
        prefix_pattern=prefix_pattern,
        fallback_match=match_filter,
    ).label("match_priority")
    total = int(
        (
            await session.execute(
                select(func.count()).select_from(select(ExpenseClaim.id).where(*base_filters).subquery())
            )
        ).scalar_one()
    )
    rows = (
        await session.execute(
            select(ExpenseClaim, rank_expr)
            .where(*base_filters)
            .order_by(rank_expr.asc(), ExpenseClaim.created_at.desc(), ExpenseClaim.id.desc())
            .limit(fetch_size)
        )
    ).all()
    return total, [
        _SearchCandidate(
            id=str(claim.id),
            module="expense",
            title=claim.vendor_name,
            subtitle=claim.description,
            href=f"/expenses/{claim.id}",
            status=str(claim.status).upper(),
            amount=claim.amount,
            currency=claim.currency,
            created_at=claim.created_at,
            match_priority=int(rank),
        )
        for claim, rank in rows
    ]


async def _search_entities(
    session: AsyncSession,
    user: IamUser,
    *,
    query_text: str,
    fetch_size: int,
    all_entity_access: bool,
    accessible_entity_ids: set[uuid.UUID],
) -> tuple[int, list[_SearchCandidate]]:
    if user.role not in _FINANCE_REVIEWER_ROLES:
        return 0, []
    if not all_entity_access and not accessible_entity_ids:
        return 0, []

    pattern = f"%{query_text}%"
    prefix_pattern = f"{query_text}%"
    lower_q = query_text.lower()
    match_filter = or_(
        CpEntity.entity_name.ilike(pattern),
        CpEntity.entity_code.ilike(pattern),
    )
    base_filters = [
        CpEntity.tenant_id == user.tenant_id,
        CpEntity.status == "active",
        match_filter,
    ]
    if not all_entity_access:
        base_filters.append(CpEntity.id.in_(list(accessible_entity_ids)))

    rank_expr = _match_priority_expr(
        primary_text=CpEntity.entity_name,
        search_lower=lower_q,
        prefix_pattern=prefix_pattern,
        fallback_match=match_filter,
    ).label("match_priority")
    total = int(
        (
            await session.execute(
                select(func.count()).select_from(select(CpEntity.id).where(*base_filters).subquery())
            )
        ).scalar_one()
    )
    rows = (
        await session.execute(
            select(CpEntity, rank_expr)
            .where(*base_filters)
            .order_by(rank_expr.asc(), CpEntity.created_at.desc(), CpEntity.id.desc())
            .limit(fetch_size)
        )
    ).all()
    return total, [
        _SearchCandidate(
            id=str(entity.id),
            module="entity",
            title=entity.entity_name,
            subtitle=entity.entity_code,
            href=f"/control-plane/entities/{entity.id}",
            status=str(entity.status).upper(),
            amount=None,
            currency=None,
            created_at=entity.created_at,
            match_priority=int(rank),
        )
        for entity, rank in rows
    ]


async def _search_users(
    session: AsyncSession,
    user: IamUser,
    *,
    query_text: str,
    fetch_size: int,
) -> tuple[int, list[_SearchCandidate]]:
    if not await _can_search_users(session, user):
        return 0, []

    from financeops.db.models.users import IamUser as UserModel

    pattern = f"%{query_text}%"
    prefix_pattern = f"{query_text}%"
    lower_q = query_text.lower()
    match_filter = or_(
        UserModel.full_name.ilike(pattern),
        UserModel.email.ilike(pattern),
    )
    base_filters = [
        UserModel.tenant_id == user.tenant_id,
        match_filter,
    ]
    rank_expr = _match_priority_expr(
        primary_text=UserModel.full_name,
        search_lower=lower_q,
        prefix_pattern=prefix_pattern,
        fallback_match=match_filter,
    ).label("match_priority")
    total = int(
        (
            await session.execute(
                select(func.count()).select_from(select(UserModel.id).where(*base_filters).subquery())
            )
        ).scalar_one()
    )
    rows = (
        await session.execute(
            select(UserModel, rank_expr)
            .where(*base_filters)
            .order_by(rank_expr.asc(), UserModel.created_at.desc(), UserModel.id.desc())
            .limit(fetch_size)
        )
    ).all()
    return total, [
        _SearchCandidate(
            id=str(row.id),
            module="user",
            title=row.full_name,
            subtitle=row.email,
            href="/admin/users",
            status="ACTIVE" if row.is_active else "INACTIVE",
            amount=None,
            currency=None,
            created_at=row.created_at,
            match_priority=int(rank),
        )
        for row, rank in rows
    ]


def _report_definition_visible(
    definition: ReportDefinition,
    *,
    all_entity_access: bool,
    accessible_entity_ids: set[uuid.UUID],
) -> bool:
    if all_entity_access:
        return True
    raw_entity_ids = definition.filter_config.get("entity_ids") if definition.filter_config else []
    if not raw_entity_ids:
        return False
    scoped_ids: set[uuid.UUID] = set()
    for raw_value in raw_entity_ids:
        try:
            scoped_ids.add(uuid.UUID(str(raw_value)))
        except (TypeError, ValueError):
            continue
    return bool(scoped_ids.intersection(accessible_entity_ids))


async def _search_reports(
    session: AsyncSession,
    user: IamUser,
    *,
    query_text: str,
    fetch_size: int,
    all_entity_access: bool,
    accessible_entity_ids: set[uuid.UUID],
) -> tuple[int, list[_SearchCandidate]]:
    pattern = f"%{query_text}%"
    prefix_pattern = f"{query_text}%"
    lower_q = query_text.lower()
    match_filter = or_(
        ReportDefinition.name.ilike(pattern),
        func.coalesce(ReportDefinition.description, "").ilike(pattern),
    )
    rank_expr = _match_priority_expr(
        primary_text=ReportDefinition.name,
        search_lower=lower_q,
        prefix_pattern=prefix_pattern,
        fallback_match=match_filter,
    ).label("match_priority")
    rows = (
        await session.execute(
            select(ReportDefinition, rank_expr)
            .where(
                ReportDefinition.tenant_id == user.tenant_id,
                ReportDefinition.is_active.is_(True),
                match_filter,
            )
            .order_by(rank_expr.asc(), ReportDefinition.created_at.desc(), ReportDefinition.id.desc())
        )
    ).all()
    visible_rows = [
        (definition, int(rank))
        for definition, rank in rows
        if _report_definition_visible(
            definition,
            all_entity_access=all_entity_access,
            accessible_entity_ids=accessible_entity_ids,
        )
    ]
    if not visible_rows:
        return 0, []

    definition_ids = [definition.id for definition, _ in visible_rows]
    latest_runs: dict[uuid.UUID, ReportRun] = {}
    run_rows = (
        await session.execute(
            select(ReportRun)
            .where(
                ReportRun.tenant_id == user.tenant_id,
                ReportRun.definition_id.in_(definition_ids),
            )
            .order_by(ReportRun.definition_id.asc(), ReportRun.created_at.desc(), ReportRun.id.desc())
        )
    ).scalars().all()
    for run in run_rows:
        latest_runs.setdefault(run.definition_id, run)

    candidates = [
        _SearchCandidate(
            id=str(definition.id),
            module="report",
            title=definition.name,
            subtitle=definition.description,
            href=f"/reports/{latest_runs[definition.id].id}" if definition.id in latest_runs else "/reports",
            status=latest_runs[definition.id].status if definition.id in latest_runs else "ACTIVE",
            amount=None,
            currency=None,
            created_at=latest_runs[definition.id].created_at if definition.id in latest_runs else definition.created_at,
            match_priority=rank,
        )
        for definition, rank in visible_rows
    ]
    candidates.sort(key=_candidate_sort_key)
    return len(candidates), candidates[:fetch_size]


async def search_unified(
    session: AsyncSession,
    *,
    user: IamUser,
    query_text: str,
    module: SearchModule | None,
    limit: int,
    offset: int,
) -> UnifiedSearchResponse:
    started_at = perf_counter()
    fetch_size = max(1, offset + limit)
    all_entity_access, accessible_entity_ids = await _resolve_entity_scope(session, user)

    module_searchers = {
        "journal": lambda: _search_journals(
            session,
            user,
            query_text=query_text,
            fetch_size=fetch_size,
            all_entity_access=all_entity_access,
            accessible_entity_ids=accessible_entity_ids,
        ),
        "expense": lambda: _search_expenses(
            session,
            user,
            query_text=query_text,
            fetch_size=fetch_size,
            all_entity_access=all_entity_access,
            accessible_entity_ids=accessible_entity_ids,
        ),
        "report": lambda: _search_reports(
            session,
            user,
            query_text=query_text,
            fetch_size=fetch_size,
            all_entity_access=all_entity_access,
            accessible_entity_ids=accessible_entity_ids,
        ),
        "user": lambda: _search_users(
            session,
            user,
            query_text=query_text,
            fetch_size=fetch_size,
        ),
        "entity": lambda: _search_entities(
            session,
            user,
            query_text=query_text,
            fetch_size=fetch_size,
            all_entity_access=all_entity_access,
            accessible_entity_ids=accessible_entity_ids,
        ),
    }
    modules_to_run: list[SearchModule] = [module] if module is not None else list(module_searchers)

    combined: list[_SearchCandidate] = []
    total_results = 0
    for module_name in modules_to_run:
        module_total, module_rows = await module_searchers[module_name]()
        total_results += module_total
        combined.extend(module_rows)

    combined.sort(key=_candidate_sort_key)
    page = combined[offset : offset + limit]
    elapsed_ms = int(round((perf_counter() - started_at) * 1000))
    return UnifiedSearchResponse(
        data=[_candidate_to_item(item) for item in page],
        meta=UnifiedSearchMeta(
            query=query_text,
            total_results=total_results,
            limit=limit,
            offset=offset,
            query_time_ms=max(0, elapsed_ms),
        ),
    )


__all__ = ["search_unified"]
