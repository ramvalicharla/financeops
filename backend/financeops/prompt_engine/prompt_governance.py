from __future__ import annotations

import logging
from dataclasses import dataclass

from financeops.prompt_engine import PromptDefinition

log = logging.getLogger(__name__)

RISK_LOW = "LOW"
RISK_MEDIUM = "MEDIUM"
RISK_HIGH = "HIGH"
RISK_LEVELS = {RISK_LOW, RISK_MEDIUM, RISK_HIGH}


@dataclass(slots=True)
class PromptGovernanceDecision:
    allowed: bool
    risk: str
    reason: str | None = None


def normalize_risk(
    *,
    prompt_id: str,
    raw_risk: str | None,
    logger: logging.Logger | None = None,
) -> str:
    target_logger = logger or log
    if raw_risk is None or not raw_risk.strip():
        target_logger.warning(
            "Prompt %s missing risk classification; defaulting to MEDIUM",
            prompt_id,
        )
        return RISK_MEDIUM

    normalized = raw_risk.strip().upper()
    if normalized not in RISK_LEVELS:
        raise ValueError(
            f"Invalid risk classification for {prompt_id}: {raw_risk}. "
            "Expected LOW, MEDIUM, or HIGH."
        )
    return normalized


def evaluate_prompt_approval(
    prompt: PromptDefinition,
    *,
    approve_high_risk: bool,
    approval_token: str | None,
) -> PromptGovernanceDecision:
    risk = normalize_risk(prompt_id=prompt.prompt_id, raw_risk=prompt.risk)
    if risk != RISK_HIGH:
        return PromptGovernanceDecision(allowed=True, risk=risk)

    if not approve_high_risk:
        return PromptGovernanceDecision(
            allowed=False,
            risk=risk,
            reason=(
                f"HIGH risk prompt blocked: {prompt.prompt_id}. "
                "Use --approve-high-risk to continue."
            ),
        )

    if approval_token:
        return PromptGovernanceDecision(allowed=True, risk=risk)
    return PromptGovernanceDecision(allowed=True, risk=risk)


def is_high_risk(prompt: PromptDefinition) -> bool:
    return normalize_risk(prompt_id=prompt.prompt_id, raw_risk=prompt.risk) == RISK_HIGH
