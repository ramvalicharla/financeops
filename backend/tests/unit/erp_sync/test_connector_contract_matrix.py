from __future__ import annotations

from financeops.modules.erp_sync.domain.enums import DatasetType
from financeops.modules.erp_sync.infrastructure.connectors.quickbooks import (
    QuickbooksConnector,
)
from financeops.modules.erp_sync.infrastructure.connectors.zoho import (
    ZohoConnector,
    _DATASET_CONFIG,
)


class TestZohoContract:
    def test_supported_datasets_have_config(self) -> None:
        connector = ZohoConnector()
        for dataset in connector.supported_datasets:
            assert dataset in _DATASET_CONFIG

    def test_cash_flow_statement_removed(self) -> None:
        connector = ZohoConnector()
        assert DatasetType.CASH_FLOW_STATEMENT not in connector.supported_datasets

    def test_supports_resumable(self) -> None:
        connector = ZohoConnector()
        assert connector.supports_resumable_extraction is True

    def test_dataset_count_is_14(self) -> None:
        connector = ZohoConnector()
        assert len(connector.supported_datasets) == 14

    def test_paginated_configs_define_records_key(self) -> None:
        for _, config in _DATASET_CONFIG.items():
            if config.get("paginated"):
                assert "records_key" in config

    def test_envelope_contains_canonical_keys(self) -> None:
        connector = ZohoConnector()
        payload = connector._build_envelope(
            dataset_type=DatasetType.TRIAL_BALANCE,
            payload={},
            records=[],
            is_resumable=False,
            next_checkpoint=None,
        )
        expected = {
            "dataset_type",
            "payload",
            "records",
            "line_count",
            "erp_reported_line_count",
            "is_resumable",
            "next_checkpoint",
        }
        assert expected.issubset(set(payload.keys()))


class TestQboContract:
    def test_supported_datasets_have_endpoints(self) -> None:
        connector = QuickbooksConnector()
        for dataset in connector.supported_datasets:
            assert dataset in connector._DATASET_ENDPOINTS

    def test_endpoint_map_matches_supported_set(self) -> None:
        connector = QuickbooksConnector()
        assert set(connector._DATASET_ENDPOINTS.keys()) == set(connector.supported_datasets)

    def test_supports_resumable(self) -> None:
        connector = QuickbooksConnector()
        assert connector.supports_resumable_extraction is True
