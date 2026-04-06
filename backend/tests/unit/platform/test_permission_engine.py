from types import SimpleNamespace
from uuid import uuid4

import pytest

from financeops.platform.services.rbac.permission_engine import has_permission


@pytest.mark.asyncio
async def test_has_permission_allows_canonical_role_mapping() -> None:
    user = SimpleNamespace(role="finance_leader", tenant_id=uuid4())
    assert await has_permission(user, "erp.connectors.create", {}) is True


@pytest.mark.asyncio
async def test_has_permission_allows_runtime_role_override() -> None:
    user = SimpleNamespace(role="finance_approver", tenant_id=uuid4())
    assert await has_permission(user, "journal.approve", {}) is True


@pytest.mark.asyncio
async def test_has_permission_denies_unknown_role() -> None:
    user = SimpleNamespace(role="read_only", tenant_id=uuid4())
    assert await has_permission(user, "platform.users.update", {}) is False
