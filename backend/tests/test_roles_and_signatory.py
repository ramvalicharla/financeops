from __future__ import annotations

from types import SimpleNamespace
import uuid

import pytest
from fastapi import HTTPException

from financeops.api.deps import require_director
from financeops.api.v1.platform_users import _require_platform_owner
from financeops.db.models.users import UserRole
from financeops.modules.digital_signoff.service import validate_signatory_role


def test_director_role_in_enum() -> None:
    assert UserRole.director.value == "director"


def test_entity_user_role_in_enum() -> None:
    assert UserRole.entity_user.value == "entity_user"


@pytest.mark.asyncio
async def test_director_can_access_signoff() -> None:
    user = SimpleNamespace(role=UserRole.director)
    resolved = await require_director(current_user=user)
    assert resolved is user


def test_director_cannot_access_admin() -> None:
    user = SimpleNamespace(role=UserRole.director, tenant_id=uuid.uuid4())
    with pytest.raises(HTTPException) as exc:
        _require_platform_owner(user)
    assert exc.value.status_code == 403


def test_signatory_role_validation_valid() -> None:
    assert validate_signatory_role("Director") == "Director"


def test_signatory_role_validation_invalid() -> None:
    with pytest.raises(ValueError):
        validate_signatory_role("Intern")
