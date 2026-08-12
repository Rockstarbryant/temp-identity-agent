"""Provider factory — picks a concrete AIProvider based on settings.AI_PROVIDER."""
from django.conf import settings

from ai.base import AIProvider
from ai.providers.agent_router import AgentRouterProvider

_PROVIDERS: dict[str, type[AIProvider]] = {
    "agent_router": AgentRouterProvider,
}


class UnknownAIProviderError(Exception):
    pass


def get_ai_provider(name: str | None = None) -> AIProvider:
    name = name or settings.AI_PROVIDER
    provider_cls = _PROVIDERS.get(name)
    if provider_cls is None:
        raise UnknownAIProviderError(
            f"Unknown AI_PROVIDER {name!r}. Registered providers: {list(_PROVIDERS)}"
        )
    return provider_cls()
