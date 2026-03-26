from __future__ import annotations

import re
from collections.abc import Sequence

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession


_NON_ALNUM = re.compile(r"[^A-Z0-9]+")


def build_code(prefix: str, value: str, max_length: int = 50) -> str:
    cleaned = _NON_ALNUM.sub("_", value.upper()).strip("_")
    code = f"{prefix}_{cleaned}" if prefix else cleaned
    if len(code) <= max_length:
        return code
    return code[:max_length].rstrip("_")


async def fetch_code_id_map(
    session: AsyncSession,
    model,
    *,
    code_column,
    id_column,
    codes: Sequence[str] | None = None,
) -> dict[str, str]:
    stmt: Select = select(code_column, id_column)
    if codes:
        stmt = stmt.where(code_column.in_(list(codes)))
    rows = (await session.execute(stmt)).all()
    return {str(code): str(identifier) for code, identifier in rows}
