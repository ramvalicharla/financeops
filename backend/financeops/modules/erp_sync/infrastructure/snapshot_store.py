from __future__ import annotations

from typing import Any


class SnapshotStore:
    async def put(self, *, key: str, payload: dict[str, Any]) -> str:
        return key

    async def get(self, key: str) -> dict[str, Any]:
        return {"key": key}
