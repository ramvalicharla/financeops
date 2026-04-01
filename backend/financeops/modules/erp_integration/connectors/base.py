from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any


class BaseConnector(ABC):
    """ERP connector contract for Phase 7 import/export flows."""

    @abstractmethod
    async def authenticate(self, *, connection_config: Mapping[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def fetch_chart_of_accounts(
        self,
        *,
        connection_config: Mapping[str, Any],
    ) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    async def fetch_transactions(
        self,
        *,
        connection_config: Mapping[str, Any],
    ) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    async def push_journal(
        self,
        *,
        connection_config: Mapping[str, Any],
        journal_payload: Mapping[str, Any],
    ) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def fetch_vendors(
        self,
        *,
        connection_config: Mapping[str, Any],
    ) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    async def fetch_customers(
        self,
        *,
        connection_config: Mapping[str, Any],
    ) -> list[dict[str, Any]]:
        raise NotImplementedError
