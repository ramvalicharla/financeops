from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from financeops.modules.erp_sync.infrastructure.connectors.http_backoff import (
    RateLimitError,
    TransientError,
    _compute_delay,
    _parse_retry_after,
    with_backoff,
)


class TestParseRetryAfter:
    def test_valid_header(self) -> None:
        response = httpx.Response(429, headers={"Retry-After": "12"})
        assert _parse_retry_after(response) == 12.0

    def test_invalid_header(self) -> None:
        response = httpx.Response(429, headers={"Retry-After": "abc"})
        assert _parse_retry_after(response) is None


class TestComputeDelay:
    def test_uses_retry_after(self) -> None:
        assert _compute_delay(1, 1.0, 60.0, 5.0) == 5.0

    def test_caps_retry_after(self) -> None:
        assert _compute_delay(1, 1.0, 10.0, 99.0) == 10.0

    def test_without_retry_after_is_bounded(self) -> None:
        delay = _compute_delay(2, 1.0, 8.0, None)
        assert 0.0 <= delay <= 8.0


class TestWithBackoff:
    @staticmethod
    def _resp(status: int, headers: dict[str, str] | None = None) -> httpx.Response:
        request = httpx.Request("GET", "https://example.com")
        return httpx.Response(status, request=request, headers=headers)

    @pytest.mark.asyncio
    async def test_success_returns_immediately(self) -> None:
        fn = AsyncMock(return_value=self._resp(200))
        result = await with_backoff(fn, max_retries=3)
        assert result.status_code == 200
        assert fn.call_count == 1

    @pytest.mark.asyncio
    async def test_429_retries_and_raises(self) -> None:
        fn = AsyncMock(return_value=self._resp(429))
        with patch("asyncio.sleep", new_callable=AsyncMock) as sleep_mock:
            with pytest.raises(RateLimitError) as exc:
                await with_backoff(fn, max_retries=2, base_delay=0.0)
        assert exc.value.status_code == 429
        assert fn.call_count == 3
        assert sleep_mock.call_count == 2

    @pytest.mark.asyncio
    async def test_5xx_retries_and_raises(self) -> None:
        fn = AsyncMock(return_value=self._resp(503))
        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(TransientError):
                await with_backoff(fn, max_retries=1, base_delay=0.0)
        assert fn.call_count == 2

    @pytest.mark.asyncio
    async def test_hard_4xx_no_retry(self) -> None:
        fn = AsyncMock(return_value=self._resp(401))
        result = await with_backoff(fn, max_retries=5)
        assert result.status_code == 401
        assert fn.call_count == 1

    @pytest.mark.asyncio
    async def test_success_after_retry(self) -> None:
        fn = AsyncMock(side_effect=[self._resp(429), self._resp(200)])
        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await with_backoff(fn, max_retries=3, base_delay=0.0)
        assert result.status_code == 200
        assert fn.call_count == 2

    @pytest.mark.asyncio
    async def test_retry_after_header_delay_used(self) -> None:
        fn = AsyncMock(side_effect=[self._resp(429, {"Retry-After": "7"}), self._resp(200)])
        delays: list[float] = []

        async def fake_sleep(seconds: float) -> None:
            delays.append(seconds)

        with patch("asyncio.sleep", side_effect=fake_sleep):
            await with_backoff(fn, max_retries=3, base_delay=1.0)

        assert delays == [7.0]
