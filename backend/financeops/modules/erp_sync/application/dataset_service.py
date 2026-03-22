from __future__ import annotations

from typing import Any

from financeops.modules.erp_sync.domain.enums import DatasetType


ACTIVE_DATASETS: frozenset[DatasetType] = frozenset(
    {
        DatasetType.GST_RETURN_GSTR9,
        DatasetType.GST_RETURN_GSTR9C,
        DatasetType.FORM_26AS,
        DatasetType.AIS_REGISTER,
    }
)


class DatasetService:
    def is_active(self, dataset_type: DatasetType) -> bool:
        return dataset_type in ACTIVE_DATASETS

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        dataset_type_raw = kwargs.get("dataset_type")
        if isinstance(dataset_type_raw, DatasetType):
            dataset_type = dataset_type_raw
        elif isinstance(dataset_type_raw, str):
            dataset_type = DatasetType(dataset_type_raw)
        else:
            dataset_type = None

        if dataset_type is None:
            return {
                "service": "DatasetService",
                "active_dataset_types": sorted(dataset.value for dataset in ACTIVE_DATASETS),
            }
        return {
            "service": "DatasetService",
            "dataset_type": dataset_type.value,
            "active": self.is_active(dataset_type),
        }
