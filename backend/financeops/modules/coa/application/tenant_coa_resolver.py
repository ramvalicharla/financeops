from __future__ import annotations

import uuid

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.modules.coa.models import (
    CoaAccountGroup,
    CoaAccountSubgroup,
    CoaLedgerAccount,
    CoaSourceType,
)


class TenantCoaResolver:
    """Resolves effective CoA accounts by scope priority.

    Priority:
    1) TENANT_CUSTOM
    2) ADMIN_TEMPLATE
    3) SYSTEM
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _source_priority(source_type: CoaSourceType) -> int:
        if source_type == CoaSourceType.TENANT_CUSTOM:
            return 3
        if source_type == CoaSourceType.ADMIN_TEMPLATE:
            return 2
        return 1

    async def resolve_accounts(
        self,
        *,
        tenant_id: uuid.UUID,
        template_id: uuid.UUID | None = None,
        group_code: str | None = None,
        subgroup_code: str | None = None,
        include_inactive: bool = False,
    ) -> list[CoaLedgerAccount]:
        stmt = (
            select(CoaLedgerAccount)
            .join(CoaAccountSubgroup, CoaLedgerAccount.account_subgroup_id == CoaAccountSubgroup.id)
            .join(CoaAccountGroup, CoaAccountSubgroup.account_group_id == CoaAccountGroup.id)
            .where(
                or_(
                    and_(
                        CoaLedgerAccount.tenant_id == tenant_id,
                        CoaLedgerAccount.source_type == CoaSourceType.TENANT_CUSTOM,
                    ),
                    and_(
                        CoaLedgerAccount.tenant_id.is_(None),
                        CoaLedgerAccount.source_type == CoaSourceType.ADMIN_TEMPLATE,
                    ),
                    and_(
                        CoaLedgerAccount.tenant_id.is_(None),
                        CoaLedgerAccount.source_type == CoaSourceType.SYSTEM,
                    ),
                )
            )
        )
        if template_id is not None:
            stmt = stmt.where(CoaLedgerAccount.industry_template_id == template_id)
        if group_code:
            stmt = stmt.where(CoaAccountGroup.code == group_code)
        if subgroup_code:
            stmt = stmt.where(CoaAccountSubgroup.code == subgroup_code)
        if not include_inactive:
            stmt = stmt.where(CoaLedgerAccount.is_active.is_(True))

        rows = (
            await self._session.execute(
                stmt.order_by(
                    CoaLedgerAccount.industry_template_id.asc(),
                    CoaLedgerAccount.code.asc(),
                    CoaLedgerAccount.version.desc(),
                )
            )
        ).scalars().all()

        selected: dict[tuple[uuid.UUID, str], CoaLedgerAccount] = {}
        for row in rows:
            key = (row.industry_template_id, row.code)
            current = selected.get(key)
            if current is None:
                selected[key] = row
                continue

            current_priority = self._source_priority(current.source_type)
            candidate_priority = self._source_priority(row.source_type)
            if candidate_priority > current_priority:
                selected[key] = row
                continue
            if candidate_priority == current_priority and row.version > current.version:
                selected[key] = row
                continue
            if (
                candidate_priority == current_priority
                and row.version == current.version
                and row.created_at > current.created_at
            ):
                selected[key] = row

        return sorted(selected.values(), key=lambda item: (item.sort_order, item.code))
