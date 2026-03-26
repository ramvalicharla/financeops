from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, model_validator

T = TypeVar("T")


class Paginated(BaseModel, Generic[T]):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    # New canonical fields
    items: list[T]
    total: int
    skip: int
    limit: int
    has_more: bool

    # Backward compatibility fields used by existing routes/tests.
    data: list[T]
    offset: int

    @model_validator(mode="before")
    @classmethod
    def _normalize_input(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        payload = dict(value)

        if "items" not in payload and "data" in payload:
            payload["items"] = payload["data"]
        if "data" not in payload and "items" in payload:
            payload["data"] = payload["items"]

        if "skip" not in payload and "offset" in payload:
            payload["skip"] = payload["offset"]
        if "offset" not in payload and "skip" in payload:
            payload["offset"] = payload["skip"]

        if "has_more" not in payload:
            total = int(payload.get("total", 0))
            skip = int(payload.get("skip", payload.get("offset", 0)))
            limit = int(payload.get("limit", 0))
            payload["has_more"] = (skip + limit) < total if limit > 0 else False

        return payload
