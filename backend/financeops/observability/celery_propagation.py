from __future__ import annotations

from typing import Any

from celery.signals import before_task_publish, task_postrun, task_prerun

from financeops.observability.context import clear_request_context, set_request_context
from financeops.observability.propagation import current_correlation_id

_CORRELATION_HEADER = "correlation_id"
_REQUEST_HEADER = "request_id"


def _resolve_header_value(source: Any, key: str) -> str | None:
    if not isinstance(source, dict):
        return None
    value = source.get(key)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def connect_celery_correlation_signals() -> None:
    @before_task_publish.connect(weak=False)
    def _before_task_publish(
        sender: str | None = None,
        headers: dict[str, Any] | None = None,
        **_: Any,
    ) -> None:
        _ = sender
        if headers is None:
            return
        if _resolve_header_value(headers, _CORRELATION_HEADER):
            return
        correlation_id = current_correlation_id()
        if correlation_id:
            headers[_CORRELATION_HEADER] = correlation_id
            if not _resolve_header_value(headers, _REQUEST_HEADER):
                headers[_REQUEST_HEADER] = correlation_id

    @task_prerun.connect(weak=False)
    def _task_prerun(
        task_id: str | None = None,
        task: Any = None,
        kwargs: dict[str, Any] | None = None,
        **_: Any,
    ) -> None:
        request_meta = getattr(task, "request", None)
        request_headers = getattr(request_meta, "headers", None)
        correlation_id = (
            _resolve_header_value(request_headers, _CORRELATION_HEADER)
            or _resolve_header_value(kwargs or {}, _CORRELATION_HEADER)
            or task_id
        )
        request_id = _resolve_header_value(request_headers, _REQUEST_HEADER) or task_id or "unknown"
        tenant_id = _resolve_header_value(kwargs or {}, "tenant_id")
        set_request_context(
            request_id=request_id,
            correlation_id=correlation_id,
            tenant_id=tenant_id,
        )

    @task_postrun.connect(weak=False)
    def _task_postrun(**_: Any) -> None:
        clear_request_context()
