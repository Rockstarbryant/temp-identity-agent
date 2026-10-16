"""Provider factory — picks a concrete AIProvider based on settings.AI_PROVIDER."""
from django.conf import settings

from ai.base import AIProvider
from ai.providers.agent_router import AgentRouterProvider
from ai.providers.fallback import FallbackAIProvider
from ai.providers.groq import GroqProvider

_PROVIDERS: dict[str, type[AIProvider]] = {
    "agent_router": AgentRouterProvider,
    "groq": GroqProvider,
    "fallback": FallbackAIProvider,
}


class UnknownAIProviderError(Exception):
    pass


def get_ai_provider(name: str | None = None) -> AIProvider:
    """
    Return an AIProvider instance.

    Supported values for AI_PROVIDER:
      - agent_router  (primary OpenAI-compatible proxy)
      - groq          (Groq only)
      - fallback      (agent_router first, then Groq on rate-limit / 5xx / network error)

    If AI_PROVIDER is unset/empty and both AGENT_ROUTER_* and GROQ_API_KEY
    are present, defaults to "fallback".
    """
    name = name or settings.AI_PROVIDER
    if not name:
        # Auto-select fallback when both are configured
        if getattr(settings, "AGENT_ROUTER_API_KEY", "") and getattr(
            settings, "GROQ_API_KEY", ""
        ):
            name = "fallback"
        else:
            name = "agent_router"

    provider_cls = _PROVIDERS.get(name)
    if provider_cls is None:
        raise UnknownAIProviderError(
            f"Unknown AI_PROVIDER {name!r}. Registered providers: {list(_PROVIDERS)}"
        )
    return provider_cls()
