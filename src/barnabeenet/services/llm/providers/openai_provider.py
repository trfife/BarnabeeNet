"""OpenAI LLM provider implementation.

Direct access to OpenAI's API for GPT models.
See: https://platform.openai.com/docs/api-reference
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

# OpenAI pricing (USD per 1M tokens) - updated as of Jan 2026
MODEL_PRICING: dict[str, dict[str, float]] = {
    "gpt-4o": {"input": 2.5, "output": 10.0},
    "gpt-4o-mini": {"input": 0.15, "output": 0.6},
    "gpt-4-turbo": {"input": 10.0, "output": 30.0},
    "gpt-4": {"input": 30.0, "output": 60.0},
    "gpt-3.5-turbo": {"input": 0.5, "output": 1.5},
    "o1-preview": {"input": 15.0, "output": 60.0},
    "o1-mini": {"input": 3.0, "output": 12.0},
}


class OpenAIProvider(BaseLLMProvider):
    """OpenAI API provider.

    Direct access to OpenAI models including:
    - GPT-4o and GPT-4o-mini
    - GPT-4 Turbo
    - o1 reasoning models
    """

    BASE_URL = "https://api.openai.com/v1"

    def __init__(self, config: ProviderConfig) -> None:
        super().__init__(config)
        self._client: httpx.AsyncClient | None = None

    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.OPENAI

    async def init(self) -> None:
        """Initialize the HTTP client."""
        if self._initialized:
            return

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }
        if self.config.organization:
            headers["OpenAI-Organization"] = self.config.organization

        self._client = httpx.AsyncClient(
            base_url=self.config.api_base or self.BASE_URL,
            headers=headers,
            timeout=self.config.timeout,
        )
        self._initialized = True
        logger.info("OpenAI provider initialized")

    async def shutdown(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
        self._initialized = False
        logger.info("OpenAI provider shutdown")

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
        """Execute OpenAI chat completion."""
        if self._client is None:
            await self.init()

        # OpenAI models don't have prefixes, strip if present
        clean_model = model.replace("openai/", "")

        payload: dict[str, Any] = {
            "model": clean_model,
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
            model=data.get("model", clean_model),
            provider="openai",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            finish_reason=choice.get("finish_reason", "unknown"),
            cost_usd=self._estimate_cost(clean_model, input_tokens, output_tokens),
            latency_ms=latency_ms,
            raw_response=data,
        )
