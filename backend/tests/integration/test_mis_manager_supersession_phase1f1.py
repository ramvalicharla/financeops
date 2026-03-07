from __future__ import annotations

import uuid

import pytest
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.mis_phase1f1_helpers import (
    ensure_tenant_context,
    seed_mis_template,
    seed_mis_template_version,
)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_template_version_allows_valid_linear_supersession(
    mis_phase1f1_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(mis_phase1f1_session, tenant_id)
    template = await seed_mis_template(
        mis_phase1f1_session,
        tenant_id=tenant_id,
        template_code=f"sup_linear_{uuid.uuid4().hex[:8]}",
    )
    v1 = await seed_mis_template_version(
        mis_phase1f1_session,
        tenant_id=tenant_id,
        template_id=template.id,
        version_no=1,
        version_token_seed="sup_linear_v1",
        structure_seed="sup_linear_v1",
        status="active",
    )
    v2 = await seed_mis_template_version(
        mis_phase1f1_session,
        tenant_id=tenant_id,
        template_id=template.id,
        version_no=2,
        version_token_seed="sup_linear_v2",
        structure_seed="sup_linear_v2",
        status="superseded",
        supersedes_id=v1.id,
        based_on_version_id=v1.id,
    )
    v3 = await seed_mis_template_version(
        mis_phase1f1_session,
        tenant_id=tenant_id,
        template_id=template.id,
        version_no=3,
        version_token_seed="sup_linear_v3",
        structure_seed="sup_linear_v3",
        status="candidate",
        supersedes_id=v2.id,
        based_on_version_id=v2.id,
    )
    await mis_phase1f1_session.flush()
    assert v3.supersedes_id == v2.id


@pytest.mark.asyncio
@pytest.mark.integration
async def test_template_version_rejects_self_supersession(
    mis_phase1f1_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(mis_phase1f1_session, tenant_id)
    template = await seed_mis_template(
        mis_phase1f1_session,
        tenant_id=tenant_id,
        template_code=f"sup_self_{uuid.uuid4().hex[:8]}",
    )
    version_id = uuid.uuid4()
    with pytest.raises(DBAPIError, match="self-supersession"):
        await seed_mis_template_version(
            mis_phase1f1_session,
            tenant_id=tenant_id,
            template_id=template.id,
            version_no=1,
            version_token_seed="sup_self_v1",
            structure_seed="sup_self_v1",
            status="candidate",
            supersedes_id=version_id,
            row_id=version_id,
        )
        await mis_phase1f1_session.flush()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_template_version_rejects_cross_template_supersession(
    mis_phase1f1_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(mis_phase1f1_session, tenant_id)
    template_a = await seed_mis_template(
        mis_phase1f1_session,
        tenant_id=tenant_id,
        template_code=f"sup_cross_a_{uuid.uuid4().hex[:8]}",
    )
    template_b = await seed_mis_template(
        mis_phase1f1_session,
        tenant_id=tenant_id,
        template_code=f"sup_cross_b_{uuid.uuid4().hex[:8]}",
    )
    v1 = await seed_mis_template_version(
        mis_phase1f1_session,
        tenant_id=tenant_id,
        template_id=template_a.id,
        version_no=1,
        version_token_seed="sup_cross_v1",
        structure_seed="sup_cross_v1",
        status="active",
    )
    with pytest.raises(DBAPIError, match="across templates"):
        await seed_mis_template_version(
            mis_phase1f1_session,
            tenant_id=tenant_id,
            template_id=template_b.id,
            version_no=1,
            version_token_seed="sup_cross_v2",
            structure_seed="sup_cross_v2",
            status="candidate",
            supersedes_id=v1.id,
        )
        await mis_phase1f1_session.flush()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_template_version_rejects_branching_supersession(
    mis_phase1f1_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(mis_phase1f1_session, tenant_id)
    template = await seed_mis_template(
        mis_phase1f1_session,
        tenant_id=tenant_id,
        template_code=f"sup_branch_{uuid.uuid4().hex[:8]}",
    )
    v1 = await seed_mis_template_version(
        mis_phase1f1_session,
        tenant_id=tenant_id,
        template_id=template.id,
        version_no=1,
        version_token_seed="sup_branch_v1",
        structure_seed="sup_branch_v1",
        status="active",
    )
    await seed_mis_template_version(
        mis_phase1f1_session,
        tenant_id=tenant_id,
        template_id=template.id,
        version_no=2,
        version_token_seed="sup_branch_v2",
        structure_seed="sup_branch_v2",
        status="candidate",
        supersedes_id=v1.id,
    )
    with pytest.raises(DBAPIError, match="branching"):
        await seed_mis_template_version(
            mis_phase1f1_session,
            tenant_id=tenant_id,
            template_id=template.id,
            version_no=3,
            version_token_seed="sup_branch_v3",
            structure_seed="sup_branch_v3",
            status="candidate",
            supersedes_id=v1.id,
        )
        await mis_phase1f1_session.flush()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_template_version_rejects_cyclic_supersession(
    mis_phase1f1_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(mis_phase1f1_session, tenant_id)
    template = await seed_mis_template(
        mis_phase1f1_session,
        tenant_id=tenant_id,
        template_code=f"sup_cycle_{uuid.uuid4().hex[:8]}",
    )
    a_id = uuid.uuid4()
    a = await seed_mis_template_version(
        mis_phase1f1_session,
        tenant_id=tenant_id,
        template_id=template.id,
        version_no=1,
        version_token_seed="sup_cycle_v1",
        structure_seed="sup_cycle_v1",
        status="active",
        row_id=a_id,
    )
    b = await seed_mis_template_version(
        mis_phase1f1_session,
        tenant_id=tenant_id,
        template_id=template.id,
        version_no=2,
        version_token_seed="sup_cycle_v2",
        structure_seed="sup_cycle_v2",
        status="candidate",
        supersedes_id=a.id,
    )
    # Reusing a's id triggers the cycle check before PK uniqueness validation.
    with pytest.raises(DBAPIError, match="cycle"):
        await seed_mis_template_version(
            mis_phase1f1_session,
            tenant_id=tenant_id,
            template_id=template.id,
            version_no=3,
            version_token_seed="sup_cycle_v3",
            structure_seed="sup_cycle_v3",
            status="candidate",
            row_id=a.id,
            supersedes_id=b.id,
        )
        await mis_phase1f1_session.flush()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_template_version_rejects_second_active_version_for_same_template(
    mis_phase1f1_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(mis_phase1f1_session, tenant_id)
    template = await seed_mis_template(
        mis_phase1f1_session,
        tenant_id=tenant_id,
        template_code=f"sup_active_{uuid.uuid4().hex[:8]}",
    )
    await seed_mis_template_version(
        mis_phase1f1_session,
        tenant_id=tenant_id,
        template_id=template.id,
        version_no=1,
        version_token_seed="sup_active_v1",
        structure_seed="sup_active_v1",
        status="active",
    )
    with pytest.raises(IntegrityError, match="uq_mis_template_versions_one_active"):
        await seed_mis_template_version(
            mis_phase1f1_session,
            tenant_id=tenant_id,
            template_id=template.id,
            version_no=2,
            version_token_seed="sup_active_v2",
            structure_seed="sup_active_v2",
            status="active",
        )
        await mis_phase1f1_session.flush()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_template_version_rejects_malformed_supersedes_reference(
    mis_phase1f1_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(mis_phase1f1_session, tenant_id)
    template = await seed_mis_template(
        mis_phase1f1_session,
        tenant_id=tenant_id,
        template_code=f"sup_missing_{uuid.uuid4().hex[:8]}",
    )
    with pytest.raises(DBAPIError, match="supersedes_id must reference an existing version"):
        await seed_mis_template_version(
            mis_phase1f1_session,
            tenant_id=tenant_id,
            template_id=template.id,
            version_no=1,
            version_token_seed="sup_missing_v1",
            structure_seed="sup_missing_v1",
            status="candidate",
            supersedes_id=uuid.uuid4(),
        )
        await mis_phase1f1_session.flush()
