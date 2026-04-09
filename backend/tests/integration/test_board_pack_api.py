from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.security import hash_password
from financeops.db.models.board_pack_generator import BoardPackGeneratorDefinition
from financeops.db.models.tenants import IamTenant, TenantStatus, TenantType
from financeops.db.models.users import IamUser, UserRole
from financeops.db.rls import set_tenant_context
from financeops.platform.services.control_plane.phase4_service import Phase4ControlPlaneService
from financeops.utils.chain_hash import GENESIS_HASH, compute_chain_hash

pytest_plugins: tuple[str, ...] = ()


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
    await async_session.execute(text("ALTER TABLE board_pack_runs DROP CONSTRAINT IF EXISTS ck_board_pack_runs_status"))
    await async_session.execute(text("ALTER TABLE board_pack_runs DROP CONSTRAINT IF EXISTS ck_board_pack_runs_metric_sources_required"))
    await async_session.execute(text("ALTER TABLE board_pack_runs DROP CONSTRAINT IF EXISTS ck_board_pack_runs_risk_sources_required"))
    await async_session.execute(text("ALTER TABLE board_pack_runs DROP CONSTRAINT IF EXISTS ck_board_pack_runs_anomaly_sources_required"))
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
            END $$;
            """
        )
    )
    await async_session.commit()


def _definition_payload(entity_id: uuid.UUID) -> dict:
    return {
        "name": "Monthly Pack",
        "description": "API test",
        "section_types": ["PROFIT_AND_LOSS", "BALANCE_SHEET"],
        "entity_ids": [str(entity_id)],
        "period_type": "MONTHLY",
        "config": {},
    }


async def _create_definition(
    client: AsyncClient,
    token: str,
    entity_id: uuid.UUID,
) -> dict:
    response = await client.post(
        "/api/v1/board-packs/definitions",
        headers={"Authorization": f"Bearer {token}"},
        json=_definition_payload(entity_id),
    )
    assert response.status_code == 201
    return response.json()["data"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_t_040_create_definition_returns_201(
    async_client: AsyncClient, async_session: AsyncSession, test_access_token: str, test_user
) -> None:
    await _relax_board_pack_schema(async_session)
    response = await async_client.post(
        "/api/v1/board-packs/definitions",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json=_definition_payload(test_user.tenant_id),
    )

    assert response.status_code == 201
    payload = response.json()["data"]
    assert payload["id"]
    assert payload["intent_id"]
    assert payload["job_id"]
    await set_tenant_context(async_session, test_user.tenant_id)
    row = await async_session.get(BoardPackGeneratorDefinition, uuid.UUID(payload["id"]))
    assert row is not None
    assert row.created_by_intent_id is not None
    assert row.recorded_by_job_id is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_t_041_generate_enqueues_task_once(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_access_token: str,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _relax_board_pack_schema(async_session)
    definition = await _create_definition(async_client, test_access_token, test_user.tenant_id)

    calls: list[tuple[str, str]] = []

    def _fake_delay(run_id: str, tenant_id: str) -> None:
        calls.append((run_id, tenant_id))

    monkeypatch.setattr(
        "financeops.modules.board_pack_generator.tasks.generate_board_pack_task.delay",
        _fake_delay,
    )

    response = await async_client.post(
        "/api/v1/board-packs/generate",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={
            "definition_id": definition["id"],
            "period_start": "2026-01-01",
            "period_end": "2026-01-31",
        },
    )

    assert response.status_code == 202
    payload = response.json()["data"]
    assert payload["status"] == "PENDING"
    assert payload["intent_id"]
    assert payload["job_id"]
    assert calls == [(payload["id"], str(test_user.tenant_id))]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_t_042_list_runs_returns_latest_row_per_origin_run_id(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_access_token: str,
    test_user,
) -> None:
    from financeops.modules.board_pack_generator.infrastructure.repository import BoardPackRepository

    await _relax_board_pack_schema(async_session)
    definition = await _create_definition(async_client, test_access_token, test_user.tenant_id)
    await set_tenant_context(async_session, test_user.tenant_id)
    definition_id = uuid.UUID(definition["id"])
    repo = BoardPackRepository()
    first_run = await repo.create_run(
        db=async_session,
        tenant_id=test_user.tenant_id,
        definition_id=definition_id,
        period_start=datetime(2026, 1, 1, tzinfo=UTC).date(),
        period_end=datetime(2026, 1, 31, tzinfo=UTC).date(),
        triggered_by=test_user.id,
    )

    origin = str((first_run.run_metadata or {}).get("origin_run_id", first_run.id))
    now = datetime.now(UTC)
    await async_session.execute(
        text(
            """
            INSERT INTO board_pack_runs (
                id, tenant_id, definition_id, period_start, period_end,
                status, triggered_by, started_at, run_metadata, chain_hash,
                previous_hash, created_at,
                source_metric_run_ids_json, source_risk_run_ids_json,
                source_anomaly_run_ids_json, validation_summary_json
            ) VALUES (
                :id, :tenant_id, :definition_id, :period_start, :period_end,
                :status, :triggered_by, :started_at, CAST(:run_metadata AS jsonb), :chain_hash,
                :previous_hash, :created_at,
                CAST(:source_metric_run_ids_json AS jsonb), CAST(:source_risk_run_ids_json AS jsonb),
                CAST(:source_anomaly_run_ids_json AS jsonb), CAST(:validation_summary_json AS jsonb)
            )
            """
        ),
        {
            "id": str(uuid.uuid4()),
            "tenant_id": str(test_user.tenant_id),
            "definition_id": str(definition_id),
            "period_start": first_run.period_start,
            "period_end": first_run.period_end,
            "status": "RUNNING",
            "triggered_by": str(test_user.id),
            "started_at": now,
            "run_metadata": '{"origin_run_id": "%s", "previous_run_id": "%s"}'
            % (origin, str(first_run.id)),
            "chain_hash": "a" * 64,
            "previous_hash": "0" * 64,
            "created_at": now,
            "source_metric_run_ids_json": '["metric-run-1"]',
            "source_risk_run_ids_json": '["risk-run-1"]',
            "source_anomaly_run_ids_json": '["anomaly-run-1"]',
            "validation_summary_json": "{}",
        },
    )
    await async_session.execute(
        text(
            """
            INSERT INTO board_pack_runs (
                id, tenant_id, definition_id, period_start, period_end,
                status, triggered_by, started_at, completed_at, run_metadata,
                chain_hash, previous_hash, created_at,
                source_metric_run_ids_json, source_risk_run_ids_json,
                source_anomaly_run_ids_json, validation_summary_json
            ) VALUES (
                :id, :tenant_id, :definition_id, :period_start, :period_end,
                :status, :triggered_by, :started_at, :completed_at, CAST(:run_metadata AS jsonb),
                :chain_hash, :previous_hash, :created_at,
                CAST(:source_metric_run_ids_json AS jsonb), CAST(:source_risk_run_ids_json AS jsonb),
                CAST(:source_anomaly_run_ids_json AS jsonb), CAST(:validation_summary_json AS jsonb)
            )
            """
        ),
            {
                "id": str(uuid.uuid4()),
                "tenant_id": str(test_user.tenant_id),
                "definition_id": str(definition_id),
                "period_start": first_run.period_start,
                "period_end": first_run.period_end,
                "status": "COMPLETE",
                "triggered_by": str(test_user.id),
                "started_at": now + timedelta(seconds=1),
                "completed_at": now + timedelta(seconds=1),
                "run_metadata": '{"origin_run_id": "%s", "previous_run_id": "%s"}'
                % (origin, str(first_run.id)),
                "chain_hash": "f" * 64,
                "previous_hash": "a" * 64,
                "created_at": now + timedelta(seconds=1),
                "source_metric_run_ids_json": '["metric-run-2"]',
                "source_risk_run_ids_json": '["risk-run-2"]',
                "source_anomaly_run_ids_json": '["anomaly-run-2"]',
                "validation_summary_json": "{}",
            },
    )
    await async_session.commit()

    response = await async_client.get(
        "/api/v1/board-packs/runs",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["status"] == "COMPLETE"
    assert data[0]["determinism_hash"] == "f" * 64


@pytest.mark.integration
@pytest.mark.asyncio
async def test_t_042b_get_run_includes_snapshot_refs(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_access_token: str,
    test_user,
) -> None:
    await _relax_board_pack_schema(async_session)
    from financeops.modules.board_pack_generator.infrastructure.repository import BoardPackRepository

    definition = await _create_definition(async_client, test_access_token, test_user.tenant_id)
    await set_tenant_context(async_session, test_user.tenant_id)
    repo = BoardPackRepository()
    run = await repo.create_run(
        db=async_session,
        tenant_id=test_user.tenant_id,
        definition_id=uuid.UUID(definition["id"]),
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
        triggered_by=test_user.id,
    )
    run.chain_hash = "c" * 64
    await Phase4ControlPlaneService(async_session).ensure_snapshot_for_subject(
        tenant_id=test_user.tenant_id,
        actor_user_id=test_user.id,
        actor_role=test_user.role.value,
        subject_type="board_pack_run",
        subject_id=str(run.id),
        trigger_event="board_pack_generation_complete",
    )
    await async_session.commit()

    response = await async_client.get(
        f"/api/v1/board-packs/runs/{run.id}",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["determinism_hash"] == "c" * 64
    assert payload["snapshot_refs"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_t_043_sections_endpoint_excludes_data_snapshot(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_access_token: str,
    test_user,
) -> None:
    await _relax_board_pack_schema(async_session)
    from financeops.db.models.board_pack_generator import BoardPackGeneratorSection
    from financeops.modules.board_pack_generator.infrastructure.repository import BoardPackRepository

    await set_tenant_context(async_session, test_user.tenant_id)
    definition = await _create_definition(async_client, test_access_token, test_user.tenant_id)

    repo = BoardPackRepository()
    run = await repo.create_run(
        db=async_session,
        tenant_id=test_user.tenant_id,
        definition_id=uuid.UUID(definition["id"]),
        period_start=datetime(2026, 1, 1, tzinfo=UTC).date(),
        period_end=datetime(2026, 1, 31, tzinfo=UTC).date(),
        triggered_by=test_user.id,
    )
    async_session.add(
        BoardPackGeneratorSection(
            run_id=run.id,
            tenant_id=test_user.tenant_id,
            section_type="PROFIT_AND_LOSS",
            section_order=1,
            data_snapshot={"title": "P&L", "payload": {"value": "1"}},
            section_hash="c" * 64,
        )
    )
    await async_session.commit()

    response = await async_client.get(
        f"/api/v1/board-packs/runs/{run.id}/sections",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code == 200
    first_item = response.json()["data"][0]
    assert "data_snapshot" not in first_item


@pytest.mark.integration
@pytest.mark.asyncio
async def test_t_044_download_pdf_artifact_returns_file(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_access_token: str,
    test_user,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _relax_board_pack_schema(async_session)
    from financeops.db.models.board_pack_generator import BoardPackGeneratorArtifact
    import financeops.modules.board_pack_generator.api.routes as board_pack_api_routes_module
    import financeops.modules.board_pack_generator.infrastructure.repository as board_pack_repository_module
    from financeops.modules.board_pack_generator.infrastructure.repository import BoardPackRepository

    monkeypatch.setattr(
        board_pack_api_routes_module,
        "settings",
        SimpleNamespace(ARTIFACTS_BASE_DIR=str(tmp_path)),
    )
    monkeypatch.setattr(
        board_pack_repository_module,
        "settings",
        SimpleNamespace(ARTIFACTS_BASE_DIR=str(tmp_path)),
    )

    await set_tenant_context(async_session, test_user.tenant_id)
    definition = await _create_definition(async_client, test_access_token, test_user.tenant_id)
    repo = BoardPackRepository()
    run = await repo.create_run(
        db=async_session,
        tenant_id=test_user.tenant_id,
        definition_id=uuid.UUID(definition["id"]),
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
        triggered_by=test_user.id,
    )
    storage_path = f"artifacts/board_packs/{test_user.tenant_id}/{run.id}/board_pack.pdf"
    file_path = tmp_path / storage_path
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_bytes(b"%PDF-1.4\ncontent\n")

    async_session.add(
        BoardPackGeneratorArtifact(
            run_id=run.id,
            tenant_id=test_user.tenant_id,
            format="PDF",
            storage_path=storage_path,
            file_size_bytes=file_path.stat().st_size,
            checksum="d" * 64,
        )
    )
    await async_session.commit()

    response = await async_client.get(
        f"/api/v1/board-packs/runs/{run.id}/download/pdf",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/pdf")
    assert response.content.startswith(b"%PDF")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_t_045_delete_definition_then_active_only_list_returns_404(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_access_token: str,
    test_user,
) -> None:
    await _relax_board_pack_schema(async_session)
    definition = await _create_definition(async_client, test_access_token, test_user.tenant_id)

    delete_response = await async_client.delete(
        f"/api/v1/board-packs/definitions/{definition['id']}",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert delete_response.status_code == 204

    list_response = await async_client.get(
        "/api/v1/board-packs/definitions?active_only=true",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert list_response.status_code == 404


@pytest.mark.integration
@pytest.mark.asyncio
async def test_t_045b_update_definition_uses_governed_pipeline(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_access_token: str,
    test_user,
) -> None:
    await _relax_board_pack_schema(async_session)
    definition = await _create_definition(async_client, test_access_token, test_user.tenant_id)

    response = await async_client.patch(
        f"/api/v1/board-packs/definitions/{definition['id']}",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={"description": "updated via intent"},
    )
    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["intent_id"]
    assert payload["job_id"]
    assert payload["description"] == "updated via intent"
    await set_tenant_context(async_session, test_user.tenant_id)
    row = await async_session.get(BoardPackGeneratorDefinition, uuid.UUID(definition["id"]))
    assert row is not None
    assert row.recorded_by_job_id is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_t_046_generate_rejects_inactive_definition(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_access_token: str,
    test_user,
) -> None:
    await _relax_board_pack_schema(async_session)
    from financeops.modules.board_pack_generator.infrastructure.repository import BoardPackRepository

    await set_tenant_context(async_session, test_user.tenant_id)
    definition = await _create_definition(async_client, test_access_token, test_user.tenant_id)

    repo = BoardPackRepository()
    await repo.deactivate_definition(
        db=async_session,
        tenant_id=test_user.tenant_id,
        definition_id=uuid.UUID(definition["id"]),
    )
    await async_session.commit()

    response = await async_client.post(
        "/api/v1/board-packs/generate",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={
            "definition_id": definition["id"],
            "period_start": "2026-01-01",
            "period_end": "2026-01-31",
        },
    )

    assert response.status_code == 400


@pytest.mark.integration
@pytest.mark.asyncio
async def test_t_047_definitions_are_tenant_isolated_in_list(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_access_token: str,
    test_user,
) -> None:
    await _relax_board_pack_schema(async_session)
    from financeops.modules.board_pack_generator.domain.enums import PeriodType, SectionType
    from financeops.modules.board_pack_generator.domain.pack_definition import (
        PackDefinitionSchema,
        SectionConfig,
    )
    from financeops.modules.board_pack_generator.infrastructure.repository import BoardPackRepository

    tenant_b_id = uuid.uuid4()
    tenant_b_user_id = uuid.uuid4()

    tenant_b = IamTenant(
        id=tenant_b_id,
        tenant_id=tenant_b_id,
        display_name="Tenant B",
        tenant_type=TenantType.direct,
        country="US",
        timezone="UTC",
        status=TenantStatus.active,
        chain_hash=compute_chain_hash(
            {
                "display_name": "Tenant B",
                "tenant_type": TenantType.direct.value,
                "country": "US",
                "timezone": "UTC",
            },
            GENESIS_HASH,
        ),
        previous_hash=GENESIS_HASH,
    )
    async_session.add(tenant_b)
    async_session.add(
        IamUser(
            id=tenant_b_user_id,
            tenant_id=tenant_b_id,
            email=f"tenantb_{uuid.uuid4().hex[:8]}@example.com",
            hashed_password=hash_password("TestPass123!"),
            full_name="Tenant B User",
            role=UserRole.finance_leader,
            is_active=True,
            mfa_enabled=False,
        )
    )
    await async_session.flush()

    repo = BoardPackRepository()
    await set_tenant_context(async_session, test_user.tenant_id)
    await repo.create_definition(
        db=async_session,
        tenant_id=test_user.tenant_id,
        schema=PackDefinitionSchema(
            name="Tenant A Def",
            section_configs=[SectionConfig(section_type=SectionType.PROFIT_AND_LOSS, order=1)],
            entity_ids=[uuid.uuid4()],
            period_type=PeriodType.MONTHLY,
            config={},
        ),
        created_by=test_user.id,
    )

    await set_tenant_context(async_session, tenant_b_id)
    await repo.create_definition(
        db=async_session,
        tenant_id=tenant_b_id,
        schema=PackDefinitionSchema(
            name="Tenant B Def",
            section_configs=[SectionConfig(section_type=SectionType.PROFIT_AND_LOSS, order=1)],
            entity_ids=[uuid.uuid4()],
            period_type=PeriodType.MONTHLY,
            config={},
        ),
        created_by=tenant_b_user_id,
    )
    await async_session.commit()

    response = await async_client.get(
        "/api/v1/board-packs/definitions",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )

    assert response.status_code == 200
    names = [item["name"] for item in response.json()["data"]]
    assert "Tenant A Def" in names
    assert "Tenant B Def" not in names
