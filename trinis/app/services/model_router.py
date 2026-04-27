"""
AI model router — supports OpenAI, Google Gemini and Anthropic.
Selects the right client and model based on job.ai_model.
"""
from app.core.config import get_settings

settings = get_settings()

# Model → tier mapping
MODEL_TIER = {
    "gpt-4o-mini": "economy",
    "gemini-2.5-flash-lite": "economy",
    "gpt-4.1": "standard",
    "gemini-2.5-flash": "standard",
    "claude-haiku-4-5": "standard",
    "gpt-4o": "premium",
    "gemini-2.5-pro": "premium",
    "claude-sonnet-4-6": "premium",
    "claude-opus-4-7": "ultra",
}

FALLBACK_MODEL = "gpt-4o-mini"


def get_model_tier(model: str) -> str:
    return MODEL_TIER.get(model, "economy")


def is_openai_model(model: str) -> bool:
    return model.startswith("gpt-")


def is_google_model(model: str) -> bool:
    return model.startswith("gemini-")


def is_anthropic_model(model: str) -> bool:
    return model.startswith("claude-")


def call_enrich(model: str, system_prompt: str, user_content: str) -> str:
    """
    Call the appropriate AI provider with the given model.
    Returns the raw text response.
    Falls back to gpt-4o-mini on error.
    """
    try:
        if is_openai_model(model):
            return _call_openai(model, system_prompt, user_content)
        elif is_google_model(model):
            return _call_google(model, system_prompt, user_content)
        elif is_anthropic_model(model):
            return _call_anthropic(model, system_prompt, user_content)
        else:
            return _call_openai(FALLBACK_MODEL, system_prompt, user_content)
    except Exception as e:
        import logging
        logging.warning(f"[model_router] {model} failed: {e} — falling back to {FALLBACK_MODEL}")
        return _call_openai(FALLBACK_MODEL, system_prompt, user_content)


def _call_openai(model: str, system_prompt: str, user_content: str) -> str:
    from openai import OpenAI
    client = OpenAI(api_key=settings.openai_api_key)
    resp = client.chat.completions.create(
        model=model,
        temperature=0.7,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
    )
    return resp.choices[0].message.content or "{}"


def _call_google(model: str, system_prompt: str, user_content: str) -> str:
    import google.generativeai as genai
    genai.configure(api_key=settings.google_api_key)
    # Map model name to Gemini API name
    model_map = {
        "gemini-2.5-flash-lite": "gemini-2.5-flash-lite-preview-06-17",
        "gemini-2.5-flash": "gemini-2.5-flash-preview-05-20",
        "gemini-2.5-pro": "gemini-2.5-pro-preview-06-05",
    }
    api_model = model_map.get(model, "gemini-2.5-flash-lite-preview-06-17")
    gemini = genai.GenerativeModel(
        model_name=api_model,
        system_instruction=system_prompt,
    )
    resp = gemini.generate_content(
        user_content,
        generation_config={"response_mime_type": "application/json", "temperature": 0.7},
    )
    return resp.text or "{}"


def _call_anthropic(model: str, system_prompt: str, user_content: str) -> str:
    import anthropic
    model_map = {
        "claude-haiku-4-5": "claude-haiku-4-5-20251001",
        "claude-sonnet-4-6": "claude-sonnet-4-6",
        "claude-opus-4-7": "claude-opus-4-7",
    }
    api_model = model_map.get(model, "claude-haiku-4-5-20251001")
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    resp = client.messages.create(
        model=api_model,
        max_tokens=2000,
        system=system_prompt,
        messages=[{"role": "user", "content": user_content}],
    )
    return resp.content[0].text or "{}"
