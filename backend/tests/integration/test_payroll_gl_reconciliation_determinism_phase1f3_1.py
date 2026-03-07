from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.payroll_gl_reconciliation_phase1f3_1_helpers import (
    build_payroll_gl_reconciliation_service,
    ensure_tenant_context,
    seed_finalized_normalization_pair,
    seed_mapping_and_rule,
)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_identical_inputs_produce_identical_run_token(
    payroll_gl_recon_phase1f3_1_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(payroll_gl_recon_phase1f3_1_session, tenant_id)
    pair = await seed_finalized_normalization_pair(
        payroll_gl_recon_phase1f3_1_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        created_by=tenant_id,
        reporting_period=date(2026, 1, 31),
    )
    await seed_mapping_and_rule(
        payroll_gl_recon_phase1f3_1_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        created_by=tenant_id,
        effective_from=date(2026, 1, 1),
    )
    service = build_payroll_gl_reconciliation_service(payroll_gl_recon_phase1f3_1_session)
    first = await service.create_run(
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        payroll_run_id=uuid.UUID(pair["payroll_run_id"]),
        gl_run_id=uuid.UUID(pair["gl_run_id"]),
        reporting_period=date(2026, 1, 31),
        created_by=tenant_id,
    )
    second = await service.create_run(
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        payroll_run_id=uuid.UUID(pair["payroll_run_id"]),
        gl_run_id=uuid.UUID(pair["gl_run_id"]),
        reporting_period=date(2026, 1, 31),
        created_by=tenant_id,
    )
    assert first["run_token"] == second["run_token"]
    assert first["run_id"] == second["run_id"]
    assert second["idempotent"] is True


@pytest.mark.asyncio
@pytest.mark.integration
async def test_execute_is_idempotent_and_does_not_duplicate_lines(
    payroll_gl_recon_phase1f3_1_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(payroll_gl_recon_phase1f3_1_session, tenant_id)
    pair = await seed_finalized_normalization_pair(
        payroll_gl_recon_phase1f3_1_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        created_by=tenant_id,
        reporting_period=date(2026, 1, 31),
    )
    await seed_mapping_and_rule(
        payroll_gl_recon_phase1f3_1_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        created_by=tenant_id,
        effective_from=date(2026, 1, 1),
    )
    service = build_payroll_gl_reconciliation_service(payroll_gl_recon_phase1f3_1_session)
    created = await service.create_run(
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        payroll_run_id=uuid.UUID(pair["payroll_run_id"]),
        gl_run_id=uuid.UUID(pair["gl_run_id"]),
        reporting_period=date(2026, 1, 31),
        created_by=tenant_id,
    )
    first = await service.execute_run(
        tenant_id=tenant_id,
        run_id=uuid.UUID(created["run_id"]),
        actor_user_id=tenant_id,
    )
    second = await service.execute_run(
        tenant_id=tenant_id,
        run_id=uuid.UUID(created["run_id"]),
        actor_user_id=tenant_id,
    )
    assert second["idempotent"] is True
    assert first["line_count"] == second["line_count"]
    line_count = (
        await payroll_gl_recon_phase1f3_1_session.execute(
            text(
                """
                SELECT COUNT(*)
                FROM reconciliation_lines
                WHERE session_id=:session_id
                """
            ),
            {"session_id": first["reconciliation_session_id"]},
        )
    ).scalar_one()
    assert line_count == first["line_count"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_changed_mapping_set_changes_run_token(
    payroll_gl_recon_phase1f3_1_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(payroll_gl_recon_phase1f3_1_session, tenant_id)
    pair = await seed_finalized_normalization_pair(
        payroll_gl_recon_phase1f3_1_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        created_by=tenant_id,
        reporting_period=date(2026, 1, 31),
    )
    await seed_mapping_and_rule(
        payroll_gl_recon_phase1f3_1_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        created_by=tenant_id,
        effective_from=date(2026, 1, 1),
    )
    service = build_payroll_gl_reconciliation_service(payroll_gl_recon_phase1f3_1_session)
    first = await service.create_run(
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        payroll_run_id=uuid.UUID(pair["payroll_run_id"]),
        gl_run_id=uuid.UUID(pair["gl_run_id"]),
        reporting_period=date(2026, 1, 31),
        created_by=tenant_id,
    )
    await payroll_gl_recon_phase1f3_1_session.execute(
        text(
            """
            INSERT INTO payroll_gl_reconciliation_mappings
              (id, tenant_id, chain_hash, previous_hash, organisation_id, mapping_code,
               mapping_name, payroll_metric_code, gl_account_selector_json, cost_center_rule_json,
               department_rule_json, entity_rule_json, effective_from, supersedes_id, status, created_by)
            VALUES
              (:id, :tenant_id, :chain_hash, :previous_hash, :organisation_id, :mapping_code,
               :mapping_name, 'bonus', '{"account_codes":["5300"]}'::jsonb, '{}'::jsonb,
               '{}'::jsonb, '{}'::jsonb, :effective_from, NULL, 'active', :created_by)
            """
        ),
        {
            "id": str(uuid.uuid4()),
            "tenant_id": str(tenant_id),
            "chain_hash": "1" * 64,
            "previous_hash": "0" * 64,
            "organisation_id": str(tenant_id),
            "mapping_code": f"MAP_BONUS_{uuid.uuid4().hex[:6]}",
            "mapping_name": "Bonus",
            "effective_from": date(2026, 1, 1),
            "created_by": str(tenant_id),
        },
    )
    second = await service.create_run(
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        payroll_run_id=uuid.UUID(pair["payroll_run_id"]),
        gl_run_id=uuid.UUID(pair["gl_run_id"]),
        reporting_period=date(2026, 1, 31),
        created_by=tenant_id,
    )
    assert first["run_token"] != second["run_token"]
    assert first["run_id"] != second["run_id"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_changed_source_run_changes_run_token(
    payroll_gl_recon_phase1f3_1_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(payroll_gl_recon_phase1f3_1_session, tenant_id)
    pair_a = await seed_finalized_normalization_pair(
        payroll_gl_recon_phase1f3_1_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        created_by=tenant_id,
        reporting_period=date(2026, 1, 31),
    )
    pair_b = await seed_finalized_normalization_pair(
        payroll_gl_recon_phase1f3_1_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        created_by=tenant_id,
        reporting_period=date(2026, 1, 31),
    )
    await seed_mapping_and_rule(
        payroll_gl_recon_phase1f3_1_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        created_by=tenant_id,
        effective_from=date(2026, 1, 1),
    )
    service = build_payroll_gl_reconciliation_service(payroll_gl_recon_phase1f3_1_session)
    run_a = await service.create_run(
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        payroll_run_id=uuid.UUID(pair_a["payroll_run_id"]),
        gl_run_id=uuid.UUID(pair_a["gl_run_id"]),
        reporting_period=date(2026, 1, 31),
        created_by=tenant_id,
    )
    run_b = await service.create_run(
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        payroll_run_id=uuid.UUID(pair_b["payroll_run_id"]),
        gl_run_id=uuid.UUID(pair_b["gl_run_id"]),
        reporting_period=date(2026, 1, 31),
        created_by=tenant_id,
    )
    assert run_a["run_token"] != run_b["run_token"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_line_ordering_and_content_are_stable(
    payroll_gl_recon_phase1f3_1_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(payroll_gl_recon_phase1f3_1_session, tenant_id)
    pair = await seed_finalized_normalization_pair(
        payroll_gl_recon_phase1f3_1_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        created_by=tenant_id,
        reporting_period=date(2026, 1, 31),
    )
    await seed_mapping_and_rule(
        payroll_gl_recon_phase1f3_1_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        created_by=tenant_id,
        effective_from=date(2026, 1, 1),
    )
    service = build_payroll_gl_reconciliation_service(payroll_gl_recon_phase1f3_1_session)
    created = await service.create_run(
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        payroll_run_id=uuid.UUID(pair["payroll_run_id"]),
        gl_run_id=uuid.UUID(pair["gl_run_id"]),
        reporting_period=date(2026, 1, 31),
        created_by=tenant_id,
    )
    await service.execute_run(
        tenant_id=tenant_id,
        run_id=uuid.UUID(created["run_id"]),
        actor_user_id=tenant_id,
    )
    first = await service.list_lines(tenant_id=tenant_id, run_id=uuid.UUID(created["run_id"]))
    second = await service.list_lines(tenant_id=tenant_id, run_id=uuid.UUID(created["run_id"]))
    assert first == second

