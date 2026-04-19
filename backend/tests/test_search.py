from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.intent.context import MutationContext, governed_mutation_context
from financeops.core.security import create_access_token, hash_password
from financeops.db.models.accounting_jv import AccountingJVAggregate, JVStatus
from financeops.db.models.custom_report_builder import ReportDefinition, ReportRun
from financeops.db.models.users import IamUser, UserRole
from financeops.modules.expense_management.service import submit_claim as _submit_claim
from financeops.modules.search.indexers.anomaly_indexer import index_anomaly
from financeops.modules.search.indexers.expense_indexer import index_expense
from financeops.modules.search.models import SearchIndexEntry
from financeops.modules.search.service import reindex_tenant, search, upsert_index_entry
from financeops.platform.db.models.entities import CpEntity
from financeops.platform.db.models.user_membership import CpUserEntityAssignment
from financeops.utils.chain_hash import GENESIS_HASH, compute_chain_hash


def _auth_headers(user) -> dict[str, str]:  # type: ignore[no-untyped-def]
    token = create_access_token(user.id, user.tenant_id, user.role.value)
    return {"Authorization": f"Bearer {token}"}


def _expense_context() -> MutationContext:
    return MutationContext(
        intent_id=uuid.uuid4(),
        job_id=uuid.uuid4(),
        actor_user_id=None,
        actor_role="finance_leader",
        intent_type="SUBMIT_EXPENSE_CLAIM",
    )


async def submit_claim(*args, **kwargs):
    with governed_mutation_context(_expense_context()):
        return await _submit_claim(*args, **kwargs)


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


async def _get_default_entity(session: AsyncSession, tenant_id: uuid.UUID) -> CpEntity:
    return (
        await session.execute(
            select(CpEntity)
            .where(CpEntity.tenant_id == tenant_id)
            .order_by(CpEntity.created_at.asc(), CpEntity.id.asc())
        )
    ).scalar_one()


async def _create_entity(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    organisation_id: uuid.UUID,
    entity_code: str,
    entity_name: str,
) -> CpEntity:
    payload = {
        "tenant_id": str(tenant_id),
        "entity_code": entity_code,
        "entity_name": entity_name,
        "organisation_id": str(organisation_id),
    }
    entity = CpEntity(
        tenant_id=tenant_id,
        organisation_id=organisation_id,
        group_id=None,
        entity_code=entity_code,
        entity_name=entity_name,
        base_currency="USD",
        country_code="US",
        status="active",
        correlation_id=f"search-{entity_code.lower()}",
        chain_hash=compute_chain_hash(payload, GENESIS_HASH),
        previous_hash=GENESIS_HASH,
    )
    session.add(entity)
    await session.flush()
    return entity


async def _create_user(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    role: UserRole,
    email: str,
    full_name: str,
) -> IamUser:
    user = IamUser(
        tenant_id=tenant_id,
        email=email,
        hashed_password=hash_password("SearchTestPassword!1"),
        full_name=full_name,
        role=role,
        is_active=True,
        mfa_enabled=True,
    )
    session.add(user)
    await session.flush()
    return user


async def _assign_user_to_entity(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    entity_id: uuid.UUID,
) -> None:
    assignment_payload = {
        "tenant_id": str(tenant_id),
        "user_id": str(user_id),
        "entity_id": str(entity_id),
    }
    session.add(
        CpUserEntityAssignment(
            tenant_id=tenant_id,
            user_id=user_id,
            entity_id=entity_id,
            is_active=True,
            effective_from=datetime.now(UTC),
            effective_to=None,
            correlation_id=f"search-assignment-{entity_id}",
            chain_hash=compute_chain_hash(assignment_payload, GENESIS_HASH),
            previous_hash=GENESIS_HASH,
        )
    )
    await session.flush()


async def _create_journal(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    created_by: uuid.UUID,
    number: str,
    description: str,
) -> AccountingJVAggregate:
    payload = {
        "tenant_id": str(tenant_id),
        "entity_id": str(entity_id),
        "jv_number": number,
    }
    journal = AccountingJVAggregate(
        tenant_id=tenant_id,
        entity_id=entity_id,
        location_id=None,
        cost_centre_id=None,
        jv_number=number,
        status=JVStatus.APPROVED,
        version=1,
        period_date=date(2026, 4, 19),
        fiscal_year=2026,
        fiscal_period=4,
        description=description,
        reference="SEARCH-REF",
        source="MANUAL",
        external_reference_id=f"EXT-{number}",
        total_debit=Decimal("14500.00"),
        total_credit=Decimal("14500.00"),
        currency="USD",
        workflow_instance_id=None,
        created_by=created_by,
        created_by_intent_id=None,
        recorded_by_job_id=None,
        resubmission_count=0,
        voided_by=None,
        void_reason=None,
        voided_at=None,
        submitted_at=datetime.now(UTC),
        first_reviewed_at=None,
        decided_at=None,
        chain_hash=compute_chain_hash(payload, GENESIS_HASH),
        previous_hash=GENESIS_HASH,
    )
    session.add(journal)
    await session.flush()
    return journal


async def _create_report_definition(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    created_by: uuid.UUID,
    name: str,
    description: str,
    entity_ids: list[uuid.UUID],
) -> ReportDefinition:
    definition = ReportDefinition(
        tenant_id=tenant_id,
        name=name,
        description=description,
        metric_keys=["revenue"],
        filter_config={"entity_ids": [str(entity_id) for entity_id in entity_ids]},
        group_by=[],
        sort_config={},
        export_formats=["CSV"],
        config={},
        created_by=created_by,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        is_active=True,
    )
    session.add(definition)
    await session.flush()
    return definition


async def _create_report_run(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    definition_id: uuid.UUID,
    triggered_by: uuid.UUID,
    status: str = "COMPLETE",
) -> ReportRun:
    run = ReportRun(
        tenant_id=tenant_id,
        definition_id=definition_id,
        status=status,
        triggered_by=triggered_by,
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
        error_message=None,
        row_count=12,
        run_metadata={"origin_run_id": str(uuid.uuid4())},
        created_at=datetime.now(UTC),
    )
    session.add(run)
    await session.flush()
    return run


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
    entity = await _get_default_entity(async_session, test_user.tenant_id)
    await _create_journal(
        async_session,
        tenant_id=test_user.tenant_id,
        entity_id=entity.id,
        created_by=test_user.id,
        number="JRN-SEARCH-001",
        description="Market services accrual",
    )
    response = await async_client.get(
        "/api/v1/search?q=market",
        headers=_auth_headers(test_user),
    )
    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["data"]
    assert payload["meta"]["query"] == "market"
    assert payload["meta"]["limit"] == 25
    assert payload["meta"]["offset"] == 0
    first = payload["data"][0]
    assert set(first) == {
        "id",
        "module",
        "title",
        "subtitle",
        "href",
        "status",
        "amount",
        "currency",
        "created_at",
    }


@pytest.mark.asyncio
async def test_search_endpoint_rejects_blank_query(async_client, test_user) -> None:  # type: ignore[no-untyped-def]
    response = await async_client.get("/api/v1/search?q= ", headers=_auth_headers(test_user))
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_search_endpoint_module_filter_and_tenant_isolation(
    async_client,
    api_session_factory,
    test_tenant,
    test_user,
) -> None:  # type: ignore[no-untyped-def]
    async with api_session_factory() as session:
        entity = await _get_default_entity(session, test_tenant.id)
        own_journal = await _create_journal(
            session,
            tenant_id=test_tenant.id,
            entity_id=entity.id,
            created_by=test_user.id,
            number="JRN-ORBIT-001",
            description="Orbit tenant entry",
        )

        other_tenant_id = uuid.uuid4()
        other_org_id = entity.organisation_id
        other_entity = CpEntity(
            tenant_id=other_tenant_id,
            organisation_id=other_org_id,
            group_id=None,
            entity_code="ENT_ORBIT_OTHER",
            entity_name="Orbit Other Entity",
            base_currency="USD",
            country_code="US",
            status="active",
            correlation_id="search-other-tenant-entity",
            chain_hash=compute_chain_hash({"tenant_id": str(other_tenant_id), "entity_code": "ENT_ORBIT_OTHER"}, GENESIS_HASH),
            previous_hash=GENESIS_HASH,
        )
        session.add(other_entity)
        await session.flush()
        await _create_journal(
            session,
            tenant_id=other_tenant_id,
            entity_id=other_entity.id,
            created_by=test_user.id,
            number="JRN-ORBIT-999",
            description="Should stay hidden",
        )
        await session.commit()

    response = await async_client.get(
        "/api/v1/search?q=orbit&module=journal",
        headers=_auth_headers(test_user),
    )
    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["meta"]["total_results"] == 1
    assert payload["data"] == [
        {
            "id": str(own_journal.id),
            "module": "journal",
            "title": "JRN-ORBIT-001",
            "subtitle": "Orbit tenant entry",
            "href": f"/accounting/journals/{own_journal.id}",
            "status": JVStatus.APPROVED,
            "amount": 14500.0,
            "currency": "USD",
            "created_at": payload["data"][0]["created_at"],
        }
    ]


@pytest.mark.asyncio
async def test_search_endpoint_finance_team_rbac_limits_visibility(
    async_client,
    api_session_factory,
    test_tenant,
    test_user,
) -> None:  # type: ignore[no-untyped-def]
    async with api_session_factory() as session:
        default_entity = await _get_default_entity(session, test_tenant.id)
        visible_entity = await _create_entity(
            session,
            tenant_id=test_tenant.id,
            organisation_id=default_entity.organisation_id,
            entity_code="ENT_SCOPE_1",
            entity_name="Scoped Visible Entity",
        )
        restricted_entity = await _create_entity(
            session,
            tenant_id=test_tenant.id,
            organisation_id=default_entity.organisation_id,
            entity_code="ENT_SCOPE_2",
            entity_name="Scope Hidden Entity",
        )
        scoped_user = await _create_user(
            session,
            tenant_id=test_tenant.id,
            role=UserRole.finance_team,
            email=f"scoped_{uuid.uuid4().hex[:8]}@example.com",
            full_name="Scoped Search User",
        )
        await _assign_user_to_entity(
            session,
            tenant_id=test_tenant.id,
            user_id=scoped_user.id,
            entity_id=visible_entity.id,
        )
        own_claim = await submit_claim(
            session,
            tenant_id=test_tenant.id,
            submitted_by=scoped_user.id,
            entity_id=visible_entity.id,
            vendor_name="Scoped Vendor",
            description="Scoped travel expense",
            category="travel",
            amount=Decimal("99.00"),
            currency="USD",
            claim_date=date(2026, 4, 20),
            has_receipt=True,
        )
        await submit_claim(
            session,
            tenant_id=test_tenant.id,
            submitted_by=test_user.id,
            entity_id=visible_entity.id,
            vendor_name="Scoped Vendor",
            description="Leader-only expense",
            category="travel",
            amount=Decimal("199.00"),
            currency="USD",
            claim_date=date(2026, 4, 20),
            has_receipt=True,
        )
        visible_journal = await _create_journal(
            session,
            tenant_id=test_tenant.id,
            entity_id=visible_entity.id,
            created_by=test_user.id,
            number="JRN-SCOPED-001",
            description="Scoped journal visible",
        )
        await _create_journal(
            session,
            tenant_id=test_tenant.id,
            entity_id=restricted_entity.id,
            created_by=test_user.id,
            number="JRN-SCOPED-999",
            description="Scoped journal hidden",
        )
        visible_definition = await _create_report_definition(
            session,
            tenant_id=test_tenant.id,
            created_by=test_user.id,
            name="Scoped Report Visible",
            description="Scoped report",
            entity_ids=[visible_entity.id],
        )
        visible_run = await _create_report_run(
            session,
            tenant_id=test_tenant.id,
            definition_id=visible_definition.id,
            triggered_by=test_user.id,
        )
        await _create_report_definition(
            session,
            tenant_id=test_tenant.id,
            created_by=test_user.id,
            name="Scoped Report Hidden",
            description="Scoped report hidden",
            entity_ids=[restricted_entity.id],
        )
        await session.commit()

    token = create_access_token(scoped_user.id, scoped_user.tenant_id, scoped_user.role.value)
    response = await async_client.get(
        "/api/v1/search?q=scoped",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    payload = response.json()["data"]
    modules = {item["module"] for item in payload["data"]}
    assert "user" not in modules
    assert "entity" in modules
    assert "journal" in modules
    assert "report" in modules
    assert any(item["id"] == str(own_claim.id) and item["module"] == "expense" for item in payload["data"])
    assert any(item["id"] == str(visible_journal.id) and item["module"] == "journal" for item in payload["data"])
    assert any(item["href"] == f"/reports/{visible_run.id}" and item["module"] == "report" for item in payload["data"])
    assert all(item["title"] != "Scope Hidden Entity" for item in payload["data"])
    assert all(item.get("subtitle") != "Leader-only expense" for item in payload["data"])


@pytest.mark.asyncio
async def test_reindex_endpoint_queues_task(async_client, test_user) -> None:  # type: ignore[no-untyped-def]
    response = await async_client.post("/api/v1/search/reindex", headers=_auth_headers(test_user))
    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["status"] == "queued"
    assert isinstance(payload["task_id"], str)
