from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from financeops.modules.erp_sync.domain.enums import DatasetType
from financeops.modules.erp_sync.infrastructure.connectors.http_backoff import RateLimitError
from financeops.modules.erp_sync.infrastructure.connectors.quickbooks import (
    QuickbooksConnector,
)


@pytest.fixture
def connector() -> QuickbooksConnector:
    return QuickbooksConnector()


@pytest.fixture
def credentials() -> dict[str, str]:
    return {
        "client_id": "cid",
        "client_secret": "csec",
        "realm_id": "realm",
        "access_token": "token",
    }


class TestQboContract:
    def test_supported_datasets_have_endpoint_entries(self, connector: QuickbooksConnector) -> None:
        for dataset in connector.supported_datasets:
            assert dataset in connector._DATASET_ENDPOINTS

    def test_supported_count_matches_endpoint_map(self, connector: QuickbooksConnector) -> None:
        assert len(connector.supported_datasets) == len(connector._DATASET_ENDPOINTS)

    def test_supports_resumable(self, connector: QuickbooksConnector) -> None:
        assert connector.supports_resumable_extraction is True


class TestQboCheckpoint:
    def test_next_checkpoint_none_when_last_page(self) -> None:
        payload = {"totalCount": 150}
        result = QuickbooksConnector._next_checkpoint(payload=payload, start_position=101, max_results=100)
        assert result is None

    def test_next_checkpoint_when_more_pages(self) -> None:
        payload = {"totalCount": 300}
        result = QuickbooksConnector._next_checkpoint(payload=payload, start_position=1, max_results=100)
        assert result == {"startPosition": 101, "maxResults": 100}


class TestQboExtract:
    @pytest.mark.asyncio
    async def test_extract_returns_canonical_keys(self, connector: QuickbooksConnector, credentials: dict[str, str]) -> None:
        async def fake_request(*args, **kwargs):
            return {
                "Rows": {"Row": [{"account": "1000", "amount": "10.00"}]},
                "totalCount": 1,
            }

        with patch.object(connector, "_request_json", side_effect=fake_request):
            result = await connector.extract(DatasetType.TRIAL_BALANCE, credentials=credentials)

        expected = {
            "dataset_type",
            "raw_data",
            "records",
            "line_count",
            "is_resumable",
            "next_checkpoint",
        }
        assert expected.issubset(set(result.keys()))
        assert result["dataset_type"] == DatasetType.TRIAL_BALANCE.value

    @pytest.mark.asyncio
    async def test_checkpoint_input_used(self, connector: QuickbooksConnector, credentials: dict[str, str]) -> None:
        captured_params: list[dict[str, object]] = []

        async def fake_request(*args, **kwargs):
            captured_params.append(dict(kwargs["params"]))
            return {"Rows": {"Row": []}, "totalCount": 0}

        with patch.object(connector, "_request_json", side_effect=fake_request):
            await connector.extract(
                DatasetType.TRIAL_BALANCE,
                credentials=credentials,
                checkpoint={"startPosition": 201, "maxResults": 50},
            )

        assert captured_params[0]["startPosition"] == 201
        assert captured_params[0]["maxResults"] == 50


class TestQboBackoffIntegration:
    @pytest.mark.asyncio
    async def test_rate_limit_error_propagates(self, connector: QuickbooksConnector) -> None:
        with patch(
            "financeops.modules.erp_sync.infrastructure.connectors.quickbooks.with_backoff",
            new_callable=AsyncMock,
            side_effect=RateLimitError(429, 3),
        ):
            with pytest.raises(RateLimitError):
                await connector._request_json(
                    {"use_sandbox": True},
                    endpoint="company/realm/query",
                    access_token="token",
                    params={},
                    body={"query": "SELECT 1"},
                    method="POST",
                )
