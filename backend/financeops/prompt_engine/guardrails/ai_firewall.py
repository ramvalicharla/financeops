from __future__ import annotations

from dataclasses import dataclass

from financeops.prompt_engine.guardrails.security_policy import (
    AI_FIREWALL_PATTERNS,
    SECRET_ACCESS_PATTERNS,
)


@dataclass(slots=True)
class FirewallResult:
    ok: bool
    reason: str | None = None


class AIFirewall:
    def check(self, prompt_text: str) -> FirewallResult:
        text = prompt_text.lower()

        for marker in AI_FIREWALL_PATTERNS:
            if marker in text:
                return FirewallResult(
                    ok=False, reason=f"Blocked unsafe code pattern: {marker}"
                )

        for marker in SECRET_ACCESS_PATTERNS:
            if marker in text:
                return FirewallResult(
                    ok=False, reason=f"Blocked secret/environment access pattern: {marker}"
                )

        return FirewallResult(ok=True)

