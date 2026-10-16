"""
OpenRouter provider — OpenAI-compatible /chat/completions endpoint.

Default model is `openrouter/free`, OpenRouter's free-models router: it
picks an available free model per request (filtering for the features
the request needs, such as tool calling), so we never hard-code a
specific free model that may be retired or rate-limited tomorrow.

Free models are rate-limited, so this provider is normally used through
FallbackAIProvider, which switches to Groq when OpenRouter returns 429
(or 5xx / network errors).

API docs: https://openrouter.ai/docs/api-reference/overview
"""
from typing import Any

from django.conf import settings

from ai.base import AIProviderError
from ai.providers.openai_compat import DEFAULT_RETRYABLE_STATUSES, OpenAICompatibleProvider

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "openrouter/free"


class OpenRouterProvider(OpenAICompatibleProvider):
    name = "openrouter"
    label = "OpenRouter"
    # Also fall back on 402 (credits/free quota exhausted) and 404
    # ("no endpoints found that support tool use" for the request).
    retryable_statuses = DEFAULT_RETRYABLE_STATUSES | {402, 404}

    def __init__(self):
        api_key = getattr(settings, "OPENROUTER_API_KEY", "")
        if not api_key:
            raise AIProviderError("OPENROUTER_API_KEY must be set to use the openrouter provider.")
        super().__init__(
            api_key=api_key,
            base_url=getattr(settings, "OPENROUTER_BASE_URL", "") or DEFAULT_BASE_URL,
            model=getattr(settings, "OPENROUTER_MODEL", "") or DEFAULT_MODEL,
        )
        self.site_url = getattr(settings, "OPENROUTER_SITE_URL", "")
        self.app_name = getattr(settings, "OPENROUTER_APP_NAME", "")

    def _headers(self) -> dict[str, str]:
        headers = super()._headers()
        # Optional attribution headers (show up on openrouter.ai rankings).
        if self.site_url:
            headers["HTTP-Referer"] = self.site_url
        if self.app_name:
            headers["X-Title"] = self.app_name
        return headers

    def _extra_payload(self) -> dict[str, Any]:
        return {}
