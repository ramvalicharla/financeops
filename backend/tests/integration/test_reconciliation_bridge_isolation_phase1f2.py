from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.reconciliation_phase1f2_helpers import (
    build_reconciliation_service,
    ensure_tenant_context,
    seed_gl_tb_pair,
)


ENGINE_TABLES = (
    "revenue_schedules",
    "lease_liability_schedule",
    "prepaid_amortization_schedule",
    "asset_depreciation_schedule",
)

JOURNAL_TABLES = (
    "revenue_journal_entries",
    "lease_journal_entries",
    "prepaid_journal_entries",
    "asset_journal_entries",
)


async def _table_counts(session: AsyncSession, table_names: tuple[str, ...]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for table_name in table_names:
        count = (
            await session.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
        ).scalar_one()
        counts[table_name] = int(count)
    return counts


@pytest.mark.asyncio
@pytest.mark.integration
async def test_reconciliation_bridge_run_does_not_mutate_accounting_engine_tables(
    recon_phase1f2_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(recon_phase1f2_session, tenant_id)
    await seed_gl_tb_pair(
        recon_phase1f2_session, tenant_id=tenant_id, created_by=tenant_id
    )
    before_engine = await _table_counts(recon_phase1f2_session, ENGINE_TABLES)
    before_journals = await _table_counts(recon_phase1f2_session, JOURNAL_TABLES)

    service = build_reconciliation_service(recon_phase1f2_session)
    created = await service.create_session(
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        reconciliation_type="gl_vs_trial_balance",
        source_a_type="gl_entries",
        source_a_ref="gl_seed",
        source_b_type="trial_balance_rows",
        source_b_ref="tb_seed",
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
        matching_rule_version="recon_match_v1",
        tolerance_rule_version="recon_tolerance_v1",
        materiality_config_json={"absolute_threshold": "0"},
        created_by=tenant_id,
    )
    await service.run_session(
        tenant_id=tenant_id,
        session_id=uuid.UUID(created["session_id"]),
        actor_user_id=tenant_id,
    )

    after_engine = await _table_counts(recon_phase1f2_session, ENGINE_TABLES)
    after_journals = await _table_counts(recon_phase1f2_session, JOURNAL_TABLES)
    assert before_engine == after_engine
    assert before_journals == after_journals
