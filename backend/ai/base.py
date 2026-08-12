"""
AI provider abstraction.

Every concrete provider (Agent Router today; OpenAI/Anthropic/Google
later — see PHASE 4 of the architecture doc) implements this interface.
Nothing else in the codebase should import a specific provider class
directly — go through ai.router.get_ai_provider(), which picks based
on settings.AI_PROVIDER.
"""
from abc import ABC, abstractmethod

from ai.schemas import ChatMessage, CompletionResult, ToolDefinition


class AIProviderError(Exception):
    pass


class AIProvider(ABC):
    name: str = "base"

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
