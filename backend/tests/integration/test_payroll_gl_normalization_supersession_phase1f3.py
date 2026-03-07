from __future__ import annotations

import uuid

import pytest
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.normalization_phase1f3_helpers import (
    ensure_tenant_context,
    seed_normalization_source,
    seed_normalization_source_version,
)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_source_version_allows_valid_linear_supersession(
    normalization_phase1f3_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(normalization_phase1f3_session, tenant_id)
    source = await seed_normalization_source(
        normalization_phase1f3_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        source_family="payroll",
        source_code=f"sup_linear_{uuid.uuid4().hex[:8]}",
        source_name="Payroll",
        created_by=tenant_id,
    )
    v1 = await seed_normalization_source_version(
        normalization_phase1f3_session,
        tenant_id=tenant_id,
        source_id=source.id,
        version_no=1,
        version_token_seed="sup_linear_v1",
        structure_seed="sup_linear_v1",
        status="active",
        created_by=tenant_id,
    )
    v2 = await seed_normalization_source_version(
        normalization_phase1f3_session,
        tenant_id=tenant_id,
        source_id=source.id,
        version_no=2,
        version_token_seed="sup_linear_v2",
        structure_seed="sup_linear_v2",
        status="superseded",
        supersedes_id=v1.id,
        created_by=tenant_id,
    )
    v3 = await seed_normalization_source_version(
        normalization_phase1f3_session,
        tenant_id=tenant_id,
        source_id=source.id,
        version_no=3,
        version_token_seed="sup_linear_v3",
        structure_seed="sup_linear_v3",
        status="candidate",
        supersedes_id=v2.id,
        created_by=tenant_id,
    )
    await normalization_phase1f3_session.flush()
    assert v3.supersedes_id == v2.id


@pytest.mark.asyncio
@pytest.mark.integration
async def test_source_version_rejects_self_supersession(
    normalization_phase1f3_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(normalization_phase1f3_session, tenant_id)
    source = await seed_normalization_source(
        normalization_phase1f3_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        source_family="gl",
        source_code=f"sup_self_{uuid.uuid4().hex[:8]}",
        source_name="GL",
        created_by=tenant_id,
    )
    version_id = uuid.uuid4()
    with pytest.raises(DBAPIError, match="self-supersession"):
        await seed_normalization_source_version(
            normalization_phase1f3_session,
            tenant_id=tenant_id,
            source_id=source.id,
            version_no=1,
            version_token_seed="sup_self_v1",
            structure_seed="sup_self_v1",
            status="candidate",
            supersedes_id=version_id,
            row_id=version_id,
            created_by=tenant_id,
        )
        await normalization_phase1f3_session.flush()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_source_version_rejects_cross_source_supersession(
    normalization_phase1f3_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(normalization_phase1f3_session, tenant_id)
    source_a = await seed_normalization_source(
        normalization_phase1f3_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        source_family="payroll",
        source_code=f"sup_cross_a_{uuid.uuid4().hex[:8]}",
        source_name="Payroll A",
        created_by=tenant_id,
    )
    source_b = await seed_normalization_source(
        normalization_phase1f3_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        source_family="payroll",
        source_code=f"sup_cross_b_{uuid.uuid4().hex[:8]}",
        source_name="Payroll B",
        created_by=tenant_id,
    )
    v1 = await seed_normalization_source_version(
        normalization_phase1f3_session,
        tenant_id=tenant_id,
        source_id=source_a.id,
        version_no=1,
        version_token_seed="sup_cross_v1",
        structure_seed="sup_cross_v1",
        status="active",
        created_by=tenant_id,
    )
    with pytest.raises(DBAPIError, match="across normalization sources"):
        await seed_normalization_source_version(
            normalization_phase1f3_session,
            tenant_id=tenant_id,
            source_id=source_b.id,
            version_no=1,
            version_token_seed="sup_cross_v2",
            structure_seed="sup_cross_v2",
            status="candidate",
            supersedes_id=v1.id,
            created_by=tenant_id,
        )
        await normalization_phase1f3_session.flush()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_source_version_rejects_branching_supersession(
    normalization_phase1f3_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(normalization_phase1f3_session, tenant_id)
    source = await seed_normalization_source(
        normalization_phase1f3_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        source_family="payroll",
        source_code=f"sup_branch_{uuid.uuid4().hex[:8]}",
        source_name="Payroll",
        created_by=tenant_id,
    )
    v1 = await seed_normalization_source_version(
        normalization_phase1f3_session,
        tenant_id=tenant_id,
        source_id=source.id,
        version_no=1,
        version_token_seed="sup_branch_v1",
        structure_seed="sup_branch_v1",
        status="active",
        created_by=tenant_id,
    )
    await seed_normalization_source_version(
        normalization_phase1f3_session,
        tenant_id=tenant_id,
        source_id=source.id,
        version_no=2,
        version_token_seed="sup_branch_v2",
        structure_seed="sup_branch_v2",
        status="candidate",
        supersedes_id=v1.id,
        created_by=tenant_id,
    )
    with pytest.raises(DBAPIError, match="branching"):
        await seed_normalization_source_version(
            normalization_phase1f3_session,
            tenant_id=tenant_id,
            source_id=source.id,
            version_no=3,
            version_token_seed="sup_branch_v3",
            structure_seed="sup_branch_v3",
            status="candidate",
            supersedes_id=v1.id,
            created_by=tenant_id,
        )
        await normalization_phase1f3_session.flush()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_source_version_rejects_cyclic_supersession(
    normalization_phase1f3_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(normalization_phase1f3_session, tenant_id)
    source = await seed_normalization_source(
        normalization_phase1f3_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        source_family="gl",
        source_code=f"sup_cycle_{uuid.uuid4().hex[:8]}",
        source_name="GL",
        created_by=tenant_id,
    )
    a_id = uuid.uuid4()
    a = await seed_normalization_source_version(
        normalization_phase1f3_session,
        tenant_id=tenant_id,
        source_id=source.id,
        version_no=1,
        version_token_seed="sup_cycle_v1",
        structure_seed="sup_cycle_v1",
        status="active",
        row_id=a_id,
        created_by=tenant_id,
    )
    b = await seed_normalization_source_version(
        normalization_phase1f3_session,
        tenant_id=tenant_id,
        source_id=source.id,
        version_no=2,
        version_token_seed="sup_cycle_v2",
        structure_seed="sup_cycle_v2",
        status="candidate",
        supersedes_id=a.id,
        created_by=tenant_id,
    )
    with pytest.raises(DBAPIError, match="cycle"):
        await seed_normalization_source_version(
            normalization_phase1f3_session,
            tenant_id=tenant_id,
            source_id=source.id,
            version_no=3,
            version_token_seed="sup_cycle_v3",
            structure_seed="sup_cycle_v3",
            status="candidate",
            row_id=a.id,
            supersedes_id=b.id,
            created_by=tenant_id,
        )
        await normalization_phase1f3_session.flush()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_source_version_rejects_second_active_version_for_same_source(
    normalization_phase1f3_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(normalization_phase1f3_session, tenant_id)
    source = await seed_normalization_source(
        normalization_phase1f3_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        source_family="payroll",
        source_code=f"sup_active_{uuid.uuid4().hex[:8]}",
        source_name="Payroll",
        created_by=tenant_id,
    )
    await seed_normalization_source_version(
        normalization_phase1f3_session,
        tenant_id=tenant_id,
        source_id=source.id,
        version_no=1,
        version_token_seed="sup_active_v1",
        structure_seed="sup_active_v1",
        status="active",
        created_by=tenant_id,
    )
    with pytest.raises(IntegrityError, match="uq_normalization_source_versions_one_active"):
        await seed_normalization_source_version(
            normalization_phase1f3_session,
            tenant_id=tenant_id,
            source_id=source.id,
            version_no=2,
            version_token_seed="sup_active_v2",
            structure_seed="sup_active_v2",
            status="active",
            created_by=tenant_id,
        )
        await normalization_phase1f3_session.flush()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_source_version_rejects_malformed_supersedes_reference(
    normalization_phase1f3_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(normalization_phase1f3_session, tenant_id)
    source = await seed_normalization_source(
        normalization_phase1f3_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        source_family="payroll",
        source_code=f"sup_missing_{uuid.uuid4().hex[:8]}",
        source_name="Payroll",
        created_by=tenant_id,
    )
    with pytest.raises(
        DBAPIError, match="supersedes_id must reference existing source version"
    ):
        await seed_normalization_source_version(
            normalization_phase1f3_session,
            tenant_id=tenant_id,
            source_id=source.id,
            version_no=1,
            version_token_seed="sup_missing_v1",
            structure_seed="sup_missing_v1",
            status="candidate",
            supersedes_id=uuid.uuid4(),
            created_by=tenant_id,
        )
        await normalization_phase1f3_session.flush()
