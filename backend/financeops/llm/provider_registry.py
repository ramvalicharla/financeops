from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum


class ProviderStatus(str, Enum):
    ACTIVE = "active"
    DEGRADED = "degraded"
    DISABLED = "disabled"


@dataclass(slots=True)
class ProviderSlot:
    name: str
    provider: str
    model: str
    base_url: str | None = None
    task_types: list[str] = field(default_factory=list)
    max_tokens: int = 1000
    priority: int = 1
    status: ProviderStatus = ProviderStatus.ACTIVE
    sensitivity_allowed: bool = True
    cost_per_1k_tokens: Decimal = Decimal("0.003")


class ProviderRegistry:
    """
    Runtime registry of provider slots.
    """

    def __init__(self) -> None:
        self._slots: dict[str, ProviderSlot] = {}

    def register(self, slot: ProviderSlot) -> None:
        self._slots[slot.name] = slot

    def list_all(self) -> list[ProviderSlot]:
        return sorted(self._slots.values(), key=lambda row: row.priority)

    def get(self, slot_name: str) -> ProviderSlot | None:
        return self._slots.get(slot_name)

    def get_for_task(
        self,
        task_type: str,
        *,
        allow_cloud: bool = True,
    ) -> list[ProviderSlot]:
        rows = [
            slot
            for slot in self._slots.values()
            if slot.status == ProviderStatus.ACTIVE
            and (task_type in slot.task_types or len(slot.task_types) == 0)
            and (allow_cloud or slot.provider == "ollama")
        ]
        return sorted(rows, key=lambda row: row.priority)

    def disable(self, slot_name: str) -> bool:
        slot = self._slots.get(slot_name)
        if slot is None:
            return False
        slot.status = ProviderStatus.DISABLED
        return True

    def enable(self, slot_name: str) -> bool:
        slot = self._slots.get(slot_name)
        if slot is None:
            return False
        slot.status = ProviderStatus.ACTIVE
        return True

    def update(
        self,
        slot_name: str,
        *,
        priority: int | None = None,
        task_types: list[str] | None = None,
        status: ProviderStatus | None = None,
    ) -> ProviderSlot | None:
        slot = self._slots.get(slot_name)
        if slot is None:
            return None
        if priority is not None:
            slot.priority = priority
        if task_types is not None:
            slot.task_types = task_types
        if status is not None:
            slot.status = status
        return slot


provider_registry = ProviderRegistry()

__all__ = [
    "ProviderStatus",
    "ProviderSlot",
    "ProviderRegistry",
    "provider_registry",
]
