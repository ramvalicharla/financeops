from __future__ import annotations

import logging
import re
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import NotFoundError, ValidationError
from financeops.db.models.tenants import IamTenant
from financeops.db.models.users import IamUser
from financeops.modules.coa.application.erp_mapping_service import ErpMappingService
from financeops.modules.coa.application.tenant_coa_service import TenantCoaService
from financeops.modules.coa.models import CoaIndustryTemplate, ErpAccountMapping, TenantCoaAccount
from financeops.modules.org_setup.application.consolidation_method_service import (
    ConsolidationMethodService,
)
from financeops.modules.org_setup.models import (
    OrgEntity,
    OrgEntityErpConfig,
    OrgGroup,
    OrgOwnership,
    OrgSetupProgress,
)
from financeops.modules.fixed_assets.application.seeds import seed_standard_indian_asset_classes
from financeops.platform.db.models.entities import CpEntity
from financeops.platform.db.models.organisations import CpOrganisation
from financeops.services.audit_writer import AuditWriter
from financeops.utils.gstin import extract_state_code, validate_gstin, validate_pan, validate_tan

_CODE_SANITIZE = re.compile(r"[^A-Z0-9]+")
_GSTIN_BASIC_RE = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][A-Z0-9]Z[A-Z0-9]$")
log = logging.getLogger(__name__)


def _clean_code(prefix: str, source: str, fallback: str) -> str:
    cleaned = _CODE_SANITIZE.sub("_", source.upper()).strip("_")
    if not cleaned:
        cleaned = fallback
    value = f"{prefix}_{cleaned}"
    return value[:64]


def _is_basic_gstin_format_valid(value: str) -> bool:
    normalized = value.strip().upper()
    if _GSTIN_BASIC_RE.fullmatch(normalized) is None:
        return False
    if extract_state_code(normalized) is None:
        return False
    return validate_pan(normalized[2:12])


class OrgSetupService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._consolidation = ConsolidationMethodService()
        self._tenant_coa = TenantCoaService(session)
        self._erp_mapping = ErpMappingService(session)

    async def _get_tenant(self, tenant_id: uuid.UUID) -> IamTenant:
        tenant = (
            await self._session.execute(select(IamTenant).where(IamTenant.id == tenant_id))
        ).scalar_one_or_none()
        if tenant is None:
            raise NotFoundError("Tenant not found")
        return tenant

    async def get_or_create_progress(self, tenant_id: uuid.UUID) -> OrgSetupProgress:
        row = (
            await self._session.execute(
                select(OrgSetupProgress).where(OrgSetupProgress.tenant_id == tenant_id)
            )
        ).scalar_one_or_none()
        if row is not None:
            return row
        row = OrgSetupProgress(tenant_id=tenant_id, current_step=1)
        self._session.add(row)
        await self._session.flush()
        return row

    async def save_step(self, tenant_id: uuid.UUID, step: int, data: dict[str, Any]) -> OrgSetupProgress:
        if step < 1 or step > 6:
            raise ValidationError("step must be between 1 and 6")
        progress = await self.get_or_create_progress(tenant_id)
        setattr(progress, f"step{step}_data", data)
        if step > progress.current_step:
            progress.current_step = step

        tenant = await self._get_tenant(tenant_id)
        if step > tenant.org_setup_step and not tenant.org_setup_complete:
            tenant.org_setup_step = step

        await self._session.flush()
        return progress

    async def submit_step1(self, tenant_id: uuid.UUID, data: dict[str, Any]) -> OrgGroup:
        group = (
            await self._session.execute(
                select(OrgGroup).where(OrgGroup.tenant_id == tenant_id)
            )
        ).scalar_one_or_none()
        if group is None:
            group = OrgGroup(
                tenant_id=tenant_id,
                group_name=str(data["group_name"]).strip(),
                country_of_incorp=str(data["country_of_incorp"]).strip(),
                country_code=str(data["country_code"]).strip().upper(),
                functional_currency=str(data["functional_currency"]).strip().upper(),
                reporting_currency=str(data["reporting_currency"]).strip().upper(),
                logo_url=data.get("logo_url"),
                website=data.get("website"),
            )
            self._session.add(group)
        else:
            group.group_name = str(data["group_name"]).strip()
            group.country_of_incorp = str(data["country_of_incorp"]).strip()
            group.country_code = str(data["country_code"]).strip().upper()
            group.functional_currency = str(data["functional_currency"]).strip().upper()
            group.reporting_currency = str(data["reporting_currency"]).strip().upper()
            group.logo_url = data.get("logo_url")
            group.website = data.get("website")

        await self._session.flush()
        await self.save_step(
            tenant_id,
            1,
            {
                "group_id": str(group.id),
                "group_name": group.group_name,
                "country_code": group.country_code,
                "functional_currency": group.functional_currency,
                "reporting_currency": group.reporting_currency,
            },
        )
        return group

    async def _get_or_create_cp_organisation(self, tenant_id: uuid.UUID, group: OrgGroup) -> CpOrganisation:
        org_code = _clean_code("ORG", group.group_name, f"GROUP_{group.id.hex[:8].upper()}")
        existing = (
            await self._session.execute(
                select(CpOrganisation)
                .where(
                    CpOrganisation.tenant_id == tenant_id,
                    CpOrganisation.organisation_code == org_code,
                )
                .order_by(CpOrganisation.created_at.desc())
            )
        ).scalars().first()
        if existing is not None:
            return existing

        return await AuditWriter.insert_financial_record(
            self._session,
            model_class=CpOrganisation,
            tenant_id=tenant_id,
            record_data={
                "organisation_code": org_code,
                "organisation_name": group.group_name,
            },
            values={
                "organisation_code": org_code,
                "organisation_name": group.group_name,
                "parent_organisation_id": None,
                "supersedes_id": None,
                "is_active": True,
                "correlation_id": f"org-setup-{group.id}",
            },
            audit=None,
        )

    async def _get_or_create_cp_entity(
        self,
        *,
        tenant_id: uuid.UUID,
        organisation_id: uuid.UUID,
        legal_name: str,
        base_currency: str,
        country_code: str,
        seed: str,
        pan: str | None = None,
        tan: str | None = None,
        cin: str | None = None,
        gstin: str | None = None,
        lei: str | None = None,
        fiscal_year_start: int | None = None,
        applicable_gaap: str | None = None,
        tax_rate: Decimal | None = None,
        state_code: str | None = None,
        registered_address: str | None = None,
        city: str | None = None,
        pincode: str | None = None,
    ) -> CpEntity:
        entity_code = _clean_code("ENT", legal_name, seed)
        existing = (
            await self._session.execute(
                select(CpEntity)
                .where(CpEntity.tenant_id == tenant_id, CpEntity.entity_code == entity_code)
                .order_by(CpEntity.created_at.desc())
            )
        ).scalars().first()
        if existing is not None:
            return existing

        return await AuditWriter.insert_financial_record(
            self._session,
            model_class=CpEntity,
            tenant_id=tenant_id,
            record_data={
                "entity_code": entity_code,
                "entity_name": legal_name,
            },
            values={
                "entity_code": entity_code,
                "entity_name": legal_name,
                "organisation_id": organisation_id,
                "group_id": None,
                "base_currency": base_currency,
                "country_code": country_code,
                "pan": pan,
                "tan": tan,
                "cin": cin,
                "gstin": gstin,
                "lei": lei,
                "fiscal_year_start": fiscal_year_start,
                "applicable_gaap": applicable_gaap,
                "tax_rate": tax_rate,
                "state_code": state_code,
                "registered_address": registered_address,
                "city": city,
                "pincode": pincode,
                "status": "active",
                "deactivated_at": None,
                "correlation_id": f"org-setup-{seed}",
            },
            audit=None,
        )

    async def submit_step2(
        self,
        tenant_id: uuid.UUID,
        group_id: uuid.UUID,
        entities: list[dict[str, Any]],
    ) -> list[OrgEntity]:
        if not entities:
            raise ValidationError("At least one entity is required")

        log.info("Step2 lookup group_id=%s tenant_id=%s", group_id, tenant_id)
        group = (
            await self._session.execute(
                select(OrgGroup).where(
                    OrgGroup.id == group_id,
                    OrgGroup.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        if group is None:
            raise NotFoundError("Group not found")

        cp_org = await self._get_or_create_cp_organisation(tenant_id, group)
        rows: list[OrgEntity] = []
        for entity in entities:
            legal_name = str(entity["legal_name"]).strip()
            if not legal_name:
                raise ValidationError("legal_name is required")

            pan = entity.get("pan")
            if pan and not validate_pan(str(pan)):
                raise ValidationError("Invalid PAN")
            tan = entity.get("tan")
            if tan and not validate_tan(str(tan)):
                raise ValidationError("Invalid TAN")
            gstin = entity.get("gstin")
            normalized_gstin: str | None = None
            if gstin:
                normalized_gstin = str(gstin).strip().upper()
                # Accept legacy onboarding payloads with valid structure even if checksum is absent/incorrect.
                if not validate_gstin(normalized_gstin) and not _is_basic_gstin_format_valid(normalized_gstin):
                    raise ValidationError("Invalid GSTIN")
            inferred_state_code = extract_state_code(normalized_gstin) if normalized_gstin else entity.get("state_code")

            row = (
                await self._session.execute(
                    select(OrgEntity).where(
                        OrgEntity.tenant_id == tenant_id,
                        OrgEntity.org_group_id == group_id,
                        OrgEntity.legal_name == legal_name,
                    )
                )
            ).scalar_one_or_none()

            payload = {
                "display_name": entity.get("display_name"),
                "entity_type": str(entity["entity_type"]),
                "country_code": str(entity["country_code"]).upper(),
                "state_code": inferred_state_code,
                "functional_currency": str(entity["functional_currency"]).upper(),
                "reporting_currency": str(entity["reporting_currency"]).upper(),
                "fiscal_year_start": int(entity["fiscal_year_start"]),
                "applicable_gaap": str(entity["applicable_gaap"]).upper(),
                "incorporation_number": entity.get("incorporation_number"),
                "pan": str(pan).upper() if pan else None,
                "tan": str(tan).upper() if tan else None,
                "cin": entity.get("cin"),
                "gstin": normalized_gstin,
                "lei": entity.get("lei"),
                "tax_jurisdiction": entity.get("tax_jurisdiction"),
                "tax_rate": entity.get("tax_rate"),
                "is_active": True,
            }

            if row is None:
                row = OrgEntity(
                    tenant_id=tenant_id,
                    org_group_id=group_id,
                    cp_entity_id=None,
                    legal_name=legal_name,
                    **payload,
                )
                self._session.add(row)
            else:
                row.display_name = payload["display_name"]
                row.entity_type = payload["entity_type"]
                row.country_code = payload["country_code"]
                row.state_code = payload["state_code"]
                row.functional_currency = payload["functional_currency"]
                row.reporting_currency = payload["reporting_currency"]
                row.fiscal_year_start = payload["fiscal_year_start"]
                row.applicable_gaap = payload["applicable_gaap"]
                row.incorporation_number = payload["incorporation_number"]
                row.pan = payload["pan"]
                row.tan = payload["tan"]
                row.cin = payload["cin"]
                row.gstin = payload["gstin"]
                row.lei = payload["lei"]
                row.tax_jurisdiction = payload["tax_jurisdiction"]
                row.tax_rate = payload["tax_rate"]
                row.is_active = True

            await self._session.flush()
            if row.cp_entity_id is None:
                cp_entity = await self._get_or_create_cp_entity(
                    tenant_id=tenant_id,
                    organisation_id=cp_org.id,
                    legal_name=legal_name,
                    base_currency=row.functional_currency,
                    country_code=row.country_code,
                    seed=row.id.hex[:8].upper(),
                    pan=payload["pan"],
                    tan=payload["tan"],
                    cin=payload["cin"],
                    gstin=payload["gstin"],
                    lei=payload["lei"],
                    fiscal_year_start=payload["fiscal_year_start"],
                    applicable_gaap=payload["applicable_gaap"],
                    tax_rate=payload["tax_rate"],
                    state_code=payload["state_code"],
                    registered_address=entity.get("registered_address"),
                    city=entity.get("city"),
                    pincode=entity.get("pincode"),
                )
                row.cp_entity_id = cp_entity.id
            await self._session.flush()
            await self._session.refresh(row)
            rows.append(row)

        await self.save_step(
            tenant_id,
            2,
            {
                "group_id": str(group_id),
                "entity_ids": [str(item.id) for item in rows],
            },
        )
        return rows

    async def submit_step3(
        self,
        tenant_id: uuid.UUID,
        relationships: list[dict[str, Any]],
    ) -> list[OrgOwnership]:
        rows: list[OrgOwnership] = []
        for relationship in relationships:
            parent_entity_id = uuid.UUID(str(relationship["parent_entity_id"]))
            child_entity_id = uuid.UUID(str(relationship["child_entity_id"]))
            if parent_entity_id == child_entity_id:
                raise ValidationError("Parent and child entities must differ")

            parent = (
                await self._session.execute(
                    select(OrgEntity).where(
                        OrgEntity.id == parent_entity_id,
                        OrgEntity.tenant_id == tenant_id,
                    )
                )
            ).scalar_one_or_none()
            child = (
                await self._session.execute(
                    select(OrgEntity).where(
                        OrgEntity.id == child_entity_id,
                        OrgEntity.tenant_id == tenant_id,
                    )
                )
            ).scalar_one_or_none()
            if parent is None or child is None:
                raise NotFoundError("Entity relationship references unknown entity")

            ownership_pct = Decimal(str(relationship["ownership_pct"]))
            manual_override = relationship.get("manual_consolidation_method")
            consolidation_method = self._consolidation.derive_method(
                ownership_pct=ownership_pct,
                entity_type=child.entity_type,
                manual_override=manual_override,
            )

            effective_from_value = relationship.get("effective_from")
            if effective_from_value is None:
                effective_from = date.today()
            elif isinstance(effective_from_value, date):
                effective_from = effective_from_value
            else:
                effective_from = date.fromisoformat(str(effective_from_value))

            current = (
                await self._session.execute(
                    select(OrgOwnership).where(
                        OrgOwnership.tenant_id == tenant_id,
                        OrgOwnership.parent_entity_id == parent_entity_id,
                        OrgOwnership.child_entity_id == child_entity_id,
                        OrgOwnership.effective_from == effective_from,
                    )
                )
            ).scalar_one_or_none()

            if current is None:
                current = OrgOwnership(
                    tenant_id=tenant_id,
                    parent_entity_id=parent_entity_id,
                    child_entity_id=child_entity_id,
                    ownership_pct=ownership_pct,
                    consolidation_method=consolidation_method,
                    effective_from=effective_from,
                    effective_to=relationship.get("effective_to"),
                    notes=relationship.get("notes"),
                )
                self._session.add(current)
            else:
                current.ownership_pct = ownership_pct
                current.consolidation_method = consolidation_method
                current.effective_to = relationship.get("effective_to")
                current.notes = relationship.get("notes")
            rows.append(current)

        await self._session.flush()
        await self.save_step(
            tenant_id,
            3,
            {"relationship_count": len(rows)},
        )
        return rows

    async def submit_step4(
        self,
        tenant_id: uuid.UUID,
        configs: list[dict[str, Any]],
    ) -> list[OrgEntityErpConfig]:
        rows: list[OrgEntityErpConfig] = []
        for config in configs:
            entity_id = uuid.UUID(str(config["org_entity_id"]))
            exists = (
                await self._session.execute(
                    select(OrgEntity.id).where(
                        OrgEntity.id == entity_id,
                        OrgEntity.tenant_id == tenant_id,
                    )
                )
            ).scalar_one_or_none()
            if exists is None:
                raise NotFoundError("Org entity not found")

            row = (
                await self._session.execute(
                    select(OrgEntityErpConfig).where(
                        OrgEntityErpConfig.tenant_id == tenant_id,
                        OrgEntityErpConfig.org_entity_id == entity_id,
                        OrgEntityErpConfig.erp_type == str(config["erp_type"]),
                        OrgEntityErpConfig.is_primary == bool(config.get("is_primary", True)),
                    )
                )
            ).scalar_one_or_none()

            if row is None:
                row = OrgEntityErpConfig(
                    tenant_id=tenant_id,
                    org_entity_id=entity_id,
                    erp_type=str(config["erp_type"]),
                    erp_version=config.get("erp_version"),
                    connection_config=config.get("connection_config"),
                    is_primary=bool(config.get("is_primary", True)),
                    connection_tested=bool(config.get("connection_tested", False)),
                    connection_tested_at=config.get("connection_tested_at"),
                    is_active=True,
                )
                self._session.add(row)
            else:
                row.erp_version = config.get("erp_version")
                row.connection_config = config.get("connection_config")
                row.connection_tested = bool(config.get("connection_tested", False))
                row.connection_tested_at = config.get("connection_tested_at")
                row.is_active = True

            rows.append(row)

        await self._session.flush()
        await self.save_step(tenant_id, 4, {"config_count": len(rows)})
        return rows

    async def submit_step5(
        self,
        tenant_id: uuid.UUID,
        entity_templates: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        summaries: list[dict[str, Any]] = []
        template_ids: set[uuid.UUID] = set()
        for item in entity_templates:
            entity_id = uuid.UUID(str(item["entity_id"]))
            template_id = uuid.UUID(str(item["template_id"]))
            template_ids.add(template_id)
            entity = (
                await self._session.execute(
                    select(OrgEntity).where(
                        OrgEntity.id == entity_id,
                        OrgEntity.tenant_id == tenant_id,
                    )
                )
            ).scalar_one_or_none()
            if entity is None:
                raise NotFoundError("Org entity not found")
            entity.industry_template_id = template_id

            await self._tenant_coa.initialise_tenant_coa(tenant_id, template_id)
            if entity.cp_entity_id is not None:
                await seed_standard_indian_asset_classes(
                    self._session,
                    tenant_id=tenant_id,
                    entity_id=entity.cp_entity_id,
                )
            account_count = int(
                (
                    await self._session.execute(
                        select(func.count())
                        .select_from(TenantCoaAccount)
                        .where(TenantCoaAccount.tenant_id == tenant_id)
                    )
                ).scalar_one()
            )

            template_code = (
                await self._session.execute(
                    select(CoaIndustryTemplate.code).where(CoaIndustryTemplate.id == template_id)
                )
            ).scalar_one_or_none()
            summaries.append(
                {
                    "entity_id": str(entity_id),
                    "template_code": str(template_code or ""),
                    "account_count": account_count,
                }
            )

        await self._session.flush()
        await self.save_step(
            tenant_id,
            5,
            {
                "entity_templates": [
                    {"entity_id": str(item["entity_id"]), "template_id": str(item["template_id"])}
                    for item in entity_templates
                ],
                "template_count": len(template_ids),
            },
        )
        return summaries

    async def _resolve_confirmer(self, tenant_id: uuid.UUID, confirmed_by: uuid.UUID | None) -> uuid.UUID:
        if confirmed_by is not None:
            return confirmed_by
        fallback = (
            await self._session.execute(
                select(IamUser.id)
                .where(IamUser.tenant_id == tenant_id, IamUser.is_active.is_(True))
                .order_by(IamUser.created_at.asc())
            )
        ).scalar_one_or_none()
        if fallback is None:
            raise NotFoundError("No active user available to confirm mappings")
        return fallback

    async def submit_step6(
        self,
        tenant_id: uuid.UUID,
        confirmed_mapping_ids: list[uuid.UUID],
        confirmed_by: uuid.UUID | None = None,
    ) -> int:
        confirmer = await self._resolve_confirmer(tenant_id, confirmed_by)
        confirmed_count = await self._erp_mapping.bulk_confirm_mappings(
            tenant_id=tenant_id,
            mapping_ids=confirmed_mapping_ids,
            confirmed_by=confirmer,
        )
        await self.save_step(
            tenant_id,
            6,
            {
                "confirmed_mapping_ids": [str(item) for item in confirmed_mapping_ids],
                "confirmed_count": confirmed_count,
            },
        )
        await self.complete_setup(tenant_id)
        return confirmed_count

    async def complete_setup(self, tenant_id: uuid.UUID) -> None:
        tenant = await self._get_tenant(tenant_id)
        progress = await self.get_or_create_progress(tenant_id)
        tenant.org_setup_complete = True
        tenant.org_setup_step = 7
        progress.completed_at = datetime.now(UTC)
        if progress.current_step < 6:
            progress.current_step = 6
        await self._session.flush()

    async def get_setup_summary(self, tenant_id: uuid.UUID) -> dict[str, Any]:
        group = (
            await self._session.execute(
                select(OrgGroup).where(OrgGroup.tenant_id == tenant_id)
            )
        ).scalar_one_or_none()
        entities = (
            await self._session.execute(
                select(OrgEntity)
                .where(OrgEntity.tenant_id == tenant_id)
                .order_by(OrgEntity.legal_name)
            )
        ).scalars().all()
        ownership = (
            await self._session.execute(
                select(OrgOwnership).where(OrgOwnership.tenant_id == tenant_id)
            )
        ).scalars().all()
        erp_configs = (
            await self._session.execute(
                select(OrgEntityErpConfig).where(OrgEntityErpConfig.tenant_id == tenant_id)
            )
        ).scalars().all()

        total_mappings = int(
            (
                await self._session.execute(
                    select(func.count())
                    .select_from(ErpAccountMapping)
                    .where(ErpAccountMapping.tenant_id == tenant_id)
                )
            ).scalar_one()
        )
        confirmed_mappings = int(
            (
                await self._session.execute(
                    select(func.count())
                    .select_from(ErpAccountMapping)
                    .where(
                        ErpAccountMapping.tenant_id == tenant_id,
                        ErpAccountMapping.is_confirmed.is_(True),
                    )
                )
            ).scalar_one()
        )
        mapped_mappings = int(
            (
                await self._session.execute(
                    select(func.count())
                    .select_from(ErpAccountMapping)
                    .where(
                        ErpAccountMapping.tenant_id == tenant_id,
                        ErpAccountMapping.tenant_coa_account_id.is_not(None),
                    )
                )
            ).scalar_one()
        )
        avg_confidence_raw = (
            await self._session.execute(
                select(func.avg(ErpAccountMapping.mapping_confidence)).where(
                    ErpAccountMapping.tenant_id == tenant_id,
                    ErpAccountMapping.mapping_confidence.is_not(None),
                )
            )
        ).scalar_one_or_none()

        account_count = int(
            (
                await self._session.execute(
                    select(func.count())
                    .select_from(TenantCoaAccount)
                    .where(TenantCoaAccount.tenant_id == tenant_id)
                )
            ).scalar_one()
        )

        return {
            "group": group,
            "entities": list(entities),
            "ownership": list(ownership),
            "erp_configs": list(erp_configs),
            "coa_account_count": account_count,
            "mapping_summary": {
                "total": total_mappings,
                "mapped": mapped_mappings,
                "confirmed": confirmed_mappings,
                "unmapped": total_mappings - confirmed_mappings,
                "confidence_avg": Decimal(str(avg_confidence_raw or "0")).quantize(Decimal("0.0001")),
            },
        }

    async def get_entities(self, tenant_id: uuid.UUID) -> list[OrgEntity]:
        rows = (
            await self._session.execute(
                select(OrgEntity)
                .where(OrgEntity.tenant_id == tenant_id)
                .order_by(OrgEntity.legal_name)
            )
        ).scalars().all()
        return list(rows)

    async def get_entity(self, tenant_id: uuid.UUID, entity_id: uuid.UUID) -> OrgEntity:
        row = (
            await self._session.execute(
                select(OrgEntity).where(
                    OrgEntity.tenant_id == tenant_id,
                    OrgEntity.id == entity_id,
                )
            )
        ).scalar_one_or_none()
        if row is None:
            raise NotFoundError("Org entity not found")
        return row

    async def update_entity(self, tenant_id: uuid.UUID, entity_id: uuid.UUID, payload: dict[str, Any]) -> OrgEntity:
        row = await self.get_entity(tenant_id, entity_id)
        if "pan" in payload and payload["pan"] and not validate_pan(str(payload["pan"])):
            raise ValidationError("Invalid PAN")
        if "tan" in payload and payload["tan"] and not validate_tan(str(payload["tan"])):
            raise ValidationError("Invalid TAN")
        if "gstin" in payload and payload["gstin"]:
            gstin = str(payload["gstin"]).upper()
            if not validate_gstin(gstin):
                raise ValidationError("Invalid GSTIN")
            payload["gstin"] = gstin
            payload["state_code"] = extract_state_code(gstin)

        for key, value in payload.items():
            if hasattr(row, key) and value is not None:
                setattr(row, key, value)

        if row.cp_entity_id is not None:
            cp_entity = (
                await self._session.execute(
                    select(CpEntity).where(
                        CpEntity.id == row.cp_entity_id,
                        CpEntity.tenant_id == tenant_id,
                    )
                )
            ).scalar_one_or_none()
            if cp_entity is not None:
                field_map = {
                    "display_name": "entity_name",
                    "functional_currency": "base_currency",
                }
                for key, value in payload.items():
                    if value is None:
                        continue
                    target_attr = field_map.get(key, key)
                    if hasattr(cp_entity, target_attr):
                        setattr(cp_entity, target_attr, value)

        await self._session.flush()
        await self._session.refresh(row)
        return row

    async def get_ownership_tree(self, tenant_id: uuid.UUID) -> dict[str, Any]:
        entities = await self.get_entities(tenant_id)
        links = (
            await self._session.execute(
                select(OrgOwnership).where(
                    OrgOwnership.tenant_id == tenant_id,
                    OrgOwnership.effective_to.is_(None),
                )
            )
        ).scalars().all()
        by_parent: dict[uuid.UUID, list[OrgOwnership]] = {}
        child_ids: set[uuid.UUID] = set()
        for link in links:
            by_parent.setdefault(link.parent_entity_id, []).append(link)
            child_ids.add(link.child_entity_id)

        node_by_id = {
            entity.id: {
                "entity_id": str(entity.id),
                "legal_name": entity.legal_name,
                "display_name": entity.display_name,
                "entity_type": entity.entity_type,
                "children": [],
            }
            for entity in entities
        }

        def build(entity_id: uuid.UUID, visited: set[uuid.UUID]) -> dict[str, Any]:
            node = dict(node_by_id[entity_id])
            next_visited = set(visited)
            next_visited.add(entity_id)
            children: list[dict[str, Any]] = []
            for rel in by_parent.get(entity_id, []):
                if rel.child_entity_id in next_visited:
                    continue
                child = build(rel.child_entity_id, next_visited)
                child["ownership_pct"] = rel.ownership_pct
                child["consolidation_method"] = rel.consolidation_method
                children.append(child)
            node["children"] = children
            return node

        roots = [entity.id for entity in entities if entity.id not in child_ids]
        if not roots:
            roots = [entity.id for entity in entities]

        tree = [build(root, set()) for root in roots]
        group = (
            await self._session.execute(
                select(OrgGroup).where(OrgGroup.tenant_id == tenant_id)
            )
        ).scalar_one_or_none()
        return {
            "group_id": str(group.id) if group is not None else None,
            "group_name": group.group_name if group is not None else None,
            "entities": tree,
        }


__all__ = ["OrgSetupService"]
