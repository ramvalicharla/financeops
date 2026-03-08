from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.anomaly_pattern_phase1f6_helpers import ensure_tenant_context


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
            INSERT INTO anomaly_definitions
              (id, tenant_id, chain_hash, previous_hash, organisation_id,
               anomaly_code, anomaly_name, anomaly_domain, signal_selector_json,
               definition_json, version_token, effective_from, effective_to,
               supersedes_id, status, created_by)
            VALUES
              (:id, :tenant_id, :chain_hash, :previous_hash, :organisation_id,
               :anomaly_code, :anomaly_name, 'payroll', '{}'::jsonb,
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
            "anomaly_code": code,
            "anomaly_name": code,
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
async def test_anomaly_definition_allows_valid_linear_supersession(
    anomaly_phase1f6_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(anomaly_phase1f6_session, tenant_id)
    code = f"ANOM_{uuid.uuid4().hex[:6]}"
    v1 = await _insert_definition(
        anomaly_phase1f6_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        code=code,
        supersedes_id=None,
        status="active",
        effective_from=date(2026, 1, 1),
    )
    v2 = await _insert_definition(
        anomaly_phase1f6_session,
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
async def test_anomaly_definition_rejects_self_cross_branch_and_second_active(
    anomaly_phase1f6_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(anomaly_phase1f6_session, tenant_id)

    row_id = uuid.uuid4()
    with pytest.raises(DBAPIError, match="self-supersession"):
        await _insert_definition(
            anomaly_phase1f6_session,
            tenant_id=tenant_id,
            organisation_id=tenant_id,
            code="ANOM_SELF",
            supersedes_id=row_id,
            status="candidate",
            effective_from=date(2026, 1, 1),
            row_id=row_id,
        )
        await anomaly_phase1f6_session.flush()
    if anomaly_phase1f6_session.in_transaction():
        await anomaly_phase1f6_session.rollback()
    await ensure_tenant_context(anomaly_phase1f6_session, tenant_id)

    parent = await _insert_definition(
        anomaly_phase1f6_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        code=f"ANOM_A_{uuid.uuid4().hex[:4]}",
        supersedes_id=None,
        status="active",
        effective_from=date(2026, 1, 1),
    )
    with pytest.raises(DBAPIError, match="across anomaly codes"):
        await _insert_definition(
            anomaly_phase1f6_session,
            tenant_id=tenant_id,
            organisation_id=tenant_id,
            code=f"ANOM_B_{uuid.uuid4().hex[:4]}",
            supersedes_id=parent,
            status="candidate",
            effective_from=date(2026, 2, 1),
        )
        await anomaly_phase1f6_session.flush()
    if anomaly_phase1f6_session.in_transaction():
        await anomaly_phase1f6_session.rollback()
    await ensure_tenant_context(anomaly_phase1f6_session, tenant_id)

    code = f"ANOM_BRANCH_{uuid.uuid4().hex[:4]}"
    p = await _insert_definition(
        anomaly_phase1f6_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        code=code,
        supersedes_id=None,
        status="candidate",
        effective_from=date(2026, 1, 1),
    )
    await _insert_definition(
        anomaly_phase1f6_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        code=code,
        supersedes_id=p,
        status="candidate",
        effective_from=date(2026, 2, 1),
    )
    with pytest.raises(DBAPIError, match="branching"):
        await _insert_definition(
            anomaly_phase1f6_session,
            tenant_id=tenant_id,
            organisation_id=tenant_id,
            code=code,
            supersedes_id=p,
            status="candidate",
            effective_from=date(2026, 3, 1),
        )
        await anomaly_phase1f6_session.flush()
    if anomaly_phase1f6_session.in_transaction():
        await anomaly_phase1f6_session.rollback()
    await ensure_tenant_context(anomaly_phase1f6_session, tenant_id)

    active_code = f"ANOM_ACTIVE_{uuid.uuid4().hex[:4]}"
    await _insert_definition(
        anomaly_phase1f6_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        code=active_code,
        supersedes_id=None,
        status="active",
        effective_from=date(2026, 1, 1),
    )
    with pytest.raises(IntegrityError, match="uq_anomaly_definitions_one_active"):
        await _insert_definition(
            anomaly_phase1f6_session,
            tenant_id=tenant_id,
            organisation_id=tenant_id,
            code=active_code,
            supersedes_id=None,
            status="active",
            effective_from=date(2026, 2, 1),
        )
        await anomaly_phase1f6_session.flush()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_rules_reject_self_supersession(
    anomaly_phase1f6_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(anomaly_phase1f6_session, tenant_id)

    with pytest.raises(DBAPIError, match="self-supersession"):
        row_id = uuid.uuid4()
        await anomaly_phase1f6_session.execute(
            text(
                """
                INSERT INTO anomaly_pattern_rules
                  (id, tenant_id, chain_hash, previous_hash, organisation_id,
                   rule_code, rule_name, pattern_signature_json, classification_behavior_json,
                   version_token, effective_from, supersedes_id, status, created_by)
                VALUES
                  (:id, :tenant_id, :chain_hash, :previous_hash, :organisation_id,
                   'APR_SELF', 'APR_SELF', '{}'::jsonb, '{}'::jsonb,
                   :version_token, :effective_from, :supersedes_id, 'candidate', :created_by)
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
        await anomaly_phase1f6_session.flush()

    if anomaly_phase1f6_session.in_transaction():
        await anomaly_phase1f6_session.rollback()
    await ensure_tenant_context(anomaly_phase1f6_session, tenant_id)

    with pytest.raises(DBAPIError, match="self-supersession"):
        row_id = uuid.uuid4()
        await anomaly_phase1f6_session.execute(
            text(
                """
                INSERT INTO anomaly_statistical_rules
                  (id, tenant_id, chain_hash, previous_hash, organisation_id,
                   rule_code, rule_name, rolling_window, baseline_type, z_threshold,
                   regime_shift_threshold_pct, seasonal_period, seasonal_adjustment_flag,
                   benchmark_group_id, configuration_json, version_token, effective_from,
                   supersedes_id, status, created_by)
                VALUES
                  (:id, :tenant_id, :chain_hash, :previous_hash, :organisation_id,
                   'ASR_SELF', 'ASR_SELF', 3, 'rolling_mean', 1.5,
                   0.15, 12, false,
                   NULL, '{}'::jsonb, :version_token, :effective_from,
                   :supersedes_id, 'candidate', :created_by)
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
        await anomaly_phase1f6_session.flush()
