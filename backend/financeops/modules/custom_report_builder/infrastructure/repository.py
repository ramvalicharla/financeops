from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.custom_report_builder import (
    ReportDefinition,
    ReportResult,
    ReportRun,
)
from financeops.modules.custom_report_builder.domain.filter_dsl import (
    ReportDefinitionSchema,
)


class ReportRepository:
    async def create_definition(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        schema: ReportDefinitionSchema,
        created_by: uuid.UUID,
    ) -> ReportDefinition:
        row = ReportDefinition(
            tenant_id=tenant_id,
            name=schema.name,
            description=schema.description,
            metric_keys=list(schema.metric_keys),
            filter_config=schema.filter_config.model_dump(mode="json"),
            group_by=list(schema.group_by),
            sort_config=schema.sort_config.model_dump(mode="json") if schema.sort_config else {},
            export_formats=[fmt.value for fmt in schema.export_formats],
            config=dict(schema.config or {}),
            created_by=created_by,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            is_active=True,
        )
        db.add(row)
        await db.flush()
        return row

    async def get_definition(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        definition_id: uuid.UUID,
    ) -> ReportDefinition | None:
        result = await db.execute(
            select(ReportDefinition).where(
                ReportDefinition.tenant_id == tenant_id,
                ReportDefinition.id == definition_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_definitions(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        *,
        active_only: bool = True,
    ) -> list[ReportDefinition]:
        stmt = select(ReportDefinition).where(ReportDefinition.tenant_id == tenant_id)
        if active_only:
            stmt = stmt.where(ReportDefinition.is_active.is_(True))
        stmt = stmt.order_by(ReportDefinition.created_at.desc(), ReportDefinition.id.desc())
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def update_definition(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        definition_id: uuid.UUID,
        updates: dict[str, Any],
    ) -> ReportDefinition:
        row = await self.get_definition(db, tenant_id, definition_id)
        if row is None:
            raise ValueError("Report definition not found")

        if "name" in updates:
            row.name = str(updates["name"])
        if "description" in updates:
            row.description = updates["description"]
        if "metric_keys" in updates and updates["metric_keys"] is not None:
            row.metric_keys = [str(v) for v in updates["metric_keys"]]
        if "filter_config" in updates and updates["filter_config"] is not None:
            row.filter_config = dict(updates["filter_config"])
        if "group_by" in updates and updates["group_by"] is not None:
            row.group_by = [str(v) for v in updates["group_by"]]
        if "sort_config" in updates and updates["sort_config"] is not None:
            row.sort_config = dict(updates["sort_config"])
        if "export_formats" in updates and updates["export_formats"] is not None:
            row.export_formats = [str(v) for v in updates["export_formats"]]
        if "config" in updates and updates["config"] is not None:
            row.config = dict(updates["config"])
        if "is_active" in updates and updates["is_active"] is not None:
            row.is_active = bool(updates["is_active"])
        row.updated_at = datetime.now(UTC)
        await db.flush()
        return row

    async def deactivate_definition(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        definition_id: uuid.UUID,
    ) -> ReportDefinition:
        return await self.update_definition(
            db=db,
            tenant_id=tenant_id,
            definition_id=definition_id,
            updates={"is_active": False},
        )

    async def create_run(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        definition_id: uuid.UUID,
        triggered_by: uuid.UUID,
    ) -> ReportRun:
        run_id = uuid.uuid4()
        row = ReportRun(
            id=run_id,
            tenant_id=tenant_id,
            definition_id=definition_id,
            status="PENDING",
            triggered_by=triggered_by,
            run_metadata={"origin_run_id": str(run_id)},
            created_at=datetime.now(UTC),
        )
        db.add(row)
        await db.flush()
        return row

    async def get_run(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        run_id: uuid.UUID,
    ) -> ReportRun | None:
        result = await db.execute(
            select(ReportRun).where(
                ReportRun.tenant_id == tenant_id,
                ReportRun.id == run_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_runs(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        *,
        definition_id: uuid.UUID | None = None,
        status: str | None = None,
        limit: int = 20,
    ) -> list[ReportRun]:
        clamped_limit = max(1, min(200, int(limit)))
        sql = text(
            """
            WITH ranked AS (
                SELECT
                    id,
                    status,
                    created_at,
                    ROW_NUMBER() OVER (
                        PARTITION BY COALESCE(run_metadata->>'origin_run_id', id::text)
                        ORDER BY created_at DESC, id DESC
                    ) AS rn
                FROM report_runs
                WHERE tenant_id = :tenant_id
                  AND (CAST(:definition_id AS uuid) IS NULL OR definition_id = CAST(:definition_id AS uuid))
            )
            SELECT id
            FROM ranked
            WHERE rn = 1
              AND (CAST(:status AS text) IS NULL OR status = CAST(:status AS text))
            ORDER BY created_at DESC, id DESC
            LIMIT :limit
            """
        )
        ids_result = await db.execute(
            sql,
            {
                "tenant_id": str(tenant_id),
                "definition_id": str(definition_id) if definition_id else None,
                "status": status,
                "limit": clamped_limit,
            },
        )
        run_ids = [row[0] for row in ids_result.all()]
        if not run_ids:
            return []
        rows_result = await db.execute(
            select(ReportRun).where(
                ReportRun.tenant_id == tenant_id,
                ReportRun.id.in_(run_ids),
            )
        )
        rows = list(rows_result.scalars().all())
        by_id = {row.id: row for row in rows}
        return [by_id[run_id] for run_id in run_ids if run_id in by_id]

    async def get_result_for_run(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        run_id: uuid.UUID,
    ) -> ReportResult | None:
        result = await db.execute(
            select(ReportResult).where(
                ReportResult.tenant_id == tenant_id,
                ReportResult.run_id == run_id,
            )
        )
        return result.scalar_one_or_none()

    async def save_result(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        run_id: uuid.UUID,
        result_data: list[dict[str, Any]],
        result_hash: str,
        export_paths: dict[str, str],
    ) -> ReportResult:
        row = ReportResult(
            tenant_id=tenant_id,
            run_id=run_id,
            result_data=result_data,
            result_hash=result_hash,
            export_path_csv=export_paths.get("CSV"),
            export_path_excel=export_paths.get("EXCEL"),
            export_path_pdf=export_paths.get("PDF"),
            created_at=datetime.now(UTC),
        )
        db.add(row)
        await db.flush()
        return row


__all__ = ["ReportRepository"]

