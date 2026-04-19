from __future__ import annotations

from types import SimpleNamespace

from financeops import config as config_module


def test_build_limiter_uses_shared_redis_storage_and_fallback() -> None:
    limiter = config_module._build_limiter(redis_url="redis://localhost:6380/0")

    assert limiter._storage_uri == "redis://localhost:6380/0"
    assert limiter._headers_enabled is True
    assert limiter._in_memory_fallback_enabled is True
    assert limiter._key_func is config_module._rate_limit_key


def test_global_limiter_uses_resolved_cache_url() -> None:
    assert config_module.limiter._storage_uri == config_module.settings.redis_cache_url


def test_rate_limit_key_includes_tenant_and_test_context(monkeypatch) -> None:
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "tests/test_rate_limit_config.py::test_case (call)")
    request = SimpleNamespace(
        headers={},
        client=SimpleNamespace(host="127.0.0.1"),
        state=SimpleNamespace(tenant_id="tenant-123"),
    )

    key = config_module._rate_limit_key(request)

    assert key == "127.0.0.1:tenant-123:tests/test_rate_limit_config.py::test_case"
