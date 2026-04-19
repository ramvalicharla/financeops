from __future__ import annotations

from financeops.config import Settings


def test_redis_topology_defaults_fall_back_to_single_url() -> None:
    settings = Settings(
        REDIS_URL="redis://localhost:6380/0",
        JWT_SECRET="a" * 32,
        FIELD_ENCRYPTION_KEY="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
    )

    assert settings.REDIS_TOPOLOGY == "single"
    assert settings.redis_broker_url == "redis://localhost:6380/0"
    assert settings.redis_cache_url == "redis://localhost:6380/0"
    assert settings.redis_result_backend_url == "redis://localhost:6380/0"


def test_redis_topology_supports_explicit_split_urls() -> None:
    settings = Settings(
        REDIS_URL="redis://localhost:6380/0",
        REDIS_TOPOLOGY="sentinel",
        REDIS_BROKER_URL="redis://localhost:6381/0",
        REDIS_CACHE_URL="redis://localhost:6382/0",
        REDIS_RESULT_BACKEND_URL="redis://localhost:6383/0",
        JWT_SECRET="a" * 32,
        FIELD_ENCRYPTION_KEY="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
    )

    assert settings.REDIS_TOPOLOGY == "sentinel"
    assert settings.redis_broker_url == "redis://localhost:6381/0"
    assert settings.redis_cache_url == "redis://localhost:6382/0"
    assert settings.redis_result_backend_url == "redis://localhost:6383/0"
