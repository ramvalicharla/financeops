from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import sentry_sdk
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.config import settings
from financeops.db.models.custom_report_builder import ReportDefinition, ReportRun
from financeops.modules.custom_report_builder.application.export_service import (
    ReportExportService,
)
from financeops.modules.custom_report_builder.domain.enums import (
    FilterOperator,
    ReportExportFormat,
    ReportRunStatus,
    SortDirection,
)
from financeops.modules.custom_report_builder.domain.filter_dsl import (
    FilterConfig,
    ReportDefinitionSchema,
)
from financeops.modules.custom_report_builder.domain.metric_registry import get_metric
from financeops.modules.custom_report_builder.infrastructure.repository import (
    ReportRepository,
)

_SAFE_IDENT = re.compile(r"^[a-z_][a-z0-9_]*$")


class InvalidReportRunStateError(Exception):
    pass


class ReportRunError(Exception):
    pass


class ReportRunService:
    _ALLOWED_TRANSITIONS: dict[ReportRunStatus, set[ReportRunStatus]] = {
        ReportRunStatus.PENDING: {ReportRunStatus.RUNNING},
        ReportRunStatus.RUNNING: {ReportRunStatus.COMPLETE, ReportRunStatus.FAILED},
    }

    def __init__(
        self,
        *,
        repository: ReportRepository | None = None,
        export_service: ReportExportService | None = None,
    ) -> None:
        self._repository = repository or ReportRepository()
        self._export_service = export_service or ReportExportService()

    async def run(
        self,
        db: AsyncSession,
        run_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> dict[str, Any]:
        run = await self._load_run(db=db, tenant_id=tenant_id, run_id=run_id)
        definition = await self._load_definition(
            db=db,
            tenant_id=tenant_id,
            definition_id=run.definition_id,
        )

        running_run = await self._transition_run_state(
            db=db,
            source_run=run,
            to_status=ReportRunStatus.RUNNING,
            started_at=datetime.now(UTC),
        )
        await db.commit()

        try:
            schema = self._build_definition_schema(definition)
            rows = await self._collect_rows(
                db=db,
                tenant_id=tenant_id,
                schema=schema,
            )
            rows = self._apply_group_by(rows=rows, group_by=schema.group_by)
            rows = self._apply_sort(rows=rows, schema=schema)
            result_hash = self._compute_result_hash(rows)

            export_paths = await self._export_rows(
                tenant_id=tenant_id,
                run_id=running_run.id,
                rows=rows,
                report_name=schema.name,
                export_formats=schema.export_formats,
            )

            await self._repository.save_result(
                db=db,
                tenant_id=tenant_id,
                run_id=running_run.id,
                result_data=rows,
                result_hash=result_hash,
                export_paths=export_paths,
            )

            completed_run = await self._transition_run_state(
                db=db,
                source_run=running_run,
                to_status=ReportRunStatus.COMPLETE,
                completed_at=datetime.now(UTC),
                row_count=len(rows),
                result_hash=result_hash,
            )
            await db.commit()
            return {
                "run_id": str(completed_run.id),
                "status": completed_run.status,
                "row_count": completed_run.row_count,
                "result_hash": result_hash,
            }
        except Exception as exc:
            await db.rollback()
            sentry_sdk.add_breadcrumb(
                category="custom_report_builder",
                message="report run failed",
                level="error",
                data={
                    "run_id": str(run_id),
                    "tenant_id": str(tenant_id),
                    "error": str(exc),
                },
            )
            try:
                # After rollback SQLAlchemy expires loaded instances; reload the
                # persisted RUNNING row so the append-only FAILED transition can
                # be derived without touching expired state.
                failed_source = await self._load_run(
                    db=db,
                    tenant_id=tenant_id,
                    run_id=running_run.id,
                )
                await self._transition_run_state(
                    db=db,
                    source_run=failed_source,
                    to_status=ReportRunStatus.FAILED,
                    completed_at=datetime.now(UTC),
                    error_message=str(exc)[:2000],
                )
                await db.commit()
            except Exception:
                await db.rollback()
            if isinstance(exc, (InvalidReportRunStateError, ReportRunError)):
                raise
            raise ReportRunError(str(exc)) from exc

    async def _load_run(
        self,
        *,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        run_id: uuid.UUID,
    ) -> ReportRun:
        row = await self._repository.get_run(db=db, tenant_id=tenant_id, run_id=run_id)
        if row is None:
            raise ReportRunError("Report run not found")
        return row

    async def _load_definition(
        self,
        *,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        definition_id: uuid.UUID,
    ) -> ReportDefinition:
        row = await self._repository.get_definition(
            db=db,
            tenant_id=tenant_id,
            definition_id=definition_id,
        )
        if row is None:
            raise ReportRunError("Report definition not found")
        if not row.is_active:
            raise ReportRunError("Report definition is inactive")
        return row

    def _build_definition_schema(self, definition: ReportDefinition) -> ReportDefinitionSchema:
        return ReportDefinitionSchema(
            name=definition.name,
            description=definition.description,
            metric_keys=list(definition.metric_keys or []),
            filter_config=FilterConfig.model_validate(definition.filter_config or {}),
            group_by=list(definition.group_by or []),
            sort_config=(definition.sort_config or None),
            export_formats=[ReportExportFormat(value) for value in (definition.export_formats or ["CSV"])],
            config=dict(definition.config or {}),
        )

    async def _collect_rows(
        self,
        *,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        schema: ReportDefinitionSchema,
    ) -> list[dict[str, Any]]:
        collected: list[dict[str, Any]] = []
        for metric_key in schema.metric_keys:
            metric = get_metric(metric_key)
            table_name = self._safe_ident(metric.source_table)
            source_column = self._safe_ident(metric.source_column)
            table_columns = await self._get_table_columns(db=db, table_name=table_name)
            if source_column not in table_columns:
                continue

            rows = await self._query_metric_rows(
                db=db,
                tenant_id=tenant_id,
                metric_key=metric_key,
                table_name=table_name,
                source_column=source_column,
                table_columns=table_columns,
                filters=schema.filter_config,
                group_by=schema.group_by,
            )
            for row in rows:
                value = row.get("metric_value")
                metric_value = self._normalize_metric_value(value=value, data_type=metric.data_type)
                result_row: dict[str, Any] = {
                    "metric_key": metric.key,
                    "metric_label": metric.label,
                    "engine": metric.engine,
                    "metric_value": metric_value,
                }
                for key in schema.group_by:
                    result_row[key] = self._canonicalize(row.get(key))
                if "reporting_period" in row:
                    result_row["reporting_period"] = self._canonicalize(row.get("reporting_period"))
                collected.append(result_row)

        if not collected:
            return []
        return [row for row in collected if self._passes_conditions(row, schema.filter_config)]

    async def _query_metric_rows(
        self,
        *,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        metric_key: str,
        table_name: str,
        source_column: str,
        table_columns: set[str],
        filters: FilterConfig,
        group_by: list[str],
    ) -> list[dict[str, Any]]:
        selected_cols = [f"{source_column} AS metric_value"]
        for field in group_by:
            if field in table_columns:
                selected_cols.append(field)
        if "reporting_period" in table_columns:
            selected_cols.append("reporting_period")

        sql_parts = [
            f"SELECT {', '.join(selected_cols)}",
            f"FROM {table_name}",
            "WHERE 1=1",
        ]
        params: dict[str, Any] = {}

        if "tenant_id" in table_columns:
            sql_parts.append("AND tenant_id = CAST(:tenant_id AS uuid)")
            params["tenant_id"] = str(tenant_id)

        period_col = self._pick_period_column(table_columns)
        if period_col and filters.period_start is not None:
            sql_parts.append(f"AND {period_col} >= :period_start")
            params["period_start"] = filters.period_start
        if period_col and filters.period_end is not None:
            sql_parts.append(f"AND {period_col} <= :period_end")
            params["period_end"] = filters.period_end

        entity_col = self._pick_entity_column(table_columns)
        if entity_col and filters.entity_ids:
            sql_parts.append(f"AND {entity_col} = ANY(CAST(:entity_ids AS uuid[]))")
            params["entity_ids"] = [str(v) for v in filters.entity_ids]

        metric_code_col = "metric_code" if "metric_code" in table_columns else None
        if metric_code_col:
            sql_parts.append("AND metric_code = :metric_code")
            params["metric_code"] = metric_key.split(".")[-1]

        sql_parts.append("ORDER BY 1")
        result = await db.execute(text("\n".join(sql_parts)), params)
        return [dict(row) for row in result.mappings().all()]

    def _apply_group_by(
        self,
        *,
        rows: list[dict[str, Any]],
        group_by: list[str],
    ) -> list[dict[str, Any]]:
        if not rows or not group_by:
            return rows

        grouped: dict[tuple[Any, ...], dict[str, Any]] = {}
        for row in rows:
            key = tuple(row.get(field) for field in group_by)
            bucket = grouped.get(key)
            if bucket is None:
                bucket = {field: row.get(field) for field in group_by}
                grouped[key] = bucket
            metric_key = str(row.get("metric_key"))
            current = bucket.get(metric_key)
            next_value = row.get("metric_value")
            if current is None:
                bucket[metric_key] = next_value
                continue
            try:
                total = Decimal(str(current)) + Decimal(str(next_value))
                bucket[metric_key] = str(total)
            except (InvalidOperation, TypeError):
                bucket[metric_key] = next_value

        result = list(grouped.values())
        result.sort(key=lambda item: tuple(str(item.get(field, "")) for field in group_by))
        return result

    def _apply_sort(
        self,
        *,
        rows: list[dict[str, Any]],
        schema: ReportDefinitionSchema,
    ) -> list[dict[str, Any]]:
        if not rows or schema.sort_config is None:
            return rows
        field = schema.sort_config.field
        reverse = schema.sort_config.direction == SortDirection.DESC
        return sorted(rows, key=lambda item: str(item.get(field, "")), reverse=reverse)

    def _compute_result_hash(self, rows: list[dict[str, Any]]) -> str:
        canonical = self._canonicalize(rows)
        payload = json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    async def _export_rows(
        self,
        *,
        tenant_id: uuid.UUID,
        run_id: uuid.UUID,
        rows: list[dict[str, Any]],
        report_name: str,
        export_formats: list[ReportExportFormat],
    ) -> dict[str, str]:
        paths: dict[str, str] = {}
        base_dir = Path(str(getattr(settings, "ARTIFACTS_BASE_DIR", "artifacts")))
        for export_format in export_formats:
            if export_format == ReportExportFormat.CSV:
                content, filename = self._export_service.export_csv(rows=rows, report_name=report_name)
            elif export_format == ReportExportFormat.EXCEL:
                content, filename = self._export_service.export_excel(rows=rows, report_name=report_name)
            elif export_format == ReportExportFormat.PDF:
                content, filename = self._export_service.export_pdf(
                    rows=rows,
                    report_name=report_name,
                    generated_at=datetime.now(UTC),
                )
            else:
                continue

            storage_path = f"artifacts/custom_reports/{tenant_id}/{run_id}/{filename}"
            absolute_path = base_dir / storage_path
            absolute_path.parent.mkdir(parents=True, exist_ok=True)
            absolute_path.write_bytes(content)
            paths[export_format.value] = storage_path
        return paths

    async def _transition_run_state(
        self,
        *,
        db: AsyncSession,
        source_run: ReportRun,
        to_status: ReportRunStatus,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
        error_message: str | None = None,
        row_count: int | None = None,
        result_hash: str | None = None,
    ) -> ReportRun:
        from_status = ReportRunStatus(str(source_run.status))
        allowed = self._ALLOWED_TRANSITIONS.get(from_status, set())
        if to_status not in allowed:
            raise InvalidReportRunStateError(
                f"Invalid run state transition: {from_status.value} -> {to_status.value}"
            )

        metadata = dict(source_run.run_metadata or {})
        origin_run_id = metadata.get("origin_run_id", str(source_run.id))
        metadata["origin_run_id"] = origin_run_id
        metadata["previous_run_id"] = str(source_run.id)
        metadata["state_transition"] = f"{from_status.value}->{to_status.value}"
        metadata["transitioned_at"] = datetime.now(UTC).isoformat()
        if result_hash:
            metadata["result_hash"] = result_hash

        next_row = ReportRun(
            tenant_id=source_run.tenant_id,
            definition_id=source_run.definition_id,
            status=to_status.value,
            triggered_by=source_run.triggered_by,
            started_at=started_at if to_status == ReportRunStatus.RUNNING else source_run.started_at,
            completed_at=completed_at if to_status in {ReportRunStatus.COMPLETE, ReportRunStatus.FAILED} else None,
            error_message=error_message if to_status == ReportRunStatus.FAILED else None,
            row_count=row_count if to_status == ReportRunStatus.COMPLETE else None,
            run_metadata=metadata,
            created_at=datetime.now(UTC),
        )
        db.add(next_row)
        await db.flush()
        return next_row

    async def _get_table_columns(self, *, db: AsyncSession, table_name: str) -> set[str]:
        result = await db.execute(
            text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = :table_name
                """
            ),
            {"table_name": table_name},
        )
        return {str(row[0]) for row in result.all()}

    def _safe_ident(self, value: str) -> str:
        if not _SAFE_IDENT.match(value):
            raise ReportRunError(f"Unsafe identifier: {value}")
        return value

    def _pick_period_column(self, columns: set[str]) -> str | None:
        candidates = [
            "reporting_period",
            "period_start",
            "period_end",
            "period_date",
            "as_of_date",
            "posting_date",
        ]
        return next((name for name in candidates if name in columns), None)

    def _pick_entity_column(self, columns: set[str]) -> str | None:
        candidates = ["entity_id", "reporting_entity_id", "company_id"]
        return next((name for name in candidates if name in columns), None)

    def _normalize_metric_value(self, *, value: Any, data_type: str) -> str | int | None:
        if value is None:
            return None
        if data_type == "integer":
            try:
                return int(value)
            except (ValueError, TypeError):
                return int(Decimal(str(value)))
        if data_type == "decimal":
            try:
                return str(Decimal(str(value)))
            except (InvalidOperation, TypeError):
                return str(value)
        return str(self._canonicalize(value))

    def _passes_conditions(self, row: dict[str, Any], filters: FilterConfig) -> bool:
        if not filters.conditions:
            return True
        for condition in filters.conditions:
            value = row.get(condition.field)
            operator = condition.operator
            target = condition.value
            if operator == FilterOperator.EQ and value != target:
                return False
            if operator == FilterOperator.NEQ and value == target:
                return False
            if operator == FilterOperator.IN:
                if not isinstance(target, list) or value not in target:
                    return False
            if operator == FilterOperator.BETWEEN:
                if not isinstance(target, list) or len(target) != 2:
                    return False
                if not self._between(value, target[0], target[1]):
                    return False
            if operator in {FilterOperator.GT, FilterOperator.GTE, FilterOperator.LT, FilterOperator.LTE}:
                if not self._compare(value, target, operator):
                    return False
        return True

    def _between(self, value: Any, low: Any, high: Any) -> bool:
        try:
            dv = Decimal(str(value))
            return Decimal(str(low)) <= dv <= Decimal(str(high))
        except (InvalidOperation, TypeError):
            sv = str(value)
            return str(low) <= sv <= str(high)

    def _compare(self, value: Any, target: Any, operator: FilterOperator) -> bool:
        try:
            left = Decimal(str(value))
            right = Decimal(str(target))
        except (InvalidOperation, TypeError):
            left = str(value)
            right = str(target)
        if operator == FilterOperator.GT:
            return left > right
        if operator == FilterOperator.GTE:
            return left >= right
        if operator == FilterOperator.LT:
            return left < right
        if operator == FilterOperator.LTE:
            return left <= right
        return False

    def _canonicalize(self, value: Any) -> Any:
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, uuid.UUID):
            return str(value)
        if isinstance(value, (date, datetime)):
            return value.isoformat()
        if isinstance(value, dict):
            return {str(key): self._canonicalize(child) for key, child in value.items()}
        if isinstance(value, list):
            return [self._canonicalize(item) for item in value]
        if isinstance(value, tuple):
            return [self._canonicalize(item) for item in value]
        return value


__all__ = [
    "InvalidReportRunStateError",
    "ReportRunError",
    "ReportRunService",
]
