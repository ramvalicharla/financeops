from __future__ import annotations

from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_audit_log_and_record_committed_atomically(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If audit log write fails, auth session write is rolled back."""
    user_id = str(test_user.id)
    user_email = str(test_user.email)
    before_count = (
        await async_session.execute(
            text("SELECT COUNT(*) FROM iam_sessions WHERE user_id = CAST(:id AS uuid)"),
            {"id": user_id},
        )
    ).scalar_one()

    async def _boom(*args, **kwargs):
        raise RuntimeError("audit write failed")

    monkeypatch.setattr("financeops.api.v1.auth.log_action", _boom)
    response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": user_email, "password": "TestPass123!"},
    )
    assert response.status_code == 500

    await async_session.rollback()
    after_count = (
        await async_session.execute(
            text("SELECT COUNT(*) FROM iam_sessions WHERE user_id = CAST(:id AS uuid)"),
            {"id": user_id},
        )
    ).scalar_one()
    assert after_count == before_count


def test_commit_not_called_in_route_handler() -> None:
    """Route handlers do not call session.commit() directly."""
    root = Path(__file__).resolve().parents[1]
    target_files = list((root / "financeops" / "api").rglob("*.py"))
    target_files.extend((root / "financeops" / "modules").rglob("api/routes.py"))
    violations: list[str] = []
    for file_path in target_files:
        source = file_path.read_text(encoding="utf-8")
        if "session.commit()" in source:
            violations.append(str(file_path))
    assert not violations, f"session.commit() found in route handlers: {violations}"
