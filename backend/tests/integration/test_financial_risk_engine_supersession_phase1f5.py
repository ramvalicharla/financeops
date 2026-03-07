from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.financial_risk_phase1f5_helpers import ensure_tenant_context


async def _insert_definition(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    organisation_id: uuid.UUID,
    code: str,
    supersedes_id: uuid.UUID | None,
    status: str,
    effective_from: date,
    row_id: uuid.UUID | None = None,
) -> uuid.UUID:
    row_id = row_id or uuid.uuid4()
    await session.execute(
        text(
            """
            INSERT INTO risk_definitions
              (id, tenant_id, chain_hash, previous_hash, organisation_id,
               risk_code, risk_name, risk_domain, signal_selector_json,
               definition_json, version_token, effective_from, effective_to,
               supersedes_id, status, created_by)
            VALUES
              (:id, :tenant_id, :chain_hash, :previous_hash, :organisation_id,
               :risk_code, :risk_name, 'payroll', '{}'::jsonb,
               '{}'::jsonb, :version_token, :effective_from, NULL,
               :supersedes_id, :status, :created_by)
            """
        ),
        {
            "id": str(row_id),
            "tenant_id": str(tenant_id),
            "chain_hash": "1" * 64,
            "previous_hash": "0" * 64,
            "organisation_id": str(organisation_id),
            "risk_code": code,
            "risk_name": code,
            "version_token": uuid.uuid4().hex,
            "effective_from": effective_from,
            "supersedes_id": str(supersedes_id) if supersedes_id else None,
            "status": status,
            "created_by": str(tenant_id),
        },
    )
    return row_id


@pytest.mark.asyncio
@pytest.mark.integration
async def test_risk_definition_allows_linear_supersession(
    financial_risk_phase1f5_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(financial_risk_phase1f5_session, tenant_id)
    code = f"RISK_{uuid.uuid4().hex[:6]}"
    v1 = await _insert_definition(
        financial_risk_phase1f5_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        code=code,
        supersedes_id=None,
        status="active",
        effective_from=date(2026, 1, 1),
    )
    v2 = await _insert_definition(
        financial_risk_phase1f5_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        code=code,
        supersedes_id=v1,
        status="candidate",
        effective_from=date(2026, 2, 1),
    )
    assert v2 is not None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_risk_definition_rejects_self_cross_branch_and_second_active(
    financial_risk_phase1f5_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(financial_risk_phase1f5_session, tenant_id)

    row_id = uuid.uuid4()
    with pytest.raises(DBAPIError, match="self-supersession"):
        await _insert_definition(
            financial_risk_phase1f5_session,
            tenant_id=tenant_id,
            organisation_id=tenant_id,
            code="RISK_SELF",
            supersedes_id=row_id,
            status="candidate",
            effective_from=date(2026, 1, 1),
            row_id=row_id,
        )
        await financial_risk_phase1f5_session.flush()
    if financial_risk_phase1f5_session.in_transaction():
        await financial_risk_phase1f5_session.rollback()
    await ensure_tenant_context(financial_risk_phase1f5_session, tenant_id)

    parent = await _insert_definition(
        financial_risk_phase1f5_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        code=f"RISK_A_{uuid.uuid4().hex[:4]}",
        supersedes_id=None,
        status="active",
        effective_from=date(2026, 1, 1),
    )
    with pytest.raises(DBAPIError, match="across risk codes"):
        await _insert_definition(
            financial_risk_phase1f5_session,
            tenant_id=tenant_id,
            organisation_id=tenant_id,
            code=f"RISK_B_{uuid.uuid4().hex[:4]}",
            supersedes_id=parent,
            status="candidate",
            effective_from=date(2026, 2, 1),
        )
        await financial_risk_phase1f5_session.flush()
    if financial_risk_phase1f5_session.in_transaction():
        await financial_risk_phase1f5_session.rollback()
    await ensure_tenant_context(financial_risk_phase1f5_session, tenant_id)

    code = f"RISK_BRANCH_{uuid.uuid4().hex[:4]}"
    p = await _insert_definition(
        financial_risk_phase1f5_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        code=code,
        supersedes_id=None,
        status="candidate",
        effective_from=date(2026, 1, 1),
    )
    await _insert_definition(
        financial_risk_phase1f5_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        code=code,
        supersedes_id=p,
        status="candidate",
        effective_from=date(2026, 2, 1),
    )
    with pytest.raises(DBAPIError, match="branching"):
        await _insert_definition(
            financial_risk_phase1f5_session,
            tenant_id=tenant_id,
            organisation_id=tenant_id,
            code=code,
            supersedes_id=p,
            status="candidate",
            effective_from=date(2026, 3, 1),
        )
        await financial_risk_phase1f5_session.flush()
    if financial_risk_phase1f5_session.in_transaction():
        await financial_risk_phase1f5_session.rollback()
    await ensure_tenant_context(financial_risk_phase1f5_session, tenant_id)

    active_code = f"RISK_ACTIVE_{uuid.uuid4().hex[:4]}"
    await _insert_definition(
        financial_risk_phase1f5_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        code=active_code,
        supersedes_id=None,
        status="active",
        effective_from=date(2026, 1, 1),
    )
    with pytest.raises(IntegrityError, match="uq_risk_definitions_one_active"):
        await _insert_definition(
            financial_risk_phase1f5_session,
            tenant_id=tenant_id,
            organisation_id=tenant_id,
            code=active_code,
            supersedes_id=None,
            status="active",
            effective_from=date(2026, 2, 1),
        )
        await financial_risk_phase1f5_session.flush()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_weight_and_materiality_reject_self_supersession(
    financial_risk_phase1f5_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(financial_risk_phase1f5_session, tenant_id)

    with pytest.raises(DBAPIError, match="self-supersession"):
        row_id = uuid.uuid4()
        await financial_risk_phase1f5_session.execute(
            text(
                """
                INSERT INTO risk_weight_configurations
                  (id, tenant_id, chain_hash, previous_hash, organisation_id,
                   weight_code, risk_code, scope_type, scope_value, weight_value,
                   board_critical_override, configuration_json, version_token,
                   effective_from, supersedes_id, status, created_by)
                VALUES
                  (:id, :tenant_id, :chain_hash, :previous_hash, :organisation_id,
                   'W_SELF', '*', 'global', NULL, 1,
                   false, '{}'::jsonb, :version_token,
                   :effective_from, :supersedes_id, 'candidate', :created_by)
                """
            ),
            {
                "id": str(row_id),
                "tenant_id": str(tenant_id),
                "chain_hash": "1" * 64,
                "previous_hash": "0" * 64,
                "organisation_id": str(tenant_id),
                "version_token": uuid.uuid4().hex,
                "effective_from": date(2026, 1, 1),
                "supersedes_id": str(row_id),
                "created_by": str(tenant_id),
            },
        )
        await financial_risk_phase1f5_session.flush()
    if financial_risk_phase1f5_session.in_transaction():
        await financial_risk_phase1f5_session.rollback()
    await ensure_tenant_context(financial_risk_phase1f5_session, tenant_id)

    with pytest.raises(DBAPIError, match="self-supersession"):
        row_id = uuid.uuid4()
        await financial_risk_phase1f5_session.execute(
            text(
                """
                INSERT INTO risk_materiality_rules
                  (id, tenant_id, chain_hash, previous_hash, organisation_id,
                   rule_code, rule_name, threshold_json, severity_mapping_json,
                   propagation_behavior_json, escalation_rule_json, version_token,
                   effective_from, supersedes_id, status, created_by)
                VALUES
                  (:id, :tenant_id, :chain_hash, :previous_hash, :organisation_id,
                   'M_SELF', 'M_SELF', '{}'::jsonb, '{}'::jsonb,
                   '{}'::jsonb, '{}'::jsonb, :version_token,
                   :effective_from, :supersedes_id, 'candidate', :created_by)
                """
            ),
            {
                "id": str(row_id),
                "tenant_id": str(tenant_id),
                "chain_hash": "1" * 64,
                "previous_hash": "0" * 64,
                "organisation_id": str(tenant_id),
                "version_token": uuid.uuid4().hex,
                "effective_from": date(2026, 1, 1),
                "supersedes_id": str(row_id),
                "created_by": str(tenant_id),
            },
        )
        await financial_risk_phase1f5_session.flush()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_dependency_rejects_cycles(
    financial_risk_phase1f5_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(financial_risk_phase1f5_session, tenant_id)

    a = await _insert_definition(
        financial_risk_phase1f5_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        code=f"RISK_CYA_{uuid.uuid4().hex[:4]}",
        supersedes_id=None,
        status="active",
        effective_from=date(2026, 1, 1),
    )
    b = await _insert_definition(
        financial_risk_phase1f5_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        code=f"RISK_CYB_{uuid.uuid4().hex[:4]}",
        supersedes_id=None,
        status="active",
        effective_from=date(2026, 1, 1),
    )

    await financial_risk_phase1f5_session.execute(
        text(
            """
            INSERT INTO risk_definition_dependencies
              (id, tenant_id, chain_hash, previous_hash, risk_definition_id,
               dependency_type, depends_on_risk_definition_id, signal_reference_code,
               propagation_factor, amplification_rule_json, attenuation_rule_json,
               cap_limit, created_by)
            VALUES
              (:id, :tenant_id, :chain_hash, :previous_hash, :risk_definition_id,
               'risk_result', :depends_on_risk_definition_id, NULL,
               1, '{}'::jsonb, '{}'::jsonb,
               1, :created_by)
            """
        ),
        {
            "id": str(uuid.uuid4()),
            "tenant_id": str(tenant_id),
            "chain_hash": "1" * 64,
            "previous_hash": "0" * 64,
            "risk_definition_id": str(a),
            "depends_on_risk_definition_id": str(b),
            "created_by": str(tenant_id),
        },
    )

    with pytest.raises(DBAPIError, match="cycle"):
        await financial_risk_phase1f5_session.execute(
            text(
                """
                INSERT INTO risk_definition_dependencies
                  (id, tenant_id, chain_hash, previous_hash, risk_definition_id,
                   dependency_type, depends_on_risk_definition_id, signal_reference_code,
                   propagation_factor, amplification_rule_json, attenuation_rule_json,
                   cap_limit, created_by)
                VALUES
                  (:id, :tenant_id, :chain_hash, :previous_hash, :risk_definition_id,
                   'risk_result', :depends_on_risk_definition_id, NULL,
                   1, '{}'::jsonb, '{}'::jsonb,
                   1, :created_by)
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "tenant_id": str(tenant_id),
                "chain_hash": "1" * 64,
                "previous_hash": "0" * 64,
                "risk_definition_id": str(b),
                "depends_on_risk_definition_id": str(a),
                "created_by": str(tenant_id),
            },
        )
        await financial_risk_phase1f5_session.flush()
