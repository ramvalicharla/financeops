from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession


async def commit_session(session: AsyncSession) -> None:
    await session.commit()

