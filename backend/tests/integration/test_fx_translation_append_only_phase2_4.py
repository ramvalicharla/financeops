from __future__ import annotations

import uuid
from datetime import date

import asyncpg
import pytest


@pytest.mark.asyncio
@pytest.mark.integration
async def test_append_only_rejects_update_on_reporting_currency_definitions(
    fx_translation_phase2_4_db_url: str,
) -> None:
    tenant_id = uuid.uuid4()
    conn = await asyncpg.connect(
        fx_translation_phase2_4_db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    )
    try:
        await conn.execute(f"SET app.current_tenant_id = '{tenant_id}'")
        definition_id = uuid.uuid4()
        await conn.execute(
            """
            INSERT INTO reporting_currency_definitions (
                id, tenant_id, chain_hash, previous_hash, organisation_id,
                reporting_currency_code, reporting_currency_name,
                reporting_scope_type, reporting_scope_ref, version_token,
                effective_from, status, created_by
            )
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)
            """,
            definition_id,
            tenant_id,
            "f" * 64,
            "0" * 64,
            tenant_id,
            "USD",
            "US Dollar",
            "organisation",
            str(tenant_id),
            "ver_rpt_usd_1",
            date(2026, 1, 1),
            "candidate",
            uuid.uuid4(),
        )
        with pytest.raises(asyncpg.PostgresError, match="append-only"):
            await conn.execute(
                "UPDATE reporting_currency_definitions SET reporting_currency_name = $1 WHERE id = $2",
                "Changed",
                definition_id,
            )
    finally:
        await conn.close()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_append_only_rejects_update_on_fx_translation_runs(
    fx_translation_phase2_4_db_url: str,
) -> None:
    tenant_id = uuid.uuid4()
    conn = await asyncpg.connect(
        fx_translation_phase2_4_db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    )
    try:
        await conn.execute(f"SET app.current_tenant_id = '{tenant_id}'")
        run_id = uuid.uuid4()
        await conn.execute(
            """
            INSERT INTO fx_translation_runs (
                id, tenant_id, chain_hash, previous_hash, organisation_id,
                reporting_period, reporting_currency_code,
                reporting_currency_version_token, translation_rule_version_token,
                rate_policy_version_token, rate_source_version_token,
                source_consolidation_run_refs_json, run_token, run_status,
                created_by
            )
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12::jsonb,$13,$14,$15)
            """,
            run_id,
            tenant_id,
            "a" * 64,
            "0" * 64,
            tenant_id,
            date(2026, 1, 31),
            "USD",
            "rpt_ver_1",
            "trl_ver_1",
            "pol_ver_1",
            "src_ver_1",
            '[{"source_type":"consolidation_run","run_id":"00000000-0000-0000-0000-000000000001"}]',
            "run_tok_1",
            "created",
            uuid.uuid4(),
        )
        with pytest.raises(asyncpg.PostgresError, match="append-only"):
            await conn.execute(
                "UPDATE fx_translation_runs SET run_status = $1 WHERE id = $2",
                "failed",
                run_id,
            )
    finally:
        await conn.close()

