from __future__ import annotations

import logging
import uuid
from collections import defaultdict, deque
from threading import Lock
from time import monotonic
from typing import Any

from financeops.observability.business_metrics import (
    airlock_failure_count,
    api_error_counter,
    auth_failure_counter,
    job_duration_ms,
    job_failure_count,
    job_success_count,
)
from financeops.observability.logger import log_event

log = logging.getLogger(__name__)

JOB_FAILURE_STREAK_ALERT_THRESHOLD = 3
API_ERROR_SPIKE_THRESHOLD = 5
AUTH_FAILURE_SPIKE_THRESHOLD = 5
AIRLOCK_FAILURE_SPIKE_THRESHOLD = 3
ALERT_WINDOW_SECONDS = 300.0
API_ERROR_WINDOW_SECONDS = 60.0
LONG_RUNNING_JOB_THRESHOLD_MS = 30_000.0

_state_lock = Lock()
_job_failure_streak = 0
_api_error_windows: dict[str, deque[float]] = defaultdict(deque)
_auth_failure_windows: dict[str, deque[float]] = defaultdict(deque)
_airlock_failure_windows: dict[str, deque[float]] = defaultdict(deque)


def _stringify(value: Any) -> Any:
    if isinstance(value, uuid.UUID):
        return str(value)
    return value


def _emit_event(
    event: str,
    *,
    level: int = logging.INFO,
    exc_info: BaseException | None = None,
    entity_id: uuid.UUID | str | None = None,
    intent_id: uuid.UUID | str | None = None,
    details: dict[str, Any] | None = None,
    **fields: Any,
) -> None:
    log_event(
        log,
        event,
        level=level,
        exc_info=exc_info,
        entity_id=_stringify(entity_id),
        intent_id=_stringify(intent_id),
        details={key: _stringify(value) for key, value in (details or {}).items()},
        **{key: _stringify(value) for key, value in fields.items()},
    )


def _record_window(
    windows: dict[str, deque[float]],
    *,
    key: str,
    window_seconds: float,
) -> int:
    now = monotonic()
    with _state_lock:
        bucket = windows[key]
        bucket.append(now)
        cutoff = now - window_seconds
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        return len(bucket)


def record_job_started(
    *,
    job_id: uuid.UUID | str,
    intent_id: uuid.UUID | str | None,
    entity_id: uuid.UUID | str | None,
    runner_type: str | None,
) -> None:
    _emit_event(
        "job_started",
        job_id=job_id,
        entity_id=entity_id,
        intent_id=intent_id,
        details={
            "job_id": _stringify(job_id),
            "status": "started",
            "runner_type": runner_type,
        },
    )


def record_job_finished(
    *,
    job_id: uuid.UUID | str,
    intent_id: uuid.UUID | str | None,
    entity_id: uuid.UUID | str | None,
    status: str,
    duration_ms: float,
    error: str | None = None,
    retry_count: int | None = None,
    max_retries: int | None = None,
) -> None:
    global _job_failure_streak

    job_duration_ms.observe(duration_ms)
    details = {
        "job_id": _stringify(job_id),
        "status": status,
        "duration_ms": round(duration_ms, 2),
        "error": error,
        "retry_count": retry_count,
        "max_retries": max_retries,
    }

    if status == "success":
        job_success_count.inc()
        with _state_lock:
            _job_failure_streak = 0
        _emit_event(
            "job_succeeded",
            job_id=job_id,
            entity_id=entity_id,
            intent_id=intent_id,
            details=details,
        )
    else:
        job_failure_count.inc()
        with _state_lock:
            _job_failure_streak += 1
            streak = _job_failure_streak
        _emit_event(
            "job_failed",
            level=logging.ERROR,
            job_id=job_id,
            entity_id=entity_id,
            intent_id=intent_id,
            details=details,
        )
        if streak > JOB_FAILURE_STREAK_ALERT_THRESHOLD:
            _emit_event(
                "job_failure_streak_alert",
                level=logging.WARNING,
                job_id=job_id,
                entity_id=entity_id,
                intent_id=intent_id,
                details={
                    **details,
                    "failure_streak": streak,
                    "alert_threshold": JOB_FAILURE_STREAK_ALERT_THRESHOLD,
                },
            )

    if duration_ms > LONG_RUNNING_JOB_THRESHOLD_MS:
        _emit_event(
            "job_duration_exceeded",
            level=logging.WARNING,
            job_id=job_id,
            entity_id=entity_id,
            intent_id=intent_id,
            details={
                **details,
                "expected_duration_ms": LONG_RUNNING_JOB_THRESHOLD_MS,
            },
        )


def record_airlock_status(
    *,
    file_id: uuid.UUID | str,
    entity_id: uuid.UUID | str | None,
    status: str,
    validation_results: list[dict[str, Any]] | None = None,
    reason: str | None = None,
    source_type: str | None = None,
) -> None:
    details = {
        "file_id": _stringify(file_id),
        "status": status,
        "validation_results": validation_results or [],
        "reason": reason,
        "source_type": source_type,
    }
    event_name = f"airlock_{status.lower()}"
    level = logging.ERROR if status == "rejected" else logging.INFO
    _emit_event(
        event_name,
        level=level,
        file_id=file_id,
        entity_id=entity_id,
        details=details,
    )

    if status == "rejected":
        airlock_failure_count.inc()
        source_key = source_type or "unknown"
        failure_count = _record_window(
            _airlock_failure_windows,
            key=source_key,
            window_seconds=ALERT_WINDOW_SECONDS,
        )
        if failure_count >= AIRLOCK_FAILURE_SPIKE_THRESHOLD:
            _emit_event(
                "airlock_failure_spike",
                level=logging.WARNING,
                file_id=file_id,
                entity_id=entity_id,
                details={
                    **details,
                    "failure_count": failure_count,
                    "alert_window_seconds": ALERT_WINDOW_SECONDS,
                },
            )


def record_auth_event(
    *,
    event: str,
    outcome: str,
    user_id: uuid.UUID | str | None = None,
    tenant_id: uuid.UUID | str | None = None,
    email: str | None = None,
    failure_type: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    level = logging.ERROR if outcome == "failure" else logging.INFO
    payload = {
        "outcome": outcome,
        "failure_type": failure_type,
        "email": email,
        **(details or {}),
    }
    _emit_event(
        event,
        level=level,
        user_id=user_id,
        tenant_id=tenant_id,
        details=payload,
    )
    if outcome == "failure":
        auth_failure_counter.labels(failure_type=failure_type or "unknown").inc()
        key = failure_type or email or "global"
        failure_count = _record_window(
            _auth_failure_windows,
            key=key,
            window_seconds=ALERT_WINDOW_SECONDS,
        )
        if failure_count >= AUTH_FAILURE_SPIKE_THRESHOLD:
            _emit_event(
                "auth_failure_spike",
                level=logging.WARNING,
                user_id=user_id,
                tenant_id=tenant_id,
                details={
                    **payload,
                    "failure_count": failure_count,
                    "alert_window_seconds": ALERT_WINDOW_SECONDS,
                },
            )


def record_api_error(
    *,
    method: str,
    path: str,
    status_code: int,
    error_type: str,
    duration_ms: float,
    exc_info: BaseException | None = None,
) -> None:
    api_error_counter.labels(
        method=method,
        path=path,
        status_code=str(status_code),
    ).inc()
    key = f"{method}:{path}"
    error_count = _record_window(
        _api_error_windows,
        key=key,
        window_seconds=API_ERROR_WINDOW_SECONDS,
    )
    details = {
        "endpoint": path,
        "method": method,
        "status_code": status_code,
        "error_type": error_type,
        "duration_ms": round(duration_ms, 2),
    }
    _emit_event(
        "api_error",
        level=logging.ERROR,
        exc_info=exc_info,
        details=details,
    )
    if error_count >= API_ERROR_SPIKE_THRESHOLD:
        _emit_event(
            "api_error_rate_spike",
            level=logging.WARNING,
            details={
                **details,
                "error_count": error_count,
                "alert_window_seconds": API_ERROR_WINDOW_SECONDS,
            },
        )


def reset_monitoring_state_for_tests() -> None:
    global _job_failure_streak
    with _state_lock:
        _job_failure_streak = 0
        _api_error_windows.clear()
        _auth_failure_windows.clear()
        _airlock_failure_windows.clear()
