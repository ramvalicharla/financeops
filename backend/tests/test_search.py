from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.security import create_access_token
from financeops.modules.expense_management.service import submit_claim
from financeops.modules.search.indexers.anomaly_indexer import index_anomaly
from financeops.modules.search.indexers.expense_indexer import index_expense
from financeops.modules.search.models import SearchIndexEntry
from financeops.modules.search.service import reindex_tenant, search, upsert_index_entry


def _auth_headers(user) -> dict[str, str]:  # type: ignore[no-untyped-def]
    token = create_access_token(user.id, user.tenant_id, user.role.value)
    return {"Authorization": f"Bearer {token}"}


@dataclass
class _AnomalyStub:
    id: uuid.UUID
    tenant_id: uuid.UUID
    anomaly_name: str
    severity: str
    anomaly_domain: str
    status_note: str
    alert_status: str
    anomaly_code: str


@pytest.mark.asyncio
async def test_upsert_index_entry_creates_record(async_session: AsyncSession, test_user) -> None:  # type: ignore[no-untyped-def]
    row = await upsert_index_entry(
        async_session,
        tenant_id=test_user.tenant_id,
        entity_type="expense_claim",
        entity_id=uuid.uuid4(),
        title="Vendor A - INR 100",
        subtitle="Meals",
        body="Lunch claim",
        url="/expenses/1",
    )
    assert row.id is not None


@pytest.mark.asyncio
async def test_upsert_index_entry_is_idempotent(async_session: AsyncSession, test_user) -> None:  # type: ignore[no-untyped-def]
    entity_id = uuid.uuid4()
    await upsert_index_entry(
        async_session,
        tenant_id=test_user.tenant_id,
        entity_type="expense_claim",
        entity_id=entity_id,
        title="First",
        subtitle=None,
        body=None,
        url="/expenses/1",
    )
    await upsert_index_entry(
        async_session,
        tenant_id=test_user.tenant_id,
        entity_type="expense_claim",
        entity_id=entity_id,
        title="Second",
        subtitle=None,
        body=None,
        url="/expenses/1",
    )
    rows = (
        await async_session.execute(
            select(SearchIndexEntry).where(
                SearchIndexEntry.tenant_id == test_user.tenant_id,
                SearchIndexEntry.entity_type == "expense_claim",
                SearchIndexEntry.entity_id == entity_id,
            )
        )
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].title == "Second"


@pytest.mark.asyncio
async def test_index_expense_creates_searchable_entry(async_session: AsyncSession, test_user) -> None:  # type: ignore[no-untyped-def]
    claim = await submit_claim(
        async_session,
        tenant_id=test_user.tenant_id,
        submitted_by=test_user.id,
        vendor_name="Search Vendor",
        description="Travel expenses",
        category="travel",
        amount=Decimal("100.00"),
        currency="INR",
        claim_date=date(2025, 3, 17),
        has_receipt=True,
    )
    await index_expense(async_session, claim)
    row = (
        await async_session.execute(
            select(SearchIndexEntry).where(
                SearchIndexEntry.entity_type == "expense_claim",
                SearchIndexEntry.entity_id == claim.id,
            )
        )
    ).scalar_one_or_none()
    assert row is not None
    assert "/expenses/" in row.url


@pytest.mark.asyncio
async def test_index_anomaly_creates_entry(async_session: AsyncSession, test_user) -> None:  # type: ignore[no-untyped-def]
    stub = _AnomalyStub(
        id=uuid.uuid4(),
        tenant_id=test_user.tenant_id,
        anomaly_name="EBITDA variance",
        severity="high",
        anomaly_domain="profitability",
        status_note="Investigate variance",
        alert_status="OPEN",
        anomaly_code="ANM-001",
    )
    await index_anomaly(async_session, stub)  # type: ignore[arg-type]
    row = (
        await async_session.execute(
            select(SearchIndexEntry).where(
                SearchIndexEntry.entity_type == "anomaly",
                SearchIndexEntry.entity_id == stub.id,
            )
        )
    ).scalar_one_or_none()
    assert row is not None


@pytest.mark.asyncio
async def test_deactivated_entity_excluded_from_search(async_session: AsyncSession, test_user) -> None:  # type: ignore[no-untyped-def]
    row = await upsert_index_entry(
        async_session,
        tenant_id=test_user.tenant_id,
        entity_type="expense_claim",
        entity_id=uuid.uuid4(),
        title="Hidden Entry",
        subtitle=None,
        body=None,
        url="/expenses/hidden",
    )
    row.is_active = False
    await async_session.flush()
    results = await search(async_session, test_user.tenant_id, "Hidden Entry")
    assert all(item["entity_id"] != str(row.entity_id) for item in results)


@pytest.mark.asyncio
async def test_search_index_rls(async_session: AsyncSession, test_user) -> None:  # type: ignore[no-untyped-def]
    other_tenant = uuid.uuid4()
    await upsert_index_entry(
        async_session,
        tenant_id=other_tenant,
        entity_type="expense_claim",
        entity_id=uuid.uuid4(),
        title="Other tenant item",
        subtitle=None,
        body=None,
        url="/expenses/other",
    )
    results = await search(async_session, test_user.tenant_id, "Other tenant item")
    assert results == []


@pytest.mark.asyncio
async def test_search_returns_relevant_results(async_session: AsyncSession, test_user) -> None:  # type: ignore[no-untyped-def]
    await upsert_index_entry(
        async_session,
        tenant_id=test_user.tenant_id,
        entity_type="fdd_engagement",
        entity_id=uuid.uuid4(),
        title="EBITDA variance Q3",
        subtitle="FDD",
        body="Deep variance analysis",
        url="/advisory/fdd/1",
    )
    results = await search(async_session, test_user.tenant_id, "EBITDA variance")
    assert any("EBITDA variance Q3" == row["title"] for row in results)


@pytest.mark.asyncio
async def test_search_empty_query_returns_recent(async_session: AsyncSession, test_user) -> None:  # type: ignore[no-untyped-def]
    await upsert_index_entry(
        async_session,
        tenant_id=test_user.tenant_id,
        entity_type="expense_claim",
        entity_id=uuid.uuid4(),
        title="Recent One",
        subtitle=None,
        body=None,
        url="/expenses/1",
    )
    rows = await search(async_session, test_user.tenant_id, "")
    assert rows


@pytest.mark.asyncio
async def test_search_filters_by_entity_type(async_session: AsyncSession, test_user) -> None:  # type: ignore[no-untyped-def]
    await upsert_index_entry(
        async_session,
        tenant_id=test_user.tenant_id,
        entity_type="expense_claim",
        entity_id=uuid.uuid4(),
        title="Filter expense",
        subtitle=None,
        body=None,
        url="/expenses/1",
    )
    await upsert_index_entry(
        async_session,
        tenant_id=test_user.tenant_id,
        entity_type="anomaly",
        entity_id=uuid.uuid4(),
        title="Filter anomaly",
        subtitle=None,
        body=None,
        url="/anomalies/1",
    )
    rows = await search(async_session, test_user.tenant_id, "Filter", entity_types=["expense_claim"])
    assert rows
    assert all(row["entity_type"] == "expense_claim" for row in rows)


@pytest.mark.asyncio
async def test_search_rank_orders_results(async_session: AsyncSession, test_user) -> None:  # type: ignore[no-untyped-def]
    await upsert_index_entry(
        async_session,
        tenant_id=test_user.tenant_id,
        entity_type="expense_claim",
        entity_id=uuid.uuid4(),
        title="Exact EBITDA variance",
        subtitle="",
        body="",
        url="/expenses/1",
    )
    await upsert_index_entry(
        async_session,
        tenant_id=test_user.tenant_id,
        entity_type="expense_claim",
        entity_id=uuid.uuid4(),
        title="EBITDA",
        subtitle="variance maybe",
        body="partial",
        url="/expenses/2",
    )
    rows = await search(async_session, test_user.tenant_id, "Exact EBITDA variance")
    assert rows[0]["title"] == "Exact EBITDA variance"


@pytest.mark.asyncio
async def test_search_tenant_scoped(async_session: AsyncSession, test_user) -> None:  # type: ignore[no-untyped-def]
    shared_id = uuid.uuid4()
    await upsert_index_entry(
        async_session,
        tenant_id=test_user.tenant_id,
        entity_type="expense_claim",
        entity_id=shared_id,
        title="Scoped item",
        subtitle=None,
        body=None,
        url="/expenses/1",
    )
    await upsert_index_entry(
        async_session,
        tenant_id=uuid.uuid4(),
        entity_type="expense_claim",
        entity_id=uuid.uuid4(),
        title="Scoped item",
        subtitle=None,
        body=None,
        url="/expenses/2",
    )
    rows = await search(async_session, test_user.tenant_id, "Scoped item")
    assert rows
    assert all(row["url"] == "/expenses/1" for row in rows)


@pytest.mark.asyncio
async def test_search_limit_respected(async_session: AsyncSession, test_user) -> None:  # type: ignore[no-untyped-def]
    for idx in range(20):
        await upsert_index_entry(
            async_session,
            tenant_id=test_user.tenant_id,
            entity_type="expense_claim",
            entity_id=uuid.uuid4(),
            title=f"Limit item {idx}",
            subtitle=None,
            body=None,
            url=f"/expenses/{idx}",
        )
    rows = await search(async_session, test_user.tenant_id, "Limit item", limit=5)
    assert len(rows) == 5


@pytest.mark.asyncio
async def test_search_short_query_handled(async_session: AsyncSession, test_user) -> None:  # type: ignore[no-untyped-def]
    rows = await search(async_session, test_user.tenant_id, "a")
    assert isinstance(rows, list)


@pytest.mark.asyncio
async def test_full_text_search_across_body(async_session: AsyncSession, test_user) -> None:  # type: ignore[no-untyped-def]
    await upsert_index_entry(
        async_session,
        tenant_id=test_user.tenant_id,
        entity_type="expense_claim",
        entity_id=uuid.uuid4(),
        title="Normal title",
        subtitle=None,
        body="contains rarewordzeta token",
        url="/expenses/rare",
    )
    rows = await search(async_session, test_user.tenant_id, "rarewordzeta")
    assert any(row["url"] == "/expenses/rare" for row in rows)


@pytest.mark.asyncio
async def test_reindex_tenant_indexes_all_types(async_session: AsyncSession, test_user) -> None:  # type: ignore[no-untyped-def]
    await submit_claim(
        async_session,
        tenant_id=test_user.tenant_id,
        submitted_by=test_user.id,
        vendor_name="Reindex Vendor",
        description="Reindex",
        category="travel",
        amount=Decimal("50.00"),
        currency="INR",
        claim_date=date(2025, 3, 17),
        has_receipt=True,
    )
    counts = await reindex_tenant(async_session, test_user.tenant_id)
    assert "expense_claim" in counts
    assert "anomaly" in counts
    assert "checklist_task" in counts


@pytest.mark.asyncio
async def test_reindex_returns_counts(async_session: AsyncSession, test_user) -> None:  # type: ignore[no-untyped-def]
    counts = await reindex_tenant(async_session, test_user.tenant_id)
    assert isinstance(counts, dict)
    assert "expense_claim" in counts


@pytest.mark.asyncio
async def test_reindex_idempotent(async_session: AsyncSession, test_user) -> None:  # type: ignore[no-untyped-def]
    counts_first = await reindex_tenant(async_session, test_user.tenant_id)
    counts_second = await reindex_tenant(async_session, test_user.tenant_id)
    assert counts_first.keys() == counts_second.keys()


@pytest.mark.asyncio
async def test_search_endpoint_returns_results(async_client, async_session: AsyncSession, test_user) -> None:  # type: ignore[no-untyped-def]
    await upsert_index_entry(
        async_session,
        tenant_id=test_user.tenant_id,
        entity_type="expense_claim",
        entity_id=uuid.uuid4(),
        title="API searchable",
        subtitle=None,
        body=None,
        url="/expenses/api",
    )
    response = await async_client.get(
        "/api/v1/search?q=API searchable",
        headers=_auth_headers(test_user),
    )
    assert response.status_code == 200
    assert response.json()["data"]


@pytest.mark.asyncio
async def test_search_endpoint_empty_query(async_client, test_user) -> None:  # type: ignore[no-untyped-def]
    response = await async_client.get("/api/v1/search?q=", headers=_auth_headers(test_user))
    assert response.status_code == 200
    assert isinstance(response.json()["data"], list)


@pytest.mark.asyncio
async def test_reindex_endpoint_queues_task(async_client, test_user) -> None:  # type: ignore[no-untyped-def]
    response = await async_client.post("/api/v1/search/reindex", headers=_auth_headers(test_user))
    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["status"] == "queued"
    assert isinstance(payload["task_id"], str)
