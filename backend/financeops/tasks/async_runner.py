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
    """Reuse one event loop per worker thread instead of creating a new loop per task."""
    return _get_runner().run(awaitable)


@atexit.register
def _close_runners() -> None:
    for runner in _RUNNERS:
        try:
            runner.close()
        except Exception:
            continue
