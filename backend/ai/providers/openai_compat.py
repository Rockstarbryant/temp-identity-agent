"""
Shared implementation for providers that expose an OpenAI-compatible
/chat/completions endpoint with `tools` / `tool_calls` (OpenRouter, Groq).

Subclasses only supply credentials, a label for error messages, and
(optionally) extra headers / payload fields / retryable status codes.
"""
import json
import re
import uuid
from typing import Any

import httpx

from ai.base import AIProvider, AIProviderError
from ai.schemas import ChatMessage, CompletionResult, ToolCallRequest, ToolDefinition

# HTTP statuses where a *different* provider is likely to do better.
DEFAULT_RETRYABLE_STATUSES = frozenset({408, 429, 500, 502, 503, 504})


# OpenAI-style APIs only accept tool names matching ^[a-zA-Z0-9_-]{1,64}$.
# Our registry uses namespaced names like "browser.open_url", so names are
# encoded on the way out and mapped back on the way in.
_INVALID_NAME_CHARS = re.compile(r"[^A-Za-z0-9_-]")


def encode_tool_name(name: str) -> str:
    # A single underscore, not "__": some models (gpt-oss on Groq) mangle "user__ask" into a
    # call to a tool called just "user". Decoding goes through a lookup table, so it's lossless.
    return _INVALID_NAME_CHARS.sub("_", name)[:64]


def _normalize_name(name: str) -> str:
    return re.sub(r"[._-]+", "_", name.strip().lower())


class OpenAICompatibleProvider(AIProvider):
    TOOL_USE_FAILED_ATTEMPTS = 3
    label = "Provider"  # used in error messages, e.g. "OpenRouter returned 429: ..."
    timeout = 60.0
    retryable_statuses: frozenset[int] = DEFAULT_RETRYABLE_STATUSES

    def __init__(self, api_key: str, base_url: str, model: str):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        # encoded wire name -> our original tool name, rebuilt on every request
        self._tool_names: dict[str, str] = {}

    # -- hooks ---------------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _extra_payload(self) -> dict[str, Any]:
        return {}

    # -- request / response translation --------------------------------------

    def _to_provider_request(
        self, messages: list[ChatMessage], tools: list[ToolDefinition]
    ) -> dict[str, Any]:
        self._tool_names = {}

        def wire_name(name: str) -> str:
            encoded = encode_tool_name(name)
            self._tool_names[encoded] = name
            return encoded

        for t in tools:
            wire_name(t.name)

        # The prompts refer to tools by their registry names ("browser.open");
        # show the model the same names it will see in the tool list.
        renames = sorted(self._tool_names.items(), key=lambda kv: len(kv[1]), reverse=True)
        rename_re = (
            re.compile(
                r"(?<![\w.])(" + "|".join(re.escape(orig) for _, orig in renames) + r")(?!\w)"
            )
            if renames
            else None
        )
        to_wire = {orig: enc for enc, orig in renames}

        def rewrite(text: str) -> str:
            if rename_re is None:
                return text
            return rename_re.sub(lambda mo: to_wire[mo.group(1)], text)

        provider_messages = []
        for m in messages:
            content = rewrite(m.content) if m.role in ("system", "user") else m.content
            entry: dict[str, Any] = {"role": m.role, "content": content}
            if m.role == "tool":
                entry["tool_call_id"] = m.tool_call_id
            if m.role == "assistant" and m.tool_calls:
                entry["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": wire_name(tc.name),
                            "arguments": json.dumps(tc.arguments),
                        },
                    }
                    for tc in m.tool_calls
                ]
            provider_messages.append(entry)

        provider_tools = [
            {
                "type": "function",
                "function": {
                    "name": wire_name(t.name),
                    "description": t.description,
                    "parameters": t.parameters,
                },
            }
            for t in tools
        ]

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": provider_messages,
            "tools": provider_tools,
            "tool_choice": "auto",
        }
        payload.update(self._extra_payload())
        return payload

    def _decode_tool_name(self, wire: str) -> str:
        """Map a name from the API back to our registry name."""
        if wire in self._tool_names:
            return self._tool_names[wire]
        # Be forgiving about separators ("user.ask", "user__ask", "User-Ask" -> user.ask).
        wanted = _normalize_name(wire)
        for enc, orig in self._tool_names.items():
            if _normalize_name(enc) == wanted:
                return orig
        return wire

    def _parse_arguments(self, raw: Any) -> dict[str, Any]:
        """Tool-call arguments arrive as a JSON string; free models sometimes mangle it."""
        if isinstance(raw, dict):
            return raw
        if raw is None or (isinstance(raw, str) and not raw.strip()):
            return {}
        try:
            parsed = json.loads(raw)
        except (TypeError, ValueError) as exc:
            raise AIProviderError(
                f"{self.label} returned malformed tool-call arguments: {str(raw)[:200]}",
                retryable=True,
            ) from exc
        if not isinstance(parsed, dict):
            raise AIProviderError(
                f"{self.label} returned non-object tool-call arguments: {str(raw)[:200]}",
                retryable=True,
            )
        return parsed

    def _raise_if_error_body(self, data: dict[str, Any]) -> None:
        """
        OpenRouter (and some upstreams behind it) can answer HTTP 200 with
        an `{"error": {...}}` body. Treat that as a failure, using the
        embedded code when there is one.
        """
        err = data.get("error")
        if not err:
            return
        if isinstance(err, dict):
            code = err.get("code")
            message = err.get("message") or json.dumps(err)[:500]
        else:
            code, message = None, str(err)
        status = code if isinstance(code, int) else None
        raise AIProviderError(
            f"{self.label} returned {status or 'error'}: {str(message)[:500]}",
            status_code=status,
            # A 200-with-error from a router is an upstream hiccup unless
            # the code says otherwise.
            retryable=status is None or status in self.retryable_statuses,
        )

    def _from_provider_response(self, data: dict[str, Any]) -> CompletionResult:
        self._raise_if_error_body(data)

        choice = data["choices"][0]
        raw_message = choice["message"]

        tool_calls = None
        if raw_message.get("tool_calls"):
            tool_calls = [
                ToolCallRequest(
                    id=tc.get("id") or f"call_{uuid.uuid4().hex[:12]}",
                    name=self._decode_tool_name(tc["function"]["name"]),
                    arguments=self._parse_arguments(tc["function"].get("arguments")),
                )
                for tc in raw_message["tool_calls"]
            ]

        message = ChatMessage(
            role="assistant",
            content=raw_message.get("content") or "",
            tool_calls=tool_calls,
        )

        usage = data.get("usage") or {}
        return CompletionResult(
            message=message,
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
            stop_reason=choice.get("finish_reason") or "",
            provider=self.name,
            # Routers report the concrete model that served the call.
            model=data.get("model") or self.model,
        )

    # -- public API ----------------------------------------------------------

    def complete(
        self, messages: list[ChatMessage], tools: list[ToolDefinition]
    ) -> CompletionResult:
        payload = self._to_provider_request(messages, tools)
        resp = None
        for attempt in range(1, self.TOOL_USE_FAILED_ATTEMPTS + 1):
            try:
                with httpx.Client(base_url=self.base_url, timeout=self.timeout) as client:
                    resp = client.post("/chat/completions", json=payload, headers=self._headers())
            except httpx.HTTPError as exc:
                raise AIProviderError(
                    f"{self.label} request failed: {exc}", retryable=True
                ) from exc
            # The model produced a malformed tool call and the API rejected it. Sampling is
            # random, so simply asking again usually works.
            if resp.status_code == 400 and "tool_use_failed" in resp.text and attempt < self.TOOL_USE_FAILED_ATTEMPTS:
                continue
            break

        if resp.status_code != 200:
            raise AIProviderError(
                f"{self.label} returned {resp.status_code}: {resp.text[:500]}",
                status_code=resp.status_code,
                retryable=resp.status_code in self.retryable_statuses,
            )

        try:
            data = resp.json()
        except ValueError as exc:
            raise AIProviderError(
                f"Unexpected {self.label} response (not JSON): {resp.text[:500]}",
                retryable=True,
            ) from exc

        try:
            return self._from_provider_response(data)
        except AIProviderError:
            raise
        except (KeyError, IndexError, TypeError, AttributeError) as exc:
            raise AIProviderError(
                f"Unexpected {self.label} response shape: {resp.text[:500]}",
                retryable=True,
            ) from exc
