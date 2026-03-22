from __future__ import annotations

from dataclasses import dataclass
import secrets

from financeops.llm.pii_patterns import PII_PATTERNS


@dataclass
class MaskingResult:
    masked_text: str
    mask_map: dict[str, str]
    pii_found: list[str]


class PIIMasker:
    """
    Masks PII in text before sending to external LLM providers.
    """

    def mask(self, text: str) -> MaskingResult:
        masked = text
        mask_map: dict[str, str] = {}
        pii_found: list[str] = []

        for pattern in sorted(PII_PATTERNS, key=lambda p: p.priority):
            matches = list(pattern.pattern.finditer(masked))
            for match in matches:
                original = match.group(0)
                if original.startswith("__PII_"):
                    continue
                token = f"__PII_{secrets.token_hex(4).upper()}__"
                mask_map[token] = original
                masked = masked.replace(original, token, 1)
                if pattern.name not in pii_found:
                    pii_found.append(pattern.name)

        return MaskingResult(masked_text=masked, mask_map=mask_map, pii_found=pii_found)

    def unmask(self, text: str, mask_map: dict[str, str]) -> str:
        result = text
        for token, original in mask_map.items():
            result = result.replace(token, original)
        return result

    def should_mask(self, provider: str) -> bool:
        return provider not in ("ollama", "local")

