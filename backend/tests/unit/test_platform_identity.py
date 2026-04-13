"""Unit tests for financeops.services.platform_identity."""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest

from financeops.core.exceptions import AuthorizationError
from financeops.db.models.users import UserRole
from financeops.services.platform_identity import (
    PLATFORM_TENANT_ID,
    is_platform_user,
    require_platform_owner,
    require_platform_user,
)


def _make_user(role: UserRole, tenant_id: uuid.UUID | None = None) -> MagicMock:
    user = MagicMock()
    user.role = role
    user.tenant_id = tenant_id if tenant_id is not None else PLATFORM_TENANT_ID
    return user


OTHER_TENANT = uuid.uuid4()


# ---------------------------------------------------------------------------
# PLATFORM_TENANT_ID sentinel
# ---------------------------------------------------------------------------

def test_platform_tenant_id_is_zero_uuid() -> None:
    assert PLATFORM_TENANT_ID == uuid.UUID(int=0)


# ---------------------------------------------------------------------------
# is_platform_user
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "role",
    [UserRole.platform_owner, UserRole.platform_admin, UserRole.platform_support, UserRole.super_admin],
)
def test_is_platform_user_true_for_platform_roles(role: UserRole) -> None:
    user = _make_user(role, PLATFORM_TENANT_ID)
    assert is_platform_user(user) is True


def test_is_platform_user_false_for_wrong_tenant() -> None:
    user = _make_user(UserRole.platform_owner, OTHER_TENANT)
    assert is_platform_user(user) is False


@pytest.mark.parametrize(
    "role",
    [UserRole.finance_leader, UserRole.finance_team, UserRole.auditor, UserRole.director],
)
def test_is_platform_user_false_for_non_platform_roles(role: UserRole) -> None:
    user = _make_user(role, PLATFORM_TENANT_ID)
    assert is_platform_user(user) is False


# ---------------------------------------------------------------------------
# require_platform_user
# ---------------------------------------------------------------------------

def test_require_platform_user_returns_user_when_allowed() -> None:
    user = _make_user(UserRole.platform_admin, PLATFORM_TENANT_ID)
    assert require_platform_user(user) is user


def test_require_platform_user_raises_for_wrong_tenant() -> None:
    user = _make_user(UserRole.platform_admin, OTHER_TENANT)
    with pytest.raises(AuthorizationError):
        require_platform_user(user)


def test_require_platform_user_raises_for_tenant_user_role() -> None:
    user = _make_user(UserRole.finance_leader, PLATFORM_TENANT_ID)
    with pytest.raises(AuthorizationError):
        require_platform_user(user)


# ---------------------------------------------------------------------------
# require_platform_owner
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("role", [UserRole.platform_owner, UserRole.super_admin])
def test_require_platform_owner_returns_user_when_allowed(role: UserRole) -> None:
    user = _make_user(role, PLATFORM_TENANT_ID)
    assert require_platform_owner(user) is user


def test_require_platform_owner_raises_for_platform_admin() -> None:
    user = _make_user(UserRole.platform_admin, PLATFORM_TENANT_ID)
    with pytest.raises(AuthorizationError):
        require_platform_owner(user)


def test_require_platform_owner_raises_for_wrong_tenant() -> None:
    user = _make_user(UserRole.platform_owner, OTHER_TENANT)
    with pytest.raises(AuthorizationError):
        require_platform_owner(user)


def test_require_platform_owner_raises_for_finance_leader() -> None:
    user = _make_user(UserRole.finance_leader, PLATFORM_TENANT_ID)
    with pytest.raises(AuthorizationError):
        require_platform_owner(user)
