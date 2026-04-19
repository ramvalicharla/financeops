from __future__ import annotations


class FixedAssetError(Exception):
    pass


class DepreciationCalculationError(FixedAssetError):
    def __init__(self, asset_id: object, reason: str):
        super().__init__(f"Depreciation error for asset {asset_id}: {reason}")
