from __future__ import annotations

import uuid
from collections.abc import Mapping
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from financeops.core.exceptions import NotFoundError, ValidationError
from financeops.core.intent.enums import IntentSourceChannel, IntentType
from financeops.core.intent.journal_pipeline import submit_governed_journal_intent
from financeops.core.security import decrypt_field, encrypt_field
from financeops.db.models.accounting_jv import AccountingJVAggregate, JVStatus
from financeops.db.models.accounting_vendor import AccountingVendor
from financeops.db.models.erp_integration import (
    ErpConnector,
    ErpConnectorStatus,
    ErpCoaMapping,
    ErpJournalMapping,
    ErpMasterEntityType,
    ErpMasterMapping,
    ErpSyncJob,
    ErpSyncLog,
    ErpSyncModule,
    ErpSyncStatus,
    ErpSyncType,
)
from financeops.db.models.users import IamUser
from financeops.modules.accounting_layer.domain.schemas import JournalCreate, JournalLineCreate
from financeops.modules.coa.models import TenantCoaAccount
from financeops.modules.erp_integration.connectors.registry import get_connector
from financeops.modules.erp_integration.schemas import (
    CoaMapRequest,
    ConnectorCreateRequest,
    JournalExportRequest,
    JournalImportRequest,
    MasterSyncRequest,
    SyncRunRequest,
)
from financeops.platform.db.models.entities import CpEntity
from financeops.services.audit_writer import AuditWriter

MAX_SYNC_JOB_RETRIES = 3


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def _to_decimal(value: Any, *, field: str) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError) as exc:
        raise ValidationError(f"{field} must be a decimal value.") from exc
    if parsed < 0:
        raise ValidationError(f"{field} cannot be negative.")
    return parsed


def _to_date(value: Any) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
        except ValueError:
            return date.fromisoformat(value)
    raise ValidationError("journal_date must be an ISO date/datetime string.")


def _extract_external_id(row: Mapping[str, Any]) -> str | None:
    for key in ("external_reference_id", "external_id", "erp_journal_id", "id", "code"):
        raw = row.get(key)
        if raw is not None and str(raw).strip():
            return str(raw).strip()
    return None


class ErpIntegrationService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_connector(
        self,
        *,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        body: ConnectorCreateRequest,
    ) -> ErpConnector:
        await self._assert_entity_scope(tenant_id=tenant_id, org_entity_id=body.org_entity_id)
        encrypted_config = self._encrypt_connection_config(body.connection_config)
        row = ErpConnector(
            tenant_id=tenant_id,
            org_entity_id=body.org_entity_id,
            erp_type=body.erp_type.strip().upper(),
            connection_config=encrypted_config,
            auth_type=body.auth_type,
            status=ErpConnectorStatus.ACTIVE,
            created_by=user_id,
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def list_connectors(self, *, tenant_id: uuid.UUID) -> list[ErpConnector]:
        result = await self._session.execute(
            select(ErpConnector)
            .where(ErpConnector.tenant_id == tenant_id)
            .order_by(ErpConnector.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_connector(
        self,
        *,
        tenant_id: uuid.UUID,
        connector_id: uuid.UUID,
    ) -> ErpConnector:
        return await self._get_connector(tenant_id=tenant_id, connector_id=connector_id)

    async def update_connector_status(
        self,
        *,
        tenant_id: uuid.UUID,
        connector_id: uuid.UUID,
        status: str,
    ) -> ErpConnector:
        row = await self._get_connector(tenant_id=tenant_id, connector_id=connector_id)
        row.status = ErpConnectorStatus(status)
        row.updated_at = _utcnow()
        await self._session.flush()
        return row

    async def test_connector(
        self,
        *,
        tenant_id: uuid.UUID,
        connector_id: uuid.UUID,
    ) -> dict[str, Any]:
        row = await self._get_connector(tenant_id=tenant_id, connector_id=connector_id)
        connector = get_connector(row.erp_type)
        runtime_config = self._runtime_connection_config(row.connection_config)
        return await connector.authenticate(connection_config=runtime_config)

    async def list_jobs(
        self,
        *,
        tenant_id: uuid.UUID,
        erp_connector_id: uuid.UUID | None = None,
    ) -> list[ErpSyncJob]:
        stmt = (
            select(ErpSyncJob)
            .where(ErpSyncJob.tenant_id == tenant_id)
            .order_by(ErpSyncJob.created_at.desc())
        )
        if erp_connector_id is not None:
            stmt = stmt.where(ErpSyncJob.erp_connector_id == erp_connector_id)
        rows = (await self._session.execute(stmt)).scalars().all()
        return list(rows)

    async def get_job(
        self,
        *,
        tenant_id: uuid.UUID,
        job_id: uuid.UUID,
    ) -> ErpSyncJob:
        row = (
            await self._session.execute(
                select(ErpSyncJob).where(
                    ErpSyncJob.tenant_id == tenant_id,
                    ErpSyncJob.id == job_id,
                )
            )
        ).scalar_one_or_none()
        if row is None:
            raise NotFoundError("ERP sync job not found.")
        return row

    async def run_sync_job(
        self,
        *,
        tenant_id: uuid.UUID,
        actor: IamUser,
        body: SyncRunRequest,
    ) -> ErpSyncJob:
        connector_row = await self._get_connector(
            tenant_id=tenant_id,
            connector_id=body.erp_connector_id,
        )
        runtime_config = self._runtime_connection_config(connector_row.connection_config)
        connector = get_connector(connector_row.erp_type)

        retry_count = 0
        if body.retry_of_job_id is not None:
            previous = await self.get_job(tenant_id=tenant_id, job_id=body.retry_of_job_id)
            if previous.retry_count >= MAX_SYNC_JOB_RETRIES:
                raise ValidationError("ERP sync retry limit reached.")
            retry_count = previous.retry_count + 1

        job = ErpSyncJob(
            tenant_id=tenant_id,
            org_entity_id=connector_row.org_entity_id,
            erp_connector_id=connector_row.id,
            sync_type=body.sync_type,
            module=body.module,
            status=ErpSyncStatus.RUNNING,
            started_at=_utcnow(),
            retry_count=retry_count,
            request_payload=body.payload,
            created_by=actor.id,
        )
        self._session.add(job)
        await self._session.flush()

        result_payload: dict[str, Any]
        try:
            if body.sync_type == ErpSyncType.IMPORT and body.module == ErpSyncModule.COA:
                result_payload = await self._import_coa(
                    tenant_id=tenant_id,
                    connector_row=connector_row,
                    connector=connector,
                    runtime_config=runtime_config,
                )
            elif body.sync_type == ErpSyncType.IMPORT and body.module == ErpSyncModule.JOURNALS:
                request = JournalImportRequest(
                    erp_connector_id=body.erp_connector_id,
                    transactions=body.payload.get("transactions"),
                )
                result_payload = await self.import_journals(
                    tenant_id=tenant_id,
                    actor=actor,
                    body=request,
                )
            elif body.sync_type == ErpSyncType.EXPORT and body.module == ErpSyncModule.JOURNALS:
                request = JournalExportRequest(
                    erp_connector_id=body.erp_connector_id,
                    journal_ids=body.payload.get("journal_ids"),
                )
                result_payload = await self.export_journals(
                    tenant_id=tenant_id,
                    actor=actor,
                    body=request,
                )
            elif body.sync_type == ErpSyncType.IMPORT and body.module == ErpSyncModule.VENDORS:
                request = MasterSyncRequest(
                    erp_connector_id=body.erp_connector_id,
                    rows=body.payload.get("rows"),
                    entity_type=ErpMasterEntityType.VENDOR,
                )
                result_payload = await self.sync_master_data(
                    tenant_id=tenant_id,
                    actor=actor,
                    body=request,
                )
            elif body.sync_type == ErpSyncType.IMPORT and body.module == ErpSyncModule.CUSTOMERS:
                request = MasterSyncRequest(
                    erp_connector_id=body.erp_connector_id,
                    rows=body.payload.get("rows"),
                    entity_type=ErpMasterEntityType.CUSTOMER,
                )
                result_payload = await self.sync_master_data(
                    tenant_id=tenant_id,
                    actor=actor,
                    body=request,
                )
            else:
                raise ValidationError("Unsupported sync_type/module combination.")

            job.status = ErpSyncStatus.SUCCESS
            job.completed_at = _utcnow()
            job.result_summary = result_payload
            job.error_message = None
            connector_row.last_sync_at = job.completed_at

            self._session.add(
                ErpSyncLog(
                    job_id=job.id,
                    payload_json=body.payload,
                    result_json=result_payload,
                )
            )
            await self._session.flush()
            return job
        except Exception as exc:  # noqa: BLE001
            job.status = ErpSyncStatus.FAILED
            job.completed_at = _utcnow()
            job.error_message = str(exc)
            job.result_summary = {"error": str(exc)}
            self._session.add(
                ErpSyncLog(
                    job_id=job.id,
                    payload_json=body.payload,
                    result_json={"error": str(exc)},
                )
            )
            await self._session.flush()
            return job

    async def import_coa(
        self,
        *,
        tenant_id: uuid.UUID,
        body: SyncRunRequest | None = None,
        connector_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        resolved_connector_id = connector_id or (body.erp_connector_id if body else None)
        if resolved_connector_id is None:
            raise ValidationError("erp_connector_id is required.")
        connector_row = await self._get_connector(tenant_id=tenant_id, connector_id=resolved_connector_id)
        connector = get_connector(connector_row.erp_type)
        runtime_config = self._runtime_connection_config(connector_row.connection_config)
        return await self._import_coa(
            tenant_id=tenant_id,
            connector_row=connector_row,
            connector=connector,
            runtime_config=runtime_config,
        )

    async def map_coa(
        self,
        *,
        tenant_id: uuid.UUID,
        body: CoaMapRequest,
    ) -> dict[str, Any]:
        connector_row = await self._get_connector(
            tenant_id=tenant_id,
            connector_id=body.erp_connector_id,
        )
        upserted = 0
        for mapping in body.mappings:
            await self._assert_account_scope(
                tenant_id=tenant_id,
                internal_account_id=mapping.internal_account_id,
            )
            stmt = insert(ErpCoaMapping).values(
                tenant_id=tenant_id,
                erp_connector_id=connector_row.id,
                erp_account_id=mapping.erp_account_id,
                internal_account_id=mapping.internal_account_id,
            )
            stmt = stmt.on_conflict_do_update(
                constraint="uq_erp_coa_mappings_connector_account",
                set_={
                    "internal_account_id": stmt.excluded.internal_account_id,
                    "updated_at": _utcnow(),
                },
            )
            await self._session.execute(stmt)
            upserted += 1
        await self._session.flush()
        return {"upserted": upserted}

    async def import_journals(
        self,
        *,
        tenant_id: uuid.UUID,
        actor: IamUser,
        body: JournalImportRequest,
    ) -> dict[str, Any]:
        connector_row = await self._get_connector(
            tenant_id=tenant_id,
            connector_id=body.erp_connector_id,
        )
        connector = get_connector(connector_row.erp_type)
        runtime_config = self._runtime_connection_config(connector_row.connection_config)

        if body.transactions is None:
            normalized: list[Any] = await connector.fetch_transactions(connection_config=runtime_config)
        else:
            normalized = body.transactions

        external_ids = (
            await self._session.execute(
                select(ErpJournalMapping.erp_journal_id).where(
                    ErpJournalMapping.tenant_id == tenant_id,
                    ErpJournalMapping.erp_connector_id == connector_row.id,
                )
            )
        ).scalars().all()
        existing_external_ids = set(external_ids)

        imported_count = 0
        skipped_duplicates = 0
        failed_records: list[dict[str, Any]] = []

        for row in normalized:
            row_data = row.model_dump(mode="python") if hasattr(row, "model_dump") else dict(row)
            external_reference_id = _extract_external_id(row_data)
            if not external_reference_id:
                failed_records.append({"reason": "missing_external_reference_id", "row": row_data})
                continue
            if external_reference_id in existing_external_ids:
                skipped_duplicates += 1
                continue

            try:
                line_rows = row_data.get("lines") or []
                if not isinstance(line_rows, list) or len(line_rows) < 2:
                    raise ValidationError("lines must contain at least two rows.")
                lines: list[JournalLineCreate] = []
                for line_row in line_rows:
                    account_code = str(line_row.get("account_code") or "").strip()
                    if not account_code:
                        raise ValidationError("account_code is required on all lines.")
                    await self._assert_account_code_scope(tenant_id=tenant_id, account_code=account_code)
                    lines.append(
                        JournalLineCreate(
                            account_code=account_code,
                            debit=_to_decimal(line_row.get("debit", 0), field="debit"),
                            credit=_to_decimal(line_row.get("credit", 0), field="credit"),
                            memo=line_row.get("memo"),
                        )
                    )
                payload = JournalCreate(
                    org_entity_id=connector_row.org_entity_id,
                    journal_date=_to_date(row_data.get("journal_date") or _utcnow().date().isoformat()),
                    reference=row_data.get("reference"),
                    narration=row_data.get("narration"),
                    lines=lines,
                )
                intent_payload = payload.model_dump(mode="json")
                intent_payload["source"] = "ERP"
                intent_payload["external_reference_id"] = external_reference_id
                journal_mutation = await submit_governed_journal_intent(
                    self._session,
                    intent_type=IntentType.CREATE_JOURNAL,
                    tenant_id=tenant_id,
                    user_id=actor.id,
                    actor_role=getattr(actor.role, "value", str(getattr(actor, "role", ""))),
                    source_channel=IntentSourceChannel.IMPORT.value,
                    namespace=f"erp_import_journal:{connector_row.id}:{external_reference_id}",
                    payload=intent_payload,
                )
                created_journal_id = journal_mutation.require_journal_id()
                self._session.add(
                    ErpJournalMapping(
                        tenant_id=tenant_id,
                        erp_connector_id=connector_row.id,
                        internal_journal_id=created_journal_id,
                        erp_journal_id=external_reference_id,
                    )
                )
                imported_count += 1
                existing_external_ids.add(external_reference_id)
                failed_records.append(
                    {
                        "external_reference_id": external_reference_id,
                        "journal_id": str(created_journal_id),
                        "intent_id": str(journal_mutation.intent_id),
                        "job_id": str(journal_mutation.job_id) if journal_mutation.job_id else None,
                        "record_refs": journal_mutation.record_refs,
                        "result": "IMPORTED",
                    }
                )
            except Exception as exc:  # noqa: BLE001
                failed_records.append(
                    {
                        "external_reference_id": external_reference_id,
                        "reason": str(exc),
                    }
                )

        await self._session.flush()
        return {
            "imported_count": imported_count,
            "skipped_duplicates": skipped_duplicates,
            "failed_count": len(
                [row for row in failed_records if row.get("result") != "IMPORTED"]
            ),
            "imported_journals": [row for row in failed_records if row.get("result") == "IMPORTED"],
            "failed_records": [row for row in failed_records if row.get("result") != "IMPORTED"],
        }

    async def export_journals(
        self,
        *,
        tenant_id: uuid.UUID,
        actor: IamUser,
        body: JournalExportRequest,
    ) -> dict[str, Any]:
        connector_row = await self._get_connector(
            tenant_id=tenant_id,
            connector_id=body.erp_connector_id,
        )
        connector = get_connector(connector_row.erp_type)
        runtime_config = self._runtime_connection_config(connector_row.connection_config)

        stmt = (
            select(AccountingJVAggregate)
            .options(selectinload(AccountingJVAggregate.lines))
            .where(
                AccountingJVAggregate.tenant_id == tenant_id,
                AccountingJVAggregate.entity_id == connector_row.org_entity_id,
                AccountingJVAggregate.status == JVStatus.PUSHED,
            )
            .order_by(AccountingJVAggregate.created_at.asc())
        )
        if body.journal_ids:
            stmt = stmt.where(AccountingJVAggregate.id.in_(body.journal_ids))

        journals = (await self._session.execute(stmt)).scalars().all()
        existing_internal_ids = set(
            (
                await self._session.execute(
                    select(ErpJournalMapping.internal_journal_id).where(
                        ErpJournalMapping.tenant_id == tenant_id,
                        ErpJournalMapping.erp_connector_id == connector_row.id,
                    )
                )
            ).scalars().all()
        )

        exported_count = 0
        skipped_duplicates = 0
        failed_records: list[dict[str, Any]] = []
        for journal in journals:
            if journal.id in existing_internal_ids:
                skipped_duplicates += 1
                continue
            lines = sorted(
                [line for line in journal.lines if line.jv_version == journal.version],
                key=lambda item: item.line_number,
            )
            journal_payload = {
                "internal_journal_id": str(journal.id),
                "journal_number": journal.jv_number,
                "journal_date": journal.period_date.isoformat(),
                "reference": journal.reference,
                "narration": journal.description,
                "external_reference_id": journal.external_reference_id or journal.jv_number,
                "lines": [
                    {
                        "account_code": line.account_code,
                        "account_name": line.account_name,
                        "entry_type": line.entry_type,
                        "amount": str(line.amount),
                        "currency": line.currency,
                    }
                    for line in lines
                ],
            }
            try:
                push_result = await connector.push_journal(
                    connection_config=runtime_config,
                    journal_payload=journal_payload,
                )
                erp_journal_id = str(
                    push_result.get("erp_journal_id")
                    or push_result.get("id")
                    or journal_payload["external_reference_id"]
                )
                self._session.add(
                    ErpJournalMapping(
                        tenant_id=tenant_id,
                        erp_connector_id=connector_row.id,
                        internal_journal_id=journal.id,
                        erp_journal_id=erp_journal_id,
                    )
                )
                exported_count += 1
                existing_internal_ids.add(journal.id)
            except Exception as exc:  # noqa: BLE001
                failed_records.append(
                    {
                        "journal_id": str(journal.id),
                        "reason": str(exc),
                    }
                )

        await self._session.flush()
        return {
            "exported_count": exported_count,
            "skipped_duplicates": skipped_duplicates,
            "failed_count": len(failed_records),
            "failed_records": failed_records,
        }

    async def sync_master_data(
        self,
        *,
        tenant_id: uuid.UUID,
        actor: IamUser,
        body: MasterSyncRequest,
    ) -> dict[str, Any]:
        connector_row = await self._get_connector(
            tenant_id=tenant_id,
            connector_id=body.erp_connector_id,
        )
        connector = get_connector(connector_row.erp_type)
        runtime_config = self._runtime_connection_config(connector_row.connection_config)

        if body.rows is not None:
            rows = body.rows
        elif body.entity_type == ErpMasterEntityType.VENDOR:
            rows = await connector.fetch_vendors(connection_config=runtime_config)
        else:
            rows = await connector.fetch_customers(connection_config=runtime_config)

        inserted_count = 0
        updated_count = 0
        failed_records: list[dict[str, Any]] = []

        for row in rows:
            erp_id = str(row.get("erp_id") or row.get("id") or row.get("code") or "").strip()
            if not erp_id:
                failed_records.append({"row": row, "reason": "missing erp id"})
                continue

            name = str(
                row.get("name")
                or row.get("vendor_name")
                or row.get("customer_name")
                or erp_id
            ).strip()
            try:
                if body.entity_type == ErpMasterEntityType.VENDOR:
                    vendor = await self._upsert_vendor(
                        tenant_id=tenant_id,
                        entity_id=connector_row.org_entity_id,
                        actor_id=actor.id,
                        connector_type=connector_row.erp_type,
                        erp_id=erp_id,
                        payload=row,
                        default_name=name,
                    )
                    internal_id = str(vendor.id)
                else:
                    internal_id = str(row.get("internal_id") or erp_id)

                existing = (
                    await self._session.execute(
                        select(ErpMasterMapping).where(
                            ErpMasterMapping.tenant_id == tenant_id,
                            ErpMasterMapping.erp_connector_id == connector_row.id,
                            ErpMasterMapping.entity_type == body.entity_type,
                            ErpMasterMapping.erp_id == erp_id,
                        )
                    )
                ).scalar_one_or_none()
                if existing is None:
                    self._session.add(
                        ErpMasterMapping(
                            tenant_id=tenant_id,
                            org_entity_id=connector_row.org_entity_id,
                            erp_connector_id=connector_row.id,
                            entity_type=body.entity_type,
                            erp_id=erp_id,
                            internal_id=internal_id,
                        )
                    )
                    inserted_count += 1
                else:
                    existing.internal_id = internal_id
                    existing.updated_at = _utcnow()
                    updated_count += 1
            except Exception as exc:  # noqa: BLE001
                failed_records.append({"erp_id": erp_id, "reason": str(exc)})

        await self._session.flush()
        return {
            "entity_type": body.entity_type.value,
            "inserted_count": inserted_count,
            "updated_count": updated_count,
            "failed_count": len(failed_records),
            "failed_records": failed_records,
        }

    async def _import_coa(
        self,
        *,
        tenant_id: uuid.UUID,
        connector_row: ErpConnector,
        connector: Any,
        runtime_config: Mapping[str, Any],
    ) -> dict[str, Any]:
        rows = await connector.fetch_chart_of_accounts(connection_config=runtime_config)
        tenant_accounts = (
            await self._session.execute(
                select(TenantCoaAccount).where(
                    TenantCoaAccount.tenant_id == tenant_id,
                    TenantCoaAccount.is_active.is_(True),
                )
            )
        ).scalars().all()
        by_code = {account.account_code.strip().upper(): account for account in tenant_accounts}

        new_accounts: list[dict[str, Any]] = []
        updated_accounts: list[dict[str, Any]] = []
        conflicts: list[dict[str, Any]] = []
        mapped_count = 0

        for row in rows:
            erp_account_id = str(row.get("id") or row.get("code") or "").strip()
            if not erp_account_id:
                conflicts.append({"row": row, "reason": "missing erp account id"})
                continue
            account_code = str(row.get("code") or erp_account_id).strip().upper()
            account_name = str(row.get("name") or row.get("account_name") or account_code).strip()
            internal = by_code.get(account_code)
            if internal is None:
                new_accounts.append(
                    {
                        "erp_account_id": erp_account_id,
                        "account_code": account_code,
                        "account_name": account_name,
                    }
                )
                continue

            existing_mapping = (
                await self._session.execute(
                    select(ErpCoaMapping).where(
                        ErpCoaMapping.tenant_id == tenant_id,
                        ErpCoaMapping.erp_connector_id == connector_row.id,
                        ErpCoaMapping.erp_account_id == erp_account_id,
                    )
                )
            ).scalar_one_or_none()
            if existing_mapping is not None and existing_mapping.internal_account_id not in {None, internal.id}:
                conflicts.append(
                    {
                        "erp_account_id": erp_account_id,
                        "existing_internal_account_id": str(existing_mapping.internal_account_id),
                        "proposed_internal_account_id": str(internal.id),
                    }
                )
                continue

            stmt = insert(ErpCoaMapping).values(
                tenant_id=tenant_id,
                erp_connector_id=connector_row.id,
                erp_account_id=erp_account_id,
                internal_account_id=internal.id,
            )
            stmt = stmt.on_conflict_do_update(
                constraint="uq_erp_coa_mappings_connector_account",
                set_={
                    "internal_account_id": stmt.excluded.internal_account_id,
                    "updated_at": _utcnow(),
                },
            )
            await self._session.execute(stmt)
            mapped_count += 1

            if internal.display_name.strip() != account_name:
                updated_accounts.append(
                    {
                        "erp_account_id": erp_account_id,
                        "account_code": account_code,
                        "internal_account_id": str(internal.id),
                        "erp_account_name": account_name,
                        "internal_display_name": internal.display_name,
                    }
                )

        await self._session.flush()
        return {
            "mapped_count": mapped_count,
            "new_accounts": new_accounts,
            "updated_accounts": updated_accounts,
            "conflicts": conflicts,
            "new_count": len(new_accounts),
            "updated_count": len(updated_accounts),
            "conflict_count": len(conflicts),
        }

    async def _upsert_vendor(
        self,
        *,
        tenant_id: uuid.UUID,
        entity_id: uuid.UUID,
        actor_id: uuid.UUID,
        connector_type: str,
        erp_id: str,
        payload: Mapping[str, Any],
        default_name: str,
    ) -> AccountingVendor:
        existing = (
            await self._session.execute(
                select(AccountingVendor).where(
                    AccountingVendor.tenant_id == tenant_id,
                    AccountingVendor.entity_id == entity_id,
                    AccountingVendor.erp_vendor_id == erp_id,
                )
            )
        ).scalar_one_or_none()

        vendor_code = str(payload.get("vendor_code") or payload.get("code") or erp_id).strip()
        vendor_name = str(payload.get("vendor_name") or payload.get("name") or default_name).strip()
        email = payload.get("email")
        phone = payload.get("phone")

        if existing is not None:
            existing.vendor_code = vendor_code
            existing.vendor_name = vendor_name
            existing.email = str(email) if email is not None else existing.email
            existing.phone = str(phone) if phone is not None else existing.phone
            existing.erp_connector_type = connector_type
            existing.updated_at = _utcnow()
            await self._session.flush()
            return existing

        created = await AuditWriter.insert_financial_record(
            self._session,
            model_class=AccountingVendor,
            tenant_id=tenant_id,
            record_data={
                "entity_id": str(entity_id),
                "vendor_code": vendor_code,
                "erp_vendor_id": erp_id,
            },
            values={
                "entity_id": entity_id,
                "vendor_name": vendor_name,
                "vendor_code": vendor_code,
                "email": str(email) if email is not None else None,
                "phone": str(phone) if phone is not None else None,
                "is_active": True,
                "erp_vendor_id": erp_id,
                "erp_connector_type": connector_type,
                "created_by": actor_id,
                "updated_at": _utcnow(),
            },
        )
        return created

    async def _get_connector(
        self,
        *,
        tenant_id: uuid.UUID,
        connector_id: uuid.UUID,
    ) -> ErpConnector:
        row = (
            await self._session.execute(
                select(ErpConnector).where(
                    ErpConnector.id == connector_id,
                    ErpConnector.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        if row is None:
            raise NotFoundError("ERP connector not found.")
        return row

    async def _assert_entity_scope(self, *, tenant_id: uuid.UUID, org_entity_id: uuid.UUID) -> None:
        entity = (
            await self._session.execute(
                select(CpEntity.id).where(
                    CpEntity.id == org_entity_id,
                    CpEntity.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        if entity is None:
            raise ValidationError("org_entity_id does not belong to tenant.")

    async def _assert_account_scope(
        self,
        *,
        tenant_id: uuid.UUID,
        internal_account_id: uuid.UUID,
    ) -> None:
        account = (
            await self._session.execute(
                select(TenantCoaAccount.id).where(
                    TenantCoaAccount.id == internal_account_id,
                    TenantCoaAccount.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        if account is None:
            raise ValidationError("internal_account_id does not belong to tenant.")

    async def _assert_account_code_scope(
        self,
        *,
        tenant_id: uuid.UUID,
        account_code: str,
    ) -> None:
        account = (
            await self._session.execute(
                select(TenantCoaAccount.id).where(
                    TenantCoaAccount.tenant_id == tenant_id,
                    TenantCoaAccount.account_code == account_code,
                    TenantCoaAccount.is_active.is_(True),
                )
            )
        ).scalar_one_or_none()
        if account is None:
            raise ValidationError(f"account_code '{account_code}' does not exist or is inactive.")

    @staticmethod
    def _encrypt_connection_config(connection_config: Mapping[str, Any]) -> dict[str, Any]:
        payload = dict(connection_config)
        credentials = payload.pop("credentials", None)
        if isinstance(credentials, Mapping):
            encrypted_credentials: dict[str, str] = {}
            for key, value in credentials.items():
                if value is None:
                    continue
                encrypted_credentials[str(key)] = encrypt_field(str(value))
            payload["credentials_encrypted"] = encrypted_credentials
        return payload

    @staticmethod
    def _runtime_connection_config(connection_config: Mapping[str, Any]) -> dict[str, Any]:
        payload = dict(connection_config)
        encrypted = payload.pop("credentials_encrypted", None)
        if isinstance(encrypted, Mapping):
            credentials: dict[str, str] = {}
            for key, value in encrypted.items():
                if value is None:
                    continue
                credentials[str(key)] = decrypt_field(str(value))
            payload["credentials"] = credentials
        return payload
