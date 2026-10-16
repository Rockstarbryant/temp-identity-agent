"""Provider factory — picks a concrete AIProvider based on settings.AI_PROVIDER."""
import logging

from django.conf import settings

from ai.base import AIProvider
from ai.providers.fallback import FallbackAIProvider
from ai.providers.groq import GroqProvider
from ai.providers.openrouter import OpenRouterProvider

logger = logging.getLogger("apps.ai")

_PROVIDERS: dict[str, type[AIProvider]] = {
    "openrouter": OpenRouterProvider,
    "groq": GroqProvider,
    "fallback": FallbackAIProvider,
}

# Old AI_PROVIDER values that still appear in existing .env / Render configs.
_LEGACY_ALIASES = {"agent_router": "fallback"}


class UnknownAIProviderError(Exception):
    pass


def get_ai_provider(name: str | None = None) -> AIProvider:
    """
    Return an AIProvider instance.

    Supported values for AI_PROVIDER:
      - openrouter  (OpenRouter only, default model `openrouter/free`)
      - groq        (Groq only)
      - fallback    (OpenRouter first, then Groq on rate-limit / 5xx / network error)

    If AI_PROVIDER is unset/empty, picks based on which keys are present:
    both → "fallback", otherwise whichever one is configured.
    """
    name = name or settings.AI_PROVIDER
    if not name:
        has_openrouter = bool(getattr(settings, "OPENROUTER_API_KEY", ""))
        has_groq = bool(getattr(settings, "GROQ_API_KEY", ""))
        if has_openrouter and has_groq:
            name = "fallback"
        elif has_groq:
            name = "groq"
        else:
            name = "openrouter"

    if name in _LEGACY_ALIASES:
        replacement = _LEGACY_ALIASES[name]
        logger.warning(
            "AI_PROVIDER=%r is no longer supported (Agent Router was replaced by "
            "OpenRouter); using %r. Update your environment.",
            name,
            replacement,
        )
        name = replacement

    provider_cls = _PROVIDERS.get(name)
    if provider_cls is None:
        raise UnknownAIProviderError(
            f"Unknown AI_PROVIDER {name!r}. Registered providers: {list(_PROVIDERS)}"
        )
    return provider_cls()
