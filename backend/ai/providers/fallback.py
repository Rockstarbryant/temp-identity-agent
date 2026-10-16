"""
Fallback AI provider: OpenRouter (`openrouter/free`) → Groq.

Each call goes to OpenRouter first. If that fails in a way another
provider could plausibly fix — rate limit (429), quota/credits (402),
no capable free endpoint (404), 5xx, timeouts/network errors, or
garbled model output — the *same* request is retried once on Groq.
Non-retryable errors (e.g. 401 bad key, 400 bad request) are raised
as-is so misconfiguration isn't silently masked.

Usage:
  AI_PROVIDER=fallback
  # primary  via OPENROUTER_*
  # fallback via GROQ_*

If OPENROUTER_API_KEY is not set, calls go straight to Groq (with a
warning); if GROQ_API_KEY is not set, OpenRouter errors are raised
without a fallback.
"""
import logging

from ai.base import AIProvider, AIProviderError
from ai.providers.groq import GroqProvider
from ai.providers.openrouter import OpenRouterProvider
from ai.schemas import ChatMessage, CompletionResult, ToolDefinition

logger = logging.getLogger("apps.ai")


class FallbackAIProvider(AIProvider):
    """
    Primary → Groq fallback wrapper.

    `.name` / `.model` reflect whichever provider last answered, so the
    AgentSession row stays accurate.
    """

    name = "fallback"

    def __init__(self):
        self.primary: AIProvider | None = None
        self.fallback: AIProvider | None = None

        try:
            self.primary = OpenRouterProvider()
        except AIProviderError as exc:
            logger.warning("OpenRouter not configured (%s); using Groq only.", exc)

        try:
            self.fallback = GroqProvider()
        except AIProviderError as exc:
            if self.primary is None:
                raise AIProviderError(
                    "No AI provider configured: set OPENROUTER_API_KEY and/or GROQ_API_KEY."
                ) from exc
            logger.warning("Groq not configured (%s); OpenRouter errors will not fall back.", exc)

        first = self.primary or self.fallback
        self.name = first.name  # type: ignore[misc]
        self.model = first.model

    def _mark(self, provider: AIProvider) -> None:
        self.name = provider.name  # type: ignore[misc]
        self.model = provider.model

    def complete(
        self, messages: list[ChatMessage], tools: list[ToolDefinition]
    ) -> CompletionResult:
        if self.primary is None:
            assert self.fallback is not None
            result = self.fallback.complete(messages, tools)
            self._mark(self.fallback)
            return result

        try:
            result = self.primary.complete(messages, tools)
            self._mark(self.primary)
            return result
        except AIProviderError as primary_exc:
            if self.fallback is None or not primary_exc.retryable:
                raise

            logger.warning(
                "Primary AI provider (%s) failed (%s); falling back to %s",
                self.primary.name,
                primary_exc,
                self.fallback.name,
            )
            try:
                result = self.fallback.complete(messages, tools)
            except AIProviderError as fallback_exc:
                # Surface both errors for debugging; keep the fallback's
                # status/retryable flags for callers that inspect them.
                raise AIProviderError(
                    f"Primary ({self.primary.name}) failed: {primary_exc}; "
                    f"fallback ({self.fallback.name}) also failed: {fallback_exc}",
                    status_code=fallback_exc.status_code,
                    retryable=fallback_exc.retryable,
                ) from fallback_exc
            self._mark(self.fallback)
            return result
