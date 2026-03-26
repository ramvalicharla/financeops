from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import NotFoundError
from financeops.modules.coa.models import (
    CoaAccountGroup,
    CoaAccountSubgroup,
    CoaFsClassification,
    CoaFsLineItem,
    CoaFsSchedule,
    CoaFsSubline,
    CoaGaapMapping,
    CoaIndustryTemplate,
    CoaLedgerAccount,
)


class CoaTemplateService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_all_templates(self) -> list[CoaIndustryTemplate]:
        rows = (
            await self._session.execute(
                select(CoaIndustryTemplate)
                .where(CoaIndustryTemplate.is_active.is_(True))
                .order_by(CoaIndustryTemplate.name)
            )
        ).scalars().all()
        return list(rows)

    async def get_template_by_code(self, code: str) -> CoaIndustryTemplate:
        row = (
            await self._session.execute(
                select(CoaIndustryTemplate).where(CoaIndustryTemplate.code == code)
            )
        ).scalar_one_or_none()
        if row is None:
            raise NotFoundError("Industry template not found")
        return row

    async def get_full_hierarchy(self, template_id: uuid.UUID) -> dict[str, object]:
        template = (
            await self._session.execute(
                select(CoaIndustryTemplate).where(CoaIndustryTemplate.id == template_id)
            )
        ).scalar_one_or_none()
        if template is None:
            raise NotFoundError("Industry template not found")

        classifications = (
            await self._session.execute(
                select(CoaFsClassification)
                .where(CoaFsClassification.is_active.is_(True))
                .order_by(CoaFsClassification.sort_order, CoaFsClassification.code)
            )
        ).scalars().all()
        schedules = (
            await self._session.execute(
                select(CoaFsSchedule)
                .where(CoaFsSchedule.is_active.is_(True))
                .order_by(CoaFsSchedule.sort_order, CoaFsSchedule.code)
            )
        ).scalars().all()
        line_items = (
            await self._session.execute(
                select(CoaFsLineItem)
                .where(CoaFsLineItem.is_active.is_(True))
                .order_by(CoaFsLineItem.sort_order, CoaFsLineItem.code)
            )
        ).scalars().all()
        sublines = (
            await self._session.execute(
                select(CoaFsSubline)
                .where(CoaFsSubline.is_active.is_(True))
                .order_by(CoaFsSubline.sort_order, CoaFsSubline.code)
            )
        ).scalars().all()
        groups = (
            await self._session.execute(
                select(CoaAccountGroup)
                .where(CoaAccountGroup.industry_template_id == template_id)
                .where(CoaAccountGroup.is_active.is_(True))
                .order_by(CoaAccountGroup.sort_order, CoaAccountGroup.code)
            )
        ).scalars().all()
        group_ids = [group.id for group in groups]
        subgroups = (
            await self._session.execute(
                select(CoaAccountSubgroup)
                .where(CoaAccountSubgroup.account_group_id.in_(group_ids))
                .where(CoaAccountSubgroup.is_active.is_(True))
                .order_by(CoaAccountSubgroup.sort_order, CoaAccountSubgroup.code)
            )
        ).scalars().all()
        subgroup_ids = [subgroup.id for subgroup in subgroups]
        ledgers = (
            await self._session.execute(
                select(CoaLedgerAccount)
                .where(CoaLedgerAccount.industry_template_id == template_id)
                .where(CoaLedgerAccount.account_subgroup_id.in_(subgroup_ids))
                .where(CoaLedgerAccount.is_active.is_(True))
                .order_by(CoaLedgerAccount.sort_order, CoaLedgerAccount.code)
            )
        ).scalars().all()

        schedules_by_classification: dict[uuid.UUID, list[CoaFsSchedule]] = {}
        for schedule in schedules:
            schedules_by_classification.setdefault(schedule.fs_classification_id, []).append(schedule)

        line_items_by_schedule: dict[uuid.UUID, list[CoaFsLineItem]] = {}
        for line_item in line_items:
            line_items_by_schedule.setdefault(line_item.fs_schedule_id, []).append(line_item)

        sublines_by_line_item: dict[uuid.UUID, list[CoaFsSubline]] = {}
        for subline in sublines:
            sublines_by_line_item.setdefault(subline.fs_line_item_id, []).append(subline)

        groups_by_subline: dict[uuid.UUID, list[CoaAccountGroup]] = {}
        for group in groups:
            if group.fs_subline_id is not None:
                groups_by_subline.setdefault(group.fs_subline_id, []).append(group)

        subgroups_by_group: dict[uuid.UUID, list[CoaAccountSubgroup]] = {}
        for subgroup in subgroups:
            subgroups_by_group.setdefault(subgroup.account_group_id, []).append(subgroup)

        ledgers_by_subgroup: dict[uuid.UUID, list[CoaLedgerAccount]] = {}
        for ledger in ledgers:
            ledgers_by_subgroup.setdefault(ledger.account_subgroup_id, []).append(ledger)

        hierarchy: list[dict[str, object]] = []
        for classification in classifications:
            classification_node = {
                "id": str(classification.id),
                "code": classification.code,
                "name": classification.name,
                "sort_order": classification.sort_order,
                "schedules": [],
            }
            for schedule in schedules_by_classification.get(classification.id, []):
                schedule_node = {
                    "id": str(schedule.id),
                    "gaap": schedule.gaap,
                    "code": schedule.code,
                    "name": schedule.name,
                    "sort_order": schedule.sort_order,
                    "line_items": [],
                }
                for line_item in line_items_by_schedule.get(schedule.id, []):
                    line_item_node = {
                        "id": str(line_item.id),
                        "code": line_item.code,
                        "name": line_item.name,
                        "sort_order": line_item.sort_order,
                        "sublines": [],
                    }
                    for subline in sublines_by_line_item.get(line_item.id, []):
                        subline_node = {
                            "id": str(subline.id),
                            "code": subline.code,
                            "name": subline.name,
                            "sort_order": subline.sort_order,
                            "account_groups": [],
                        }
                        for group in groups_by_subline.get(subline.id, []):
                            group_node = {
                                "id": str(group.id),
                                "code": group.code,
                                "name": group.name,
                                "sort_order": group.sort_order,
                                "account_subgroups": [],
                            }
                            for subgroup in subgroups_by_group.get(group.id, []):
                                subgroup_node = {
                                    "id": str(subgroup.id),
                                    "code": subgroup.code,
                                    "name": subgroup.name,
                                    "sort_order": subgroup.sort_order,
                                    "ledger_accounts": [],
                                }
                                for ledger in ledgers_by_subgroup.get(subgroup.id, []):
                                    subgroup_node["ledger_accounts"].append(
                                        {
                                            "id": str(ledger.id),
                                            "code": ledger.code,
                                            "name": ledger.name,
                                            "sort_order": ledger.sort_order,
                                            "normal_balance": ledger.normal_balance,
                                            "cash_flow_tag": ledger.cash_flow_tag,
                                            "bs_pl_flag": ledger.bs_pl_flag,
                                            "asset_liability_class": ledger.asset_liability_class,
                                        }
                                    )
                                group_node["account_subgroups"].append(subgroup_node)
                            subline_node["account_groups"].append(group_node)
                        line_item_node["sublines"].append(subline_node)
                    schedule_node["line_items"].append(line_item_node)
                classification_node["schedules"].append(schedule_node)
            hierarchy.append(classification_node)

        return {
            "template": {
                "id": str(template.id),
                "code": template.code,
                "name": template.name,
                "description": template.description,
            },
            "classifications": hierarchy,
        }

    async def get_ledger_accounts_for_template(self, template_id: uuid.UUID) -> list[CoaLedgerAccount]:
        rows = (
            await self._session.execute(
                select(CoaLedgerAccount)
                .where(CoaLedgerAccount.industry_template_id == template_id)
                .where(CoaLedgerAccount.is_active.is_(True))
                .order_by(CoaLedgerAccount.sort_order, CoaLedgerAccount.code)
            )
        ).scalars().all()
        return list(rows)

    async def get_gaap_mapping(self, ledger_account_id: uuid.UUID, gaap: str) -> CoaGaapMapping | None:
        return (
            await self._session.execute(
                select(CoaGaapMapping)
                .where(CoaGaapMapping.ledger_account_id == ledger_account_id)
                .where(CoaGaapMapping.gaap == gaap.upper())
                .where(CoaGaapMapping.is_active.is_(True))
            )
        ).scalar_one_or_none()
