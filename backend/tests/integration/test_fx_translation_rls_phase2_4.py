from __future__ import annotations

import uuid
from datetime import date

import asyncpg
import pytest

from tests.integration.fx_translation_phase2_4_helpers import FX_TRANSLATION_TABLES


async def _configure_probe_role(conn: asyncpg.Connection) -> None:
    await conn.execute(
        """
        DO $$
        BEGIN
          CREATE ROLE rls_fx_translation_probe_user NOLOGIN NOSUPERUSER NOBYPASSRLS;
        EXCEPTION
          WHEN duplicate_object THEN NULL;
        END $$;
        """
    )
    await conn.execute("GRANT USAGE ON SCHEMA public TO rls_fx_translation_probe_user")
    await conn.execute(
        "GRANT SELECT, INSERT ON reporting_currency_definitions TO rls_fx_translation_probe_user"
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_tenant_can_read_own_reporting_currency_definition(
    fx_translation_phase2_4_db_url: str,
) -> None:
    tenant_id = uuid.uuid4()
    conn = await asyncpg.connect(
        fx_translation_phase2_4_db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    )
    try:
        await _configure_probe_role(conn)
        await conn.execute(f"SET app.current_tenant_id = '{tenant_id}'")
        await conn.execute(
            """
            INSERT INTO reporting_currency_definitions (
                id, tenant_id, chain_hash, previous_hash, organisation_id,
                reporting_currency_code, reporting_currency_name,
                reporting_scope_type, reporting_scope_ref, version_token,
                effective_from, status, created_by
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)
            """,
            uuid.uuid4(),
            tenant_id,
            "a" * 64,
            "0" * 64,
            tenant_id,
            "USD",
            "US Dollar",
            "organisation",
            str(tenant_id),
            "tok_own_1",
            date(2026, 1, 1),
            "candidate",
            uuid.uuid4(),
        )
        await conn.execute("SET ROLE rls_fx_translation_probe_user")
        await conn.execute(f"SET app.current_tenant_id = '{tenant_id}'")
        count = await conn.fetchval("SELECT COUNT(*) FROM reporting_currency_definitions")
        assert count >= 1
    finally:
        try:
            await conn.execute("RESET ROLE")
        except Exception:
            pass
        await conn.close()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_tenant_cannot_read_other_tenant_reporting_currency_definition(
    fx_translation_phase2_4_db_url: str,
) -> None:
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    conn = await asyncpg.connect(
        fx_translation_phase2_4_db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    )
    try:
        await _configure_probe_role(conn)
        await conn.execute(f"SET app.current_tenant_id = '{tenant_b}'")
        await conn.execute(
            """
            INSERT INTO reporting_currency_definitions (
                id, tenant_id, chain_hash, previous_hash, organisation_id,
                reporting_currency_code, reporting_currency_name,
                reporting_scope_type, reporting_scope_ref, version_token,
                effective_from, status, created_by
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)
            """,
            uuid.uuid4(),
            tenant_b,
            "b" * 64,
            "0" * 64,
            tenant_b,
            "USD",
            "US Dollar",
            "organisation",
            str(tenant_b),
            "tok_other_1",
            date(2026, 1, 1),
            "candidate",
            uuid.uuid4(),
        )
        await conn.execute("SET ROLE rls_fx_translation_probe_user")
        await conn.execute(f"SET app.current_tenant_id = '{tenant_a}'")
        count = await conn.fetchval("SELECT COUNT(*) FROM reporting_currency_definitions")
        assert count == 0
    finally:
        try:
            await conn.execute("RESET ROLE")
        except Exception:
            pass
        await conn.close()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_tenant_cannot_insert_other_tenant_reporting_currency_definition(
    fx_translation_phase2_4_db_url: str,
) -> None:
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    conn = await asyncpg.connect(
        fx_translation_phase2_4_db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    )
    try:
        await _configure_probe_role(conn)
        await conn.execute("SET ROLE rls_fx_translation_probe_user")
        await conn.execute(f"SET app.current_tenant_id = '{tenant_a}'")
        with pytest.raises(asyncpg.PostgresError):
            await conn.execute(
                """
                INSERT INTO reporting_currency_definitions (
                    id, tenant_id, chain_hash, previous_hash, organisation_id,
                    reporting_currency_code, reporting_currency_name,
                    reporting_scope_type, reporting_scope_ref, version_token,
                    effective_from, status, created_by
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)
                """,
                uuid.uuid4(),
                tenant_b,
                "c" * 64,
                "0" * 64,
                tenant_b,
                "USD",
                "US Dollar",
                "organisation",
                str(tenant_b),
                "tok_insert_1",
                date(2026, 1, 1),
                "candidate",
                uuid.uuid4(),
            )
    finally:
        try:
            await conn.execute("RESET ROLE")
        except Exception:
            pass
        await conn.close()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_force_rls_active_on_all_fx_translation_tables(
    fx_translation_phase2_4_db_url: str,
) -> None:
    conn = await asyncpg.connect(
        fx_translation_phase2_4_db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    )
    try:
        rows = await conn.fetch(
            """
            SELECT relname, relrowsecurity, relforcerowsecurity
            FROM pg_class
            WHERE relname = ANY($1::text[])
            ORDER BY relname
            """,
            list(FX_TRANSLATION_TABLES),
        )
        assert len(rows) == len(FX_TRANSLATION_TABLES)
        for row in rows:
            assert row["relrowsecurity"] is True
            assert row["relforcerowsecurity"] is True
    finally:
        await conn.close()

