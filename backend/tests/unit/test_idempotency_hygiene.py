from __future__ import annotations

import pytest

from financeops.shared_kernel.idempotency import cleanup_nonexpiring_idempotency_keys


class _FakeRedis:
    def __init__(self) -> None:
        self._keys = {
            "idempotency:tenant-a:stale": "stale",
            "idempotency:tenant-a:valid": "valid",
            "other-prefix:key": "ignore",
        }
        self._ttl = {
            "idempotency:tenant-a:stale": -1,
            "idempotency:tenant-a:valid": 3600,
            "other-prefix:key": -1,
        }
        self.deleted: list[str] = []

    async def scan_iter(self, *, match: str):
        prefix = match[:-1] if match.endswith("*") else match
        for key in list(self._keys):
            if key.startswith(prefix):
                yield key

    async def ttl(self, key: str) -> int:
        return self._ttl[key]

    async def delete(self, key: str) -> None:
        self.deleted.append(key)
        self._keys.pop(key, None)


@pytest.mark.asyncio
async def test_cleanup_nonexpiring_idempotency_keys_removes_only_ttl_minus_one_entries() -> None:
    redis = _FakeRedis()

    removed = await cleanup_nonexpiring_idempotency_keys(redis)

    assert removed == 1
    assert redis.deleted == ["idempotency:tenant-a:stale"]
    assert "idempotency:tenant-a:valid" in redis._keys
    assert "other-prefix:key" in redis._keys


@pytest.mark.asyncio
async def test_cleanup_nonexpiring_idempotency_keys_noops_without_redis_client() -> None:
    removed = await cleanup_nonexpiring_idempotency_keys(None)
    assert removed == 0
