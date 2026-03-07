from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.rls import set_tenant_context


@pytest.mark.asyncio
async def test_fx_manual_monthly_rates_rls_isolates_tenants(async_session: AsyncSession):
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()

    await async_session.execute(
        text("ALTER TABLE fx_manual_monthly_rates ENABLE ROW LEVEL SECURITY")
    )
    await async_session.execute(
        text("ALTER TABLE fx_manual_monthly_rates FORCE ROW LEVEL SECURITY")
    )
    await async_session.execute(
        text(
            """
            DO $$
            BEGIN
              IF NOT EXISTS (
                SELECT 1
                FROM pg_policies
                WHERE tablename = 'fx_manual_monthly_rates'
                  AND policyname = 'fx_manual_monthly_rates_tenant_isolation'
              ) THEN
                CREATE POLICY fx_manual_monthly_rates_tenant_isolation
                  ON fx_manual_monthly_rates
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
              CREATE ROLE rls_fx_probe_user NOLOGIN NOSUPERUSER NOBYPASSRLS;
            EXCEPTION
              WHEN duplicate_object THEN NULL;
            END $$;
            """
        )
    )
    await async_session.execute(text("GRANT USAGE ON SCHEMA public TO rls_fx_probe_user"))
    await async_session.execute(
        text("GRANT SELECT, INSERT ON fx_manual_monthly_rates TO rls_fx_probe_user")
    )
    await async_session.execute(text("SET ROLE rls_fx_probe_user"))

    insert_sql = text(
        """
        INSERT INTO fx_manual_monthly_rates (
          id, tenant_id, chain_hash, previous_hash, created_at,
          period_year, period_month, base_currency, quote_currency, rate,
          entered_by, reason, supersedes_rate_id, source_type, is_month_end_locked, correlation_id
        ) VALUES (
          :id, :tenant_id, :chain_hash, :previous_hash, :created_at,
          :period_year, :period_month, :base_currency, :quote_currency, :rate,
          :entered_by, :reason, :supersedes_rate_id, :source_type, :is_month_end_locked, :correlation_id
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
            "period_year": 2026,
            "period_month": 3,
            "base_currency": "USD",
            "quote_currency": "INR",
            "rate": Decimal("83.100000"),
            "entered_by": str(tenant_a),
            "reason": "tenant-a",
            "supersedes_rate_id": None,
            "source_type": "manual",
            "is_month_end_locked": False,
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
            "period_year": 2026,
            "period_month": 3,
            "base_currency": "USD",
            "quote_currency": "INR",
            "rate": Decimal("83.200000"),
            "entered_by": str(tenant_b),
            "reason": "tenant-b",
            "supersedes_rate_id": None,
            "source_type": "manual",
            "is_month_end_locked": False,
            "correlation_id": "corr-b",
        },
    )

    await set_tenant_context(async_session, tenant_a)
    rows_a = (
        await async_session.execute(
            text("SELECT reason FROM fx_manual_monthly_rates ORDER BY reason")
        )
    ).scalars().all()

    await set_tenant_context(async_session, tenant_b)
    rows_b = (
        await async_session.execute(
            text("SELECT reason FROM fx_manual_monthly_rates ORDER BY reason")
        )
    ).scalars().all()
    await async_session.execute(text("RESET ROLE"))

    assert rows_a == ["tenant-a"]
    assert rows_b == ["tenant-b"]
