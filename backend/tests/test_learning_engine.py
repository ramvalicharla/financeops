from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.security import create_access_token, hash_password
from financeops.db.append_only import append_only_function_sql, create_trigger_sql, drop_trigger_sql
from financeops.db.models.tenants import IamTenant, TenantStatus, TenantType
from financeops.db.models.users import IamUser, UserRole
from financeops.modules.learning_engine.benchmarks.classification_benchmark import (
    CLASSIFICATION_TEST_CASES,
    run_classification_benchmark,
)
from financeops.modules.learning_engine.benchmarks.commentary_benchmark import (
    COMMENTARY_TEST_CASES,
    run_commentary_benchmark,
)
from financeops.modules.learning_engine.models import AIBenchmarkResult, LearningCorrection, LearningSignal
from financeops.modules.learning_engine.service import (
    capture_signal,
    compute_correction_delta,
    get_learning_stats,
    get_tenant_context_for_task,
)
from financeops.utils.chain_hash import GENESIS_HASH, compute_chain_hash

PLATFORM_TENANT_ID = uuid.UUID(int=0)


def _auth_headers(user: IamUser) -> dict[str, str]:
    token = create_access_token(user.id, user.tenant_id, user.role.value)
    return {"Authorization": f"Bearer {token}"}


async def _ensure_platform_tenant(session: AsyncSession) -> IamTenant:
    tenant = (
        await session.execute(select(IamTenant).where(IamTenant.id == PLATFORM_TENANT_ID))
    ).scalar_one_or_none()
    if tenant is not None:
        return tenant
    record_data = {
        "display_name": "FinanceOps Platform",
        "tenant_type": TenantType.direct.value,
        "country": "US",
        "timezone": "UTC",
    }
    tenant = IamTenant(
        id=PLATFORM_TENANT_ID,
        tenant_id=PLATFORM_TENANT_ID,
        display_name="FinanceOps Platform",
        tenant_type=TenantType.direct,
        country="US",
        timezone="UTC",
        status=TenantStatus.active,
        is_platform_tenant=True,
        chain_hash=compute_chain_hash(record_data, GENESIS_HASH),
        previous_hash=GENESIS_HASH,
    )
    session.add(tenant)
    await session.flush()
    return tenant


async def _create_platform_admin(session: AsyncSession, email: str) -> IamUser:
    await _ensure_platform_tenant(session)
    user = IamUser(
        tenant_id=PLATFORM_TENANT_ID,
        email=email,
        hashed_password=hash_password("TestPass123!"),
        full_name="Platform Admin",
        role=UserRole.platform_admin,
        is_active=True,
        mfa_enabled=True,
    )
    session.add(user)
    await session.flush()
    return user


@pytest.mark.asyncio
async def test_capture_signal_creates_records(async_session: AsyncSession, test_user: IamUser) -> None:
    signal = await capture_signal(
        async_session,
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
        signal_type="classification_correction",
        task_type="classification",
        original_ai_output={"category": "meals"},
        human_correction={"category": "travel"},
        model_used="gpt-test",
        provider="openai",
    )
    correction = (
        await async_session.execute(
            select(LearningCorrection).where(LearningCorrection.signal_id == signal.id)
        )
    ).scalar_one_or_none()
    assert correction is not None


@pytest.mark.asyncio
async def test_signal_is_append_only(async_session: AsyncSession, test_user: IamUser) -> None:
    signal = await capture_signal(
        async_session,
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
        signal_type="classification_correction",
        task_type="classification",
        original_ai_output={"category": "meals"},
        human_correction={"category": "travel"},
        model_used="gpt-test",
        provider="openai",
    )
    await async_session.execute(text(append_only_function_sql()))
    await async_session.execute(text(drop_trigger_sql("learning_signals")))
    await async_session.execute(text(create_trigger_sql("learning_signals")))
    await async_session.flush()
    with pytest.raises(Exception):
        await async_session.execute(
            text("UPDATE learning_signals SET signal_type = 'commentary_edit' WHERE id = :id"),
            {"id": signal.id},
        )


def test_correction_delta_computed() -> None:
    delta = compute_correction_delta({"category": "meals"}, {"category": "travel"})
    assert delta["modifications"]["category"]["from"] == "meals"
    assert delta["modifications"]["category"]["to"] == "travel"


def test_correction_delta_detects_additions() -> None:
    delta = compute_correction_delta({"a": 1}, {"a": 1, "b": 2})
    assert "b" in delta["additions"]


def test_correction_delta_detects_removals() -> None:
    delta = compute_correction_delta({"a": 1, "b": 2}, {"a": 1})
    assert "b" in delta["removals"]


@pytest.mark.asyncio
async def test_learning_stats_structure(async_session: AsyncSession, test_user: IamUser) -> None:
    await capture_signal(
        async_session,
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
        signal_type="classification_correction",
        task_type="classification",
        original_ai_output={"x": 1},
        human_correction={"x": 2},
        model_used="gpt-test",
        provider="openai",
    )
    stats = await get_learning_stats(async_session, test_user.tenant_id)
    assert {"total_signals", "signals_by_type", "most_corrected_task"}.issubset(stats.keys())


@pytest.mark.asyncio
async def test_correction_rate_is_decimal(async_session: AsyncSession, test_user: IamUser) -> None:
    await capture_signal(
        async_session,
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
        signal_type="classification_correction",
        task_type="classification",
        original_ai_output={"x": 1},
        human_correction={"x": 2},
        model_used="gpt-test",
        provider="openai",
    )
    stats = await get_learning_stats(async_session, test_user.tenant_id)
    assert isinstance(stats["correction_rate_by_task"]["classification"], Decimal)


@pytest.mark.asyncio
async def test_stats_tenant_scoped(async_session: AsyncSession, test_user: IamUser) -> None:
    tenant_b = uuid.uuid4()
    record_data = {
        "display_name": "Tenant B",
        "tenant_type": TenantType.direct.value,
        "country": "US",
        "timezone": "UTC",
    }
    tenant_row = IamTenant(
        id=tenant_b,
        tenant_id=tenant_b,
        display_name="Tenant B",
        tenant_type=TenantType.direct,
        country="US",
        timezone="UTC",
        status=TenantStatus.active,
        chain_hash=compute_chain_hash(record_data, GENESIS_HASH),
        previous_hash=GENESIS_HASH,
    )
    async_session.add(tenant_row)
    await async_session.flush()
    row = IamUser(
        tenant_id=tenant_b,
        email="tenantb.learning@example.com",
        hashed_password=hash_password("TestPass123!"),
        full_name="Tenant B",
        role=UserRole.employee,
        is_active=True,
        mfa_enabled=False,
    )
    async_session.add(row)
    await async_session.flush()
    await capture_signal(
        async_session,
        tenant_id=tenant_b,
        user_id=row.id,
        signal_type="commentary_edit",
        task_type="commentary",
        original_ai_output={"x": 1},
        human_correction={"x": 2},
        model_used="gpt-test",
        provider="openai",
    )
    stats_a = await get_learning_stats(async_session, test_user.tenant_id)
    assert stats_a["signals_by_type"].get("commentary_edit") is None


@pytest.mark.asyncio
async def test_most_corrected_task_correct(async_session: AsyncSession, test_user: IamUser) -> None:
    for _ in range(5):
        await capture_signal(
            async_session,
            tenant_id=test_user.tenant_id,
            user_id=test_user.id,
            signal_type="classification_correction",
            task_type="classification",
            original_ai_output={"x": 1},
            human_correction={"x": 2},
            model_used="gpt-test",
            provider="openai",
        )
    for _ in range(2):
        await capture_signal(
            async_session,
            tenant_id=test_user.tenant_id,
            user_id=test_user.id,
            signal_type="commentary_edit",
            task_type="commentary",
            original_ai_output={"x": 1},
            human_correction={"x": 2},
            model_used="gpt-test",
            provider="openai",
        )
    stats = await get_learning_stats(async_session, test_user.tenant_id)
    assert stats["most_corrected_task"] == "classification"


@pytest.mark.asyncio
async def test_get_tenant_context_returns_validated_only(async_session: AsyncSession, test_user: IamUser) -> None:
    first = await capture_signal(
        async_session,
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
        signal_type="classification_correction",
        task_type="classification",
        original_ai_output={"a": "x"},
        human_correction={"a": "y"},
        model_used="gpt-test",
        provider="openai",
    )
    second = await capture_signal(
        async_session,
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
        signal_type="classification_correction",
        task_type="classification",
        original_ai_output={"b": "x"},
        human_correction={"b": "y"},
        model_used="gpt-test",
        provider="openai",
    )
    corrections = (
        await async_session.execute(
            select(LearningCorrection).where(
                LearningCorrection.signal_id.in_([first.id, second.id])
            )
        )
    ).scalars().all()
    corrections[0].is_validated = True
    corrections[0].quality_score = Decimal("0.90")
    corrections[1].is_validated = False
    await async_session.flush()
    rows = await get_tenant_context_for_task(async_session, test_user.tenant_id, "classification")
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_get_tenant_context_ordered_by_quality(async_session: AsyncSession, test_user: IamUser) -> None:
    sig_a = await capture_signal(
        async_session,
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
        signal_type="classification_correction",
        task_type="classification",
        original_ai_output={"a": 1},
        human_correction={"a": 2},
        model_used="gpt-test",
        provider="openai",
    )
    sig_b = await capture_signal(
        async_session,
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
        signal_type="classification_correction",
        task_type="classification",
        original_ai_output={"b": 1},
        human_correction={"b": 2},
        model_used="gpt-test",
        provider="openai",
    )
    rows = (
        await async_session.execute(
            select(LearningCorrection).where(
                LearningCorrection.signal_id.in_([sig_a.id, sig_b.id])
            )
        )
    ).scalars().all()
    rows[0].is_validated = True
    rows[0].quality_score = Decimal("0.60")
    rows[1].is_validated = True
    rows[1].quality_score = Decimal("0.90")
    await async_session.flush()
    ctx = await get_tenant_context_for_task(async_session, test_user.tenant_id, "classification")
    assert ctx[0]["quality_score"] == Decimal("0.90")


@pytest.mark.asyncio
async def test_get_tenant_context_empty_when_no_corrections(async_session: AsyncSession, test_user: IamUser) -> None:
    ctx = await get_tenant_context_for_task(async_session, test_user.tenant_id, "classification")
    assert ctx == []


@pytest.mark.asyncio
async def test_few_shot_context_structure(async_session: AsyncSession, test_user: IamUser) -> None:
    sig = await capture_signal(
        async_session,
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
        signal_type="classification_correction",
        task_type="classification",
        original_ai_output={"a": 1},
        human_correction={"a": 2},
        model_used="gpt-test",
        provider="openai",
    )
    correction = (
        await async_session.execute(
            select(LearningCorrection).where(LearningCorrection.signal_id == sig.id)
        )
    ).scalar_one()
    correction.is_validated = True
    correction.quality_score = Decimal("0.80")
    await async_session.flush()
    ctx = await get_tenant_context_for_task(async_session, test_user.tenant_id, "classification")
    assert {"input_context", "correct_output", "quality_score"}.issubset(ctx[0].keys())


@pytest.mark.asyncio
async def test_benchmark_result_is_append_only(async_session: AsyncSession) -> None:
    row = await run_classification_benchmark(async_session, run_by="test")
    await async_session.execute(text(append_only_function_sql()))
    await async_session.execute(text(drop_trigger_sql("ai_benchmark_results")))
    await async_session.execute(text(create_trigger_sql("ai_benchmark_results")))
    await async_session.flush()
    with pytest.raises(Exception):
        await async_session.execute(
            text("UPDATE ai_benchmark_results SET benchmark_version = '9.9' WHERE id = :id"),
            {"id": row.id},
        )


def test_classification_benchmark_test_cases_exist() -> None:
    assert len(CLASSIFICATION_TEST_CASES) >= 10


def test_commentary_benchmark_test_cases_exist() -> None:
    assert len(COMMENTARY_TEST_CASES) >= 2


@pytest.mark.asyncio
async def test_accuracy_pct_is_decimal_range(async_session: AsyncSession) -> None:
    row = await run_commentary_benchmark(async_session, run_by="test")
    assert Decimal("0.0000") <= Decimal(str(row.accuracy_pct)) <= Decimal("1.0000")


@pytest.mark.asyncio
async def test_signal_endpoint(async_client, test_user: IamUser) -> None:
    response = await async_client.post(
        "/api/v1/learning/signal",
        headers=_auth_headers(test_user),
        json={
            "signal_type": "classification_correction",
            "task_type": "classification",
            "original_ai_output": {"category": "meals"},
            "human_correction": {"category": "travel"},
            "model_used": "gpt-test",
            "provider": "openai",
        },
    )
    assert response.status_code == 200
    assert response.json()["data"]["signal_type"] == "classification_correction"


@pytest.mark.asyncio
async def test_benchmark_results_endpoint(async_client, async_session: AsyncSession) -> None:
    admin = await _create_platform_admin(async_session, "learning.admin@example.com")
    await run_classification_benchmark(async_session, run_by="ci")
    response = await async_client.get(
        "/api/v1/learning/benchmark/results",
        headers=_auth_headers(admin),
    )
    assert response.status_code == 200
    assert response.json()["data"]["total"] >= 1


@pytest.mark.asyncio
async def test_validate_correction_endpoint_requires_admin(
    async_client,
    async_session: AsyncSession,
    test_user: IamUser,
) -> None:
    signal = await capture_signal(
        async_session,
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
        signal_type="classification_correction",
        task_type="classification",
        original_ai_output={"a": 1},
        human_correction={"a": 2},
        model_used="gpt-test",
        provider="openai",
    )
    correction = (
        await async_session.execute(
            select(LearningCorrection).where(LearningCorrection.signal_id == signal.id)
        )
    ).scalar_one()

    denied = await async_client.post(
        f"/api/v1/learning/corrections/{correction.id}/validate",
        headers=_auth_headers(test_user),
        json={"quality_score": "0.90"},
    )
    assert denied.status_code == 403
