from __future__ import annotations

import uuid
from collections.abc import Iterable
from datetime import date
from time import perf_counter
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.anomaly_pattern_engine import AnomalyRun
from financeops.db.models.board_pack_narrative_engine import BoardPackRun
from financeops.db.models.cash_flow_engine import CashFlowRun
from financeops.db.models.equity_engine import EquityRun
from financeops.db.models.financial_risk_engine import RiskRun
from financeops.db.models.fx_translation_reporting import FxTranslationRun
from financeops.db.models.multi_entity_consolidation import MultiEntityConsolidationRun
from financeops.db.models.observability_engine import (
    GovernanceEvent,
    LineageGraphSnapshot,
    ObservabilityEvidenceLink,
    ObservabilityResult,
    ObservabilityRun,
    ObservabilityRunRegistry,
    RunPerformanceMetric,
    RunTokenDiffResult,
)
from financeops.db.models.ownership_consolidation import OwnershipConsolidationRun
from financeops.db.models.payroll_gl_normalization import NormalizationRun
from financeops.db.models.payroll_gl_reconciliation import PayrollGlReconciliationRun
from financeops.db.models.ratio_variance_engine import MetricRun
from financeops.db.models.reconciliation_bridge import ReconciliationSession
from financeops.services.audit_writer import AuditEvent, AuditWriter


class ObservabilityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_registry(self, *, tenant_id: uuid.UUID) -> list[ObservabilityRunRegistry]:
        rows = await self._session.execute(
            select(ObservabilityRunRegistry)
            .where(ObservabilityRunRegistry.tenant_id == tenant_id)
            .order_by(
                ObservabilityRunRegistry.created_at.desc(),
                ObservabilityRunRegistry.module_code.asc(),
                ObservabilityRunRegistry.run_id.asc(),
            )
        )
        return list(rows.scalars().all())

    async def get_registry(self, *, tenant_id: uuid.UUID, registry_id: uuid.UUID) -> ObservabilityRunRegistry | None:
        row = await self._session.execute(
            select(ObservabilityRunRegistry).where(
                ObservabilityRunRegistry.tenant_id == tenant_id,
                ObservabilityRunRegistry.id == registry_id,
            )
        )
        return row.scalar_one_or_none()

    async def get_latest_registry_by_run_id(
        self, *, tenant_id: uuid.UUID, run_id: uuid.UUID
    ) -> ObservabilityRunRegistry | None:
        row = await self._session.execute(
            select(ObservabilityRunRegistry)
            .where(
                ObservabilityRunRegistry.tenant_id == tenant_id,
                ObservabilityRunRegistry.run_id == run_id,
            )
            .order_by(ObservabilityRunRegistry.created_at.desc(), ObservabilityRunRegistry.id.desc())
            .limit(1)
        )
        return row.scalar_one_or_none()

    async def get_registry_by_run(
        self,
        *,
        tenant_id: uuid.UUID,
        module_code: str,
        run_id: uuid.UUID,
        run_token: str,
    ) -> ObservabilityRunRegistry | None:
        row = await self._session.execute(
            select(ObservabilityRunRegistry).where(
                ObservabilityRunRegistry.tenant_id == tenant_id,
                ObservabilityRunRegistry.module_code == module_code,
                ObservabilityRunRegistry.run_id == run_id,
                ObservabilityRunRegistry.run_token == run_token,
            )
        )
        return row.scalar_one_or_none()

    async def create_registry_entry(self, **values: Any) -> ObservabilityRunRegistry:
        return await AuditWriter.insert_financial_record(
            self._session,
            model_class=ObservabilityRunRegistry,
            tenant_id=values["tenant_id"],
            record_data={
                "module_code": values["module_code"],
                "run_id": str(values["run_id"]),
                "run_token": values["run_token"],
            },
            values=values,
            audit=AuditEvent(
                tenant_id=values["tenant_id"],
                user_id=values["created_by"],
                action="observability.registry.synced",
                resource_type="observability_run_registry",
                resource_name=f"{values['module_code']}:{values['run_id']}",
            ),
        )

    async def create_observability_run(self, **values: Any) -> ObservabilityRun:
        return await AuditWriter.insert_financial_record(
            self._session,
            model_class=ObservabilityRun,
            tenant_id=values["tenant_id"],
            record_data={"operation_type": values["operation_type"], "operation_token": values["operation_token"]},
            values=values,
            audit=AuditEvent(
                tenant_id=values["tenant_id"],
                user_id=values["created_by"],
                action="observability.run.created",
                resource_type="observability_run",
                resource_name=values["operation_type"],
            ),
        )

    async def get_observability_run_by_token(self, *, tenant_id: uuid.UUID, operation_token: str) -> ObservabilityRun | None:
        row = await self._session.execute(
            select(ObservabilityRun).where(
                ObservabilityRun.tenant_id == tenant_id,
                ObservabilityRun.operation_token == operation_token,
            )
        )
        return row.scalar_one_or_none()

    async def create_observability_result(self, **values: Any) -> ObservabilityResult:
        return await AuditWriter.insert_financial_record(
            self._session,
            model_class=ObservabilityResult,
            tenant_id=values["tenant_id"],
            record_data={"observability_run_id": str(values["observability_run_id"])},
            values=values,
            audit=AuditEvent(
                tenant_id=values["tenant_id"],
                user_id=values["created_by"],
                action="observability.result.created",
                resource_type="observability_result",
                resource_name=str(values["observability_run_id"]),
            ),
        )

    async def create_observability_evidence_links(
        self,
        *,
        tenant_id: uuid.UUID,
        observability_run_id: uuid.UUID,
        rows: Iterable[dict[str, Any]],
        created_by: uuid.UUID,
    ) -> list[ObservabilityEvidenceLink]:
        created: list[ObservabilityEvidenceLink] = []
        for payload in rows:
            row = await AuditWriter.insert_financial_record(
                self._session,
                model_class=ObservabilityEvidenceLink,
                tenant_id=tenant_id,
                record_data={
                    "observability_run_id": str(observability_run_id),
                    "evidence_type": payload["evidence_type"],
                    "evidence_ref": payload["evidence_ref"],
                },
                values={
                    "observability_run_id": observability_run_id,
                    "created_by": created_by,
                    **payload,
                },
                audit=AuditEvent(
                    tenant_id=tenant_id,
                    user_id=created_by,
                    action="observability.evidence.created",
                    resource_type="observability_evidence_link",
                    resource_name=payload["evidence_type"],
                ),
            )
            created.append(row)
        return created

    async def create_diff_result(self, **values: Any) -> RunTokenDiffResult:
        return await AuditWriter.insert_financial_record(
            self._session,
            model_class=RunTokenDiffResult,
            tenant_id=values["tenant_id"],
            record_data={
                "base_run_id": str(values["base_run_id"]),
                "compare_run_id": str(values["compare_run_id"]),
            },
            values=values,
            audit=AuditEvent(
                tenant_id=values["tenant_id"],
                user_id=values["created_by"],
                action="observability.diff.created",
                resource_type="run_token_diff_result",
                resource_name=f"{values['base_run_id']}->{values['compare_run_id']}",
            ),
        )

    async def get_diff_result(self, *, tenant_id: uuid.UUID, diff_id: uuid.UUID) -> RunTokenDiffResult | None:
        row = await self._session.execute(
            select(RunTokenDiffResult).where(
                RunTokenDiffResult.tenant_id == tenant_id,
                RunTokenDiffResult.id == diff_id,
            )
        )
        return row.scalar_one_or_none()

    async def create_graph_snapshot(self, **values: Any) -> LineageGraphSnapshot:
        return await AuditWriter.insert_financial_record(
            self._session,
            model_class=LineageGraphSnapshot,
            tenant_id=values["tenant_id"],
            record_data={
                "root_run_id": str(values["root_run_id"]),
                "deterministic_hash": values["deterministic_hash"],
            },
            values=values,
            audit=AuditEvent(
                tenant_id=values["tenant_id"],
                user_id=values["created_by"],
                action="observability.graph.created",
                resource_type="lineage_graph_snapshot",
                resource_name=str(values["root_run_id"]),
            ),
        )

    async def get_latest_graph_snapshot(
        self, *, tenant_id: uuid.UUID, root_run_id: uuid.UUID
    ) -> LineageGraphSnapshot | None:
        row = await self._session.execute(
            select(LineageGraphSnapshot)
            .where(
                LineageGraphSnapshot.tenant_id == tenant_id,
                LineageGraphSnapshot.root_run_id == root_run_id,
            )
            .order_by(LineageGraphSnapshot.created_at.desc(), LineageGraphSnapshot.id.desc())
            .limit(1)
        )
        return row.scalar_one_or_none()

    async def create_governance_event(self, **values: Any) -> GovernanceEvent:
        return await AuditWriter.insert_financial_record(
            self._session,
            model_class=GovernanceEvent,
            tenant_id=values["tenant_id"],
            record_data={
                "module_code": values["module_code"],
                "run_id": str(values["run_id"]),
                "event_type": values["event_type"],
            },
            values=values,
            audit=AuditEvent(
                tenant_id=values["tenant_id"],
                user_id=values["created_by"],
                action="observability.governance_event.created",
                resource_type="governance_event",
                resource_name=values["event_type"],
            ),
        )

    async def list_governance_events(self, *, tenant_id: uuid.UUID, run_id: uuid.UUID) -> list[GovernanceEvent]:
        rows = await self._session.execute(
            select(GovernanceEvent)
            .where(
                GovernanceEvent.tenant_id == tenant_id,
                GovernanceEvent.run_id == run_id,
            )
            .order_by(GovernanceEvent.created_at.asc(), GovernanceEvent.id.asc())
        )
        return list(rows.scalars().all())

    async def create_performance_metric(self, **values: Any) -> RunPerformanceMetric:
        return await AuditWriter.insert_financial_record(
            self._session,
            model_class=RunPerformanceMetric,
            tenant_id=values["tenant_id"],
            record_data={
                "module_code": values["module_code"],
                "run_id": str(values["run_id"]),
            },
            values=values,
            audit=AuditEvent(
                tenant_id=values["tenant_id"],
                user_id=values["created_by"],
                action="observability.performance_metric.created",
                resource_type="run_performance_metric",
                resource_name=str(values["run_id"]),
            ),
        )

    async def latest_performance_metric(self, *, tenant_id: uuid.UUID, run_id: uuid.UUID) -> RunPerformanceMetric | None:
        row = await self._session.execute(
            select(RunPerformanceMetric)
            .where(
                RunPerformanceMetric.tenant_id == tenant_id,
                RunPerformanceMetric.run_id == run_id,
            )
            .order_by(RunPerformanceMetric.created_at.desc(), RunPerformanceMetric.id.desc())
            .limit(1)
        )
        return row.scalar_one_or_none()

    async def get_observability_result(self, *, tenant_id: uuid.UUID, result_id: uuid.UUID) -> ObservabilityResult | None:
        row = await self._session.execute(
            select(ObservabilityResult).where(
                ObservabilityResult.tenant_id == tenant_id,
                ObservabilityResult.id == result_id,
            )
        )
        return row.scalar_one_or_none()

    async def get_observability_result_for_run(
        self, *, tenant_id: uuid.UUID, observability_run_id: uuid.UUID
    ) -> ObservabilityResult | None:
        row = await self._session.execute(
            select(ObservabilityResult)
            .where(
                ObservabilityResult.tenant_id == tenant_id,
                ObservabilityResult.observability_run_id == observability_run_id,
            )
            .order_by(ObservabilityResult.created_at.desc(), ObservabilityResult.id.desc())
            .limit(1)
        )
        return row.scalar_one_or_none()

    async def resolve_run_snapshot(self, *, tenant_id: uuid.UUID, run_id: uuid.UUID) -> dict[str, Any] | None:
        start = perf_counter()
        for module_code, model_cls, token_field, status_field in RUN_MODEL_CONFIGS:
            row = (
                await self._session.execute(
                    select(model_cls).where(
                        model_cls.tenant_id == tenant_id,
                        model_cls.id == run_id,
                    )
                )
            ).scalar_one_or_none()
            if row is None:
                continue
            version_tokens = {
                column.name: getattr(row, column.name)
                for column in row.__table__.columns
                if column.name.endswith("_version_token") or column.name == "version_token"
            }
            dependencies = _extract_dependencies(module_code=module_code, row=row)
            elapsed_ms = int((perf_counter() - start) * 1000)
            return {
                "module_code": module_code,
                "run_id": row.id,
                "run_token": getattr(row, token_field),
                "status": str(getattr(row, status_field)),
                "version_tokens": version_tokens,
                "dependencies": dependencies,
                "row": row,
                "execution_time_ms": max(elapsed_ms, 0),
            }
        return None


RUN_MODEL_CONFIGS: tuple[tuple[str, Any, str, str], ...] = (
    ("payroll_gl_normalization", NormalizationRun, "run_token", "run_status"),
    ("reconciliation_bridge", ReconciliationSession, "session_token", "status"),
    ("payroll_gl_reconciliation", PayrollGlReconciliationRun, "run_token", "status"),
    ("ratio_variance_engine", MetricRun, "run_token", "status"),
    ("multi_entity_consolidation", MultiEntityConsolidationRun, "run_token", "run_status"),
    ("fx_translation_reporting", FxTranslationRun, "run_token", "run_status"),
    ("ownership_consolidation", OwnershipConsolidationRun, "run_token", "run_status"),
    ("cash_flow_engine", CashFlowRun, "run_token", "run_status"),
    ("equity_engine", EquityRun, "run_token", "run_status"),
    ("financial_risk_engine", RiskRun, "run_token", "status"),
    ("anomaly_pattern_engine", AnomalyRun, "run_token", "status"),
    ("board_pack_narrative_engine", BoardPackRun, "run_token", "status"),
)


def _extract_dependencies(*, module_code: str, row: Any) -> list[dict[str, Any]]:
    deps: list[dict[str, Any]] = []

    def add_ref(ref: Any, kind: str = "run_ref") -> None:
        if ref is None:
            return
        ref_value = str(ref)
        if not ref_value:
            return
        deps.append({"kind": kind, "run_id": ref_value})

    if module_code == "equity_engine":
        add_ref(getattr(row, "consolidation_run_ref_nullable", None))
        add_ref(getattr(row, "fx_translation_run_ref_nullable", None))
        add_ref(getattr(row, "ownership_consolidation_run_ref_nullable", None))
    elif module_code == "cash_flow_engine":
        add_ref(getattr(row, "source_consolidation_run_ref", None))
        add_ref(getattr(row, "source_fx_translation_run_ref_nullable", None))
        add_ref(getattr(row, "source_ownership_consolidation_run_ref_nullable", None))
    elif module_code == "ownership_consolidation":
        add_ref(getattr(row, "fx_translation_run_ref_nullable", None))
        for payload in sorted(getattr(row, "source_consolidation_run_refs_json", []) or [], key=lambda item: str(item)):
            add_ref(payload.get("run_id"), kind=str(payload.get("source_type", "run_ref")))
    elif module_code == "fx_translation_reporting":
        for payload in sorted(getattr(row, "source_consolidation_run_refs_json", []) or [], key=lambda item: str(item)):
            add_ref(payload.get("run_id"), kind=str(payload.get("source_type", "run_ref")))
    elif module_code == "multi_entity_consolidation":
        for payload in sorted(getattr(row, "source_run_refs_json", []) or [], key=lambda item: str(item)):
            add_ref(payload.get("run_id"), kind=str(payload.get("source_type", "run_ref")))
    elif module_code == "ratio_variance_engine":
        add_ref(getattr(row, "payroll_run_id", None), kind="normalization_run")
        add_ref(getattr(row, "gl_run_id", None), kind="normalization_run")
        add_ref(getattr(row, "payroll_gl_reconciliation_run_id", None), kind="payroll_gl_reconciliation_run")
        add_ref(getattr(row, "reconciliation_session_id", None), kind="reconciliation_session")
        add_ref(getattr(row, "mis_snapshot_id", None), kind="mis_snapshot")
    elif module_code == "financial_risk_engine":
        for field in (
            "source_metric_run_ids_json",
            "source_variance_run_ids_json",
            "source_trend_run_ids_json",
            "source_reconciliation_session_ids_json",
        ):
            values = list(getattr(row, field, []) or [])
            for value in sorted(str(item) for item in values):
                add_ref(value, kind=field)
    elif module_code == "anomaly_pattern_engine":
        for field in (
            "source_metric_run_ids_json",
            "source_variance_run_ids_json",
            "source_trend_run_ids_json",
            "source_risk_run_ids_json",
            "source_reconciliation_session_ids_json",
        ):
            values = list(getattr(row, field, []) or [])
            for value in sorted(str(item) for item in values):
                add_ref(value, kind=field)
    elif module_code == "board_pack_narrative_engine":
        for field in (
            "source_metric_run_ids_json",
            "source_risk_run_ids_json",
            "source_anomaly_run_ids_json",
        ):
            values = list(getattr(row, field, []) or [])
            for value in sorted(str(item) for item in values):
                add_ref(value, kind=field)
    elif module_code == "payroll_gl_reconciliation":
        add_ref(getattr(row, "payroll_run_id", None), kind="normalization_run")
        add_ref(getattr(row, "gl_run_id", None), kind="normalization_run")
        add_ref(getattr(row, "reconciliation_session_id", None), kind="reconciliation_session")

    deps.sort(key=lambda item: (item.get("kind", ""), item.get("run_id", "")))
    return deps
