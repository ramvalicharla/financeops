from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.utils.consolidation_seed import seed_consolidation_drill_dataset


@pytest.mark.asyncio
async def test_consolidation_drill_flow_end_to_end(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_tenant,
    test_user,
    test_access_token: str,
) -> None:
    seeded = await seed_consolidation_drill_dataset(
        async_session,
        tenant_id=test_tenant.id,
        user_id=test_user.id,
        correlation_id="corr-drill-flow",
    )
    run_id = seeded["run_id"]

    account_response = await async_client.get(
        f"/api/v1/consolidation/run/{run_id}/accounts/4000",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert account_response.status_code == 200
    account_payload = account_response.json()["data"]
    assert account_payload["child_entity_ids"]
    assert account_payload["parent_reference_id"] == str(run_id)
    assert account_payload["source_reference_id"] == "4000"

    entity_id = account_payload["child_entity_ids"][0]
    entity_response = await async_client.get(
        f"/api/v1/consolidation/run/{run_id}/entities/{entity_id}",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert entity_response.status_code == 200
    entity_payload = entity_response.json()["data"]
    assert entity_payload["child_line_item_ids"]

    line_item_id = entity_payload["child_line_item_ids"][0]
    line_item_response = await async_client.get(
        f"/api/v1/consolidation/run/{run_id}/line-items/{line_item_id}",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert line_item_response.status_code == 200
    line_payload = line_item_response.json()["data"]
    assert line_payload["child_snapshot_line_id"]
    assert line_payload["source_reference_id"] == line_payload["child_snapshot_line_id"]

    snapshot_response = await async_client.get(
        f"/api/v1/consolidation/run/{run_id}/snapshot-lines/{line_payload['child_snapshot_line_id']}",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert snapshot_response.status_code == 200
    snapshot_payload = snapshot_response.json()["data"]
    assert snapshot_payload["snapshot_line"]["snapshot_line_id"] == line_payload["child_snapshot_line_id"]

