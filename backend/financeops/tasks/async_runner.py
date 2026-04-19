from __future__ import annotations

import atexit
import asyncio
from threading import local
from typing import TypeVar

_T = TypeVar("_T")
_STATE = local()
_RUNNERS: list[asyncio.Runner] = []


def _get_runner() -> asyncio.Runner:
    runner = getattr(_STATE, "runner", None)
    if runner is None:
        runner = asyncio.Runner()
        _STATE.runner = runner
        _RUNNERS.append(runner)
    return runner


def run_async(awaitable: "asyncio.Future[_T] | asyncio.coroutines.Coroutine[object, object, _T]") -> _T:
    """Reuse one event loop per worker thread instead of creating a new loop per task.

    Saves and restores the thread's current event loop so that callers running
    inside a pytest-asyncio session loop (or any other pre-existing loop) are
    not permanently displaced by the runner's private loop.  In a plain Celery
    worker thread there is no prior loop, so the finally branch is a no-op.
    """
    try:
        _prior_loop: asyncio.AbstractEventLoop | None = asyncio.get_event_loop_policy().get_event_loop()
    except RuntimeError:
        _prior_loop = None
    try:
        return _get_runner().run(awaitable)
    finally:
        asyncio.get_event_loop_policy().set_event_loop(_prior_loop)


@atexit.register
def _close_runners() -> None:
    for runner in _RUNNERS:
        try:
            runner.close()
        except Exception:
            continue
