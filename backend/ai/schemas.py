"""
Provider-agnostic schemas for chat + tool calling.

Every AIProvider implementation converts its own API's request/response
shape to and from these — nothing else in the codebase should know what
"Agent Router" or any other provider's raw JSON looks like.
"""
from typing import Any, Literal

from pydantic import BaseModel


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str = ""
    tool_call_id: str | None = None  # set when role == "tool"
    tool_calls: list["ToolCallRequest"] | None = None  # set when role == "assistant"


class ToolDefinition(BaseModel):
    """One tool the model is allowed to call, in provider-agnostic form."""

    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema, generated from a Pydantic args model


class ToolCallRequest(BaseModel):
    """A single tool invocation the model asked for."""

    id: str
    name: str
    arguments: dict[str, Any]


class CompletionResult(BaseModel):
    """Normalized result of one provider.complete() call."""

    message: ChatMessage
    input_tokens: int | None = None
    output_tokens: int | None = None
    stop_reason: str = ""


ChatMessage.model_rebuild()
