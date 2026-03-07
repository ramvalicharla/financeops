from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.ratio_variance_phase1f4_helpers import ensure_tenant_context


async def _insert_metric_definition(
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
            INSERT INTO metric_definitions
              (id, tenant_id, chain_hash, previous_hash, organisation_id,
               definition_code, definition_name, metric_code, formula_type,
               formula_json, unit_type, directionality, version_token,
               effective_from, supersedes_id, status, created_by)
            VALUES
              (:id, :tenant_id, :chain_hash, :previous_hash, :organisation_id,
               :definition_code, :definition_name, :metric_code, 'sum',
               '{}'::jsonb, 'amount', 'neutral', :version_token,
               :effective_from, :supersedes_id, :status, :created_by)
            """
        ),
        {
            "id": str(row_id),
            "tenant_id": str(tenant_id),
            "chain_hash": "1" * 64,
            "previous_hash": "0" * 64,
            "organisation_id": str(organisation_id),
            "definition_code": code,
            "definition_name": code,
            "metric_code": "revenue",
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
async def test_metric_definition_allows_linear_supersession(
    ratio_phase1f4_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(ratio_phase1f4_session, tenant_id)
    code = f"MD_{uuid.uuid4().hex[:6]}"
    v1 = await _insert_metric_definition(
        ratio_phase1f4_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        code=code,
        supersedes_id=None,
        status="active",
        effective_from=date(2026, 1, 1),
    )
    v2 = await _insert_metric_definition(
        ratio_phase1f4_session,
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
async def test_metric_definition_rejects_self_cross_branch_and_second_active(
    ratio_phase1f4_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(ratio_phase1f4_session, tenant_id)

    row_id = uuid.uuid4()
    with pytest.raises(DBAPIError, match="self-supersession"):
        await _insert_metric_definition(
            ratio_phase1f4_session,
            tenant_id=tenant_id,
            organisation_id=tenant_id,
            code="MD_SELF",
            supersedes_id=row_id,
            status="candidate",
            effective_from=date(2026, 1, 1),
            row_id=row_id,
        )
        await ratio_phase1f4_session.flush()
    if ratio_phase1f4_session.in_transaction():
        await ratio_phase1f4_session.rollback()
    await ensure_tenant_context(ratio_phase1f4_session, tenant_id)

    parent = await _insert_metric_definition(
        ratio_phase1f4_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        code=f"MD_A_{uuid.uuid4().hex[:4]}",
        supersedes_id=None,
        status="active",
        effective_from=date(2026, 1, 1),
    )
    with pytest.raises(DBAPIError, match="across metric definition codes"):
        await _insert_metric_definition(
            ratio_phase1f4_session,
            tenant_id=tenant_id,
            organisation_id=tenant_id,
            code=f"MD_B_{uuid.uuid4().hex[:4]}",
            supersedes_id=parent,
            status="candidate",
            effective_from=date(2026, 2, 1),
        )
        await ratio_phase1f4_session.flush()
    if ratio_phase1f4_session.in_transaction():
        await ratio_phase1f4_session.rollback()
    await ensure_tenant_context(ratio_phase1f4_session, tenant_id)

    code = f"MD_BRANCH_{uuid.uuid4().hex[:4]}"
    p = await _insert_metric_definition(
        ratio_phase1f4_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        code=code,
        supersedes_id=None,
        status="candidate",
        effective_from=date(2026, 1, 1),
    )
    await _insert_metric_definition(
        ratio_phase1f4_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        code=code,
        supersedes_id=p,
        status="candidate",
        effective_from=date(2026, 2, 1),
    )
    with pytest.raises(DBAPIError, match="branching"):
        await _insert_metric_definition(
            ratio_phase1f4_session,
            tenant_id=tenant_id,
            organisation_id=tenant_id,
            code=code,
            supersedes_id=p,
            status="candidate",
            effective_from=date(2026, 3, 1),
        )
        await ratio_phase1f4_session.flush()
    if ratio_phase1f4_session.in_transaction():
        await ratio_phase1f4_session.rollback()
    await ensure_tenant_context(ratio_phase1f4_session, tenant_id)

    active_code = f"MD_ACTIVE_{uuid.uuid4().hex[:4]}"
    await _insert_metric_definition(
        ratio_phase1f4_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        code=active_code,
        supersedes_id=None,
        status="active",
        effective_from=date(2026, 1, 1),
    )
    with pytest.raises(IntegrityError, match="uq_metric_definitions_one_active"):
        await _insert_metric_definition(
            ratio_phase1f4_session,
            tenant_id=tenant_id,
            organisation_id=tenant_id,
            code=active_code,
            supersedes_id=None,
            status="active",
            effective_from=date(2026, 2, 1),
        )
        await ratio_phase1f4_session.flush()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_variance_trend_materiality_reject_self_supersession(
    ratio_phase1f4_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(ratio_phase1f4_session, tenant_id)

    with pytest.raises(DBAPIError, match="self-supersession"):
        row_id = uuid.uuid4()
        await ratio_phase1f4_session.execute(
            text(
                """
                INSERT INTO variance_definitions
                  (id, tenant_id, chain_hash, previous_hash, organisation_id,
                   definition_code, definition_name, metric_code, comparison_type,
                   configuration_json, version_token, effective_from, supersedes_id,
                   status, created_by)
                VALUES
                  (:id, :tenant_id, :chain_hash, :previous_hash, :organisation_id,
                   'VD_SELF', 'VD_SELF', 'revenue', 'mom_abs_pct',
                   '{}'::jsonb, :version_token, :effective_from, :supersedes_id,
                   'candidate', :created_by)
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
        await ratio_phase1f4_session.flush()
    if ratio_phase1f4_session.in_transaction():
        await ratio_phase1f4_session.rollback()
    await ensure_tenant_context(ratio_phase1f4_session, tenant_id)

    with pytest.raises(DBAPIError, match="self-supersession"):
        row_id = uuid.uuid4()
        await ratio_phase1f4_session.execute(
            text(
                """
                INSERT INTO trend_definitions
                  (id, tenant_id, chain_hash, previous_hash, organisation_id,
                   definition_code, definition_name, metric_code, trend_type,
                   window_size, configuration_json, version_token, effective_from,
                   supersedes_id, status, created_by)
                VALUES
                  (:id, :tenant_id, :chain_hash, :previous_hash, :organisation_id,
                   'TD_SELF', 'TD_SELF', 'revenue', 'rolling_average',
                   3, '{}'::jsonb, :version_token, :effective_from,
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
        await ratio_phase1f4_session.flush()
    if ratio_phase1f4_session.in_transaction():
        await ratio_phase1f4_session.rollback()
    await ensure_tenant_context(ratio_phase1f4_session, tenant_id)

    with pytest.raises(DBAPIError, match="self-supersession"):
        row_id = uuid.uuid4()
        await ratio_phase1f4_session.execute(
            text(
                """
                INSERT INTO materiality_rules
                  (id, tenant_id, chain_hash, previous_hash, organisation_id,
                   definition_code, definition_name, rule_json, version_token,
                   effective_from, supersedes_id, status, created_by)
                VALUES
                  (:id, :tenant_id, :chain_hash, :previous_hash, :organisation_id,
                   'MR_SELF', 'MR_SELF', '{}'::jsonb, :version_token,
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
        await ratio_phase1f4_session.flush()
