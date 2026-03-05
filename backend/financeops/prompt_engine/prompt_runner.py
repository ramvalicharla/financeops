from __future__ import annotations

from collections.abc import Callable
import logging

from financeops.prompt_engine import PromptDefinition, PromptRunResult

log = logging.getLogger(__name__)

PromptExecutorCallback = Callable[[PromptDefinition], PromptRunResult]


class PromptRunner:
    """
    Executes a single prompt through a pluggable callback.

    The engine intentionally keeps execution transport abstract so it can
    integrate with different AI runtimes without changing orchestration logic.
    """

    def __init__(self, callback: PromptExecutorCallback | None = None) -> None:
        self.callback = callback

    def run(self, prompt: PromptDefinition) -> PromptRunResult:
        if self.callback is None:
            return PromptRunResult(
                completed=False,
                failure_reason=(
                    "No prompt execution backend configured. "
                    "Provide a PromptRunner callback."
                ),
            )

        try:
            result = self.callback(prompt)
            if not isinstance(result, PromptRunResult):
                return PromptRunResult(
                    completed=False,
                    failure_reason=(
                        "Prompt executor returned invalid result type; "
                        "expected PromptRunResult."
                    ),
                )
            return result
        except Exception as exc:
            log.exception("Prompt execution callback failed for %s", prompt.prompt_id)
            return PromptRunResult(
                completed=False,
                failure_reason=f"Prompt execution callback error: {exc}",
            )

