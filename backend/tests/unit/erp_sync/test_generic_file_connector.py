from __future__ import annotations

import pytest

from financeops.modules.erp_sync.infrastructure.connectors.generic_file import (
    GenericFileConnector,
)


@pytest.mark.asyncio
async def test_generic_file_test_connection_reports_ok_for_supported_extension() -> None:
    connector = GenericFileConnector()
    result = await connector.test_connection({"filename": "sample.csv"})
    assert result["ok"] is True
    assert result["latency_ms"] == 0


@pytest.mark.asyncio
async def test_generic_file_test_connection_reports_error_for_unsupported_extension() -> None:
    connector = GenericFileConnector()
    result = await connector.test_connection({"filename": "sample.txt"})
    assert result["ok"] is False
    assert "Unsupported file format" in result["error"]
