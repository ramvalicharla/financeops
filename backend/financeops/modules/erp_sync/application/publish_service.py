from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import NotFoundError, ValidationError
from financeops.db.models.erp_sync import (
    ExternalSyncDriftReport,
    ExternalSyncPublishEvent,
    ExternalSyncRun,
)
from financeops.modules.erp_sync.application.period_lock_service import PeriodLockService
from financeops.services.audit_writer import AuditWriter


DATASET_CONSUMPTION_MAP: dict[str, str] = {
    "trial_balance": "reconciliation_trial_balance",
    "general_ledger": "reconciliation_gl_entries",
    "bank_statement": "bank_reconciliation_statements",
    "bank_transaction_register": "bank_reconciliation_transactions",
    "invoice_register": "gst_invoice_register",
    "purchase_register": "gst_purchase_register",
    "tax_ledger": "gst_tax_ledger",
    "tds_register": "tds_reconciliation_register",
    "form_26as": "tds_reconciliation_register",
    "ais_register": "tds_reconciliation_register",
    "gst_return_gstr1": "gst_returns_ingested",
    "gst_return_gstr2b": "gst_returns_ingested",
    "gst_return_gstr3b": "gst_returns_ingested",
    "einvoice_register": "gst_einvoice_register",
    "balance_sheet": "working_capital_balance_sheet",
    "ar_ageing": "working_capital_ar_ageing",
    "ap_ageing": "working_capital_ap_ageing",
    "inventory_register": "working_capital_inventory",
    "fixed_asset_register": "fixed_assets_register",
    "prepaid_register": "prepaid_register",
    "sales_order_register": "revenue_sales_orders",
    "contract_register": "revenue_contracts",
    "profit_and_loss": "ratio_variance_profit_and_loss",
    "budget_data": "ratio_variance_budget",
    "cash_flow_statement": "risk_cash_flow",
    "intercompany_transactions": "multi_entity_intercompany",
    "currency_master": "fx_translation_currency_master",
    "payroll_summary": "payroll_gl_normalized",
}


class PublishService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        period_lock_service: PeriodLockService | None = None,
    ) -> None:
        self._session = session
        self._period_lock_service = period_lock_service or PeriodLockService(session)

    async def approve_publish_event(
        self,
        *,
        tenant_id: uuid.UUID,
        sync_run_id: uuid.UUID,
        idempotency_key: str,
        actor_user_id: uuid.UUID,
    ) -> dict[str, Any]:
        existing_for_run = (
            await self._session.execute(
                select(ExternalSyncPublishEvent)
                .where(
                    ExternalSyncPublishEvent.tenant_id == tenant_id,
                    ExternalSyncPublishEvent.sync_run_id == sync_run_id,
                    ExternalSyncPublishEvent.event_status == "approved",
                )
                .order_by(ExternalSyncPublishEvent.created_at.desc(), ExternalSyncPublishEvent.id.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if existing_for_run is not None:
            return {
                "publish_event_id": str(existing_for_run.id),
                "sync_run_id": str(sync_run_id),
                "status": "approved",
                "idempotent_replay": True,
            }

        existing_with_key = (
            await self._session.execute(
                select(ExternalSyncPublishEvent).where(
                    ExternalSyncPublishEvent.tenant_id == tenant_id,
                    ExternalSyncPublishEvent.sync_run_id == sync_run_id,
                    ExternalSyncPublishEvent.idempotency_key == idempotency_key,
                )
            )
        ).scalar_one_or_none()
        if existing_with_key is not None:
            return {
                "publish_event_id": str(existing_with_key.id),
                "sync_run_id": str(sync_run_id),
                "status": existing_with_key.event_status,
                "idempotent_replay": True,
            }

        run = (
            await self._session.execute(
                select(ExternalSyncRun).where(
                    ExternalSyncRun.tenant_id == tenant_id,
                    ExternalSyncRun.id == sync_run_id,
                )
            )
        ).scalar_one_or_none()
        if run is None:
            raise NotFoundError("Sync run not found")

        validation_summary = dict(run.validation_summary_json or {})
        if not bool(validation_summary.get("passed", False)):
            raise ValidationError("Publish blocked: validation summary not fully passed")
        category_rows = validation_summary.get("categories", [])
        if not isinstance(category_rows, list) or len(category_rows) < 20:
            raise ValidationError("Publish blocked: incomplete validation category coverage")
        failed_categories = [row.get("category") for row in category_rows if not bool(row.get("passed", False))]
        if failed_categories:
            raise ValidationError(f"Publish blocked: failed validation categories {failed_categories}")

        drift = (
            await self._session.execute(
                select(ExternalSyncDriftReport).where(
                    ExternalSyncDriftReport.tenant_id == tenant_id,
                    ExternalSyncDriftReport.sync_run_id == sync_run_id,
                )
            )
        ).scalar_one_or_none()
        if drift is not None and drift.drift_severity == "critical":
            raise ValidationError("Publish blocked: critical drift report is unacknowledged")

        has_critical_backdated = await self._period_lock_service.has_unacknowledged_critical_alerts(
            tenant_id=tenant_id,
            sync_run_id=sync_run_id,
        )
        if has_critical_backdated:
            raise ValidationError("Publish blocked: critical backdated modification alert is unacknowledged")

        target_table = DATASET_CONSUMPTION_MAP.get(run.dataset_type, "mis_manager_ingest")
        row = await AuditWriter.insert_financial_record(
            self._session,
            model_class=ExternalSyncPublishEvent,
            tenant_id=tenant_id,
            record_data={
                "sync_run_id": str(sync_run_id),
                "idempotency_key": idempotency_key,
                "event_status": "approved",
                "target_table": target_table,
            },
            values={
                "sync_run_id": sync_run_id,
                "idempotency_key": idempotency_key,
                "event_status": "approved",
                "approved_by": actor_user_id,
                "approved_at": datetime.now(UTC),
                "rejection_reason": None,
                "created_by": actor_user_id,
            },
        )

        await self._period_lock_service.auto_lock_on_publish(
            tenant_id=tenant_id,
            sync_run_id=sync_run_id,
            created_by=actor_user_id,
        )
        await self._period_lock_service.detect_backdated_modifications(
            tenant_id=tenant_id,
            sync_run_id=sync_run_id,
            created_by=actor_user_id,
        )

        return {
            "publish_event_id": str(row.id),
            "sync_run_id": str(sync_run_id),
            "status": row.event_status,
            "target_table": target_table,
            "idempotent_replay": False,
        }

    async def reject_publish_event(
        self,
        *,
        tenant_id: uuid.UUID,
        sync_run_id: uuid.UUID,
        idempotency_key: str,
        actor_user_id: uuid.UUID,
        reason: str,
    ) -> dict[str, Any]:
        row = await AuditWriter.insert_financial_record(
            self._session,
            model_class=ExternalSyncPublishEvent,
            tenant_id=tenant_id,
            record_data={
                "sync_run_id": str(sync_run_id),
                "idempotency_key": idempotency_key,
                "event_status": "rejected",
            },
            values={
                "sync_run_id": sync_run_id,
                "idempotency_key": idempotency_key,
                "event_status": "rejected",
                "approved_by": None,
                "approved_at": None,
                "rejection_reason": reason,
                "created_by": actor_user_id,
            },
        )
        return {"publish_event_id": str(row.id), "status": row.event_status}

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        action = str(kwargs.get("action", "")).strip().lower()
        if action == "approve":
            return await self.approve_publish_event(
                tenant_id=kwargs["tenant_id"],
                sync_run_id=kwargs["sync_run_id"],
                idempotency_key=str(kwargs["idempotency_key"]),
                actor_user_id=kwargs["actor_user_id"],
            )
        if action == "reject":
            return await self.reject_publish_event(
                tenant_id=kwargs["tenant_id"],
                sync_run_id=kwargs["sync_run_id"],
                idempotency_key=str(kwargs["idempotency_key"]),
                actor_user_id=kwargs["actor_user_id"],
                reason=str(kwargs.get("reason", "rejected")),
            )
        raise ValidationError("Unsupported publish service action")
