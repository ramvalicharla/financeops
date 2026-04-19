from __future__ import annotations

from financeops.db import session as session_module


def test_read_replica_session_factory_is_available() -> None:
    assert session_module.AsyncReadSessionLocal is not None
    assert session_module.read_engine is not None
    if session_module.is_read_replica_configured():
        assert session_module._READ_DATABASE_URL  # noqa: SLF001
    else:
        assert session_module._READ_DATABASE_URL == session_module._DATABASE_URL  # noqa: SLF001


def test_normalise_database_url_handles_replica_style_url() -> None:
    url, connect_args = session_module._normalise_database_url_and_connect_args(  # noqa: SLF001
        "postgresql+asyncpg://reader:secret@db-replica.example.com:5432/financeops?sslmode=require"
    )
    assert url.startswith("postgresql+asyncpg://reader:secret@db-replica.example.com")
    assert "sslmode" not in url
    assert connect_args.get("ssl") is not None
