from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.append_only import APPEND_ONLY_TABLES
from tests.integration.payroll_gl_reconciliation_phase1f3_1_helpers import (
    build_payroll_gl_reconciliation_service,
    ensure_tenant_context,
    seed_finalized_normalization_pair,
    seed_mapping_and_rule,
)


async def _seed_reconciliation_run(
    session: AsyncSession, *, tenant_id: uuid.UUID
) -> dict[str, str]:
    await ensure_tenant_context(session, tenant_id)
    pair = await seed_finalized_normalization_pair(
        session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        created_by=tenant_id,
        reporting_period=date(2026, 1, 31),
    )
    await seed_mapping_and_rule(
        session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        created_by=tenant_id,
        effective_from=date(2026, 1, 1),
    )
    service = build_payroll_gl_reconciliation_service(session)
    created = await service.create_run(
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        payroll_run_id=uuid.UUID(pair["payroll_run_id"]),
        gl_run_id=uuid.UUID(pair["gl_run_id"]),
        reporting_period=date(2026, 1, 31),
        created_by=tenant_id,
    )
    return created


@pytest.mark.asyncio
@pytest.mark.integration
async def test_append_only_rejects_update_on_payroll_gl_reconciliation_mappings(
    payroll_gl_recon_phase1f3_1_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(payroll_gl_recon_phase1f3_1_session, tenant_id)
    await seed_mapping_and_rule(
        payroll_gl_recon_phase1f3_1_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        created_by=tenant_id,
        effective_from=date(2026, 1, 1),
    )
    mapping_id = (
        await payroll_gl_recon_phase1f3_1_session.execute(
            text("SELECT id FROM payroll_gl_reconciliation_mappings LIMIT 1")
        )
    ).scalar_one()
    with pytest.raises(DBAPIError):
        await payroll_gl_recon_phase1f3_1_session.execute(
            text(
                "UPDATE payroll_gl_reconciliation_mappings "
                "SET mapping_name='changed' WHERE id=:id"
            ),
            {"id": str(mapping_id)},
        )
        await payroll_gl_recon_phase1f3_1_session.flush()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_append_only_rejects_update_on_payroll_gl_reconciliation_rules(
    payroll_gl_recon_phase1f3_1_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(payroll_gl_recon_phase1f3_1_session, tenant_id)
    await seed_mapping_and_rule(
        payroll_gl_recon_phase1f3_1_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        created_by=tenant_id,
        effective_from=date(2026, 1, 1),
    )
    rule_id = (
        await payroll_gl_recon_phase1f3_1_session.execute(
            text("SELECT id FROM payroll_gl_reconciliation_rules LIMIT 1")
        )
    ).scalar_one()
    with pytest.raises(DBAPIError):
        await payroll_gl_recon_phase1f3_1_session.execute(
            text(
                "UPDATE payroll_gl_reconciliation_rules "
                "SET rule_name='changed' WHERE id=:id"
            ),
            {"id": str(rule_id)},
        )
        await payroll_gl_recon_phase1f3_1_session.flush()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_append_only_rejects_update_on_payroll_gl_reconciliation_runs(
    payroll_gl_recon_phase1f3_1_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    created = await _seed_reconciliation_run(
        payroll_gl_recon_phase1f3_1_session, tenant_id=tenant_id
    )
    with pytest.raises(DBAPIError):
        await payroll_gl_recon_phase1f3_1_session.execute(
            text(
                "UPDATE payroll_gl_reconciliation_runs SET status='failed' WHERE id=:id"
            ),
            {"id": created["run_id"]},
        )
        await payroll_gl_recon_phase1f3_1_session.flush()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_append_only_rejects_update_on_payroll_gl_reconciliation_run_scopes(
    payroll_gl_recon_phase1f3_1_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    created = await _seed_reconciliation_run(
        payroll_gl_recon_phase1f3_1_session, tenant_id=tenant_id
    )
    await payroll_gl_recon_phase1f3_1_session.execute(
        text(
            """
            INSERT INTO payroll_gl_reconciliation_run_scopes
              (id, tenant_id, chain_hash, previous_hash, payroll_gl_reconciliation_run_id,
               scope_code, scope_label, scope_json, created_by)
            VALUES
              (:id, :tenant_id, :chain_hash, :previous_hash, :run_id,
               'LE1', 'LE1', '{}'::jsonb, :created_by)
            """
        ),
        {
            "id": str(uuid.uuid4()),
            "tenant_id": str(tenant_id),
            "chain_hash": "0" * 64,
            "previous_hash": "0" * 64,
            "run_id": created["run_id"],
            "created_by": str(tenant_id),
        },
    )
    scope_id = (
        await payroll_gl_recon_phase1f3_1_session.execute(
            text("SELECT id FROM payroll_gl_reconciliation_run_scopes LIMIT 1")
        )
    ).scalar_one()
    with pytest.raises(DBAPIError):
        await payroll_gl_recon_phase1f3_1_session.execute(
            text(
                "UPDATE payroll_gl_reconciliation_run_scopes "
                "SET scope_label='changed' WHERE id=:id"
            ),
            {"id": str(scope_id)},
        )
        await payroll_gl_recon_phase1f3_1_session.flush()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_append_only_registry_includes_payroll_gl_reconciliation_tables() -> None:
    required = {
        "payroll_gl_reconciliation_mappings",
        "payroll_gl_reconciliation_rules",
        "payroll_gl_reconciliation_runs",
        "payroll_gl_reconciliation_run_scopes",
    }
    assert required.issubset(set(APPEND_ONLY_TABLES))

