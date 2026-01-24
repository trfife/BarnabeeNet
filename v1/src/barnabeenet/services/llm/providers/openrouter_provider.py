"""OpenRouter LLM provider implementation.

OpenRouter provides access to many models via a single API.
See: https://openrouter.ai/docs
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from .base import (
    BaseLLMProvider,
    ChatResponse,
    ProviderConfig,
    ProviderType,
)

logger = logging.getLogger(__name__)

# OpenRouter pricing (USD per 1M tokens) - updated as of Jan 2026
MODEL_PRICING: dict[str, dict[str, float]] = {
    "anthropic/claude-3.5-sonnet": {"input": 3.0, "output": 15.0},
    "anthropic/claude-3-haiku": {"input": 0.25, "output": 1.25},
    "openai/gpt-4o": {"input": 2.5, "output": 10.0},
    "openai/gpt-4o-mini": {"input": 0.15, "output": 0.6},
    "deepseek/deepseek-chat": {"input": 0.14, "output": 0.28},
    "deepseek/deepseek-reasoner": {"input": 0.55, "output": 2.19},
    "google/gemini-2.0-flash-001": {"input": 0.1, "output": 0.4},
    "meta-llama/llama-3.3-70b-instruct": {"input": 0.3, "output": 0.3},
    "x-ai/grok-2": {"input": 2.0, "output": 10.0},
}


class OpenRouterProvider(BaseLLMProvider):
    """OpenRouter API provider.

    Provides access to many models including:
    - Anthropic Claude
    - OpenAI GPT
    - Google Gemini
    - Meta Llama
    - DeepSeek
    - And many more
    """

    BASE_URL = "https://openrouter.ai/api/v1"

    def __init__(
        self,
        config: ProviderConfig,
        site_url: str = "https://barnabeenet.local",
        site_name: str = "BarnabeeNet",
    ) -> None:
        super().__init__(config)
        self.site_url = site_url
        self.site_name = site_name
        self._client: httpx.AsyncClient | None = None

    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.OPENROUTER

    async def init(self) -> None:
        """Initialize the HTTP client."""
        if self._initialized:
            return

        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "HTTP-Referer": self.site_url,
                "X-Title": self.site_name,
                "Content-Type": "application/json",
            },
            timeout=self.config.timeout,
        )
        self._initialized = True
        logger.info("OpenRouter provider initialized")

    async def shutdown(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
        self._initialized = False
        logger.info("OpenRouter provider shutdown")

    def _estimate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost in USD based on model pricing."""
        pricing = MODEL_PRICING.get(model, {"input": 1.0, "output": 2.0})
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        return input_cost + output_cost

    async def _do_chat(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float,
        max_tokens: int,
        **kwargs: Any,
    ) -> ChatResponse:
        """Execute OpenRouter chat completion."""
        if self._client is None:
            await self.init()

        # Build request payload
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        # Add optional parameters
        for key in ["top_p", "frequency_penalty", "presence_penalty", "stop"]:
            if key in kwargs and kwargs[key] is not None:
                payload[key] = kwargs[key]

        start_time = time.perf_counter()

        response = await self._client.post("/chat/completions", json=payload)
        response.raise_for_status()

        latency_ms = (time.perf_counter() - start_time) * 1000

        data = response.json()
        choice = data["choices"][0]
        usage = data.get("usage", {})

        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)

        return ChatResponse(
            text=choice["message"]["content"],
            model=data.get("model", model),
            provider="openrouter",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            finish_reason=choice.get("finish_reason", "unknown"),
            cost_usd=self._estimate_cost(model, input_tokens, output_tokens),
            latency_ms=latency_ms,
            raw_response=data,
        )
