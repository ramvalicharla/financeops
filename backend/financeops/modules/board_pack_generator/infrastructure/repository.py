from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.config import settings
from financeops.db.models.board_pack_generator import (
    BoardPackGeneratorArtifact,
    BoardPackGeneratorDefinition,
    BoardPackGeneratorRun,
    BoardPackGeneratorSection,
)
from financeops.modules.board_pack_generator.domain.pack_definition import (
    PackDefinitionSchema,
)


class BoardPackRepository:
    async def create_definition(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        schema: PackDefinitionSchema,
        created_by: uuid.UUID,
    ) -> BoardPackGeneratorDefinition:
        section_types = [section.section_type.value for section in sorted(schema.section_configs, key=lambda row: row.order)]
        row = BoardPackGeneratorDefinition(
            tenant_id=tenant_id,
            name=schema.name,
            description=schema.description,
            section_types=section_types,
            entity_ids=[str(entity_id) for entity_id in schema.entity_ids],
            period_type=schema.period_type.value,
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
    ) -> BoardPackGeneratorDefinition | None:
        result = await db.execute(
            select(BoardPackGeneratorDefinition).where(
                BoardPackGeneratorDefinition.tenant_id == tenant_id,
                BoardPackGeneratorDefinition.id == definition_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_definitions(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        *,
        active_only: bool = True,
    ) -> list[BoardPackGeneratorDefinition]:
        stmt = select(BoardPackGeneratorDefinition).where(
            BoardPackGeneratorDefinition.tenant_id == tenant_id,
        )
        if active_only:
            stmt = stmt.where(BoardPackGeneratorDefinition.is_active.is_(True))
        stmt = stmt.order_by(
            BoardPackGeneratorDefinition.created_at.desc(),
            BoardPackGeneratorDefinition.id.desc(),
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def update_definition(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        definition_id: uuid.UUID,
        updates: dict[str, Any],
    ) -> BoardPackGeneratorDefinition:
        definition = await self.get_definition(
            db=db,
            tenant_id=tenant_id,
            definition_id=definition_id,
        )
        if definition is None:
            raise ValueError("Board pack definition not found")

        if "name" in updates:
            definition.name = str(updates["name"])
        if "description" in updates:
            definition.description = updates["description"]
        if "section_types" in updates and updates["section_types"] is not None:
            definition.section_types = [str(value) for value in updates["section_types"]]
        if "entity_ids" in updates and updates["entity_ids"] is not None:
            definition.entity_ids = [str(value) for value in updates["entity_ids"]]
        if "period_type" in updates and updates["period_type"] is not None:
            definition.period_type = str(updates["period_type"])
        if "config" in updates and updates["config"] is not None:
            definition.config = dict(updates["config"])
        if "is_active" in updates and updates["is_active"] is not None:
            definition.is_active = bool(updates["is_active"])
        definition.updated_at = datetime.now(UTC)
        await db.flush()
        return definition

    async def deactivate_definition(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        definition_id: uuid.UUID,
    ) -> BoardPackGeneratorDefinition:
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
        period_start: date,
        period_end: date,
        triggered_by: uuid.UUID,
    ) -> BoardPackGeneratorRun:
        run_id = uuid.uuid4()
        row = BoardPackGeneratorRun(
            id=run_id,
            tenant_id=tenant_id,
            definition_id=definition_id,
            period_start=period_start,
            period_end=period_end,
            status="PENDING",
            triggered_by=triggered_by,
            run_metadata={"origin_run_id": str(run_id)},
            created_at=datetime.now(UTC),
        )
        db.add(row)
        await db.flush()
        return row

    async def get_latest_run_for_definition(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        definition_id: uuid.UUID,
    ) -> BoardPackGeneratorRun | None:
        result = await db.execute(
            select(BoardPackGeneratorRun)
            .where(
                BoardPackGeneratorRun.tenant_id == tenant_id,
                BoardPackGeneratorRun.definition_id == definition_id,
            )
            .order_by(
                BoardPackGeneratorRun.created_at.desc(),
                BoardPackGeneratorRun.id.desc(),
            )
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_run(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        run_id: uuid.UUID,
    ) -> BoardPackGeneratorRun | None:
        result = await db.execute(
            select(BoardPackGeneratorRun).where(
                BoardPackGeneratorRun.tenant_id == tenant_id,
                BoardPackGeneratorRun.id == run_id,
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
    ) -> list[BoardPackGeneratorRun]:
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
                FROM board_pack_runs
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
            select(BoardPackGeneratorRun).where(
                BoardPackGeneratorRun.tenant_id == tenant_id,
                BoardPackGeneratorRun.id.in_(run_ids),
            )
        )
        rows = list(rows_result.scalars().all())
        by_id = {row.id: row for row in rows}
        return [by_id[run_id] for run_id in run_ids if run_id in by_id]

    async def list_sections_for_run(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        run_id: uuid.UUID,
    ) -> list[BoardPackGeneratorSection]:
        result = await db.execute(
            select(BoardPackGeneratorSection)
            .where(
                BoardPackGeneratorSection.tenant_id == tenant_id,
                BoardPackGeneratorSection.run_id == run_id,
            )
            .order_by(
                BoardPackGeneratorSection.section_order.asc(),
                BoardPackGeneratorSection.id.asc(),
            )
        )
        return list(result.scalars().all())

    async def list_artifacts_for_run(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        run_id: uuid.UUID,
    ) -> list[BoardPackGeneratorArtifact]:
        result = await db.execute(
            select(BoardPackGeneratorArtifact)
            .where(
                BoardPackGeneratorArtifact.tenant_id == tenant_id,
                BoardPackGeneratorArtifact.run_id == run_id,
            )
            .order_by(
                BoardPackGeneratorArtifact.generated_at.desc(),
                BoardPackGeneratorArtifact.id.desc(),
            )
        )
        return list(result.scalars().all())

    async def get_artifact(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        artifact_id: uuid.UUID,
    ) -> BoardPackGeneratorArtifact | None:
        result = await db.execute(
            select(BoardPackGeneratorArtifact).where(
                BoardPackGeneratorArtifact.tenant_id == tenant_id,
                BoardPackGeneratorArtifact.id == artifact_id,
            )
        )
        return result.scalar_one_or_none()

    def save_artifact_bytes(
        self,
        storage_path: str,
        content: bytes,
    ) -> str:
        base_dir = Path(str(getattr(settings, "ARTIFACTS_BASE_DIR", "artifacts")))
        target_path = base_dir / storage_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(content)

        checksum_path = target_path.with_suffix(target_path.suffix + ".sha256")
        checksum_path.write_text(hashlib.sha256(content).hexdigest(), encoding="utf-8")
        return storage_path
