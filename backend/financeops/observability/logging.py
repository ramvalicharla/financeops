from __future__ import annotations

import logging
import sys

from pythonjsonlogger import jsonlogger

from financeops.observability.context import get_request_id, get_tenant_id


class _RequestContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        record.tenant_id = get_tenant_id()
        return True


def configure_logging(log_level: str = "INFO") -> None:
    """
    Configure structured JSON logging for all FinanceOps loggers.
    Output goes to stdout — ready for any log aggregator.
    Every log line is valid JSON with these fields:
      timestamp, level, logger, message,
      request_id (if in context), tenant_id (if in context),
      module, function, line
    """
    handler = logging.StreamHandler(sys.stdout)
    formatter = jsonlogger.JsonFormatter(
        fmt=(
            "%(asctime)s %(levelname)s %(name)s %(message)s "
            "%(request_id)s %(tenant_id)s %(module)s %(funcName)s %(lineno)d"
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

    # Quiet noisy third-party loggers.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("celery").setLevel(logging.INFO)

