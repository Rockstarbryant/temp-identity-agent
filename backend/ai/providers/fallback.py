"""
Fallback AI provider.

Tries the primary provider (usually Agent Router / OpenRouter-compatible).
On rate-limit (429), transient server errors (502/503/504), or network
failures, automatically retries once with the Groq provider.

Usage:
  AI_PROVIDER=fallback
  # primary (Agent Router) still configured via AGENT_ROUTER_*
  # fallback via GROQ_*
"""
import logging
import re

from ai.base import AIProvider, AIProviderError
from ai.providers.agent_router import AgentRouterProvider
from ai.providers.groq import GroqProvider
from ai.schemas import ChatMessage, CompletionResult, ToolDefinition

logger = logging.getLogger("apps.ai")

# Status codes / message patterns that warrant falling back
_FALLBACK_STATUS_RE = re.compile(r"\b(429|502|503|504)\b")
_RATE_LIMIT_RE = re.compile(
    r"rate.?limit|too many requests|quota|capacity|overloaded",
    re.IGNORECASE,
)


def _is_fallbackable(exc: Exception) -> bool:
    """Return True if this error should trigger a switch to Groq."""
    msg = str(exc)
    if _FALLBACK_STATUS_RE.search(msg):
        return True
    if _RATE_LIMIT_RE.search(msg):
        return True
    # Network / timeout style failures from httpx
    if "request failed" in msg.lower() or "timed out" in msg.lower():
        return True
    return False


class FallbackAIProvider(AIProvider):
    """
    Primary → Groq fallback wrapper.

    The public `.name` reflects whichever provider last succeeded so
    AgentSession rows stay accurate.
    """

    name = "fallback"

    def __init__(self):
        self.primary = AgentRouterProvider()
        self.fallback = GroqProvider()
        self._last_provider_name = self.primary.name

    def complete(
        self, messages: list[ChatMessage], tools: list[ToolDefinition]
    ) -> CompletionResult:
        try:
            result = self.primary.complete(messages, tools)
            self._last_provider_name = self.primary.name
            self.name = self.primary.name  # type: ignore[misc]
            return result
        except AIProviderError as primary_exc:
            if not _is_fallbackable(primary_exc):
                raise

            logger.warning(
                "Primary AI provider (%s) failed (%s); falling back to Groq",
                self.primary.name,
                primary_exc,
            )
            try:
                result = self.fallback.complete(messages, tools)
                self._last_provider_name = self.fallback.name
                self.name = self.fallback.name  # type: ignore[misc]
                return result
            except AIProviderError as fallback_exc:
                # Surface both errors for debugging
                raise AIProviderError(
                    f"Primary ({self.primary.name}) failed: {primary_exc}; "
                    f"fallback (groq) also failed: {fallback_exc}"
                ) from fallback_exc
