from __future__ import annotations


class GstReconError(Exception):
    pass


class InvalidGstinError(GstReconError):
    def __init__(self, gstin: str) -> None:
        super().__init__(f"Invalid GSTIN format: {gstin}")


class GstReturnNotFoundError(GstReconError):
    def __init__(self, period: str, return_type: str) -> None:
        super().__init__(f"No {return_type} found for period {period}")


class GstRateMasterNotSeededError(GstReconError):
    pass
