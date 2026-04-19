from __future__ import annotations

import logging

import pytest

from financeops import main
from financeops.llm.fallback import ModelConfig


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


def test_ai_cfo_enabled_with_valid_deepseek_key_passes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(main.settings, "AI_CFO_ENABLED", True)
    monkeypatch.setattr(main.settings, "ANTHROPIC_API_KEY", None)
    monkeypatch.setattr(main.settings, "OPENAI_API_KEY", None)
    monkeypatch.setattr(main.settings, "DEEPSEEK_API_KEY", "deepseek-live-key")

    main._validate_ai_cfo_configuration()


def test_validate_llm_provider_configuration_rejects_invalid_ollama_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(main.settings, "OLLAMA_BASE_URL", "localhost:11434")

    with pytest.raises(
        ValueError,
        match="OLLAMA_BASE_URL must be a valid http:// or https:// URL",
    ):
        main._validate_llm_provider_configuration()


def test_validate_llm_provider_configuration_rejects_unknown_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fallback_chains = {
        "classification": [ModelConfig("bad-model", "unknown-provider", timeout=15)],
    }
    monkeypatch.setattr("financeops.llm.fallback.FALLBACK_CHAINS", fallback_chains)
    monkeypatch.setattr(main.settings, "OLLAMA_BASE_URL", "http://localhost:11434")

    with pytest.raises(
        ValueError,
        match="Unsupported LLM providers in fallback chains: unknown-provider",
    ):
        main._validate_llm_provider_configuration()


def test_check_ai_provider_keys_warns_for_placeholder_fallback_provider_keys(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    fallback_chains = {
        "validation": [
            ModelConfig("gpt-4o-mini", "openai", timeout=30),
            ModelConfig("gemini-1.5-flash", "google", timeout=30),
        ],
    }
    monkeypatch.setattr("financeops.llm.fallback.FALLBACK_CHAINS", fallback_chains)
    monkeypatch.setattr(main.settings, "OPENAI_API_KEY", "sk-openai-PLACEHOLDER")
    monkeypatch.setattr(main.settings, "GEMINI_API_KEY", "GEMINI_PLACEHOLDER")

    caplog.set_level(logging.WARNING)
    main._check_ai_provider_keys()

    messages = [record.message for record in caplog.records]
    assert any("OPENAI_API_KEY" in message for message in messages)
    assert any("GEMINI_API_KEY" in message for message in messages)
