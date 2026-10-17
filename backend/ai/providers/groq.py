"""
Groq provider — OpenAI-compatible /chat/completions endpoint.

Used as the fast, low-latency fallback when the primary provider
(OpenRouter free router) is rate-limited or unavailable.

Model choice: Groq has no per-key "default model", and which models a key can
use varies by account/organization (a hard-coded name such as
llama-3.3-70b-versatile can 404 with "model_not_found"). So unless GROQ_MODEL is
set, the provider asks Groq which models this key can use (GET /models) and
picks a suitable chat model. If a configured model turns out to be unavailable
(404), it re-discovers once and retries.

API docs: https://console.groq.com/docs/openai
"""
import logging

import httpx
from django.conf import settings
from django.core.cache import cache

from ai.base import AIProviderError
from ai.providers.openai_compat import OpenAICompatibleProvider
from ai.schemas import ChatMessage, CompletionResult, ToolDefinition

logger = logging.getLogger("apps.ai")

DEFAULT_BASE_URL = "https://api.groq.com/openai/v1"
# Used only if the model list can't be fetched at all.
LAST_RESORT_MODEL = "llama-3.3-70b-versatile"

# Best tool-calling chat models first; anything else available is a fallback.
_PREFERRED = (
    "llama-3.3-70b-versatile",
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "llama-3.1-8b-instant",
)
# Not chat/tool models.
_EXCLUDE = ("whisper", "guard", "tts", "playai", "orpheus", "embed", "distil", "safeguard", "prompt-guard")
_CACHE_SECONDS = 3600


def pick_model(models: list[dict]) -> str | None:
    """Choose the best usable chat model from Groq's /models `data` list."""
    usable = [
        m for m in models
        if m.get("id") and m.get("active", True) and not any(x in m["id"].lower() for x in _EXCLUDE)
    ]
    ids = [m["id"] for m in usable]
    for name in _PREFERRED:
        if name in ids:
            return name
    if not usable:
        return None
    # Otherwise the one with the biggest context window (a decent proxy for "most capable").
    return max(usable, key=lambda m: m.get("context_window") or 0)["id"]


class GroqProvider(OpenAICompatibleProvider):
    name = "groq"
    label = "Groq"

    def __init__(self):
        api_key = getattr(settings, "GROQ_API_KEY", "")
        if not api_key:
            raise AIProviderError("GROQ_API_KEY must be set to use the groq provider.")
        super().__init__(
            api_key=api_key,
            base_url=getattr(settings, "GROQ_BASE_URL", "") or DEFAULT_BASE_URL,
            # Empty means "work it out from this key's available models" on first use.
            model=(getattr(settings, "GROQ_MODEL", "") or "").strip(),
        )
        self._rediscovered = False

    # -- model discovery --------------------------------------------------------

    def _cache_key(self) -> str:
        return f"groq_model:{self.base_url}:{self.api_key[-8:]}"

    def _discover_model(self, refresh: bool = False) -> str:
        if not refresh:
            cached = cache.get(self._cache_key())
            if cached:
                return cached
        try:
            with httpx.Client(base_url=self.base_url, timeout=15.0) as client:
                resp = client.get("/models", headers=self._headers())
            if resp.status_code != 200:
                raise AIProviderError(f"Groq returned {resp.status_code} listing models: {resp.text[:200]}")
            chosen = pick_model(resp.json().get("data", []))
        except (httpx.HTTPError, ValueError, AIProviderError) as exc:
            logger.warning("Could not list Groq models (%s); using %s", exc, LAST_RESORT_MODEL)
            return LAST_RESORT_MODEL
        if not chosen:
            logger.warning("Groq lists no usable chat model for this key; using %s", LAST_RESORT_MODEL)
            return LAST_RESORT_MODEL
        cache.set(self._cache_key(), chosen, _CACHE_SECONDS)
        logger.info("Groq model for this key: %s", chosen)
        return chosen

    # -- public API ----------------------------------------------------------------

    def complete(self, messages: list[ChatMessage], tools: list[ToolDefinition]) -> CompletionResult:
        if not self.model:
            self.model = self._discover_model()
        try:
            return super().complete(messages, tools)
        except AIProviderError as exc:
            # "model does not exist or you do not have access to it" -> pick again, once.
            if exc.status_code == 404 and not self._rediscovered:
                self._rediscovered = True
                fresh = self._discover_model(refresh=True)
                if fresh != self.model:
                    logger.warning("Groq model %s unavailable; switching to %s", self.model, fresh)
                    self.model = fresh
                    return super().complete(messages, tools)
            raise
