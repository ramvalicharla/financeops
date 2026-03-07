from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.payroll_gl_reconciliation_phase1f3_1_helpers import (
    ensure_tenant_context,
)


async def _insert_mapping(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    organisation_id: uuid.UUID,
    mapping_code: str,
    supersedes_id: uuid.UUID | None,
    status: str,
    effective_from: date,
    row_id: uuid.UUID | None = None,
) -> uuid.UUID:
    row_id = row_id or uuid.uuid4()
    await session.execute(
        text(
            """
            INSERT INTO payroll_gl_reconciliation_mappings
              (id, tenant_id, chain_hash, previous_hash, organisation_id, mapping_code,
               mapping_name, payroll_metric_code, gl_account_selector_json, cost_center_rule_json,
               department_rule_json, entity_rule_json, effective_from, supersedes_id, status, created_by)
            VALUES
              (:id, :tenant_id, :chain_hash, :previous_hash, :organisation_id, :mapping_code,
               :mapping_name, :payroll_metric_code, CAST(:selector AS jsonb), '{}'::jsonb,
               '{}'::jsonb, '{}'::jsonb, :effective_from, :supersedes_id, :status, :created_by)
            """
        ),
        {
            "id": str(row_id),
            "tenant_id": str(tenant_id),
            "chain_hash": "1" * 64,
            "previous_hash": "0" * 64,
            "organisation_id": str(organisation_id),
            "mapping_code": mapping_code,
            "mapping_name": mapping_code,
            "payroll_metric_code": "gross_pay",
            "selector": '{"account_codes":["5000"]}',
            "effective_from": effective_from,
            "supersedes_id": str(supersedes_id) if supersedes_id else None,
            "status": status,
            "created_by": str(tenant_id),
        },
    )
    return row_id


async def _insert_rule(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    organisation_id: uuid.UUID,
    rule_code: str,
    supersedes_id: uuid.UUID | None,
    status: str,
    effective_from: date,
    row_id: uuid.UUID | None = None,
) -> uuid.UUID:
    row_id = row_id or uuid.uuid4()
    await session.execute(
        text(
            """
            INSERT INTO payroll_gl_reconciliation_rules
              (id, tenant_id, chain_hash, previous_hash, organisation_id, rule_code, rule_name,
               rule_type, tolerance_json, materiality_json, timing_window_json,
               classification_behavior_json, effective_from, supersedes_id, status, created_by)
            VALUES
              (:id, :tenant_id, :chain_hash, :previous_hash, :organisation_id, :rule_code, :rule_name,
               'aggregate_tie_rule', '{}'::jsonb, '{}'::jsonb, '{}'::jsonb,
               '{}'::jsonb, :effective_from, :supersedes_id, :status, :created_by)
            """
        ),
        {
            "id": str(row_id),
            "tenant_id": str(tenant_id),
            "chain_hash": "1" * 64,
            "previous_hash": "0" * 64,
            "organisation_id": str(organisation_id),
            "rule_code": rule_code,
            "rule_name": rule_code,
            "effective_from": effective_from,
            "supersedes_id": str(supersedes_id) if supersedes_id else None,
            "status": status,
            "created_by": str(tenant_id),
        },
    )
    return row_id


@pytest.mark.asyncio
@pytest.mark.integration
async def test_mapping_allows_valid_linear_supersession(
    payroll_gl_recon_phase1f3_1_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(payroll_gl_recon_phase1f3_1_session, tenant_id)
    mapping_code = f"M_LINEAR_{uuid.uuid4().hex[:8]}"
    v1 = await _insert_mapping(
        payroll_gl_recon_phase1f3_1_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        mapping_code=mapping_code,
        supersedes_id=None,
        status="active",
        effective_from=date(2026, 1, 1),
    )
    v2 = await _insert_mapping(
        payroll_gl_recon_phase1f3_1_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        mapping_code=mapping_code,
        supersedes_id=v1,
        status="candidate",
        effective_from=date(2026, 2, 1),
    )
    assert v2 is not None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_mapping_rejects_self_supersession(
    payroll_gl_recon_phase1f3_1_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(payroll_gl_recon_phase1f3_1_session, tenant_id)
    row_id = uuid.uuid4()
    with pytest.raises(DBAPIError, match="self-supersession"):
        await _insert_mapping(
            payroll_gl_recon_phase1f3_1_session,
            tenant_id=tenant_id,
            organisation_id=tenant_id,
            mapping_code="M_SELF",
            supersedes_id=row_id,
            status="candidate",
            effective_from=date(2026, 1, 1),
            row_id=row_id,
        )
        await payroll_gl_recon_phase1f3_1_session.flush()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_mapping_rejects_cross_code_supersession(
    payroll_gl_recon_phase1f3_1_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(payroll_gl_recon_phase1f3_1_session, tenant_id)
    parent = await _insert_mapping(
        payroll_gl_recon_phase1f3_1_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        mapping_code=f"M_CROSS_A_{uuid.uuid4().hex[:6]}",
        supersedes_id=None,
        status="active",
        effective_from=date(2026, 1, 1),
    )
    with pytest.raises(DBAPIError, match="across mapping codes"):
        await _insert_mapping(
            payroll_gl_recon_phase1f3_1_session,
            tenant_id=tenant_id,
            organisation_id=tenant_id,
            mapping_code=f"M_CROSS_B_{uuid.uuid4().hex[:6]}",
            supersedes_id=parent,
            status="candidate",
            effective_from=date(2026, 2, 1),
        )
        await payroll_gl_recon_phase1f3_1_session.flush()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_mapping_rejects_branching_supersession(
    payroll_gl_recon_phase1f3_1_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(payroll_gl_recon_phase1f3_1_session, tenant_id)
    mapping_code = f"M_BRANCH_{uuid.uuid4().hex[:6]}"
    parent = await _insert_mapping(
        payroll_gl_recon_phase1f3_1_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        mapping_code=mapping_code,
        supersedes_id=None,
        status="active",
        effective_from=date(2026, 1, 1),
    )
    await _insert_mapping(
        payroll_gl_recon_phase1f3_1_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        mapping_code=mapping_code,
        supersedes_id=parent,
        status="candidate",
        effective_from=date(2026, 2, 1),
    )
    with pytest.raises(DBAPIError, match="branching"):
        await _insert_mapping(
            payroll_gl_recon_phase1f3_1_session,
            tenant_id=tenant_id,
            organisation_id=tenant_id,
            mapping_code=mapping_code,
            supersedes_id=parent,
            status="candidate",
            effective_from=date(2026, 3, 1),
        )
        await payroll_gl_recon_phase1f3_1_session.flush()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_mapping_rejects_cyclic_supersession(
    payroll_gl_recon_phase1f3_1_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(payroll_gl_recon_phase1f3_1_session, tenant_id)
    mapping_code = f"M_CYCLE_{uuid.uuid4().hex[:6]}"
    a_id = uuid.uuid4()
    await _insert_mapping(
        payroll_gl_recon_phase1f3_1_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        mapping_code=mapping_code,
        supersedes_id=None,
        status="active",
        effective_from=date(2026, 1, 1),
        row_id=a_id,
    )
    b_id = await _insert_mapping(
        payroll_gl_recon_phase1f3_1_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        mapping_code=mapping_code,
        supersedes_id=a_id,
        status="candidate",
        effective_from=date(2026, 2, 1),
    )
    with pytest.raises(DBAPIError, match="cycle"):
        await _insert_mapping(
            payroll_gl_recon_phase1f3_1_session,
            tenant_id=tenant_id,
            organisation_id=tenant_id,
            mapping_code=mapping_code,
            supersedes_id=b_id,
            status="candidate",
            effective_from=date(2026, 3, 1),
            row_id=a_id,
        )
        await payroll_gl_recon_phase1f3_1_session.flush()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_mapping_rejects_second_active_version_for_same_code(
    payroll_gl_recon_phase1f3_1_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(payroll_gl_recon_phase1f3_1_session, tenant_id)
    mapping_code = f"M_ACTIVE_{uuid.uuid4().hex[:6]}"
    await _insert_mapping(
        payroll_gl_recon_phase1f3_1_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        mapping_code=mapping_code,
        supersedes_id=None,
        status="active",
        effective_from=date(2026, 1, 1),
    )
    with pytest.raises(IntegrityError, match="uq_payroll_gl_recon_mappings_one_active"):
        await _insert_mapping(
            payroll_gl_recon_phase1f3_1_session,
            tenant_id=tenant_id,
            organisation_id=tenant_id,
            mapping_code=mapping_code,
            supersedes_id=None,
            status="active",
            effective_from=date(2026, 2, 1),
        )
        await payroll_gl_recon_phase1f3_1_session.flush()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_rule_rejects_self_supersession(
    payroll_gl_recon_phase1f3_1_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(payroll_gl_recon_phase1f3_1_session, tenant_id)
    rule_id = uuid.uuid4()
    with pytest.raises(DBAPIError, match="self-supersession"):
        await _insert_rule(
            payroll_gl_recon_phase1f3_1_session,
            tenant_id=tenant_id,
            organisation_id=tenant_id,
            rule_code="R_SELF",
            supersedes_id=rule_id,
            status="candidate",
            effective_from=date(2026, 1, 1),
            row_id=rule_id,
        )
        await payroll_gl_recon_phase1f3_1_session.flush()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_rule_rejects_cross_code_supersession(
    payroll_gl_recon_phase1f3_1_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(payroll_gl_recon_phase1f3_1_session, tenant_id)
    parent = await _insert_rule(
        payroll_gl_recon_phase1f3_1_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        rule_code=f"R_CROSS_A_{uuid.uuid4().hex[:6]}",
        supersedes_id=None,
        status="active",
        effective_from=date(2026, 1, 1),
    )
    with pytest.raises(DBAPIError, match="across rule codes"):
        await _insert_rule(
            payroll_gl_recon_phase1f3_1_session,
            tenant_id=tenant_id,
            organisation_id=tenant_id,
            rule_code=f"R_CROSS_B_{uuid.uuid4().hex[:6]}",
            supersedes_id=parent,
            status="candidate",
            effective_from=date(2026, 2, 1),
        )
        await payroll_gl_recon_phase1f3_1_session.flush()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_rule_rejects_second_active_version_for_same_code(
    payroll_gl_recon_phase1f3_1_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(payroll_gl_recon_phase1f3_1_session, tenant_id)
    rule_code = f"R_ACTIVE_{uuid.uuid4().hex[:6]}"
    await _insert_rule(
        payroll_gl_recon_phase1f3_1_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        rule_code=rule_code,
        supersedes_id=None,
        status="active",
        effective_from=date(2026, 1, 1),
    )
    with pytest.raises(IntegrityError, match="uq_payroll_gl_recon_rules_one_active"):
        await _insert_rule(
            payroll_gl_recon_phase1f3_1_session,
            tenant_id=tenant_id,
            organisation_id=tenant_id,
            rule_code=rule_code,
            supersedes_id=None,
            status="active",
            effective_from=date(2026, 2, 1),
        )
        await payroll_gl_recon_phase1f3_1_session.flush()
