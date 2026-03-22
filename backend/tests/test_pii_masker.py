from __future__ import annotations

from uuid import uuid4

import pytest

from financeops.llm.fallback import LLMResponse, ModelConfig
from financeops.llm.gateway import _call_provider
from financeops.llm.pii_masker import PIIMasker


def test_email_is_masked() -> None:
    """Email addresses are masked with reversible tokens."""
    masker = PIIMasker()
    result = masker.mask("Send invoice to john.doe@acmecorp.com for 50000")
    assert "john.doe@acmecorp.com" not in result.masked_text
    assert "__PII_" in result.masked_text
    assert "email" in result.pii_found
    assert len(result.mask_map) == 1


def test_pan_is_masked() -> None:
    """Indian PAN values are masked."""
    result = PIIMasker().mask("Director: ABCDE1234F approved the payment")
    assert "ABCDE1234F" not in result.masked_text
    assert "pan_india" in result.pii_found


def test_unmask_restores_original() -> None:
    """Unmasking restores source values."""
    masker = PIIMasker()
    original = "Payment to john@example.com confirmed"
    masked = masker.mask(original)
    token = next(iter(masked.mask_map.keys()))
    fake_response = f"Confirmed receipt for {token}"
    assert "john@example.com" in masker.unmask(fake_response, masked.mask_map)


def test_local_provider_not_masked() -> None:
    """Local providers skip masking."""
    masker = PIIMasker()
    assert masker.should_mask("ollama") is False
    assert masker.should_mask("local") is False
    assert masker.should_mask("anthropic") is True
    assert masker.should_mask("openai") is True


def test_financial_amounts_not_masked() -> None:
    """Currency strings are not treated as PII."""
    result = PIIMasker().mask("Revenue: ₹1,50,00,000 for Q3")
    assert "₹1,50,00,000" in result.masked_text
    assert result.pii_found == []


def test_gstin_masked() -> None:
    """GSTIN values are masked."""
    result = PIIMasker().mask("Vendor GSTIN: 29ABCDE1234F1Z5")
    assert "29ABCDE1234F1Z5" not in result.masked_text
    assert "gstin_india" in result.pii_found


def test_mask_is_idempotent_for_pre_masked_text() -> None:
    """Already masked tokens are not remasked."""
    masker = PIIMasker()
    text = "Token __PII_DEADBEEF__ already present"
    result = masker.mask(text)
    assert result.masked_text == text
    assert result.mask_map == {}


@pytest.mark.parametrize(
    ("text", "expected_tag"),
    [
        ("Contact +919876543210 for updates", "phone_india"),
        ("IFSC HDFC0ABC123 mapped", "ifsc_code"),
        ("Account 123456789012 accepted", "account_number"),
        ("Aadhar 1234 5678 9123 verified", "aadhar_india"),
    ],
)
def test_multiple_pattern_detection(text: str, expected_tag: str) -> None:
    """Masker detects all configured PII pattern families."""
    result = PIIMasker().mask(text)
    assert expected_tag in result.pii_found
    assert "__PII_" in result.masked_text


@pytest.mark.asyncio
async def test_gateway_masks_before_cloud_call(monkeypatch) -> None:
    """Gateway masks prompt before cloud provider invocation."""
    captured: dict[str, str] = {}

    class DummyProvider:
        async def generate(self, request):  # type: ignore[no-untyped-def]
            captured["prompt"] = request.prompt
            captured["system"] = request.system_prompt
            return LLMResponse(
                content=request.prompt,
                model="gpt-4o-mini",
                provider="openai",
                prompt_tokens=11,
                completion_tokens=7,
                total_tokens=18,
                duration_ms=1.0,
                raw_response={},
            )

    monkeypatch.setattr("financeops.llm.gateway._get_provider", lambda *_: DummyProvider())

    response, _, _ = await _call_provider(
        model_config=ModelConfig(model_name="gpt-4o-mini", provider="openai"),
        task_type="classification",
        prompt="Email cfo@acmecorp.com with update",
        system_prompt="System for Acme Corp",
        tenant_id=str(uuid4()),
        redis_client=None,
    )
    assert "cfo@acmecorp.com" not in captured["prompt"]
    assert "__PII_" in captured["prompt"]
    assert "cfo@acmecorp.com" in response.content


@pytest.mark.asyncio
async def test_gateway_skips_mask_for_ollama(monkeypatch) -> None:
    """Gateway does not mask when provider is local Ollama."""
    captured: dict[str, str] = {}

    class DummyProvider:
        async def generate(self, request):  # type: ignore[no-untyped-def]
            captured["prompt"] = request.prompt
            return LLMResponse(
                content=request.prompt,
                model="phi3:mini",
                provider="ollama",
                prompt_tokens=2,
                completion_tokens=2,
                total_tokens=4,
                duration_ms=1.0,
                raw_response={},
            )

    monkeypatch.setattr("financeops.llm.gateway._get_provider", lambda *_: DummyProvider())

    await _call_provider(
        model_config=ModelConfig(model_name="phi3:mini", provider="ollama"),
        task_type="classification",
        prompt="Email cfo@acmecorp.com with update",
        system_prompt="No mask expected",
        tenant_id=str(uuid4()),
        redis_client=None,
    )
    assert captured["prompt"] == "Email cfo@acmecorp.com with update"

