from __future__ import annotations

import asyncio
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from financeops.db.rls import set_tenant_context
from financeops.modules.coa.application.coa_upload_service import CoaUploadService
from financeops.modules.coa.models import (
    CoaBatchConfirmationStatus,
    CoaIndustryTemplate,
    CoaLedgerAccount,
    CoaSourceType,
    CoaUploadBatch,
    CoaUploadMode,
    TenantCoaAccount,
)
from financeops.modules.coa.seeds.runner import run_coa_seeds


@pytest.fixture(autouse=True)
def _mock_airlock_admission(monkeypatch: pytest.MonkeyPatch) -> uuid.UUID:
    admitted_item_id = uuid.uuid4()
    monkeypatch.setattr(
        "financeops.modules.coa.application.coa_upload_service.AirlockAdmissionService.assert_admitted",
        AsyncMock(return_value=SimpleNamespace(id=admitted_item_id, status="ADMITTED")),
    )
    return admitted_item_id


@pytest.fixture(autouse=True)
def _fake_idempotency_redis(monkeypatch: pytest.MonkeyPatch):
    from financeops.api import deps as api_deps

    class _FakeRedis:
        def __init__(self) -> None:
            self._store: dict[str, str] = {}

        async def get(self, key: str):
            return self._store.get(key)

        async def setex(self, key: str, ttl: int, value: str):
            _ = ttl
            self._store[key] = value
            return True

    fake = _FakeRedis()
    monkeypatch.setattr(api_deps, "_redis_pool", fake)
    return fake


async def _software_template(session: AsyncSession) -> CoaIndustryTemplate:
    return (
        await session.execute(
            select(CoaIndustryTemplate).where(CoaIndustryTemplate.code == "SOFTWARE_SAAS")
        )
    ).scalar_one()


async def _tenant_custom_ledgers(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    template_id: uuid.UUID,
    code: str,
) -> list[CoaLedgerAccount]:
    return list(
        (
            await session.execute(
                select(CoaLedgerAccount)
                .where(CoaLedgerAccount.tenant_id == tenant_id)
                .where(CoaLedgerAccount.industry_template_id == template_id)
                .where(CoaLedgerAccount.source_type == CoaSourceType.TENANT_CUSTOM)
                .where(CoaLedgerAccount.code == code)
                .order_by(CoaLedgerAccount.created_at.asc(), CoaLedgerAccount.id.asc())
            )
        ).scalars().all()
    )


async def _seed_upload_batch(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    template_id: uuid.UUID,
    ledger_code: str,
) -> uuid.UUID:
    service = CoaUploadService(session)
    upload = await service.upload(
        actor_id=user_id,
        actor_tenant_id=tenant_id,
        tenant_id=tenant_id,
        template_id=template_id,
        source_type=CoaSourceType.TENANT_CUSTOM,
        upload_mode=CoaUploadMode.APPEND,
        file_name="coa_idempotency.csv",
        file_bytes=(
            "group_code,group_name,subgroup_code,subgroup_name,ledger_code,ledger_name,ledger_type,is_control_account\n"
            f"CUS_GRP,Custom Group,CUS_SUB,Custom Subgroup,{ledger_code},Custom Ledger,EXPENSE,true\n"
        ).encode("utf-8"),
        admitted_airlock_item_id=uuid.uuid4(),
        airlock_source_type="coa_upload",
    )
    return uuid.UUID(str(upload["batch_id"]))


@pytest.mark.asyncio
@pytest.mark.integration
async def test_confirm_twice_returns_same_result_without_duplicate_rows(
    async_client: AsyncClient,
    api_session_factory: async_sessionmaker[AsyncSession],
    api_test_user,
    api_test_access_token: str,
) -> None:
    async with api_session_factory() as session:
        await set_tenant_context(session, api_test_user.tenant_id)
        await run_coa_seeds(session)
        template = await _software_template(session)
        ledger_code = f"CUS_COA_{uuid.uuid4().hex[:8].upper()}"
        batch_id = await _seed_upload_batch(
            session,
            tenant_id=api_test_user.tenant_id,
            user_id=api_test_user.id,
            template_id=template.id,
            ledger_code=ledger_code,
        )
        template_id = template.id
        await session.commit()

    headers = {
        "Authorization": f"Bearer {api_test_access_token}",
        "Idempotency-Key": "coa-apply-idem-1",
    }
    response_1 = await async_client.post(
        "/api/v1/coa/apply",
        headers=headers,
        json={"batch_id": str(batch_id)},
    )
    response_2 = await async_client.post(
        "/api/v1/coa/apply",
        headers=headers,
        json={"batch_id": str(batch_id)},
    )

    assert response_1.status_code == 200
    assert response_2.status_code == 200
    assert response_1.json()["data"] == response_2.json()["data"]
    assert response_2.headers.get("Idempotency-Replayed") == "true"

    async with api_session_factory() as session:
        await set_tenant_context(session, api_test_user.tenant_id)
        ledgers = await _tenant_custom_ledgers(
            session,
            tenant_id=api_test_user.tenant_id,
            template_id=template_id,
            code=ledger_code,
        )
        assert len(ledgers) == 1

        batch = (
            await session.execute(
                select(CoaUploadBatch)
                .execution_options(populate_existing=True)
                .where(CoaUploadBatch.id == batch_id)
            )
        ).scalar_one()
        assert batch.confirmation_status == CoaBatchConfirmationStatus.CONFIRMED


@pytest.mark.asyncio
@pytest.mark.integration
async def test_confirm_concurrent_requests_no_duplicate_accounts(
    api_session_factory: async_sessionmaker[AsyncSession],
    api_test_user,
) -> None:
    async with api_session_factory() as session:
        await set_tenant_context(session, api_test_user.tenant_id)
        await run_coa_seeds(session)
        template = await _software_template(session)
        ledger_code = f"CUS_CONC_{uuid.uuid4().hex[:8].upper()}"
        batch_id = await _seed_upload_batch(
            session,
            tenant_id=api_test_user.tenant_id,
            user_id=api_test_user.id,
            template_id=template.id,
            ledger_code=ledger_code,
        )
        template_id = template.id
        await session.commit()

    async def _apply_once() -> dict[str, object]:
        async with api_session_factory() as session:
            await set_tenant_context(session, api_test_user.tenant_id)
            service = CoaUploadService(session)
            result = await service.apply_batch(
                batch_id=batch_id,
                actor_tenant_id=api_test_user.tenant_id,
                is_platform_admin=False,
            )
            await session.commit()
            return result

    first, second = await asyncio.gather(_apply_once(), _apply_once())

    assert first["batch_id"] == second["batch_id"] == str(batch_id)
    assert first["applied_rows"] == second["applied_rows"] == 1
    assert any(
        result["idempotent_replay"] is True for result in (first, second)
    )

    async with api_session_factory() as session:
        await set_tenant_context(session, api_test_user.tenant_id)
        ledgers = await _tenant_custom_ledgers(
            session,
            tenant_id=api_test_user.tenant_id,
            template_id=template_id,
            code=ledger_code,
        )
        assert len(ledgers) == 1


@pytest.mark.asyncio
@pytest.mark.integration
async def test_account_code_uniqueness_enforced_at_db_level(
    api_db_session: AsyncSession,
    api_test_user,
) -> None:
    await set_tenant_context(api_db_session, api_test_user.tenant_id)
    await run_coa_seeds(api_db_session)
    template = await _software_template(api_db_session)
    seed_ledger = (
        await api_db_session.execute(
            select(CoaLedgerAccount)
            .where(
                CoaLedgerAccount.industry_template_id == template.id,
                CoaLedgerAccount.tenant_id.is_(None),
                CoaLedgerAccount.is_active.is_(True),
            )
            .order_by(CoaLedgerAccount.sort_order.asc(), CoaLedgerAccount.code.asc())
            .limit(1)
        )
    ).scalar_one()

    duplicate_code = f"DUP_{uuid.uuid4().hex[:8].upper()}"
    api_db_session.add_all(
        [
            TenantCoaAccount(
                tenant_id=api_test_user.tenant_id,
                ledger_account_id=seed_ledger.id,
                parent_subgroup_id=seed_ledger.account_subgroup_id,
                account_code=duplicate_code,
                display_name="Duplicate A",
                is_custom=False,
                is_active=True,
            ),
            TenantCoaAccount(
                tenant_id=api_test_user.tenant_id,
                ledger_account_id=seed_ledger.id,
                parent_subgroup_id=seed_ledger.account_subgroup_id,
                account_code=duplicate_code,
                display_name="Duplicate B",
                is_custom=False,
                is_active=True,
            ),
        ]
    )

    with pytest.raises(IntegrityError):
        await api_db_session.flush()
