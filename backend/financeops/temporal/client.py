from __future__ import annotations

import logging

from financeops.config import settings

log = logging.getLogger(__name__)

_temporal_client = None


async def get_temporal_client():
    """
    Return a cached Temporal client.
    Imported lazily so API startup does not fail if Temporal is unavailable.
    """
    global _temporal_client
    if _temporal_client is None:
        from temporalio.client import Client

        _temporal_client = await Client.connect(
            settings.TEMPORAL_ADDRESS,
            namespace=settings.TEMPORAL_NAMESPACE,
        )
    return _temporal_client


async def check_temporal_health() -> dict[str, str]:
    """
    Lightweight connectivity check: establish client connection.
    """
    try:
        await get_temporal_client()
        return {"status": "ok"}
    except Exception as exc:
        log.warning("Temporal health check failed: %s", exc)
        return {"status": "error", "detail": str(exc)}
