from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.requests import Request

from financeops.api import deps as deps_module
from financeops.db.rls import set_tenant_context
from financeops.db import session as session_module


@pytest.mark.asyncio
async def test_get_async_session_sets_rls_context(engine, monkeypatch):
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    def fake_async_session_local():
        return session_factory()

    monkeypatch.setattr(deps_module, "AsyncSessionLocal", fake_async_session_local)

    scope = {"type": "http", "method": "GET", "path": "/", "headers": []}
    request = Request(scope)
    tenant_id = str(uuid.uuid4())
    request.state.tenant_id = tenant_id

    generator = deps_module.get_async_session(request)
    session = await anext(generator)
    result = await session.execute(
        text("SELECT current_setting('app.current_tenant_id', true)")
    )
    assert result.scalar() == tenant_id
    await generator.aclose()


@pytest.mark.asyncio
async def test_tenant_session_helper_sets_rls_context(engine, monkeypatch):
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    def fake_async_session_local():
        return session_factory()

    monkeypatch.setattr(session_module, "AsyncSessionLocal", fake_async_session_local)

    tenant_id = str(uuid.uuid4())
    async with session_module.tenant_session(tenant_id) as session:
        result = await session.execute(
            text("SELECT current_setting('app.current_tenant_id', true)")
        )
        assert result.scalar() == tenant_id


@pytest.mark.asyncio
async def test_rls_blocks_cross_tenant_reads(async_session: AsyncSession):
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()

    await async_session.execute(
        text(
            """
            CREATE TABLE rls_runtime_probe (
              id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
              tenant_id uuid NOT NULL,
              payload text NOT NULL
            )
            """
        )
    )
    await async_session.execute(
        text("ALTER TABLE rls_runtime_probe ENABLE ROW LEVEL SECURITY")
    )
    await async_session.execute(
        text("ALTER TABLE rls_runtime_probe FORCE ROW LEVEL SECURITY")
    )
    await async_session.execute(
        text(
            """
            CREATE POLICY rls_runtime_probe_tenant_isolation
              ON rls_runtime_probe
              USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
            """
        )
    )
    await async_session.execute(
        text(
            """
            DO $$
            BEGIN
              CREATE ROLE rls_probe_user NOLOGIN NOSUPERUSER NOBYPASSRLS;
            EXCEPTION
              WHEN duplicate_object THEN NULL;
            END $$;
            """
        )
    )
    await async_session.execute(text("GRANT USAGE ON SCHEMA public TO rls_probe_user"))
    await async_session.execute(
        text("GRANT SELECT, INSERT ON rls_runtime_probe TO rls_probe_user")
    )
    await async_session.execute(
        text(
            "GRANT USAGE, SELECT ON SEQUENCE "
            "rls_runtime_probe_id_seq TO rls_probe_user"
        )
    )
    await async_session.execute(text("SET ROLE rls_probe_user"))

    await set_tenant_context(async_session, tenant_a)
    await async_session.execute(
        text(
            "INSERT INTO rls_runtime_probe (tenant_id, payload) "
            "VALUES (:tenant_id, :payload)"
        ),
        {"tenant_id": str(tenant_a), "payload": "A"},
    )

    await set_tenant_context(async_session, tenant_b)
    await async_session.execute(
        text(
            "INSERT INTO rls_runtime_probe (tenant_id, payload) "
            "VALUES (:tenant_id, :payload)"
        ),
        {"tenant_id": str(tenant_b), "payload": "B"},
    )

    await set_tenant_context(async_session, tenant_a)
    rows_a = (
        await async_session.execute(
            text("SELECT payload FROM rls_runtime_probe ORDER BY payload")
        )
    ).scalars().all()

    await set_tenant_context(async_session, tenant_b)
    rows_b = (
        await async_session.execute(
            text("SELECT payload FROM rls_runtime_probe ORDER BY payload")
        )
    ).scalars().all()
    await async_session.execute(text("RESET ROLE"))

    assert rows_a == ["A"]
    assert rows_b == ["B"]
