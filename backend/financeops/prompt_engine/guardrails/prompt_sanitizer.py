from __future__ import annotations

from dataclasses import dataclass

from financeops.prompt_engine.guardrails.security_policy import (
    EXTERNAL_COMMAND_PATTERNS,
    FILESYSTEM_ESCAPE_PATTERNS,
    PROMPT_INJECTION_PATTERNS,
)


@dataclass(slots=True)
class SanitizationResult:
    ok: bool
    reason: str | None = None


class PromptSanitizer:
    def sanitize(self, prompt_text: str) -> SanitizationResult:
        text = prompt_text.lower()

        for marker in FILESYSTEM_ESCAPE_PATTERNS:
            if marker in text:
                return SanitizationResult(
                    ok=False, reason=f"Filesystem escape marker detected: {marker}"
                )

        for marker in PROMPT_INJECTION_PATTERNS:
            if marker in text:
                return SanitizationResult(
                    ok=False, reason=f"Prompt-injection pattern detected: {marker}"
                )

        for marker in EXTERNAL_COMMAND_PATTERNS:
            if marker in text:
                return SanitizationResult(
                    ok=False,
                    reason=f"External command execution instruction detected: {marker}",
                )

        return SanitizationResult(ok=True)

