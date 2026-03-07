from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import ValidationError
from financeops.services.consolidation.lineage_resolver import resolve_lineage
from tests.utils.consolidation_seed import seed_consolidation_drill_dataset


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("record_type_key", "id_key"),
    (
        ("consolidation_result", "result_4000_id"),
        ("consolidation_line_item", "line_item_a_id"),
        ("intercompany_pair", "pair_id"),
        ("elimination", "elimination_id"),
        ("snapshot_line", "snapshot_line_a_id"),
    ),
)
async def test_lineage_resolver_returns_deterministic_ancestry(
    async_session: AsyncSession,
    test_tenant,
    test_user,
    record_type_key: str,
    id_key: str,
) -> None:
    seeded = await seed_consolidation_drill_dataset(
        async_session,
        tenant_id=test_tenant.id,
        user_id=test_user.id,
        correlation_id="corr-lineage",
    )

    payload = await resolve_lineage(
        async_session,
        tenant_id=test_tenant.id,
        record_type=record_type_key,
        record_id=seeded[id_key],
    )

    assert payload["record_type"] == record_type_key
    assert payload["ancestry"]
    assert payload["ancestry"][0]["record_type"] in {"consolidation_run", "snapshot"}


@pytest.mark.asyncio
async def test_lineage_resolver_rejects_unsupported_record_type(
    async_session: AsyncSession,
    test_tenant,
) -> None:
    with pytest.raises(ValidationError):
        await resolve_lineage(
            async_session,
            tenant_id=test_tenant.id,
            record_type="unsupported",
            record_id=test_tenant.id,
        )
