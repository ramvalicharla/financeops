from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine

from financeops.db.session import engine

MigrationStatus = Literal["ok", "out_of_sync", "unknown"]


@dataclass(frozen=True)
class MigrationCheckResult:
    status: MigrationStatus
    current_revision: str | None
    head_revision: str | None
    detail: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _backend_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _build_alembic_config():
    from alembic.config import Config

    backend_root = _backend_root()
    cfg = Config(str(backend_root / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend_root / "migrations"))
    return cfg


def get_head_revision() -> str | None:
    from alembic.script import ScriptDirectory

    script_dir = ScriptDirectory.from_config(_build_alembic_config())
    return script_dir.get_current_head()


async def get_current_revision(db_engine: AsyncEngine | None = None) -> str | None:
    active_engine = db_engine or engine
    async with active_engine.connect() as conn:
        result = await conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1"))
        return result.scalar_one_or_none()


async def check_migration_state(db_engine: AsyncEngine | None = None) -> MigrationCheckResult:
    try:
        head_revision = get_head_revision()
    except Exception as exc:
        return MigrationCheckResult(
            status="unknown",
            current_revision=None,
            head_revision=None,
            detail=f"failed to resolve alembic head: {exc}",
        )

    try:
        current_revision = await get_current_revision(db_engine=db_engine)
    except SQLAlchemyError as exc:
        return MigrationCheckResult(
            status="unknown",
            current_revision=None,
            head_revision=head_revision,
            detail=f"failed to read alembic_version: {exc}",
        )

    if current_revision != head_revision:
        return MigrationCheckResult(
            status="out_of_sync",
            current_revision=current_revision,
            head_revision=head_revision,
            detail=(
                f"database revision '{current_revision}' does not match "
                f"code head '{head_revision}'"
            ),
        )

    return MigrationCheckResult(
        status="ok",
        current_revision=current_revision,
        head_revision=head_revision,
        detail=None,
    )


async def enforce_migration_state(
    *,
    fail_fast: bool,
    db_engine: AsyncEngine | None = None,
) -> MigrationCheckResult:
    result = await check_migration_state(db_engine=db_engine)
    if fail_fast and result.status != "ok":
        raise RuntimeError(result.detail or "DB schema out of sync with code")
    return result
