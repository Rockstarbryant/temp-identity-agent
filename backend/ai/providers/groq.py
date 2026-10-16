"""
Groq provider — OpenAI-compatible /chat/completions endpoint.

Used as the fast, low-latency fallback when the primary provider
(OpenRouter free router) is rate-limited or unavailable.

API docs: https://console.groq.com/docs/openai
"""
from django.conf import settings

from ai.base import AIProviderError
from ai.providers.openai_compat import OpenAICompatibleProvider

DEFAULT_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_MODEL = "llama-3.3-70b-versatile"


class GroqProvider(OpenAICompatibleProvider):
    name = "groq"
    label = "Groq"

    def __init__(self):
        api_key = getattr(settings, "GROQ_API_KEY", "")
        if not api_key:
            raise AIProviderError("GROQ_API_KEY must be set to use the groq provider.")
        super().__init__(
            api_key=api_key,
            base_url=getattr(settings, "GROQ_BASE_URL", "") or DEFAULT_BASE_URL,
            model=getattr(settings, "GROQ_MODEL", "") or DEFAULT_MODEL,
        )
