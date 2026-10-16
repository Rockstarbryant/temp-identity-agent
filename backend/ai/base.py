"""
AI provider abstraction.

Every concrete provider (OpenRouter, Groq, and the OpenRouter→Groq
fallback wrapper today; OpenAI/Anthropic/Google later — see PHASE 4 of
the architecture doc) implements this interface. Nothing else in the
codebase should import a specific provider class directly — go through
ai.router.get_ai_provider(), which picks based on settings.AI_PROVIDER.
"""
from abc import ABC, abstractmethod

from ai.schemas import ChatMessage, CompletionResult, ToolDefinition


class AIProviderError(Exception):
    """
    Raised for any provider failure.

    `status_code` is the upstream HTTP status when there was one.
    `retryable` marks failures that are transient or provider-specific
    (rate limit, 5xx, network error, garbled model output) — i.e. the
    kind where trying a *different* provider is likely to succeed. The
    fallback wrapper keys off this flag instead of parsing messages.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        retryable: bool = False,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable


class AIProvider(ABC):
    name: str = "base"
    model: str = ""

    @abstractmethod
    def complete(
        self, messages: list[ChatMessage], tools: list[ToolDefinition]
    ) -> CompletionResult:
        """
        Send the conversation + available tools to the model, return its
        response (either plain text or one/more tool calls) in
        provider-agnostic form.
        """
        raise NotImplementedError
