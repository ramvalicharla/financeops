from __future__ import annotations

import uuid

from sqlalchemy import or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import NotFoundError, ValidationError
from financeops.modules.coa.models import (
    CoaAccountGroup,
    CoaAccountSubgroup,
    CoaFsLineItem,
    CoaFsSchedule,
    CoaFsSubline,
    CoaLedgerAccount,
    CoaSourceType,
    TenantCoaAccount,
)


class TenantCoaService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _source_priority(source_type: CoaSourceType) -> int:
        if source_type == CoaSourceType.TENANT_CUSTOM:
            return 3
        if source_type == CoaSourceType.ADMIN_TEMPLATE:
            return 2
        return 1

    async def has_tenant_accounts(self, tenant_id: uuid.UUID) -> bool:
        row = (
            await self._session.execute(
                select(TenantCoaAccount.id)
                .where(TenantCoaAccount.tenant_id == tenant_id)
                .limit(1)
            )
        ).scalar_one_or_none()
        return row is not None

    async def _select_source_accounts(
        self,
        tenant_id: uuid.UUID,
        template_id: uuid.UUID,
    ) -> list[CoaLedgerAccount]:
        rows = (
            await self._session.execute(
                select(CoaLedgerAccount)
                .where(CoaLedgerAccount.industry_template_id == template_id)
                .where(CoaLedgerAccount.is_active.is_(True))
                .where(
                    or_(
                        (
                            (CoaLedgerAccount.tenant_id == tenant_id)
                            & (CoaLedgerAccount.source_type == CoaSourceType.TENANT_CUSTOM)
                        ),
                        (
                            CoaLedgerAccount.tenant_id.is_(None)
                            & (CoaLedgerAccount.source_type == CoaSourceType.ADMIN_TEMPLATE)
                        ),
                        (
                            CoaLedgerAccount.tenant_id.is_(None)
                            & (CoaLedgerAccount.source_type == CoaSourceType.SYSTEM)
                        ),
                    )
                )
                .order_by(CoaLedgerAccount.code.asc(), CoaLedgerAccount.version.desc())
            )
        ).scalars().all()

        selected_by_code: dict[str, CoaLedgerAccount] = {}
        for row in rows:
            current = selected_by_code.get(row.code)
            if current is None:
                selected_by_code[row.code] = row
                continue
            current_priority = self._source_priority(current.source_type)
            candidate_priority = self._source_priority(row.source_type)
            if candidate_priority > current_priority:
                selected_by_code[row.code] = row
                continue
            if candidate_priority == current_priority and row.version > current.version:
                selected_by_code[row.code] = row
                continue
            if (
                candidate_priority == current_priority
                and row.version == current.version
                and row.created_at > current.created_at
            ):
                selected_by_code[row.code] = row

        return sorted(selected_by_code.values(), key=lambda item: (item.sort_order, item.code))

    async def initialise_tenant_coa(self, tenant_id: uuid.UUID, template_id: uuid.UUID) -> None:
        source_accounts = await self._select_source_accounts(tenant_id, template_id)
        if not source_accounts:
            raise ValidationError("CoA template has no ledger accounts")

        payload = [
            {
                "tenant_id": tenant_id,
                "ledger_account_id": row.id,
                "parent_subgroup_id": row.account_subgroup_id,
                "account_code": row.code,
                "display_name": row.name,
                "is_custom": False,
                "is_active": row.is_active,
                "default_cost_centre_id": None,
                "default_location_id": None,
                "sort_order": row.sort_order,
            }
            for row in source_accounts
        ]
        stmt = insert(TenantCoaAccount).values(payload)
        stmt = stmt.on_conflict_do_nothing(
            constraint="uq_tenant_coa_accounts_tenant_code"
        )
        await self._session.execute(stmt)

    async def get_tenant_accounts(self, tenant_id: uuid.UUID) -> list[TenantCoaAccount]:
        rows = (
            await self._session.execute(
                select(TenantCoaAccount)
                .where(TenantCoaAccount.tenant_id == tenant_id)
                .order_by(TenantCoaAccount.sort_order.nulls_last(), TenantCoaAccount.account_code)
            )
        ).scalars().all()
        return list(rows)

    async def add_custom_account(
        self,
        tenant_id: uuid.UUID,
        parent_subgroup_id: uuid.UUID,
        account_code: str,
        display_name: str,
    ) -> TenantCoaAccount:
        existing = await self.get_account_by_code(tenant_id, account_code)
        if existing is not None:
            raise ValidationError("Account code already exists for tenant")

        subgroup = (
            await self._session.execute(
                select(CoaAccountSubgroup).where(CoaAccountSubgroup.id == parent_subgroup_id)
            )
        ).scalar_one_or_none()
        if subgroup is None:
            raise NotFoundError("Parent subgroup not found")

        row = TenantCoaAccount(
            tenant_id=tenant_id,
            ledger_account_id=None,
            parent_subgroup_id=parent_subgroup_id,
            account_code=account_code,
            display_name=display_name,
            is_custom=True,
            is_active=True,
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def update_account(
        self,
        tenant_id: uuid.UUID,
        account_id: uuid.UUID,
        display_name: str | None,
        is_active: bool | None,
    ) -> TenantCoaAccount:
        row = (
            await self._session.execute(
                select(TenantCoaAccount).where(
                    TenantCoaAccount.id == account_id,
                    TenantCoaAccount.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        if row is None:
            raise NotFoundError("Tenant CoA account not found")
        if display_name is not None:
            row.display_name = display_name
        if is_active is not None:
            row.is_active = is_active
        await self._session.flush()
        return row

    async def get_account_by_code(self, tenant_id: uuid.UUID, code: str) -> TenantCoaAccount | None:
        return (
            await self._session.execute(
                select(TenantCoaAccount).where(
                    TenantCoaAccount.tenant_id == tenant_id,
                    TenantCoaAccount.account_code == code,
                )
            )
        ).scalar_one_or_none()

    async def toggle_account_active(self, tenant_id: uuid.UUID, account_id: uuid.UUID) -> TenantCoaAccount:
        row = (
            await self._session.execute(
                select(TenantCoaAccount).where(
                    TenantCoaAccount.id == account_id,
                    TenantCoaAccount.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        if row is None:
            raise NotFoundError("Tenant CoA account not found")
        row.is_active = not row.is_active
        await self._session.flush()
        return row

    async def get_account_with_hierarchy(self, tenant_id: uuid.UUID, account_id: uuid.UUID) -> dict[str, object]:
        account = (
            await self._session.execute(
                select(TenantCoaAccount).where(
                    TenantCoaAccount.id == account_id,
                    TenantCoaAccount.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        if account is None:
            raise NotFoundError("Tenant CoA account not found")

        subgroup_id = account.parent_subgroup_id
        if subgroup_id is None and account.ledger_account_id is not None:
            subgroup_id = (
                await self._session.execute(
                select(CoaLedgerAccount.account_subgroup_id).where(
                    CoaLedgerAccount.id == account.ledger_account_id,
                    or_(
                        CoaLedgerAccount.tenant_id == tenant_id,
                        CoaLedgerAccount.tenant_id.is_(None),
                    ),
                )
                )
            ).scalar_one_or_none()

        subgroup = None
        group = None
        subline = None
        line_item = None
        schedule = None

        if subgroup_id is not None:
            subgroup = (
                await self._session.execute(
                    select(CoaAccountSubgroup).where(CoaAccountSubgroup.id == subgroup_id)
                )
            ).scalar_one_or_none()
        if subgroup is not None:
            group = (
                await self._session.execute(
                    select(CoaAccountGroup).where(CoaAccountGroup.id == subgroup.account_group_id)
                )
            ).scalar_one_or_none()
        if group is not None and group.fs_subline_id is not None:
            subline = (
                await self._session.execute(
                    select(CoaFsSubline).where(CoaFsSubline.id == group.fs_subline_id)
                )
            ).scalar_one_or_none()
        if subline is not None:
            line_item = (
                await self._session.execute(
                    select(CoaFsLineItem).where(CoaFsLineItem.id == subline.fs_line_item_id)
                )
            ).scalar_one_or_none()
        if line_item is not None:
            schedule = (
                await self._session.execute(
                    select(CoaFsSchedule).where(CoaFsSchedule.id == line_item.fs_schedule_id)
                )
            ).scalar_one_or_none()

        return {
            "account": account,
            "subgroup": subgroup,
            "group": group,
            "subline": subline,
            "line_item": line_item,
            "schedule": schedule,
        }
