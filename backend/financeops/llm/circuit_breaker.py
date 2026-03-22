from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Literal

log = logging.getLogger(__name__)

FAILURE_THRESHOLD = 3
WINDOW_SECONDS = 300   # 5 minutes — sliding window for failure counting
OPEN_SECONDS = 600     # 10 minutes — circuit stays open before half-open probe


@dataclass
class CircuitState:
    failures: list[float] = field(default_factory=list)
    opened_at: float | None = None
    state: Literal["CLOSED", "OPEN", "HALF_OPEN"] = "CLOSED"

    @property
    def failure_count(self) -> int:
        now = time.time()
        return len([t for t in self.failures if now - t < WINDOW_SECONDS])

    def is_open(self) -> bool:
        return self.get_state() == "OPEN"

    def record_failure(self) -> None:
        now = time.time()
        self.failures = [t for t in self.failures if now - t < WINDOW_SECONDS]
        self.failures.append(now)
        if len(self.failures) >= FAILURE_THRESHOLD and self.opened_at is None:
            self.opened_at = now
            self.state = "OPEN"
            log.warning("Circuit OPENED for model (threshold=%d reached)", FAILURE_THRESHOLD)

    def record_success(self) -> None:
        self.failures = []
        self.opened_at = None
        self.state = "CLOSED"

    def get_state(self) -> str:
        if self.opened_at is None:
            return "CLOSED"
        elapsed = time.time() - self.opened_at
        if elapsed >= OPEN_SECONDS:
            return "HALF_OPEN"
        return "OPEN"


class CircuitBreakerRegistry:
    """
    Stores CircuitState per model key in Redis.
    The key can be provided as "provider/model" or as (provider, model).
    """
    _REDIS_PREFIX = "financeops:circuit:"
    _REDIS_TTL = OPEN_SECONDS * 2

    def __init__(self, redis_client=None) -> None:
        self._redis = redis_client

    def _normalize_model_key(self, provider_or_model: str, model_name: str | None = None) -> str:
        if model_name is not None:
            return f"{provider_or_model}/{model_name}"
        return provider_or_model

    def _key(self, model_key: str) -> str:
        return f"{self._REDIS_PREFIX}{model_key}"

    async def _get_state(self, model_key: str) -> CircuitState:
        if self._redis is None:
            return CircuitState()
        try:
            raw = await self._redis.get(self._key(model_key))
            if raw:
                data = json.loads(raw)
                state = CircuitState(
                    failures=data.get("failures", []),
                    opened_at=data.get("opened_at"),
                    state=data.get("state", "CLOSED"),
                )
                return state
        except Exception as exc:
            log.warning("Redis circuit breaker read failed: %s", exc)
        return CircuitState()

    async def _save_state(self, model_key: str, state: CircuitState) -> None:
        if self._redis is None:
            return
        data = {
            "failures": state.failures,
            "opened_at": state.opened_at,
            "state": state.state,
        }
        try:
            await self._redis.setex(
                self._key(model_key),
                self._REDIS_TTL,
                json.dumps(data),
            )
        except Exception as exc:
            log.warning("Redis circuit breaker write failed: %s", exc)

    async def get_state(self, provider_or_model: str, model_name: str | None = None) -> CircuitState:
        model_key = self._normalize_model_key(provider_or_model, model_name)
        return await self._get_state(model_key)

    async def is_open(self, provider_or_model: str, model_name: str | None = None) -> bool:
        model_key = self._normalize_model_key(provider_or_model, model_name)
        state = await self._get_state(model_key)
        return state.is_open()

    async def record_failure(self, provider_or_model: str, model_name: str | None = None) -> None:
        model_key = self._normalize_model_key(provider_or_model, model_name)
        state = await self._get_state(model_key)
        state.record_failure()
        await self._save_state(model_key, state)

    async def record_success(self, provider_or_model: str, model_name: str | None = None) -> None:
        model_key = self._normalize_model_key(provider_or_model, model_name)
        state = await self._get_state(model_key)
        state.record_success()
        await self._save_state(model_key, state)

    async def get_all_states(self) -> dict[str, str]:
        result: dict[str, str] = {}
        if self._redis is None:
            return result
        try:
            keys = await self._redis.keys(f"{self._REDIS_PREFIX}*")
            for key in keys:
                raw = await self._redis.get(key)
                if not raw:
                    continue
                data = json.loads(raw)
                name = str(key).replace(self._REDIS_PREFIX, "", 1)
                state = CircuitState(
                    failures=data.get("failures", []),
                    opened_at=data.get("opened_at"),
                    state=data.get("state", "CLOSED"),
                )
                result[name] = state.get_state()
        except Exception as exc:
            log.warning("Redis circuit breaker list failed: %s", exc)
        return result
