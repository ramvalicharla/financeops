from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.rls import set_tenant_context


@pytest.mark.asyncio
async def test_lease_runs_rls_isolates_tenant_rows(async_session: AsyncSession) -> None:
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()

    await async_session.execute(text("ALTER TABLE lease_runs ENABLE ROW LEVEL SECURITY"))
    await async_session.execute(text("ALTER TABLE lease_runs FORCE ROW LEVEL SECURITY"))
    await async_session.execute(
        text(
            """
            DO $$
            BEGIN
              IF NOT EXISTS (
                SELECT 1 FROM pg_policies
                WHERE tablename = 'lease_runs'
                  AND policyname = 'lease_runs_tenant_isolation'
              ) THEN
                CREATE POLICY lease_runs_tenant_isolation
                  ON lease_runs
                  USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid);
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
              CREATE ROLE rls_lease_probe_user NOLOGIN NOSUPERUSER NOBYPASSRLS;
            EXCEPTION
              WHEN duplicate_object THEN NULL;
            END $$;
            """
        )
    )
    await async_session.execute(text("GRANT USAGE ON SCHEMA public TO rls_lease_probe_user"))
    await async_session.execute(text("GRANT SELECT, INSERT ON lease_runs TO rls_lease_probe_user"))
    await async_session.execute(text("SET ROLE rls_lease_probe_user"))

    insert_sql = text(
        """
        INSERT INTO lease_runs (
          id, tenant_id, chain_hash, previous_hash, created_at,
          request_signature, initiated_by, configuration_json, workflow_id, correlation_id
        ) VALUES (
          :id, :tenant_id, :chain_hash, :previous_hash, :created_at,
          :request_signature, :initiated_by, :configuration_json, :workflow_id, :correlation_id
        )
        """
    )

    await set_tenant_context(async_session, tenant_a)
    await async_session.execute(
        insert_sql,
        {
            "id": str(uuid.uuid4()),
            "tenant_id": str(tenant_a),
            "chain_hash": "a" * 64,
            "previous_hash": "0" * 64,
            "created_at": datetime.now(UTC),
            "request_signature": "lease-rls-a",
            "initiated_by": str(tenant_a),
            "configuration_json": "{}",
            "workflow_id": "wf-a",
            "correlation_id": "corr-a",
        },
    )

    await set_tenant_context(async_session, tenant_b)
    await async_session.execute(
        insert_sql,
        {
            "id": str(uuid.uuid4()),
            "tenant_id": str(tenant_b),
            "chain_hash": "b" * 64,
            "previous_hash": "0" * 64,
            "created_at": datetime.now(UTC),
            "request_signature": "lease-rls-b",
            "initiated_by": str(tenant_b),
            "configuration_json": "{}",
            "workflow_id": "wf-b",
            "correlation_id": "corr-b",
        },
    )

    await set_tenant_context(async_session, tenant_a)
    rows_a = (
        await async_session.execute(text("SELECT request_signature FROM lease_runs ORDER BY request_signature"))
    ).scalars().all()

    await set_tenant_context(async_session, tenant_b)
    rows_b = (
        await async_session.execute(text("SELECT request_signature FROM lease_runs ORDER BY request_signature"))
    ).scalars().all()
    await async_session.execute(text("RESET ROLE"))

    assert rows_a == ["lease-rls-a"]
    assert rows_b == ["lease-rls-b"]
