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
    Stores CircuitState per model name in Redis.
    Falls back to in-process dict if Redis is unavailable.
    """
    _REDIS_PREFIX = "financeops:circuit:"
    _REDIS_TTL = OPEN_SECONDS * 2

    def __init__(self, redis_client=None) -> None:
        self._redis = redis_client
        self._local: dict[str, CircuitState] = {}

    def _key(self, model_name: str) -> str:
        return f"{self._REDIS_PREFIX}{model_name}"

    async def _get_state(self, model_name: str) -> CircuitState:
        if self._redis is not None:
            try:
                raw = await self._redis.get(self._key(model_name))
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
        return self._local.get(model_name, CircuitState())

    async def _save_state(self, model_name: str, state: CircuitState) -> None:
        data = {
            "failures": state.failures,
            "opened_at": state.opened_at,
            "state": state.state,
        }
        if self._redis is not None:
            try:
                await self._redis.setex(
                    self._key(model_name),
                    self._REDIS_TTL,
                    json.dumps(data),
                )
                return
            except Exception as exc:
                log.warning("Redis circuit breaker write failed: %s", exc)
        self._local[model_name] = state

    async def is_open(self, model_name: str) -> bool:
        state = await self._get_state(model_name)
        return state.is_open()

    async def record_failure(self, model_name: str) -> None:
        state = await self._get_state(model_name)
        state.record_failure()
        await self._save_state(model_name, state)

    async def record_success(self, model_name: str) -> None:
        state = await self._get_state(model_name)
        state.record_success()
        await self._save_state(model_name, state)

    async def get_all_states(self) -> dict[str, str]:
        result: dict[str, str] = {}
        for name, state in self._local.items():
            result[name] = state.get_state()
        return result
