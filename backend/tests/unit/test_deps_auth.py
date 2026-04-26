"""Unit tests for the get_current_user auth path amendment (BE-001 §4.3).

Tests:
- Switch token with active membership succeeds (returns user)
- Switch token without membership raises AuthenticationError
- Non-switch token with tenant mismatch still raises (regression guard)
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import Request

from financeops.api import deps
from financeops.core.exceptions import AuthenticationError
from financeops.core.security import create_access_token


def _make_request(path: str = "/api/v1/users/me") -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": path,
            "headers": [],
            "state": {},
        }
    )


def _make_user(user_id: uuid.UUID, home_tenant_id: uuid.UUID) -> MagicMock:
    user = MagicMock()
    user.id = user_id
    user.tenant_id = home_tenant_id
    user.is_active = True
    user.password_changed_at = None
    user.force_mfa_setup = False
    user.mfa_enabled = True
    return user


_SENTINEL = object()


def _mock_session(user_mock, membership_mock=_SENTINEL):
    """Return a mock AsyncSession whose execute() returns user then optionally membership."""
    session = AsyncMock()

    result_user = MagicMock()
    result_user.scalar_one_or_none.return_value = user_mock

    results = [result_user]
    if membership_mock is not _SENTINEL:
        result_membership = MagicMock()
        result_membership.scalar_one_or_none.return_value = membership_mock
        results.append(result_membership)

    session.execute.side_effect = results
    return session


@pytest.mark.asyncio
async def test_get_current_user_user_switch_with_active_membership_succeeds():
    home_tenant_id = uuid.uuid4()
    target_tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()

    token = create_access_token(
        user_id, target_tenant_id, "finance_team",
        additional_claims={"scope": "user_switch"},
    )
    user = _make_user(user_id, home_tenant_id)
    fake_membership = MagicMock()

    session = _mock_session(user, membership_mock=fake_membership)

    result = await deps.get_current_user(
        request=_make_request(),
        token=token,
        session=session,
    )
    assert result is user


@pytest.mark.asyncio
async def test_get_current_user_user_switch_without_membership_401():
    home_tenant_id = uuid.uuid4()
    target_tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()

    token = create_access_token(
        user_id, target_tenant_id, "finance_team",
        additional_claims={"scope": "user_switch"},
    )
    user = _make_user(user_id, home_tenant_id)

    # No membership found — pass None explicitly via sentinel-aware helper
    session = _mock_session(user, membership_mock=None)

    with pytest.raises(AuthenticationError, match="No active membership in target tenant"):
        await deps.get_current_user(
            request=_make_request(),
            token=token,
            session=session,
        )


@pytest.mark.asyncio
async def test_get_current_user_no_scope_strict_consistency_preserved():
    """Non-switch token with mismatched tenant_id must still raise (regression guard)."""
    home_tenant_id = uuid.uuid4()
    wrong_tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()

    # Token has wrong_tenant_id but no scope
    token = create_access_token(user_id, wrong_tenant_id, "finance_team")
    user = _make_user(user_id, home_tenant_id)

    session = _mock_session(user)  # No membership call expected

    with pytest.raises(AuthenticationError, match="Token tenant mismatch"):
        await deps.get_current_user(
            request=_make_request(),
            token=token,
            session=session,
        )
