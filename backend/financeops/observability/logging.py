from __future__ import annotations

import logging
import sys
from typing import Any

from pythonjsonlogger import jsonlogger

from financeops.observability.context import (
    get_correlation_id,
    get_org_entity_id,
    get_request_id,
    get_tenant_id,
)

_SENSITIVE_KEYS = (
    "password",
    "secret",
    "token",
    "api_key",
    "authorization",
    "credential",
    "dsn",
)
_MASK = "***"


def _looks_sensitive(key: str) -> bool:
    lowered = key.lower()
    return any(part in lowered for part in _SENSITIVE_KEYS)


def _sanitize_record(record: logging.LogRecord) -> None:
    for key, value in list(record.__dict__.items()):
        if _looks_sensitive(key):
            record.__dict__[key] = _MASK
            continue
        if isinstance(value, str) and _looks_sensitive(value):
            # Defensive masking for accidental secret-ish marker strings.
            record.__dict__[key] = _MASK


class _RequestContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        record.correlation_id = get_correlation_id()
        record.tenant_id = get_tenant_id()
        record.org_entity_id = get_org_entity_id()
        record.service = "financeops-backend"
        _sanitize_record(record)
        return True


class _SafeJsonFormatter(jsonlogger.JsonFormatter):
    def add_fields(
        self,
        log_record: dict[str, Any],
        record: logging.LogRecord,
        message_dict: dict[str, Any],
    ) -> None:
        super().add_fields(log_record, record, message_dict)
        # Normalize event naming for downstream processors.
        if "event" not in log_record:
            log_record["event"] = record.getMessage()


def configure_logging(log_level: str = "INFO") -> None:
    """
    Configure structured JSON logging for all FinanceOps loggers.
    """
    handler = logging.StreamHandler(sys.stdout)
    formatter = _SafeJsonFormatter(
        fmt=(
            "%(asctime)s %(levelname)s %(name)s %(message)s %(event)s "
            "%(request_id)s %(correlation_id)s %(tenant_id)s %(org_entity_id)s "
            "%(service)s %(module)s %(funcName)s %(lineno)d"
        ),
        datefmt="%Y-%m-%dT%H:%M:%S",
        rename_fields={
            "asctime": "timestamp",
            "levelname": "level",
            "name": "logger",
            "funcName": "function",
            "lineno": "line",
        },
    )
    handler.addFilter(_RequestContextFilter())
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(log_level.upper())

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("celery").setLevel(logging.INFO)
