"""Anthropic (Claude) LLM provider implementation.

Direct access to Claude models via Anthropic's API.
See: https://docs.anthropic.com/claude/reference/messages
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

# Anthropic pricing (USD per 1M tokens) - updated as of Jan 2026
MODEL_PRICING: dict[str, dict[str, float]] = {
    "claude-3-5-sonnet-latest": {"input": 3.0, "output": 15.0},
    "claude-3-5-sonnet-20241022": {"input": 3.0, "output": 15.0},
    "claude-3-5-haiku-latest": {"input": 0.8, "output": 4.0},
    "claude-3-opus-latest": {"input": 15.0, "output": 75.0},
    "claude-3-sonnet-20240229": {"input": 3.0, "output": 15.0},
    "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25},
}


class AnthropicProvider(BaseLLMProvider):
    """Anthropic (Claude) API provider.

    Direct access to Claude models:
    - Claude 3.5 Sonnet (best balance)
    - Claude 3.5 Haiku (fast/cheap)
    - Claude 3 Opus (highest capability)
    """

    BASE_URL = "https://api.anthropic.com/v1"
    API_VERSION = "2023-06-01"

    def __init__(self, config: ProviderConfig) -> None:
        super().__init__(config)
        self._client: httpx.AsyncClient | None = None

    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.ANTHROPIC

    async def init(self) -> None:
        """Initialize the HTTP client."""
        if self._initialized:
            return

        self._client = httpx.AsyncClient(
            base_url=self.config.api_base or self.BASE_URL,
            headers={
                "x-api-key": self.config.api_key,
                "anthropic-version": self.API_VERSION,
                "Content-Type": "application/json",
            },
            timeout=self.config.timeout,
        )
        self._initialized = True
        logger.info("Anthropic provider initialized")

    async def shutdown(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
        self._initialized = False
        logger.info("Anthropic provider shutdown")

    def _estimate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost in USD based on model pricing."""
        pricing = MODEL_PRICING.get(model, {"input": 3.0, "output": 15.0})
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
        """Execute Anthropic messages API call."""
        if self._client is None:
            await self.init()

        # Strip provider prefix if present
        clean_model = model.replace("anthropic/", "")

        # Anthropic separates system from messages
        system_prompt = None
        user_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_prompt = msg["content"]
            else:
                user_messages.append(msg)

        payload: dict[str, Any] = {
            "model": clean_model,
            "messages": user_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        if system_prompt:
            payload["system"] = system_prompt

        # Add optional parameters
        if "top_p" in kwargs and kwargs["top_p"] is not None:
            payload["top_p"] = kwargs["top_p"]
        if "stop" in kwargs and kwargs["stop"] is not None:
            payload["stop_sequences"] = kwargs["stop"]

        start_time = time.perf_counter()

        response = await self._client.post("/messages", json=payload)
        response.raise_for_status()

        latency_ms = (time.perf_counter() - start_time) * 1000

        data = response.json()
        usage = data.get("usage", {})

        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)

        # Extract text from content blocks
        text = ""
        for block in data.get("content", []):
            if block.get("type") == "text":
                text += block.get("text", "")

        return ChatResponse(
            text=text,
            model=data.get("model", clean_model),
            provider="anthropic",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            finish_reason=data.get("stop_reason", "unknown"),
            cost_usd=self._estimate_cost(clean_model, input_tokens, output_tokens),
            latency_ms=latency_ms,
            raw_response=data,
        )
