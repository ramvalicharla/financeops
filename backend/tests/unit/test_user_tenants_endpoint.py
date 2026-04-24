from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.dialects import postgresql

os.environ.setdefault("APP_ENV", "development")
os.environ["DEBUG"] = "false"
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/postgres",
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("SECRET_KEY", "12345678901234567890123456789012")
os.environ.setdefault("JWT_SECRET", "12345678901234567890123456789012")
os.environ.setdefault(
    "FIELD_ENCRYPTION_KEY",
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
)

from financeops.api.v1 import users as users_routes
from financeops.db.models.users import UserRole


class _AllResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return list(self._rows)


def _current_user() -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        role=UserRole.finance_leader,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


@pytest.mark.asyncio
async def test_list_user_tenants_returns_two_results() -> None:
    session = AsyncMock()
    session.execute = AsyncMock(
        return_value=_AllResult(
            [
                SimpleNamespace(
                    id=uuid.uuid4(),
                    slug="alpha",
                    name="Alpha Finance",
                    role="tenant_owner",
                    status="active",
                    plan="starter",
                    plan_fallback_applied=False,
                ),
                SimpleNamespace(
                    id=uuid.uuid4(),
                    slug="beta",
                    name="Beta Finance",
                    role="tenant_member",
                    status="active",
                    plan="enterprise",
                    plan_fallback_applied=False,
                ),
            ]
        )
    )
    log = SimpleNamespace(info=MagicMock(), warning=MagicMock())
    user = _current_user()

    original_log = users_routes.log
    users_routes.log = log
    try:
        result = await users_routes.list_user_tenants(session=session, current_user=user)
    finally:
        users_routes.log = original_log

    assert [item.model_dump() for item in result] == [
        {
            "id": str(result[0].id),
            "slug": "alpha",
            "name": "Alpha Finance",
            "role": "tenant_owner",
            "status": "active",
            "plan": "starter",
        },
        {
            "id": str(result[1].id),
            "slug": "beta",
            "name": "Beta Finance",
            "role": "tenant_member",
            "status": "active",
            "plan": "enterprise",
        },
    ]
    log.info.assert_called_once()
    session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_user_tenants_returns_empty_list_when_none_visible() -> None:
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_AllResult([]))
    log = SimpleNamespace(info=MagicMock(), warning=MagicMock())

    original_log = users_routes.log
    users_routes.log = log
    try:
        result = await users_routes.list_user_tenants(
            session=session,
            current_user=_current_user(),
        )
    finally:
        users_routes.log = original_log

    assert result == []
    log.info.assert_called_once()
    log.warning.assert_not_called()


@pytest.mark.asyncio
async def test_list_user_tenants_uses_free_plan_fallback_and_logs_warning() -> None:
    session = AsyncMock()
    tenant_id = uuid.uuid4()
    session.execute = AsyncMock(
        return_value=_AllResult(
            [
                SimpleNamespace(
                    id=tenant_id,
                    slug="fallback-tenant",
                    name="Fallback Tenant",
                    role="tenant_member",
                    status="active",
                    plan="free",
                    plan_fallback_applied=True,
                )
            ]
        )
    )
    log = SimpleNamespace(info=MagicMock(), warning=MagicMock())

    original_log = users_routes.log
    users_routes.log = log
    try:
        result = await users_routes.list_user_tenants(
            session=session,
            current_user=_current_user(),
        )
    finally:
        users_routes.log = original_log

    assert result[0].plan == "free"
    log.warning.assert_called_once()


@pytest.mark.asyncio
async def test_list_user_tenants_raises_for_invalid_response_shape() -> None:
    session = AsyncMock()
    session.execute = AsyncMock(
        return_value=_AllResult(
            [
                SimpleNamespace(
                    id=uuid.uuid4(),
                    slug=None,
                    name="Broken Tenant",
                    role="tenant_member",
                    status="active",
                    plan="starter",
                    plan_fallback_applied=False,
                )
            ]
        )
    )

    with pytest.raises(ValueError, match="Invalid tenant response shape"):
        await users_routes.list_user_tenants(session=session, current_user=_current_user())


def test_build_user_tenants_stmt_hardens_scope_and_latest_role_rule() -> None:
    stmt = users_routes._build_user_tenants_stmt(current_user=_current_user())
    compiled = str(stmt.compile(dialect=postgresql.dialect()))
    sql = compiled.lower()

    assert "cp_user_role_assignments" in sql
    assert "cp_user_entity_assignments" not in sql
    assert "cp_user_organisation_assignments" not in sql
    assert "context_type" in sql
    assert "context_id" in sql
    assert "row_number()" in sql
    assert "candidate_tenants.created_at desc" in sql
    assert "order by iam_tenants.display_name asc" in sql


@pytest.mark.asyncio
async def test_list_user_tenants_executes_single_batched_query() -> None:
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_AllResult([]))

    await users_routes.list_user_tenants(session=session, current_user=_current_user())

    session.execute.assert_awaited_once()
