import pytest
from app.services.model_router import get_model_tier, is_openai_model, is_google_model, is_anthropic_model, MODEL_TIER, FALLBACK_MODEL


def test_fallback_model_is_economy():
    assert get_model_tier(FALLBACK_MODEL) == "economy"


def test_model_tier_mapping():
    assert get_model_tier("gpt-4o") == "premium"
    assert get_model_tier("gpt-4.1") == "standard"
    assert get_model_tier("gpt-4o-mini") == "economy"
    assert get_model_tier("claude-sonnet-4-6") == "premium"
    assert get_model_tier("claude-opus-4-7") == "ultra"
    assert get_model_tier("gemini-2.5-flash") == "standard"


def test_provider_detection():
    assert is_openai_model("gpt-4o") is True
    assert is_google_model("gemini-2.5-flash") is True
    assert is_anthropic_model("claude-haiku-4-5") is True
    assert is_openai_model("claude-haiku-4-5") is False
    assert is_google_model("gpt-4o") is False


def test_unknown_model_defaults_to_economy():
    assert get_model_tier("unknown-model-xyz") == "economy"


def test_call_enrich_fallback_on_error(mocker):
    from app.services.model_router import call_enrich
    # Mock OpenAI to raise error on unknown model, fallback to gpt-4o-mini
    mock_openai = mocker.patch("app.services.model_router._call_openai")
    mock_openai.side_effect = [Exception("model error"), '{"products": []}']

    result = call_enrich("unknown-model", "system", "user content")
    assert mock_openai.call_count == 2  # first fails, fallback succeeds
