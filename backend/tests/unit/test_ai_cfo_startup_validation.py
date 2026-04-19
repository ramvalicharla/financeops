from __future__ import annotations

import pytest

from financeops import main


def test_ai_cfo_enabled_without_keys_raises_at_startup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(main.settings, "AI_CFO_ENABLED", True)
    monkeypatch.setattr(
        main.settings,
        "ANTHROPIC_API_KEY",
        "sk-ant-PLACEHOLDER-update-before-launch",
    )
    monkeypatch.setattr(main.settings, "OPENAI_API_KEY", None)
    monkeypatch.setattr(main.settings, "DEEPSEEK_API_KEY", None)

    with pytest.raises(
        ValueError,
        match="AI_CFO_ENABLED is True but no valid AI provider key is configured",
    ):
        main._validate_ai_cfo_configuration()
