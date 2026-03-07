from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.mis_manager import MisNormalizedLine
from financeops.services.audit_writer import AuditWriter
from tests.integration.mis_phase1f1_helpers import (
    seed_mis_snapshot,
    seed_mis_template,
    seed_mis_template_version,
)
from tests.integration.reconciliation_phase1f2_helpers import (
    build_reconciliation_service,
    ensure_tenant_context,
    seed_gl_tb_pair,
)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_gl_vs_tb_reconciliation_run_is_deterministic(
    recon_phase1f2_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(recon_phase1f2_session, tenant_id)
    await seed_gl_tb_pair(
        recon_phase1f2_session, tenant_id=tenant_id, created_by=tenant_id
    )
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
    replay = await service.create_session(
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
    assert created["session_token"] == replay["session_token"]
    assert created["session_id"] == replay["session_id"]
    assert replay["idempotent"] is True

    first_run = await service.run_session(
        tenant_id=tenant_id,
        session_id=uuid.UUID(created["session_id"]),
        actor_user_id=tenant_id,
    )
    second_run = await service.run_session(
        tenant_id=tenant_id,
        session_id=uuid.UUID(created["session_id"]),
        actor_user_id=tenant_id,
    )
    assert second_run["idempotent"] is True
    assert first_run["line_count"] == second_run["line_count"]
    assert first_run["exception_count"] == second_run["exception_count"]

    lines_a = await service.list_lines(
        tenant_id=tenant_id, session_id=uuid.UUID(created["session_id"])
    )
    lines_b = await service.list_lines(
        tenant_id=tenant_id, session_id=uuid.UUID(created["session_id"])
    )
    assert lines_a == lines_b


@pytest.mark.asyncio
@pytest.mark.integration
async def test_mis_vs_tb_reconciliation_run_is_deterministic(
    recon_phase1f2_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(recon_phase1f2_session, tenant_id)
    service = build_reconciliation_service(recon_phase1f2_session)

    template = await seed_mis_template(
        recon_phase1f2_session,
        tenant_id=tenant_id,
        template_code=f"recon_mis_{uuid.uuid4().hex[:8]}",
    )
    version = await seed_mis_template_version(
        recon_phase1f2_session,
        tenant_id=tenant_id,
        template_id=template.id,
        version_no=1,
        version_token_seed="recon_mis_v1",
        structure_seed="recon_mis_v1",
        status="active",
    )
    snapshot = await seed_mis_snapshot(
        recon_phase1f2_session,
        tenant_id=tenant_id,
        template_id=template.id,
        template_version_id=version.id,
        reporting_period=date(2026, 1, 31),
        snapshot_token_seed="recon_mis_snapshot",
    )
    await AuditWriter.insert_financial_record(
        recon_phase1f2_session,
        model_class=MisNormalizedLine,
        tenant_id=tenant_id,
        record_data={"snapshot_id": str(snapshot.id), "line_no": 1},
        values={
            "snapshot_id": snapshot.id,
            "line_no": 1,
            "canonical_metric_code": "4000",
            "canonical_dimension_json": {"legal_entity": "HQ"},
            "source_row_ref": "Sheet1:r1",
            "source_column_ref": "Sheet1:c2",
            "period_value": Decimal("800"),
            "currency_code": "USD",
            "sign_applied": "as_is",
            "validation_status": "valid",
            "created_by": tenant_id,
        },
    )
    await seed_gl_tb_pair(
        recon_phase1f2_session, tenant_id=tenant_id, created_by=tenant_id
    )

    created = await service.create_session(
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        reconciliation_type="mis_vs_trial_balance",
        source_a_type="mis_snapshot",
        source_a_ref=str(snapshot.id),
        source_b_type="trial_balance_rows",
        source_b_ref="tb_seed",
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
        matching_rule_version="recon_match_v1",
        tolerance_rule_version="recon_tolerance_v1",
        materiality_config_json={"absolute_threshold": "0"},
        created_by=tenant_id,
    )
    first_run = await service.run_session(
        tenant_id=tenant_id,
        session_id=uuid.UUID(created["session_id"]),
        actor_user_id=tenant_id,
    )
    second_run = await service.run_session(
        tenant_id=tenant_id,
        session_id=uuid.UUID(created["session_id"]),
        actor_user_id=tenant_id,
    )
    assert second_run["idempotent"] is True
    assert first_run["line_count"] == second_run["line_count"]
