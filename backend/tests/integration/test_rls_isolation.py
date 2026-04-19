from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.reconciliation import GlEntry
from financeops.db.models.tenants import IamTenant, TenantStatus, TenantType
from financeops.db.rls import get_current_tenant_from_db, set_tenant_context
from financeops.db.session import clear_session_db_role, set_session_db_role
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


async def _configure_bypass_probe_role(session: AsyncSession) -> None:
    await session.execute(
        text(
            """
            DO $$
            BEGIN
              CREATE ROLE rls_gl_bypass_probe NOLOGIN NOSUPERUSER BYPASSRLS;
            EXCEPTION
              WHEN duplicate_object THEN NULL;
            END $$;
            """
        )
    )
    await session.execute(text("GRANT USAGE ON SCHEMA public TO rls_gl_bypass_probe"))
    await session.execute(text("GRANT SELECT ON gl_entries TO rls_gl_bypass_probe"))


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


async def _insert_gl_entry(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    source_ref: str,
) -> uuid.UUID:
    entry = GlEntry(
        tenant_id=tenant_id,
        chain_hash=compute_chain_hash(
            {"tenant_id": str(tenant_id), "account_code": "1000", "source_ref": source_ref},
            GENESIS_HASH,
        ),
        previous_hash=GENESIS_HASH,
        entity_id=None,
        period_year=2026,
        period_month=4,
        entity_name=f"Entity-{source_ref}",
        account_code="1000",
        account_name="Cash",
        debit_amount=Decimal("10.000000"),
        credit_amount=Decimal("0.000000"),
        description="RLS isolation probe",
        source_ref=source_ref,
        currency="USD",
        uploaded_by=uuid.uuid4(),
    )
    session.add(entry)
    await session.flush()
    return entry.id


async def _visible_gl_entry_count(
    session: AsyncSession,
    *,
    entry_id: uuid.UUID | None = None,
) -> int:
    if entry_id is None:
        return int(
            (
                await session.execute(text("SELECT COUNT(*) FROM gl_entries"))
            ).scalar_one()
        )
    return int(
        (
            await session.execute(
                text("SELECT COUNT(*) FROM gl_entries WHERE id = :id"),
                {"id": str(entry_id)},
            )
        ).scalar_one()
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_tenant_a_cannot_read_tenant_b_data(async_session: AsyncSession) -> None:
    tenant_a = await _create_tenant(async_session, slug=f"rls-test-tenant-a-{uuid.uuid4().hex[:8]}")
    tenant_b = await _create_tenant(async_session, slug=f"rls-test-tenant-b-{uuid.uuid4().hex[:8]}")

    await _ensure_gl_entries_rls_policy(async_session)
    await _configure_probe_role(async_session)
    await set_session_db_role(async_session, "rls_gl_probe_user")
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
        await clear_session_db_role(async_session)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_rls_raw_sql_requires_explicit_context_and_does_not_leak_across_sessions(
    api_session_factory,
) -> None:
    async with api_session_factory() as seed_session:
        tenant_a_id = (
            await _create_tenant(
                seed_session,
                slug=f"rls-raw-a-{uuid.uuid4().hex[:8]}",
            )
        ).id
        tenant_b_id = (
            await _create_tenant(
                seed_session,
                slug=f"rls-raw-b-{uuid.uuid4().hex[:8]}",
            )
        ).id
        await _ensure_gl_entries_rls_policy(seed_session)
        await _configure_probe_role(seed_session)
        await set_session_db_role(seed_session, "rls_gl_probe_user")
        try:
            await set_tenant_context(seed_session, tenant_a_id)
            entry_a = await _insert_gl_entry(
                seed_session,
                tenant_id=tenant_a_id,
                source_ref=f"rls-raw-a-{uuid.uuid4().hex[:8]}",
            )
            await set_tenant_context(seed_session, tenant_b_id)
            entry_b = await _insert_gl_entry(
                seed_session,
                tenant_id=tenant_b_id,
                source_ref=f"rls-raw-b-{uuid.uuid4().hex[:8]}",
            )
            await seed_session.commit()
        finally:
            await clear_session_db_role(seed_session)
            if seed_session.in_transaction():
                await seed_session.rollback()

    async with api_session_factory() as fresh_session:
        await set_session_db_role(fresh_session, "rls_gl_probe_user")
        try:
            assert await get_current_tenant_from_db(fresh_session) == ""
            assert await _visible_gl_entry_count(fresh_session) == 0

            await set_tenant_context(fresh_session, tenant_a_id)
            assert await _visible_gl_entry_count(fresh_session, entry_id=entry_a) == 1
            assert await _visible_gl_entry_count(fresh_session, entry_id=entry_b) == 0
        finally:
            await clear_session_db_role(fresh_session)
            if fresh_session.in_transaction():
                await fresh_session.rollback()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_rls_tenant_context_reapplies_across_transaction_boundaries(
    api_session_factory,
) -> None:
    async with api_session_factory() as session:
        tenant_a_id = (
            await _create_tenant(session, slug=f"rls-tx-a-{uuid.uuid4().hex[:8]}")
        ).id
        tenant_b_id = (
            await _create_tenant(session, slug=f"rls-tx-b-{uuid.uuid4().hex[:8]}")
        ).id
        await _ensure_gl_entries_rls_policy(session)
        await _configure_probe_role(session)
        await set_session_db_role(session, "rls_gl_probe_user")
        try:
            await set_tenant_context(session, tenant_a_id)
            entry_a = await _insert_gl_entry(
                session,
                tenant_id=tenant_a_id,
                source_ref=f"rls-tx-a-{uuid.uuid4().hex[:8]}",
            )
            await session.commit()

            assert await get_current_tenant_from_db(session) == str(tenant_a_id)
            assert await _visible_gl_entry_count(session, entry_id=entry_a) == 1

            await set_tenant_context(session, tenant_b_id)
            entry_b = await _insert_gl_entry(
                session,
                tenant_id=tenant_b_id,
                source_ref=f"rls-tx-b-{uuid.uuid4().hex[:8]}",
            )
            await session.commit()

            assert await get_current_tenant_from_db(session) == str(tenant_b_id)
            assert await _visible_gl_entry_count(session, entry_id=entry_a) == 0
            assert await _visible_gl_entry_count(session, entry_id=entry_b) == 1
        finally:
            await clear_session_db_role(session)
            if session.in_transaction():
                await session.rollback()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_privileged_role_behavior_is_explicit_for_rls_visibility(
    api_session_factory,
) -> None:
    async with api_session_factory() as session:
        tenant_a_id = (
            await _create_tenant(session, slug=f"rls-priv-a-{uuid.uuid4().hex[:8]}")
        ).id
        tenant_b_id = (
            await _create_tenant(session, slug=f"rls-priv-b-{uuid.uuid4().hex[:8]}")
        ).id
        await _ensure_gl_entries_rls_policy(session)
        await _configure_probe_role(session)
        await _configure_bypass_probe_role(session)

        await set_tenant_context(session, tenant_a_id)
        entry_a = await _insert_gl_entry(
            session,
            tenant_id=tenant_a_id,
            source_ref=f"rls-priv-a-{uuid.uuid4().hex[:8]}",
        )
        await set_tenant_context(session, tenant_b_id)
        entry_b = await _insert_gl_entry(
            session,
            tenant_id=tenant_b_id,
            source_ref=f"rls-priv-b-{uuid.uuid4().hex[:8]}",
        )
        await session.commit()

        await set_session_db_role(session, "rls_gl_probe_user")
        try:
            await set_tenant_context(session, tenant_a_id)
            assert await _visible_gl_entry_count(session, entry_id=entry_a) == 1
            assert await _visible_gl_entry_count(session, entry_id=entry_b) == 0
        finally:
            await clear_session_db_role(session)

        bypass_rls_enabled = (
            await session.execute(
                text("SELECT rolbypassrls FROM pg_roles WHERE rolname = 'rls_gl_bypass_probe'")
            )
        ).scalar_one()
        assert bypass_rls_enabled is True

        await set_session_db_role(session, "rls_gl_bypass_probe")
        try:
            assert await _visible_gl_entry_count(session, entry_id=entry_a) == 1
            assert await _visible_gl_entry_count(session, entry_id=entry_b) == 1
        finally:
            await clear_session_db_role(session)
            if session.in_transaction():
                await session.rollback()
