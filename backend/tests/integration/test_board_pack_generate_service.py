from __future__ import annotations

import uuid
import json
from datetime import date
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock

import pytest

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.rls import set_tenant_context

pytest_plugins: tuple[str, ...] = ()


class _FakeStorage:
    def __init__(self) -> None:
        self.uploads: list[dict[str, str | bytes]] = []

    def upload_file(
        self,
        file_bytes: bytes,
        key: str,
        content_type: str,
        tenant_id: str,
        uploaded_by: str | None = None,
    ) -> str:
        self.uploads.append(
            {
                "file_bytes": file_bytes,
                "key": key,
                "content_type": content_type,
                "tenant_id": tenant_id,
                "uploaded_by": uploaded_by or "",
            }
        )
        return key


class _StubExportService:
    def export_pdf(self, pack, pack_name: str, generated_at):
        return (b"%PDF-1.4\nboard-pack\n", f"board_pack_{pack.period_start}_{pack.period_end}.pdf")

    def export_excel(self, pack, pack_name: str, generated_at):
        return (
            b"PK\x03\x04xlsx",
            f"board_pack_{pack.period_start}_{pack.period_end}.xlsx",
        )


def _contains_float(value: Any) -> bool:
    if isinstance(value, float):
        return True
    if isinstance(value, dict):
        return any(_contains_float(v) for v in value.values())
    if isinstance(value, list):
        return any(_contains_float(v) for v in value)
    return False


def _install_fake_storage(monkeypatch: pytest.MonkeyPatch) -> _FakeStorage:
    fake_storage = _FakeStorage()
    monkeypatch.setattr(
        "financeops.modules.board_pack_generator.application.generate_service.get_storage",
        lambda: fake_storage,
    )
    return fake_storage


async def _seed_definition_and_run(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    sections: list[str],
) -> tuple[uuid.UUID, uuid.UUID]:
    definition_id = uuid.uuid4()
    run_id = uuid.uuid4()
    now = datetime.now(UTC)

    await _relax_board_pack_schema(session)

    await session.execute(
        text(
            """
            INSERT INTO board_pack_definitions (
                id, tenant_id, name, description, section_types, entity_ids,
                period_type, config, created_by, created_at, updated_at, is_active,
                organisation_id, board_pack_code, board_pack_name, audience_scope,
                section_order_json, inclusion_config_json, version_token,
                effective_from, status, chain_hash, previous_hash
            ) VALUES (
                :id, :tenant_id, :name, :description, CAST(:section_types AS jsonb), CAST(:entity_ids AS jsonb),
                :period_type, CAST(:config AS jsonb), :created_by, :created_at, :updated_at, :is_active,
                :organisation_id, :board_pack_code, :board_pack_name, :audience_scope,
                CAST(:section_order_json AS jsonb), CAST(:inclusion_config_json AS jsonb), :version_token,
                :effective_from, :status, :chain_hash, :previous_hash
            )
            """
        ),
        {
            "id": str(definition_id),
            "tenant_id": str(tenant_id),
            "name": "Generator Definition",
            "description": "integration",
            "section_types": json.dumps(sections),
            "entity_ids": json.dumps([str(uuid.uuid4())]),
            "period_type": "MONTHLY",
            "config": json.dumps({}),
            "created_by": str(tenant_id),
            "created_at": now,
            "updated_at": now,
            "is_active": True,
            "organisation_id": str(tenant_id),
            "board_pack_code": f"bp_{uuid.uuid4().hex[:8]}",
            "board_pack_name": "Generator Definition",
            "audience_scope": "board",
            "section_order_json": json.dumps({section: idx + 1 for idx, section in enumerate(sections)}),
            "inclusion_config_json": json.dumps({}),
            "version_token": uuid.uuid4().hex,
            "effective_from": date(2026, 1, 1),
            "status": "candidate",
            "chain_hash": "a" * 64,
            "previous_hash": "0" * 64,
        },
    )

    await session.execute(
        text(
            """
            INSERT INTO board_pack_runs (
                id, tenant_id, definition_id, period_start, period_end,
                status, triggered_by, run_metadata, chain_hash, previous_hash,
                created_at, organisation_id, reporting_period,
                board_pack_definition_version_token, section_definition_version_token,
                narrative_template_version_token, inclusion_rule_version_token,
                source_metric_run_ids_json, source_risk_run_ids_json,
                source_anomaly_run_ids_json, run_token, validation_summary_json, created_by
            ) VALUES (
                :id, :tenant_id, :definition_id, :period_start, :period_end,
                :status, :triggered_by, CAST(:run_metadata AS jsonb), :chain_hash, :previous_hash,
                :created_at, :organisation_id, :reporting_period,
                :board_pack_definition_version_token, :section_definition_version_token,
                :narrative_template_version_token, :inclusion_rule_version_token,
                CAST(:source_metric_run_ids_json AS jsonb), CAST(:source_risk_run_ids_json AS jsonb),
                CAST(:source_anomaly_run_ids_json AS jsonb), :run_token, CAST(:validation_summary_json AS jsonb), :created_by
            )
            """
        ),
        {
            "id": str(run_id),
            "tenant_id": str(tenant_id),
            "definition_id": str(definition_id),
            "period_start": date(2026, 1, 1),
            "period_end": date(2026, 1, 31),
            "status": "PENDING",
            "triggered_by": str(tenant_id),
            "run_metadata": json.dumps({"origin_run_id": str(run_id)}),
            "chain_hash": "b" * 64,
            "previous_hash": "a" * 64,
            "created_at": now,
            "organisation_id": str(tenant_id),
            "reporting_period": date(2026, 1, 31),
            "board_pack_definition_version_token": uuid.uuid4().hex,
            "section_definition_version_token": uuid.uuid4().hex,
            "narrative_template_version_token": uuid.uuid4().hex,
            "inclusion_rule_version_token": uuid.uuid4().hex,
            "source_metric_run_ids_json": json.dumps([str(uuid.uuid4())]),
            "source_risk_run_ids_json": json.dumps([str(uuid.uuid4())]),
            "source_anomaly_run_ids_json": json.dumps([str(uuid.uuid4())]),
            "run_token": uuid.uuid4().hex,
            "validation_summary_json": json.dumps({}),
            "created_by": str(tenant_id),
        },
    )

    await session.commit()
    return definition_id, run_id


async def _relax_board_pack_schema(async_session: AsyncSession) -> None:
    await async_session.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS board_pack_sections (
              id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
              run_id UUID NOT NULL,
              tenant_id UUID NOT NULL,
              section_type VARCHAR(50) NOT NULL,
              section_order INTEGER NOT NULL,
              data_snapshot JSONB NOT NULL,
              section_hash VARCHAR(64) NOT NULL,
              rendered_at TIMESTAMPTZ NOT NULL DEFAULT now()
            );
            """
        )
    )
    await async_session.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS board_pack_artifacts (
              id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
              run_id UUID NOT NULL,
              tenant_id UUID NOT NULL,
              format VARCHAR(20) NOT NULL,
              storage_path TEXT NOT NULL,
              file_size_bytes BIGINT NULL,
              generated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
              checksum VARCHAR(64) NULL
            );
            """
        )
    )
    await async_session.execute(
        text(
            """
            DO $$
            BEGIN
              IF EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema='public' AND table_name='board_pack_sections'
              ) THEN
                ALTER TABLE board_pack_sections ALTER COLUMN id SET DEFAULT gen_random_uuid();
                ALTER TABLE board_pack_sections ALTER COLUMN rendered_at SET DEFAULT now();
              END IF;
              IF EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema='public' AND table_name='board_pack_artifacts'
              ) THEN
                ALTER TABLE board_pack_artifacts ALTER COLUMN id SET DEFAULT gen_random_uuid();
                ALTER TABLE board_pack_artifacts ALTER COLUMN generated_at SET DEFAULT now();
              END IF;
            END $$;
            """
        )
    )
    await async_session.execute(
        text(
            """
            DO $$
            BEGIN
              IF EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema='public' AND table_name='board_pack_definitions'
              ) THEN
                ALTER TABLE board_pack_definitions ALTER COLUMN id SET DEFAULT gen_random_uuid();
                ALTER TABLE board_pack_definitions ADD COLUMN IF NOT EXISTS name VARCHAR(255);
                ALTER TABLE board_pack_definitions ADD COLUMN IF NOT EXISTS description TEXT;
                ALTER TABLE board_pack_definitions ADD COLUMN IF NOT EXISTS section_types JSONB DEFAULT '[]'::jsonb;
                ALTER TABLE board_pack_definitions ADD COLUMN IF NOT EXISTS entity_ids JSONB DEFAULT '[]'::jsonb;
                ALTER TABLE board_pack_definitions ADD COLUMN IF NOT EXISTS period_type VARCHAR(50);
                ALTER TABLE board_pack_definitions ADD COLUMN IF NOT EXISTS config JSONB DEFAULT '{}'::jsonb;
                ALTER TABLE board_pack_definitions ADD COLUMN IF NOT EXISTS created_by UUID;
                ALTER TABLE board_pack_definitions ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now();
                ALTER TABLE board_pack_definitions ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT true;

                IF EXISTS (
                  SELECT 1 FROM information_schema.columns
                  WHERE table_schema='public' AND table_name='board_pack_definitions' AND column_name='created_at'
                ) THEN
                  ALTER TABLE board_pack_definitions ALTER COLUMN created_at SET DEFAULT now();
                END IF;
                IF EXISTS (
                  SELECT 1 FROM information_schema.columns
                  WHERE table_schema='public' AND table_name='board_pack_definitions' AND column_name='updated_at'
                ) THEN
                  ALTER TABLE board_pack_definitions ALTER COLUMN updated_at SET DEFAULT now();
                END IF;
              END IF;
              IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema='public' AND table_name='board_pack_definitions' AND column_name='organisation_id'
              ) THEN
                ALTER TABLE board_pack_definitions ALTER COLUMN organisation_id DROP NOT NULL;
              END IF;
              IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema='public' AND table_name='board_pack_definitions' AND column_name='board_pack_code'
              ) THEN
                ALTER TABLE board_pack_definitions ALTER COLUMN board_pack_code DROP NOT NULL;
              END IF;
              IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema='public' AND table_name='board_pack_definitions' AND column_name='board_pack_name'
              ) THEN
                ALTER TABLE board_pack_definitions ALTER COLUMN board_pack_name DROP NOT NULL;
              END IF;
              IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema='public' AND table_name='board_pack_definitions' AND column_name='version_token'
              ) THEN
                ALTER TABLE board_pack_definitions ALTER COLUMN version_token DROP NOT NULL;
              END IF;
              IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema='public' AND table_name='board_pack_definitions' AND column_name='effective_from'
              ) THEN
                ALTER TABLE board_pack_definitions ALTER COLUMN effective_from DROP NOT NULL;
              END IF;
              IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema='public' AND table_name='board_pack_definitions' AND column_name='chain_hash'
              ) THEN
                ALTER TABLE board_pack_definitions ALTER COLUMN chain_hash DROP NOT NULL;
              END IF;
              IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema='public' AND table_name='board_pack_definitions' AND column_name='previous_hash'
              ) THEN
                ALTER TABLE board_pack_definitions ALTER COLUMN previous_hash DROP NOT NULL;
              END IF;
            END $$;
            """
        )
    )
    await async_session.execute(
        text(
            """
            DO $$
            BEGIN
              IF EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema='public' AND table_name='board_pack_runs'
              ) THEN
                ALTER TABLE board_pack_runs ALTER COLUMN id SET DEFAULT gen_random_uuid();
                ALTER TABLE board_pack_runs ALTER COLUMN created_at SET DEFAULT now();
                ALTER TABLE board_pack_runs ADD COLUMN IF NOT EXISTS definition_id UUID;
                ALTER TABLE board_pack_runs ADD COLUMN IF NOT EXISTS period_start DATE;
                ALTER TABLE board_pack_runs ADD COLUMN IF NOT EXISTS period_end DATE;
                ALTER TABLE board_pack_runs ADD COLUMN IF NOT EXISTS status VARCHAR(50) DEFAULT 'PENDING';
                ALTER TABLE board_pack_runs ADD COLUMN IF NOT EXISTS triggered_by UUID;
                ALTER TABLE board_pack_runs ADD COLUMN IF NOT EXISTS started_at TIMESTAMPTZ;
                ALTER TABLE board_pack_runs ADD COLUMN IF NOT EXISTS completed_at TIMESTAMPTZ;
                ALTER TABLE board_pack_runs ADD COLUMN IF NOT EXISTS error_message TEXT;
                ALTER TABLE board_pack_runs ADD COLUMN IF NOT EXISTS run_metadata JSONB DEFAULT '{}'::jsonb;
                ALTER TABLE board_pack_runs ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT now();
              END IF;
            END $$;
            """
        )
    )
    await async_session.execute(
        text(
            """
            DO $$
            BEGIN
              IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema='public' AND table_name='board_pack_runs' AND column_name='chain_hash'
              ) THEN
                ALTER TABLE board_pack_runs ALTER COLUMN chain_hash DROP NOT NULL;
              END IF;
              IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema='public' AND table_name='board_pack_runs' AND column_name='previous_hash'
              ) THEN
                ALTER TABLE board_pack_runs ALTER COLUMN previous_hash DROP NOT NULL;
              END IF;
              IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema='public' AND table_name='board_pack_runs' AND column_name='organisation_id'
              ) THEN
                ALTER TABLE board_pack_runs ALTER COLUMN organisation_id DROP NOT NULL;
              END IF;
              IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema='public' AND table_name='board_pack_runs' AND column_name='reporting_period'
              ) THEN
                ALTER TABLE board_pack_runs ALTER COLUMN reporting_period DROP NOT NULL;
              END IF;
              IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema='public' AND table_name='board_pack_runs' AND column_name='board_pack_definition_version_token'
              ) THEN
                ALTER TABLE board_pack_runs ALTER COLUMN board_pack_definition_version_token DROP NOT NULL;
              END IF;
              IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema='public' AND table_name='board_pack_runs' AND column_name='section_definition_version_token'
              ) THEN
                ALTER TABLE board_pack_runs ALTER COLUMN section_definition_version_token DROP NOT NULL;
              END IF;
              IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema='public' AND table_name='board_pack_runs' AND column_name='narrative_template_version_token'
              ) THEN
                ALTER TABLE board_pack_runs ALTER COLUMN narrative_template_version_token DROP NOT NULL;
              END IF;
              IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema='public' AND table_name='board_pack_runs' AND column_name='inclusion_rule_version_token'
              ) THEN
                ALTER TABLE board_pack_runs ALTER COLUMN inclusion_rule_version_token DROP NOT NULL;
              END IF;
              IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema='public' AND table_name='board_pack_runs' AND column_name='run_token'
              ) THEN
                ALTER TABLE board_pack_runs ALTER COLUMN run_token DROP NOT NULL;
              END IF;
              IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema='public' AND table_name='board_pack_runs' AND column_name='created_by'
              ) THEN
                ALTER TABLE board_pack_runs ALTER COLUMN created_by DROP NOT NULL;
              END IF;
              IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema='public' AND table_name='board_pack_runs' AND column_name='source_metric_run_ids_json'
              ) THEN
                ALTER TABLE board_pack_runs ALTER COLUMN source_metric_run_ids_json DROP NOT NULL;
              END IF;
              IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema='public' AND table_name='board_pack_runs' AND column_name='source_risk_run_ids_json'
              ) THEN
                ALTER TABLE board_pack_runs ALTER COLUMN source_risk_run_ids_json DROP NOT NULL;
              END IF;
              IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema='public' AND table_name='board_pack_runs' AND column_name='source_anomaly_run_ids_json'
              ) THEN
                ALTER TABLE board_pack_runs ALTER COLUMN source_anomaly_run_ids_json DROP NOT NULL;
              END IF;
              IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema='public' AND table_name='board_pack_runs' AND column_name='validation_summary_json'
              ) THEN
                ALTER TABLE board_pack_runs ALTER COLUMN validation_summary_json DROP NOT NULL;
              END IF;

              IF EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema='public' AND table_name='board_pack_runs'
              ) THEN
                ALTER TABLE board_pack_runs DROP CONSTRAINT IF EXISTS ck_board_pack_runs_metric_sources_required;
                ALTER TABLE board_pack_runs DROP CONSTRAINT IF EXISTS ck_board_pack_runs_risk_sources_required;
                ALTER TABLE board_pack_runs DROP CONSTRAINT IF EXISTS ck_board_pack_runs_anomaly_sources_required;
                ALTER TABLE board_pack_runs DROP CONSTRAINT IF EXISTS ck_board_pack_runs_status;
                ALTER TABLE board_pack_runs DROP CONSTRAINT IF EXISTS ck_board_pack_runs_generator_status;
                ALTER TABLE board_pack_runs
                  ADD CONSTRAINT ck_board_pack_runs_status
                  CHECK (lower(status) IN ('pending', 'running', 'complete', 'failed'));
              END IF;

              IF EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema='public' AND table_name='board_pack_runs'
              ) AND EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema='public' AND table_name='board_pack_definitions'
              ) AND NOT EXISTS (
                SELECT 1
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_name = kcu.constraint_name
                 AND tc.table_schema = kcu.table_schema
                WHERE tc.table_schema = 'public'
                  AND tc.table_name = 'board_pack_runs'
                  AND tc.constraint_type = 'FOREIGN KEY'
                  AND kcu.column_name = 'definition_id'
              ) THEN
                ALTER TABLE board_pack_runs
                  ADD CONSTRAINT fk_board_pack_runs_definition_id
                  FOREIGN KEY (definition_id)
                  REFERENCES board_pack_definitions(id)
                  ON DELETE RESTRICT;
              END IF;

              IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema='public' AND table_name='board_pack_runs' AND column_name='status'
              ) AND NOT EXISTS (
                SELECT 1
                FROM information_schema.table_constraints tc
                JOIN information_schema.constraint_column_usage ccu
                  ON tc.constraint_name = ccu.constraint_name
                 AND tc.table_schema = ccu.table_schema
                WHERE tc.table_schema = 'public'
                  AND tc.table_name = 'board_pack_runs'
                  AND tc.constraint_type = 'CHECK'
                  AND ccu.column_name = 'status'
              ) THEN
                ALTER TABLE board_pack_runs
                  ADD CONSTRAINT ck_board_pack_runs_generator_status
                  CHECK (status IN ('PENDING', 'RUNNING', 'COMPLETE', 'FAILED'));
              END IF;
            END $$;
            """
        )
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_t_028_generate_full_lifecycle_creates_three_run_rows(
    async_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from financeops.db.models.board_pack_generator import BoardPackGeneratorRun
    from financeops.modules.board_pack_generator.application.generate_service import BoardPackGenerateService

    tenant_id = uuid.uuid4()
    await set_tenant_context(async_session, tenant_id)
    _, run_id = await _seed_definition_and_run(
        async_session,
        tenant_id=tenant_id,
        sections=["PROFIT_AND_LOSS"],
    )

    service = BoardPackGenerateService(export_service=_StubExportService())
    _install_fake_storage(monkeypatch)

    async def _fake_fetch(*, db, context, section_type):  # noqa: ANN001
        return {
            "section": section_type.value,
            "amount": Decimal("100.25"),
            "period_start": context.period_start,
            "period_end": context.period_end,
        }

    service._fetch_section_source_data = _fake_fetch  # type: ignore[method-assign]
    assembled = await service.generate(db=async_session, run_id=run_id, tenant_id=tenant_id)

    rows = list(
        (
            await async_session.execute(
                select(BoardPackGeneratorRun)
                .where(BoardPackGeneratorRun.tenant_id == tenant_id)
                .order_by(BoardPackGeneratorRun.created_at.asc(), BoardPackGeneratorRun.id.asc())
            )
        ).scalars()
    )
    origin_ids = {
        str((row.run_metadata or {}).get("origin_run_id", row.id))
        for row in rows
    }

    assert len(rows) == 3
    assert len(origin_ids) == 1
    complete_rows = [row for row in rows if row.status == "COMPLETE"]
    assert len(complete_rows) == 1
    assert complete_rows[0].chain_hash == assembled.chain_hash


@pytest.mark.integration
@pytest.mark.asyncio
async def test_t_029_generate_with_missing_run_raises_board_pack_generation_error(
    async_session: AsyncSession,
) -> None:
    from financeops.modules.board_pack_generator.application.generate_service import (
        BoardPackGenerateService,
        BoardPackGenerationError,
    )

    tenant_id = uuid.uuid4()
    await set_tenant_context(async_session, tenant_id)
    service = BoardPackGenerateService(export_service=_StubExportService())

    with pytest.raises(BoardPackGenerationError):
        await service.generate(db=async_session, run_id=uuid.uuid4(), tenant_id=tenant_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_t_032_generate_appends_failed_row_when_renderer_throws(
    async_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from financeops.db.models.board_pack_generator import BoardPackGeneratorRun
    from financeops.modules.board_pack_generator.application.generate_service import BoardPackGenerateService

    tenant_id = uuid.uuid4()
    await set_tenant_context(async_session, tenant_id)
    _, run_id = await _seed_definition_and_run(
        async_session,
        tenant_id=tenant_id,
        sections=["PROFIT_AND_LOSS"],
    )

    service = BoardPackGenerateService(export_service=_StubExportService())

    async def _fake_fetch(*, db, context, section_type):  # noqa: ANN001
        return {"amount": Decimal("1.00")}

    service._fetch_section_source_data = _fake_fetch  # type: ignore[method-assign]

    class _BoomRenderer:
        def render(self, context, section_config, source_data):  # noqa: ANN001
            raise RuntimeError("renderer exploded")

    monkeypatch.setattr(
        "financeops.modules.board_pack_generator.application.generate_service.get_renderer",
        lambda section_type: _BoomRenderer(),
    )

    with pytest.raises(RuntimeError, match="renderer exploded"):
        await service.generate(db=async_session, run_id=run_id, tenant_id=tenant_id)

    rows = list(
        (
            await async_session.execute(
                select(BoardPackGeneratorRun)
                .where(BoardPackGeneratorRun.tenant_id == tenant_id)
                .order_by(BoardPackGeneratorRun.created_at.asc(), BoardPackGeneratorRun.id.asc())
            )
        ).scalars()
    )
    failed_rows = [row for row in rows if row.status == "FAILED"]
    assert len(failed_rows) == 1
    assert "renderer exploded" in (failed_rows[0].error_message or "")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_t_033_generate_persists_expected_section_count(
    async_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from financeops.db.models.board_pack_generator import BoardPackGeneratorSection
    from financeops.modules.board_pack_generator.application.generate_service import BoardPackGenerateService

    tenant_id = uuid.uuid4()
    await set_tenant_context(async_session, tenant_id)
    _, run_id = await _seed_definition_and_run(
        async_session,
        tenant_id=tenant_id,
        sections=["PROFIT_AND_LOSS", "BALANCE_SHEET", "CASH_FLOW"],
    )

    service = BoardPackGenerateService(export_service=_StubExportService())
    _install_fake_storage(monkeypatch)

    async def _fake_fetch(*, db, context, section_type):  # noqa: ANN001
        return {"section": section_type.value, "amount": Decimal("10.00")}

    service._fetch_section_source_data = _fake_fetch  # type: ignore[method-assign]
    await service.generate(db=async_session, run_id=run_id, tenant_id=tenant_id)

    section_count = (
        await async_session.execute(
            select(BoardPackGeneratorSection).where(BoardPackGeneratorSection.tenant_id == tenant_id)
        )
    ).scalars().all()
    assert len(section_count) == 3


@pytest.mark.integration
@pytest.mark.asyncio
async def test_t_034_generate_persists_two_artifacts_with_expected_path(
    async_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from financeops.db.models.board_pack_generator import BoardPackGeneratorArtifact
    from financeops.modules.board_pack_generator.application.generate_service import BoardPackGenerateService

    tenant_id = uuid.uuid4()
    await set_tenant_context(async_session, tenant_id)
    _, run_id = await _seed_definition_and_run(
        async_session,
        tenant_id=tenant_id,
        sections=["PROFIT_AND_LOSS"],
    )

    service = BoardPackGenerateService(export_service=_StubExportService())
    _install_fake_storage(monkeypatch)

    async def _fake_fetch(*, db, context, section_type):  # noqa: ANN001
        return {"section": section_type.value, "amount": Decimal("10.00")}

    service._fetch_section_source_data = _fake_fetch  # type: ignore[method-assign]
    await service.generate(db=async_session, run_id=run_id, tenant_id=tenant_id)

    artifacts = list(
        (
            await async_session.execute(
                select(BoardPackGeneratorArtifact)
                .where(BoardPackGeneratorArtifact.tenant_id == tenant_id)
                .order_by(BoardPackGeneratorArtifact.format.asc())
            )
        ).scalars()
    )

    assert len(artifacts) == 2
    assert {artifact.format for artifact in artifacts} == {"PDF", "EXCEL"}
    for artifact in artifacts:
        assert artifact.storage_path.startswith(f"artifacts/board_packs/{tenant_id}/")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_t_035_complete_run_chain_hash_matches_assembled_pack(
    async_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from financeops.db.models.board_pack_generator import BoardPackGeneratorRun
    from financeops.modules.board_pack_generator.application.generate_service import BoardPackGenerateService

    tenant_id = uuid.uuid4()
    await set_tenant_context(async_session, tenant_id)
    _, run_id = await _seed_definition_and_run(
        async_session,
        tenant_id=tenant_id,
        sections=["PROFIT_AND_LOSS"],
    )

    service = BoardPackGenerateService(export_service=_StubExportService())
    _install_fake_storage(monkeypatch)

    async def _fake_fetch(*, db, context, section_type):  # noqa: ANN001
        return {"section": section_type.value, "amount": Decimal("500.00")}

    service._fetch_section_source_data = _fake_fetch  # type: ignore[method-assign]
    assembled = await service.generate(db=async_session, run_id=run_id, tenant_id=tenant_id)

    latest_complete = (
        await async_session.execute(
            select(BoardPackGeneratorRun)
            .where(
                BoardPackGeneratorRun.tenant_id == tenant_id,
                BoardPackGeneratorRun.status == "COMPLETE",
            )
            .order_by(BoardPackGeneratorRun.created_at.desc(), BoardPackGeneratorRun.id.desc())
            .limit(1)
        )
    ).scalar_one()

    assert latest_complete.chain_hash == assembled.chain_hash


@pytest.mark.integration
@pytest.mark.asyncio
async def test_t_036_all_run_rows_share_origin_run_id(
    async_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from financeops.db.models.board_pack_generator import BoardPackGeneratorRun
    from financeops.modules.board_pack_generator.application.generate_service import BoardPackGenerateService

    tenant_id = uuid.uuid4()
    await set_tenant_context(async_session, tenant_id)
    _, run_id = await _seed_definition_and_run(
        async_session,
        tenant_id=tenant_id,
        sections=["PROFIT_AND_LOSS"],
    )

    service = BoardPackGenerateService(export_service=_StubExportService())
    _install_fake_storage(monkeypatch)

    async def _fake_fetch(*, db, context, section_type):  # noqa: ANN001
        return {"section": section_type.value, "amount": Decimal("20.00")}

    service._fetch_section_source_data = _fake_fetch  # type: ignore[method-assign]
    await service.generate(db=async_session, run_id=run_id, tenant_id=tenant_id)

    rows = list(
        (
            await async_session.execute(
                select(BoardPackGeneratorRun)
                .where(BoardPackGeneratorRun.tenant_id == tenant_id)
                .order_by(BoardPackGeneratorRun.created_at.asc(), BoardPackGeneratorRun.id.asc())
            )
        ).scalars()
    )

    origins = {str((row.run_metadata or {}).get("origin_run_id", "")) for row in rows}
    assert len(origins) == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_t_037_section_snapshots_have_no_float_values(
    async_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from financeops.db.models.board_pack_generator import BoardPackGeneratorSection
    from financeops.modules.board_pack_generator.application.generate_service import BoardPackGenerateService

    tenant_id = uuid.uuid4()
    await set_tenant_context(async_session, tenant_id)
    _, run_id = await _seed_definition_and_run(
        async_session,
        tenant_id=tenant_id,
        sections=["PROFIT_AND_LOSS", "BALANCE_SHEET"],
    )

    service = BoardPackGenerateService(export_service=_StubExportService())
    _install_fake_storage(monkeypatch)

    async def _fake_fetch(*, db, context, section_type):  # noqa: ANN001
        return {
            "section": section_type.value,
            "amount": Decimal("42.42"),
            "nested": {"values": [Decimal("1.10"), Decimal("2.20")]},
        }

    service._fetch_section_source_data = _fake_fetch  # type: ignore[method-assign]
    await service.generate(db=async_session, run_id=run_id, tenant_id=tenant_id)

    sections = list(
        (
            await async_session.execute(
                select(BoardPackGeneratorSection).where(BoardPackGeneratorSection.tenant_id == tenant_id)
            )
        ).scalars()
    )
    assert sections
    assert all(not _contains_float(section.data_snapshot) for section in sections)


@pytest.mark.integration
def test_t_038_generate_board_pack_task_returns_complete_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    from financeops.modules.board_pack_generator.domain.enums import SectionType
    from financeops.modules.board_pack_generator.domain.pack_definition import AssembledPack, RenderedSection
    from financeops.modules.board_pack_generator.tasks import generate_board_pack_task

    run_row = MagicMock()
    run_row.id = uuid.uuid4()
    run_row.tenant_id = uuid.uuid4()
    run_row.definition_id = uuid.uuid4()
    run_row.triggered_by = uuid.uuid4()
    run_row.run_metadata = {}
    run_row.period_end = date(2026, 1, 31)

    class _FakeService:
        async def generate(self, *, db, run_id, tenant_id):  # noqa: ANN001
            return AssembledPack(
                run_id=run_id,
                tenant_id=tenant_id,
                period_start=date(2026, 1, 1),
                period_end=date(2026, 1, 31),
                sections=[
                    RenderedSection(
                        section_type=SectionType.PROFIT_AND_LOSS,
                        section_order=1,
                        title="P&L",
                        data_snapshot={"value": "1"},
                        section_hash="a" * 64,
                    )
                ],
                chain_hash="b" * 64,
            )

    class _FakeResult:
        def scalar_one_or_none(self):
            return run_row

        def scalars(self):
            return MagicMock(first=lambda: None)

    class _FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):  # noqa: ANN001
            return False

        async def execute(self, statement):  # noqa: ANN001
            return _FakeResult()

    class _FakeSessionFactory:
        def __call__(self):
            return _FakeSession()

    async def _noop(*args, **kwargs):  # noqa: ANN002,ANN003
        return None

    monkeypatch.setattr(
        "financeops.modules.board_pack_generator.tasks.BoardPackGenerateService",
        lambda: _FakeService(),
    )
    monkeypatch.setattr(
        "financeops.modules.board_pack_generator.tasks.AsyncSessionLocal",
        _FakeSessionFactory(),
    )
    monkeypatch.setattr("financeops.modules.board_pack_generator.tasks.set_tenant_context", _noop)
    monkeypatch.setattr("financeops.modules.board_pack_generator.tasks.clear_tenant_context", _noop)
    monkeypatch.setattr("financeops.modules.board_pack_generator.tasks.run_auto_complete_for_event", _noop)
    monkeypatch.setattr("financeops.modules.board_pack_generator.tasks.send_notification", _noop)

    retry_spy = MagicMock()
    monkeypatch.setattr(generate_board_pack_task, "retry", retry_spy)

    run_id = str(uuid.uuid4())
    tenant_id = str(uuid.uuid4())
    result = generate_board_pack_task.run(run_id=run_id, tenant_id=tenant_id)

    assert result == {"run_id": run_id, "status": "COMPLETE"}
