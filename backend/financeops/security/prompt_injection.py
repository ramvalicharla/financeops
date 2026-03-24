from __future__ import annotations

from dataclasses import dataclass
import re

INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(previous|above|all)\s+(instructions?|prompts?)", re.IGNORECASE),
    re.compile(r"(you\s+are\s+now|act\s+as|pretend\s+(to\s+be|you\s+are))", re.IGNORECASE),
    re.compile(r"(forget|disregard|override)\s+(your\s+)?(instructions?|rules?|training)", re.IGNORECASE),
    re.compile(
        r"(print|show|reveal|display|output|repeat)\s+(your\s+)?(system\s+prompt|instructions?|context)",
        re.IGNORECASE,
    ),
    re.compile(r"what\s+(are|were)\s+your\s+(instructions?|system\s+prompt)", re.IGNORECASE),
    re.compile(r"(dan|do\s+anything\s+now|jailbreak)", re.IGNORECASE),
    re.compile(r"(developer\s+mode|maintenance\s+mode|god\s+mode)", re.IGNORECASE),
    re.compile(r"you\s+are\s+a\s+(different|new|other)\s+(ai|model|assistant)", re.IGNORECASE),
    re.compile(
        r"(list|show(\s+me)?|give\s+me)\s+(all\s+)?(other\s+)?(tenant|customer|user)\s+data",
        re.IGNORECASE,
    ),
]


@dataclass(slots=True)
class InjectionScanResult:
    is_injection: bool
    matched_pattern: str | None
    risk_level: str
    sanitised_text: str | None


class PromptInjectionScanner:
    def scan(self, text: str) -> InjectionScanResult:
        for pattern in INJECTION_PATTERNS:
            match = pattern.search(text)
            if match:
                matched = match.group(0)
                risk = self._assess_risk(text)
                sanitised_text = None if risk in {"high", "critical"} else self._sanitise_text(text, matched)
                return InjectionScanResult(
                    is_injection=True,
                    matched_pattern=matched,
                    risk_level=risk,
                    sanitised_text=sanitised_text,
                )
        return InjectionScanResult(
            is_injection=False,
            matched_pattern=None,
            risk_level="low",
            sanitised_text=text,
        )

    def _assess_risk(self, text: str) -> str:
        text_lower = text.lower()
        if any(keyword in text_lower for keyword in ("system prompt", "other tenant", "all users", "jailbreak", "dan")):
            return "critical"
        if any(
            keyword in text_lower
            for keyword in ("ignore instructions", "ignore previous", "forget", "override")
        ):
            return "high"
        if any(keyword in text_lower for keyword in ("act as", "pretend", "you are now")):
            return "medium"
        return "low"

    def _sanitise_text(self, text: str, matched: str) -> str:
        cleaned = text.replace(matched, " ")
        return re.sub(r"\s+", " ", cleaned).strip()

    def is_safe(self, text: str) -> bool:
        return not self.scan(text).is_injection


__all__ = ["InjectionScanResult", "PromptInjectionScanner", "INJECTION_PATTERNS"]
