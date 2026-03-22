from __future__ import annotations

import pytest

from financeops.modules.erp_sync.domain.enums import ConnectorType, DatasetType
from financeops.modules.erp_sync.infrastructure.connectors.base import (
    ConnectorCapabilityNotSupported,
)
from financeops.modules.erp_sync.infrastructure.connectors.registry import (
    CONNECTOR_REGISTRY,
    get_connector,
)


LIVE_CONNECTORS = {ConnectorType.ZOHO, ConnectorType.GENERIC_FILE}


def test_all_connector_types_are_registered() -> None:
    assert set(CONNECTOR_REGISTRY.keys()) == set(ConnectorType)
    assert len(CONNECTOR_REGISTRY) == 23


@pytest.mark.asyncio
async def test_stub_connectors_raise_capability_not_supported() -> None:
    unsupported_count = 0
    for connector_type in ConnectorType:
        connector = get_connector(connector_type)
        if connector_type in LIVE_CONNECTORS:
            continue
        with pytest.raises(ConnectorCapabilityNotSupported):
            await connector.extract(DatasetType.TRIAL_BALANCE)
        unsupported_count += 1
    assert unsupported_count == 21


def test_live_connectors_declare_supported_capabilities() -> None:
    for connector_type in LIVE_CONNECTORS:
        connector = get_connector(connector_type)
        assert connector.supported_datasets
        assert DatasetType.TRIAL_BALANCE in connector.supported_datasets
