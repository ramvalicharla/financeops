from __future__ import annotations

import asyncio
import sys
import uuid
from typing import AsyncGenerator

import pytest
import pytest_asyncio

# On Windows, asyncpg's persistent IOCP socket readers cause GetQueuedCompletionStatus
# to block indefinitely between run_until_complete() calls (test → teardown boundary).
# Switching to SelectorEventLoop (non-IOCP) avoids this issue entirely.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from financeops.db.base import Base
# Import ALL models so Base.metadata.create_all() creates every table.
# Order matters: models with FK deps must be imported after their targets.
from financeops.db.models.tenants import IamTenant, TenantStatus, TenantType
from financeops.db.models.users import IamUser, UserRole
from financeops.db.models.audit import AuditTrail  # noqa: F401
from financeops.db.models.credits import CreditBalance, CreditTransaction, CreditReservation  # noqa: F401
from financeops.db.models.prompts import AiPromptVersion  # noqa: F401
# Phase 1 models — must be imported before Base.metadata.create_all()
from financeops.db.models.mis_manager import MisTemplate, MisUpload  # noqa: F401
from financeops.db.models.reconciliation import GlEntry, TrialBalanceRow, ReconItem  # noqa: F401
from financeops.db.models.bank_recon import BankStatement, BankTransaction, BankReconItem  # noqa: F401
from financeops.db.models.working_capital import WorkingCapitalSnapshot  # noqa: F401
from financeops.db.models.gst import GstReturn, GstReconItem  # noqa: F401
from financeops.db.models.monthend import MonthEndChecklist, MonthEndTask  # noqa: F401
from financeops.db.models.auditor import AuditorGrant, AuditorAccessLog  # noqa: F401
from financeops.core.security import create_access_token, hash_password
from financeops.utils.chain_hash import GENESIS_HASH, compute_chain_hash

import os
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://financeops_test:testpassword@localhost:5433/financeops_test",
)
TEST_REDIS_URL = os.getenv("TEST_REDIS_URL", "redis://localhost:6380/0")


@pytest_asyncio.fixture(scope="session")
async def engine():
    """
    Create test database engine and tables once per session.
    NullPool ensures each test's session gets a fresh connection,
    avoiding 'another operation is in progress' asyncpg errors.
    """
    test_engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=NullPool)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield test_engine
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


@pytest_asyncio.fixture(loop_scope="session")
async def async_session(engine) -> AsyncGenerator[AsyncSession, None]:
    """
    Provide a transactional test session that rolls back after each test.
    loop_scope="session" ensures setup AND teardown both run on the session
    event loop, preventing asyncpg 'Future attached to a different loop' errors
    that occur in pytest-asyncio 0.24.0 with function-scoped async fixtures.
    """
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        await session.begin()
        try:
            yield session
        finally:
            await session.rollback()


@pytest_asyncio.fixture
async def test_tenant(async_session: AsyncSession) -> IamTenant:
    """Create a test IamTenant for use in tests."""
    tenant_id = uuid.uuid4()
    record_data = {
        "display_name": "Test Tenant",
        "tenant_type": TenantType.direct.value,
        "country": "US",
        "timezone": "UTC",
    }
    chain_hash = compute_chain_hash(record_data, GENESIS_HASH)
    tenant = IamTenant(
        id=tenant_id,
        tenant_id=tenant_id,
        display_name="Test Tenant",
        tenant_type=TenantType.direct,
        country="US",
        timezone="UTC",
        status=TenantStatus.active,
        chain_hash=chain_hash,
        previous_hash=GENESIS_HASH,
    )
    async_session.add(tenant)
    await async_session.flush()
    return tenant


@pytest_asyncio.fixture
async def test_user(async_session: AsyncSession, test_tenant: IamTenant) -> IamUser:
    """Create a test IamUser with finance_leader role."""
    user = IamUser(
        tenant_id=test_tenant.id,
        email="testuser@example.com",
        hashed_password=hash_password("TestPass123!"),
        full_name="Test User",
        role=UserRole.finance_leader,
        is_active=True,
        mfa_enabled=False,
    )
    async_session.add(user)
    await async_session.flush()
    return user


@pytest.fixture
def test_access_token(test_user: IamUser) -> str:
    """Return a valid JWT access token for the test user."""
    return create_access_token(test_user.id, test_user.tenant_id, test_user.role.value)


@pytest_asyncio.fixture(loop_scope="session")
async def async_client(async_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """
    Return an httpx AsyncClient configured against the test FastAPI app.
    Overrides the DB session dependency to use the test session.

    session.commit() is patched to session.flush() so that application code
    calling commit() does not break the outer rollback-based test isolation.
    loop_scope="session" ensures the AsyncClient teardown uses the same loop.
    """
    from financeops.main import app
    from financeops.api.deps import get_async_session

    # Redirect commit() to flush() — keeps data in the outer transaction so
    # session.rollback() in async_session can undo everything after the test.
    original_commit = async_session.commit
    async_session.commit = async_session.flush  # type: ignore[method-assign]

    async def override_session() -> AsyncGenerator[AsyncSession, None]:
        yield async_session

    app.dependency_overrides[get_async_session] = override_session
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client
    app.dependency_overrides.clear()
    async_session.commit = original_commit  # restore original method


@pytest_asyncio.fixture(loop_scope="session")
async def redis_client():
    """Return a test Redis connection."""
    import redis.asyncio as aioredis
    client = aioredis.from_url(TEST_REDIS_URL, encoding="utf-8", decode_responses=True)
    yield client
    await client.flushdb()
    await client.aclose()
