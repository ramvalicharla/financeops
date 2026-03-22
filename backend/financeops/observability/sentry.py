from __future__ import annotations

from typing import Any

import sentry_sdk
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.redis import RedisIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

_SENSITIVE_FIELD_NAMES = {
    "password",
    "token",
    "secret",
    "api_key",
    "pan",
    "account_number",
}


def _scrub_sensitive_fields(value: Any) -> Any:
    if isinstance(value, dict):
        scrubbed: dict[str, Any] = {}
        for key, item in value.items():
            if key.lower() in _SENSITIVE_FIELD_NAMES:
                scrubbed[key] = "[Filtered]"
            else:
                scrubbed[key] = _scrub_sensitive_fields(item)
        return scrubbed
    if isinstance(value, list):
        return [_scrub_sensitive_fields(item) for item in value]
    return value


def _scrub_sensitive_data(event: dict[str, Any], hint: dict[str, Any]) -> dict[str, Any]:
    del hint  # Unused by current scrubber logic.
    request = event.get("request", {})
    headers = request.get("headers", {})

    if isinstance(headers, dict):
        for key in list(headers.keys()):
            if key.lower() in ("authorization", "x-tenant-id", "cookie"):
                headers[key] = "[Filtered]"

    return _scrub_sensitive_fields(event)


def configure_sentry(dsn: str, environment: str, release: str) -> None:
    if not dsn:
        return  # Sentry disabled if no DSN configured.

    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        release=release,
        integrations=[
            FastApiIntegration(transaction_style="endpoint"),
            SqlalchemyIntegration(),
            CeleryIntegration(),
            RedisIntegration(),
        ],
        traces_sample_rate=0.1,
        profiles_sample_rate=0.1,
        send_default_pii=False,
        before_send=_scrub_sensitive_data,
    )

