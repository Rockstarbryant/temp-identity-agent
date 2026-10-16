"""
Groq provider — OpenAI-compatible /chat/completions endpoint.

Used as a fast, low-latency fallback when the primary provider
(Agent Router / OpenRouter-style proxies) is rate-limited or unavailable.

API docs: https://console.groq.com/docs/openai
"""
from typing import Any

import httpx
from django.conf import settings

from ai.base import AIProvider, AIProviderError
from ai.schemas import ChatMessage, CompletionResult, ToolCallRequest, ToolDefinition


class GroqProvider(AIProvider):
    name = "groq"

    def __init__(self):
        self.api_key = settings.GROQ_API_KEY
        self.base_url = (settings.GROQ_BASE_URL or "https://api.groq.com/openai/v1").rstrip("/")
        self.model = settings.GROQ_MODEL or "llama-3.3-70b-versatile"
        if not self.api_key:
            raise AIProviderError(
                "GROQ_API_KEY must be set to use the groq provider."
            )

    def _to_provider_request(
        self, messages: list[ChatMessage], tools: list[ToolDefinition]
    ) -> dict[str, Any]:
        provider_messages = []
        for m in messages:
            entry: dict[str, Any] = {"role": m.role, "content": m.content}
            if m.role == "tool":
                entry["tool_call_id"] = m.tool_call_id
            if m.role == "assistant" and m.tool_calls:
                entry["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": _json_dumps(tc.arguments),
                        },
                    }
                    for tc in m.tool_calls
                ]
            provider_messages.append(entry)

        provider_tools = [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                },
            }
            for t in tools
        ]

        return {
            "model": self.model,
            "messages": provider_messages,
            "tools": provider_tools,
            "tool_choice": "auto",
        }

    def _from_provider_response(self, data: dict[str, Any]) -> CompletionResult:
        choice = data["choices"][0]
        raw_message = choice["message"]

        tool_calls = None
        if raw_message.get("tool_calls"):
            tool_calls = [
                ToolCallRequest(
                    id=tc["id"],
                    name=tc["function"]["name"],
                    arguments=_json_loads(tc["function"]["arguments"]),
                )
                for tc in raw_message["tool_calls"]
            ]

        message = ChatMessage(
            role="assistant",
            content=raw_message.get("content") or "",
            tool_calls=tool_calls,
        )

        usage = data.get("usage", {})
        return CompletionResult(
            message=message,
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
            stop_reason=choice.get("finish_reason", ""),
        )

    def complete(
        self, messages: list[ChatMessage], tools: list[ToolDefinition]
    ) -> CompletionResult:
        payload = self._to_provider_request(messages, tools)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        try:
            with httpx.Client(base_url=self.base_url, timeout=60.0) as client:
                resp = client.post("/chat/completions", json=payload, headers=headers)
        except httpx.HTTPError as exc:
            raise AIProviderError(f"Groq request failed: {exc}") from exc

        if resp.status_code != 200:
            raise AIProviderError(
                f"Groq returned {resp.status_code}: {resp.text[:500]}"
            )

        try:
            return self._from_provider_response(resp.json())
        except (KeyError, IndexError) as exc:
            raise AIProviderError(
                f"Unexpected Groq response shape: {resp.text[:500]}"
            ) from exc


def _json_dumps(obj: Any) -> str:
    import json

    return json.dumps(obj)


def _json_loads(s: str) -> dict[str, Any]:
    import json

    return json.loads(s)
