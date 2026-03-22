from __future__ import annotations

from dataclasses import dataclass

from financeops.modules.erp_sync.domain.enums import ConnectorType, DatasetType


@dataclass(frozen=True)
class ConnectorCapability:
    connector_type: ConnectorType
    dataset_type: DatasetType
    supports_full_sync: bool = True
    supports_incremental_sync: bool = False
    supports_resumable_extraction: bool = False


class ConnectorCapabilityMatrix:
    def __init__(self, capabilities: list[ConnectorCapability]) -> None:
        self._capabilities = capabilities

    def supports(self, connector_type: ConnectorType, dataset_type: DatasetType) -> bool:
        for item in self._capabilities:
            if item.connector_type == connector_type and item.dataset_type == dataset_type:
                return True
        return False

    def list_for_connector(self, connector_type: ConnectorType) -> list[ConnectorCapability]:
        return [item for item in self._capabilities if item.connector_type == connector_type]
