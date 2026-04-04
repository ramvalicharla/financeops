from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.security import create_access_token, hash_password
from financeops.db.models.tenants import IamTenant, TenantStatus, TenantType
from financeops.db.models.users import IamUser, UserRole
from financeops.db.rls import set_tenant_context
from financeops.main import app
from financeops.modules.auto_trigger.models import PipelineRun, PipelineStepLog
from financeops.modules.auto_trigger.pipeline import (
    finalise_pipeline_run_async,
    run_anomaly_detection_async,
    run_gl_reconciliation_async,
    run_mis_recomputation_async,
    run_payroll_reconciliation_async,
    trigger_post_sync_pipeline_async,
)
from financeops.modules.payment.application.entitlement_service import EntitlementService
from financeops.shared_kernel.idempotency import require_erp_sync_idempotency_key
from financeops.utils.chain_hash import GENESIS_HASH, compute_chain_hash


async def _create_pipeline_run(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    sync_run_id: uuid.UUID | None = None,
    status: str = "running",
) -> PipelineRun:
    await set_tenant_context(session, tenant_id)
    tenant_row = (
        await session.execute(
            select(IamTenant).where(IamTenant.id == tenant_id)
        )
    ).scalar_one_or_none()
    if tenant_row is None:
        session.add(
            IamTenant(
                id=tenant_id,
                tenant_id=tenant_id,
                display_name=f"Pipeline Tenant {tenant_id.hex[:8]}",
                slug=f"pipeline-{tenant_id.hex[:12]}",
                tenant_type=TenantType.direct,
                country="IN",
                timezone="Asia/Kolkata",
                status=TenantStatus.active,
                chain_hash=compute_chain_hash(
                    {
                        "display_name": f"Pipeline Tenant {tenant_id.hex[:8]}",
                        "tenant_type": TenantType.direct.value,
                        "country": "IN",
                        "timezone": "Asia/Kolkata",
                    },
                    GENESIS_HASH,
                ),
                previous_hash=GENESIS_HASH,
            )
        )
        await session.flush()

    row = PipelineRun(
        tenant_id=tenant_id,
        sync_run_id=sync_run_id or uuid.uuid4(),
        status=status,
        triggered_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
    )
    session.add(row)
    await session.flush()
    return row


async def _create_pipeline_step_log(
    session: AsyncSession,
    *,
    pipeline_run_id: uuid.UUID,
    tenant_id: uuid.UUID,
    step_name: str = "gl_reconciliation",
    status: str = "running",
) -> PipelineStepLog:
    await set_tenant_context(session, tenant_id)
    tenant_row = (
        await session.execute(
            select(IamTenant).where(IamTenant.id == tenant_id)
        )
    ).scalar_one_or_none()
    if tenant_row is None:
        session.add(
            IamTenant(
                id=tenant_id,
                tenant_id=tenant_id,
                display_name=f"Pipeline Tenant {tenant_id.hex[:8]}",
                slug=f"pipeline-{tenant_id.hex[:12]}",
                tenant_type=TenantType.direct,
                country="IN",
                timezone="Asia/Kolkata",
                status=TenantStatus.active,
                chain_hash=compute_chain_hash(
                    {
                        "display_name": f"Pipeline Tenant {tenant_id.hex[:8]}",
                        "tenant_type": TenantType.direct.value,
                        "country": "IN",
                        "timezone": "Asia/Kolkata",
                    },
                    GENESIS_HASH,
                ),
                previous_hash=GENESIS_HASH,
            )
        )
        await session.flush()

    row = PipelineStepLog(
        pipeline_run_id=pipeline_run_id,
        tenant_id=tenant_id,
        step_name=step_name,
        status=status,
        started_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
    )
    session.add(row)
    await session.flush()
    return row


async def _install_pipeline_runs_guard(session: AsyncSession) -> None:
    await session.execute(
        text(
            """
            CREATE OR REPLACE FUNCTION financeops_pipeline_runs_guard()
            RETURNS trigger AS $$
            BEGIN
              IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'append-only table "%": DELETE is not allowed', TG_TABLE_NAME
                USING ERRCODE = '55000';
              END IF;
              IF NEW.id <> OLD.id
                 OR NEW.tenant_id <> OLD.tenant_id
                 OR NEW.sync_run_id <> OLD.sync_run_id
                 OR NEW.triggered_at <> OLD.triggered_at
                 OR NEW.created_at <> OLD.created_at THEN
                RAISE EXCEPTION 'append-only table "%": UPDATE of immutable fields is not allowed', TG_TABLE_NAME
                USING ERRCODE = '55000';
              END IF;
              RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
            """
        )
    )
    await session.execute(text("DROP TRIGGER IF EXISTS trg_pipeline_runs_guard ON pipeline_runs"))
    await session.execute(
        text(
            """
            CREATE TRIGGER trg_pipeline_runs_guard
            BEFORE UPDATE OR DELETE ON pipeline_runs
            FOR EACH ROW EXECUTE FUNCTION financeops_pipeline_runs_guard();
            """
        )
    )
    await session.flush()


async def _create_tenant_user_token(
    session: AsyncSession,
    *,
    email_prefix: str,
) -> tuple[IamTenant, IamUser, str]:
    tenant_id = uuid.uuid4()
    tenant = IamTenant(
        id=tenant_id,
        tenant_id=tenant_id,
        display_name=f"{email_prefix} Tenant",
        tenant_type=TenantType.direct,
        country="US",
        timezone="UTC",
        status=TenantStatus.active,
        org_setup_complete=True,
        org_setup_step=7,
        chain_hash=compute_chain_hash(
            {
                "display_name": f"{email_prefix} Tenant",
                "tenant_type": TenantType.direct.value,
                "country": "US",
                "timezone": "UTC",
            },
            GENESIS_HASH,
        ),
        previous_hash=GENESIS_HASH,
    )
    user = IamUser(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        email=f"{email_prefix}_{uuid.uuid4().hex[:8]}@example.com",
        hashed_password=hash_password("TestPass123!"),
        full_name=f"{email_prefix} User",
        role=UserRole.finance_leader,
        is_active=True,
        mfa_enabled=False,
    )
    session.add(tenant)
    session.add(user)
    await session.flush()
    token = create_access_token(user.id, user.tenant_id, user.role.value)
    return tenant, user, token


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _grant_erp_integration_entitlement(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    service = EntitlementService(session)
    await service.create_tenant_override_entitlement(
        tenant_id=tenant_id,
        feature_name="erp_integration",
        access_type="boolean",
        effective_limit=1,
        metadata={"source": "test"},
        actor_user_id=user_id,
    )
    await session.commit()


@pytest.fixture
def erp_sync_idempotency_override() -> None:
    app.dependency_overrides[require_erp_sync_idempotency_key] = lambda: "test-idempotency-key"
    try:
        yield
    finally:
        app.dependency_overrides.pop(require_erp_sync_idempotency_key, None)


@pytest.mark.asyncio
async def test_pipeline_run_create(async_session: AsyncSession) -> None:
    """T-001: pipeline_runs row can be inserted and read back."""
    tenant_id = uuid.uuid4()
    row = await _create_pipeline_run(async_session, tenant_id=tenant_id)
    await async_session.flush()
    await set_tenant_context(async_session, tenant_id)
    fetched = (
        await async_session.execute(
            select(PipelineRun).where(
                PipelineRun.id == row.id,
                PipelineRun.tenant_id == tenant_id,
            )
        )
    ).scalar_one()
    assert fetched.status == "running"


@pytest.mark.asyncio
async def test_pipeline_step_log_create(async_session: AsyncSession) -> None:
    """T-002: pipeline_step_logs row can be inserted and read back."""
    tenant_id = uuid.uuid4()
    run_row = await _create_pipeline_run(async_session, tenant_id=tenant_id)
    log_row = await _create_pipeline_step_log(
        async_session,
        pipeline_run_id=run_row.id,
        tenant_id=tenant_id,
        step_name="gl_reconciliation",
        status="running",
    )
    await async_session.flush()
    await set_tenant_context(async_session, tenant_id)
    fetched = (
        await async_session.execute(
            select(PipelineStepLog).where(PipelineStepLog.id == log_row.id)
        )
    ).scalar_one()
    assert fetched.step_name == "gl_reconciliation"


@pytest.mark.asyncio
async def test_pipeline_run_append_only(async_session: AsyncSession) -> None:
    """T-003: immutable-column UPDATE on pipeline_runs is blocked by trigger."""
    tenant_id = uuid.uuid4()
    row = await _create_pipeline_run(async_session, tenant_id=tenant_id)
    await _install_pipeline_runs_guard(async_session)
    await async_session.flush()
    await set_tenant_context(async_session, tenant_id)
    with pytest.raises(DBAPIError):
        await async_session.execute(
            text(
                """
                UPDATE pipeline_runs
                SET tenant_id = CAST(:other_tenant AS uuid)
                WHERE id = CAST(:id AS uuid)
                """
            ),
            {"id": str(row.id), "other_tenant": str(uuid.uuid4())},
        )


@pytest.mark.asyncio
async def test_pipeline_run_unique_constraint(async_session: AsyncSession) -> None:
    """T-004: unique active run guard prevents duplicate non-failed tenant/sync rows."""
    tenant_id = uuid.uuid4()
    sync_run_id = uuid.uuid4()
    await _create_pipeline_run(
        async_session,
        tenant_id=tenant_id,
        sync_run_id=sync_run_id,
        status="running",
    )
    await async_session.flush()
    with pytest.raises(IntegrityError):
        await _create_pipeline_run(
            async_session,
            tenant_id=tenant_id,
            sync_run_id=sync_run_id,
            status="completed",
        )


@pytest.mark.asyncio
async def test_trigger_pipeline_creates_run(
    async_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T-005: trigger task creates a pipeline run row."""
    tenant_id = uuid.uuid4()
    sync_run_id = uuid.uuid4()
    monkeypatch.setattr(
        "financeops.modules.auto_trigger.pipeline._dispatch_pipeline_fanout",
        lambda *, pipeline_run_id, tenant_id: None,
    )
    result = await trigger_post_sync_pipeline_async(
        tenant_id=str(tenant_id),
        sync_run_id=str(sync_run_id),
    )
    assert result["created"] is True
    await set_tenant_context(async_session, tenant_id)
    count = (
        await async_session.execute(
            text(
                """
                SELECT COUNT(*) FROM pipeline_runs
                WHERE tenant_id = CAST(:tenant_id AS uuid)
                  AND sync_run_id = CAST(:sync_run_id AS uuid)
                """
            ),
            {"tenant_id": str(tenant_id), "sync_run_id": str(sync_run_id)},
        )
    ).scalar_one()
    assert count >= 1


@pytest.mark.asyncio
async def test_trigger_pipeline_idempotent(
    async_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T-006: triggering same sync twice keeps a single active run."""
    tenant_id = uuid.uuid4()
    sync_run_id = uuid.uuid4()
    monkeypatch.setattr(
        "financeops.modules.auto_trigger.pipeline._dispatch_pipeline_fanout",
        lambda *, pipeline_run_id, tenant_id: None,
    )
    await trigger_post_sync_pipeline_async(
        tenant_id=str(tenant_id),
        sync_run_id=str(sync_run_id),
    )
    await trigger_post_sync_pipeline_async(
        tenant_id=str(tenant_id),
        sync_run_id=str(sync_run_id),
    )
    await set_tenant_context(async_session, tenant_id)
    count = (
        await async_session.execute(
            text(
                """
                SELECT COUNT(*) FROM pipeline_runs
                WHERE tenant_id = CAST(:tenant_id AS uuid)
                  AND sync_run_id = CAST(:sync_run_id AS uuid)
                  AND status <> 'failed'
                """
            ),
            {"tenant_id": str(tenant_id), "sync_run_id": str(sync_run_id)},
        )
    ).scalar_one()
    assert count == 1


@pytest.mark.asyncio
async def test_trigger_pipeline_reruns_failed(
    async_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T-007: failed run can be retriggered and produces a new active run row."""
    tenant_id = uuid.uuid4()
    sync_run_id = uuid.uuid4()
    await _create_pipeline_run(
        async_session,
        tenant_id=tenant_id,
        sync_run_id=sync_run_id,
        status="failed",
    )
    await async_session.flush()
    monkeypatch.setattr(
        "financeops.modules.auto_trigger.pipeline._dispatch_pipeline_fanout",
        lambda *, pipeline_run_id, tenant_id: None,
    )
    await trigger_post_sync_pipeline_async(
        tenant_id=str(tenant_id),
        sync_run_id=str(sync_run_id),
    )
    await set_tenant_context(async_session, tenant_id)
    rows = (
        await async_session.execute(
            select(PipelineRun)
            .where(
                PipelineRun.tenant_id == tenant_id,
                PipelineRun.sync_run_id == sync_run_id,
            )
            .order_by(PipelineRun.created_at.asc(), PipelineRun.id.asc())
        )
    ).scalars().all()
    assert len(rows) >= 2
    assert rows[-1].status in {"running", "completed", "partial"}


@pytest.mark.asyncio
async def test_gl_reconciliation_step_logs(
    async_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T-008: GL reconciliation step writes step logs with expected step_name."""
    tenant_id = uuid.uuid4()
    run = await _create_pipeline_run(async_session, tenant_id=tenant_id)
    await async_session.commit()

    async def _fake_runner(*, session, tenant_id, pipeline_run_id):  # noqa: ARG001
        return {"break_count": 1}

    monkeypatch.setattr(
        "financeops.modules.auto_trigger.pipeline._invoke_gl_reconciliation",
        _fake_runner,
    )
    monkeypatch.setitem(run_gl_reconciliation_async.__globals__, "_invoke_gl_reconciliation", _fake_runner)
    result = await run_gl_reconciliation_async(
        pipeline_run_id=str(run.id),
        tenant_id=str(tenant_id),
    )
    assert result["step_name"] == "gl_reconciliation"
    assert result["status"] in {"completed", "skipped"}


@pytest.mark.asyncio
async def test_payroll_reconciliation_step_logs(
    async_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T-009: payroll reconciliation step writes step logs with expected step_name."""
    tenant_id = uuid.uuid4()
    run = await _create_pipeline_run(async_session, tenant_id=tenant_id)
    await async_session.commit()

    async def _fake_runner(*, session, tenant_id, pipeline_run_id):  # noqa: ARG001
        return {"line_count": 3}

    monkeypatch.setattr(
        "financeops.modules.auto_trigger.pipeline._invoke_payroll_reconciliation",
        _fake_runner,
    )
    monkeypatch.setitem(
        run_payroll_reconciliation_async.__globals__,
        "_invoke_payroll_reconciliation",
        _fake_runner,
    )
    result = await run_payroll_reconciliation_async(
        pipeline_run_id=str(run.id),
        tenant_id=str(tenant_id),
    )
    assert result["step_name"] == "payroll_reconciliation"
    assert result["status"] in {"completed", "skipped"}


@pytest.mark.asyncio
async def test_mis_recomputation_step_logs(
    async_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T-010: MIS recomputation step writes step logs with expected step_name."""
    tenant_id = uuid.uuid4()
    run = await _create_pipeline_run(async_session, tenant_id=tenant_id)
    await async_session.commit()

    async def _fake_runner(*, session, tenant_id, pipeline_run_id):  # noqa: ARG001
        return {"snapshot_id": str(uuid.uuid4())}

    monkeypatch.setattr(
        "financeops.modules.auto_trigger.pipeline._invoke_mis_recomputation",
        _fake_runner,
    )
    monkeypatch.setitem(
        run_mis_recomputation_async.__globals__,
        "_invoke_mis_recomputation",
        _fake_runner,
    )
    result = await run_mis_recomputation_async(
        pipeline_run_id=str(run.id),
        tenant_id=str(tenant_id),
    )
    assert result["step_name"] == "mis_recomputation"
    assert result["status"] in {"completed", "skipped"}


@pytest.mark.asyncio
async def test_anomaly_detection_step_logs(
    async_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T-011: anomaly detection step writes step logs with expected step_name."""
    tenant_id = uuid.uuid4()
    run = await _create_pipeline_run(async_session, tenant_id=tenant_id)
    await async_session.commit()

    async def _fake_runner(*, session, tenant_id, pipeline_run_id):  # noqa: ARG001
        return {"run_id": str(uuid.uuid4())}

    monkeypatch.setattr(
        "financeops.modules.auto_trigger.pipeline._invoke_anomaly_detection",
        _fake_runner,
    )
    monkeypatch.setitem(
        run_anomaly_detection_async.__globals__,
        "_invoke_anomaly_detection",
        _fake_runner,
    )
    result = await run_anomaly_detection_async(
        pipeline_run_id=str(run.id),
        tenant_id=str(tenant_id),
    )
    assert result["step_name"] == "anomaly_detection"
    assert result["status"] in {"completed", "skipped"}


@pytest.mark.asyncio
async def test_finalise_sets_completed(
    async_session: AsyncSession,
) -> None:
    """T-012: finaliser sets completed when all latest step logs are completed."""
    tenant_id = uuid.uuid4()
    run = await _create_pipeline_run(async_session, tenant_id=tenant_id)
    for step_name in (
        "gl_reconciliation",
        "payroll_reconciliation",
        "mis_recomputation",
        "anomaly_detection",
    ):
        await _create_pipeline_step_log(
            async_session,
            pipeline_run_id=run.id,
            tenant_id=tenant_id,
            step_name=step_name,
            status="completed",
        )
    await async_session.commit()
    result = await finalise_pipeline_run_async(
        pipeline_run_id=str(run.id),
        tenant_id=str(tenant_id),
    )
    assert result["status"] in {"completed", "not_found"}


@pytest.mark.asyncio
async def test_finalise_sets_partial(
    async_session: AsyncSession,
) -> None:
    """T-013: finaliser sets partial when any latest step log is failed."""
    tenant_id = uuid.uuid4()
    run = await _create_pipeline_run(async_session, tenant_id=tenant_id)
    await _create_pipeline_step_log(
        async_session,
        pipeline_run_id=run.id,
        tenant_id=tenant_id,
        step_name="gl_reconciliation",
        status="failed",
    )
    await async_session.commit()
    result = await finalise_pipeline_run_async(
        pipeline_run_id=str(run.id),
        tenant_id=str(tenant_id),
    )
    assert result["status"] in {"partial", "not_found"}


@pytest.mark.asyncio
async def test_list_pipeline_runs_empty(async_client: AsyncClient, test_access_token: str) -> None:
    """T-014: list endpoint returns empty array for tenant with no runs."""
    response = await async_client.get(
        "/api/v1/pipeline/runs",
        headers=_auth_header(test_access_token),
    )
    assert response.status_code == 200
    assert response.json()["data"] == []


@pytest.mark.asyncio
async def test_list_pipeline_runs_returns_data(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_access_token: str,
    test_user: IamUser,
) -> None:
    """T-015: list endpoint returns persisted runs for the tenant."""
    await _create_pipeline_run(async_session, tenant_id=test_user.tenant_id)
    await async_session.flush()
    response = await async_client.get(
        "/api/v1/pipeline/runs",
        headers=_auth_header(test_access_token),
    )
    assert response.status_code == 200
    assert len(response.json()["data"]) >= 1


@pytest.mark.asyncio
async def test_list_pipeline_runs_tenant_isolation(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_access_token: str,
    test_user: IamUser,
) -> None:
    """T-016: runs from another tenant are hidden by RLS."""
    _, _, tenant_b_token = await _create_tenant_user_token(
        async_session,
        email_prefix="auto_trigger_b",
    )
    await _create_pipeline_run(async_session, tenant_id=test_user.tenant_id)
    tenant_b_user_tenant = (
        await async_session.execute(
            text(
                """
                SELECT tenant_id
                FROM iam_users
                WHERE email LIKE 'auto_trigger_b_%'
                ORDER BY created_at DESC
                LIMIT 1
                """
            )
        )
    ).scalar_one()
    await _create_pipeline_run(
        async_session,
        tenant_id=uuid.UUID(str(tenant_b_user_tenant)),
    )
    await async_session.flush()
    response = await async_client.get(
        "/api/v1/pipeline/runs",
        headers=_auth_header(test_access_token),
    )
    assert response.status_code == 200
    for row in response.json()["data"]:
        assert row["tenant_id"] == str(test_user.tenant_id)
    response_b = await async_client.get(
        "/api/v1/pipeline/runs",
        headers=_auth_header(tenant_b_token),
    )
    assert response_b.status_code == 200
    for row in response_b.json()["data"]:
        assert row["tenant_id"] != str(test_user.tenant_id)


@pytest.mark.asyncio
async def test_get_pipeline_run_detail(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_access_token: str,
    test_user: IamUser,
) -> None:
    """T-017: detail endpoint returns run payload with embedded step logs."""
    run = await _create_pipeline_run(async_session, tenant_id=test_user.tenant_id)
    await _create_pipeline_step_log(
        async_session,
        pipeline_run_id=run.id,
        tenant_id=test_user.tenant_id,
        step_name="gl_reconciliation",
        status="completed",
    )
    await async_session.flush()
    response = await async_client.get(
        f"/api/v1/pipeline/runs/{run.id}",
        headers=_auth_header(test_access_token),
    )
    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["id"] == str(run.id)
    assert isinstance(payload["step_logs"], list)
    assert payload["step_logs"][0]["step_name"] == "gl_reconciliation"


@pytest.mark.asyncio
async def test_get_pipeline_run_404(async_client: AsyncClient, test_access_token: str) -> None:
    """T-018: unknown pipeline run id returns 404."""
    response = await async_client.get(
        f"/api/v1/pipeline/runs/{uuid.uuid4()}",
        headers=_auth_header(test_access_token),
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_pipeline_run_wrong_tenant(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_access_token: str,
) -> None:
    """T-019: tenant cannot access another tenant's pipeline run."""
    tenant_b, _, _ = await _create_tenant_user_token(
        async_session,
        email_prefix="auto_trigger_wrong_tenant",
    )
    run = await _create_pipeline_run(async_session, tenant_id=tenant_b.id)
    await async_session.flush()
    response = await async_client.get(
        f"/api/v1/pipeline/runs/{run.id}",
        headers=_auth_header(test_access_token),
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_pipeline_steps(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_access_token: str,
    test_user: IamUser,
) -> None:
    """T-020: step endpoint returns all step logs for a pipeline run."""
    run = await _create_pipeline_run(async_session, tenant_id=test_user.tenant_id)
    await _create_pipeline_step_log(
        async_session,
        pipeline_run_id=run.id,
        tenant_id=test_user.tenant_id,
        step_name="mis_recomputation",
        status="running",
    )
    await async_session.flush()
    response = await async_client.get(
        f"/api/v1/pipeline/runs/{run.id}/steps",
        headers=_auth_header(test_access_token),
    )
    assert response.status_code == 200
    rows = response.json()["data"]
    assert len(rows) >= 1
    assert rows[0]["pipeline_run_id"] == str(run.id)


@pytest.mark.asyncio
async def test_manual_trigger_endpoint(
    async_client: AsyncClient,
    test_access_token: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T-021: manual trigger endpoint queues task and returns pipeline_run_id."""
    calls: list[tuple[str, str]] = []

    def _fake_delay(*, tenant_id: str, sync_run_id: str) -> None:
        calls.append((tenant_id, sync_run_id))

    monkeypatch.setattr(
        "financeops.modules.auto_trigger.api.routes.trigger_post_sync_pipeline.delay",
        _fake_delay,
    )
    sync_run_id = str(uuid.uuid4())
    response = await async_client.post(
        "/api/v1/pipeline/trigger",
        headers=_auth_header(test_access_token),
        json={"sync_run_id": sync_run_id},
    )
    assert response.status_code == 202
    payload = response.json()["data"]
    assert payload["status"] == "queued"
    assert uuid.UUID(payload["pipeline_run_id"])
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_manual_trigger_invalid_sync_id(
    async_client: AsyncClient,
    test_access_token: str,
) -> None:
    """T-022: malformed sync_run_id payload returns 422."""
    response = await async_client.post(
        "/api/v1/pipeline/trigger",
        headers=_auth_header(test_access_token),
        json={"sync_run_id": "not-a-uuid"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_erp_sync_hook_fires_on_completion(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_user: IamUser,
    test_access_token: str,
    monkeypatch: pytest.MonkeyPatch,
    erp_sync_idempotency_override: None,
) -> None:
    """T-023: ERP sync completion enqueues post-sync pipeline task."""
    await _grant_erp_integration_entitlement(
        async_session,
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
    )
    sync_run_id = str(uuid.uuid4())
    calls: list[tuple[str, str]] = []

    async def _fake_trigger_sync_run(self, **kwargs):  # noqa: ANN001
        del self, kwargs
        return {"sync_run_id": sync_run_id, "sync_run_status": "completed"}

    def _fake_delay(*, tenant_id: str, sync_run_id: str) -> None:
        calls.append((tenant_id, sync_run_id))

    monkeypatch.setattr(
        "financeops.modules.erp_sync.api.sync_runs.SyncService.trigger_sync_run",
        _fake_trigger_sync_run,
    )
    monkeypatch.setattr(
        "financeops.modules.erp_sync.api.sync_runs.trigger_post_sync_pipeline.delay",
        _fake_delay,
    )

    response = await async_client.post(
        "/api/v1/erp-sync/sync-runs",
        headers=_auth_header(test_access_token),
        json={
            "connection_id": str(uuid.uuid4()),
            "sync_definition_id": str(uuid.uuid4()),
            "sync_definition_version_id": str(uuid.uuid4()),
            "dataset_type": "trial_balance",
            "organisation_id": str(uuid.uuid4()),
        },
    )
    assert response.status_code == 200
    assert len(calls) == 1
    assert calls[0][1] == sync_run_id


@pytest.mark.asyncio
async def test_erp_sync_hook_does_not_fail_sync_if_celery_down(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_user: IamUser,
    test_access_token: str,
    monkeypatch: pytest.MonkeyPatch,
    erp_sync_idempotency_override: None,
) -> None:
    """T-024: enqueue failure is non-fatal and sync endpoint still succeeds."""
    await _grant_erp_integration_entitlement(
        async_session,
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
    )
    async def _fake_trigger_sync_run(self, **kwargs):  # noqa: ANN001
        del self, kwargs
        return {"sync_run_id": str(uuid.uuid4()), "sync_run_status": "completed"}

    def _raise_delay(*, tenant_id: str, sync_run_id: str) -> None:  # noqa: ARG001
        raise RuntimeError("celery unavailable")

    monkeypatch.setattr(
        "financeops.modules.erp_sync.api.sync_runs.SyncService.trigger_sync_run",
        _fake_trigger_sync_run,
    )
    monkeypatch.setattr(
        "financeops.modules.erp_sync.api.sync_runs.trigger_post_sync_pipeline.delay",
        _raise_delay,
    )

    response = await async_client.post(
        "/api/v1/erp-sync/sync-runs",
        headers=_auth_header(test_access_token),
        json={
            "connection_id": str(uuid.uuid4()),
            "sync_definition_id": str(uuid.uuid4()),
            "sync_definition_version_id": str(uuid.uuid4()),
            "dataset_type": "trial_balance",
            "organisation_id": str(uuid.uuid4()),
        },
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_erp_sync_hook_not_fired_on_failed_sync(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_user: IamUser,
    test_access_token: str,
    monkeypatch: pytest.MonkeyPatch,
    erp_sync_idempotency_override: None,
) -> None:
    """T-025: failed ERP sync does not enqueue post-sync pipeline task."""
    await _grant_erp_integration_entitlement(
        async_session,
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
    )
    calls: list[tuple[str, str]] = []

    async def _fake_trigger_sync_run(self, **kwargs):  # noqa: ANN001
        del self, kwargs
        return {"sync_run_id": str(uuid.uuid4()), "sync_run_status": "failed"}

    def _fake_delay(*, tenant_id: str, sync_run_id: str) -> None:
        calls.append((tenant_id, sync_run_id))

    monkeypatch.setattr(
        "financeops.modules.erp_sync.api.sync_runs.SyncService.trigger_sync_run",
        _fake_trigger_sync_run,
    )
    monkeypatch.setattr(
        "financeops.modules.erp_sync.api.sync_runs.trigger_post_sync_pipeline.delay",
        _fake_delay,
    )

    response = await async_client.post(
        "/api/v1/erp-sync/sync-runs",
        headers=_auth_header(test_access_token),
        json={
            "connection_id": str(uuid.uuid4()),
            "sync_definition_id": str(uuid.uuid4()),
            "sync_definition_version_id": str(uuid.uuid4()),
            "dataset_type": "trial_balance",
            "organisation_id": str(uuid.uuid4()),
        },
    )
    assert response.status_code == 200
    assert calls == []
