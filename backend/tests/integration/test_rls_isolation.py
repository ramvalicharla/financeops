from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.reconciliation import GlEntry
from financeops.db.models.tenants import IamTenant, TenantStatus, TenantType
from financeops.db.rls import set_tenant_context
from financeops.utils.chain_hash import GENESIS_HASH, compute_chain_hash


async def _create_tenant(session: AsyncSession, *, slug: str) -> IamTenant:
    tenant_id = uuid.uuid4()
    record_data = {
        "display_name": slug,
        "tenant_type": TenantType.direct.value,
        "country": "US",
        "timezone": "UTC",
    }
    tenant = IamTenant(
        id=tenant_id,
        tenant_id=tenant_id,
        display_name=slug,
        slug=slug,
        tenant_type=TenantType.direct,
        country="US",
        timezone="UTC",
        status=TenantStatus.active,
        chain_hash=compute_chain_hash(record_data, GENESIS_HASH),
        previous_hash=GENESIS_HASH,
        org_setup_complete=True,
        org_setup_step=7,
    )
    session.add(tenant)
    await session.flush()
    return tenant


async def _configure_probe_role(session: AsyncSession) -> None:
    await session.execute(
        text(
            """
            DO $$
            BEGIN
              CREATE ROLE rls_gl_probe_user NOLOGIN NOSUPERUSER NOBYPASSRLS;
            EXCEPTION
              WHEN duplicate_object THEN NULL;
            END $$;
            """
        )
    )
    await session.execute(text("GRANT USAGE ON SCHEMA public TO rls_gl_probe_user"))
    await session.execute(text("GRANT SELECT, INSERT ON gl_entries TO rls_gl_probe_user"))


async def _ensure_gl_entries_rls_policy(session: AsyncSession) -> None:
    await session.execute(text("ALTER TABLE gl_entries ENABLE ROW LEVEL SECURITY"))
    await session.execute(text("ALTER TABLE gl_entries FORCE ROW LEVEL SECURITY"))
    await session.execute(text("DROP POLICY IF EXISTS gl_entries_tenant_isolation ON gl_entries"))
    await session.execute(
        text(
            """
            CREATE POLICY gl_entries_tenant_isolation
            ON gl_entries
            USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
            WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
            """
        )
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_tenant_a_cannot_read_tenant_b_data(async_session: AsyncSession) -> None:
    tenant_a = await _create_tenant(async_session, slug=f"rls-test-tenant-a-{uuid.uuid4().hex[:8]}")
    tenant_b = await _create_tenant(async_session, slug=f"rls-test-tenant-b-{uuid.uuid4().hex[:8]}")

    await _ensure_gl_entries_rls_policy(async_session)
    await _configure_probe_role(async_session)
    await async_session.execute(text("SET ROLE rls_gl_probe_user"))
    try:
        await set_tenant_context(async_session, tenant_a.id)
        entry = GlEntry(
            tenant_id=tenant_a.id,
            chain_hash=compute_chain_hash(
                {"tenant_id": str(tenant_a.id), "account_code": "1000", "source_ref": "rls-a"},
                GENESIS_HASH,
            ),
            previous_hash=GENESIS_HASH,
            entity_id=None,
            period_year=2026,
            period_month=4,
            entity_name="Tenant A Entity",
            account_code="1000",
            account_name="Cash",
            debit_amount=Decimal("10.000000"),
            credit_amount=Decimal("0.000000"),
            description="RLS isolation probe",
            source_ref="rls-a",
            currency="USD",
            uploaded_by=uuid.uuid4(),
        )
        async_session.add(entry)
        await async_session.flush()
        entry_id = entry.id

        async_session.expunge_all()
        await set_tenant_context(async_session, tenant_b.id)
        result = await async_session.execute(
            select(GlEntry).where(GlEntry.id == entry_id)
        )
        rows = result.scalars().all()
        assert len(rows) == 0, (
            f"RLS FAILURE: Tenant B can read Tenant A GL entry {entry_id}. "
            "Data isolation is broken."
        )
    finally:
        if async_session.in_transaction():
            await async_session.rollback()
        await async_session.execute(text("RESET ROLE"))
