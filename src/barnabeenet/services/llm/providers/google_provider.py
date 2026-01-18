"""Google (Gemini) LLM provider implementation.

Direct access to Google's Gemini models.
See: https://ai.google.dev/api/python/google/generativeai
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

# Gemini pricing (USD per 1M tokens) - updated as of Jan 2026
MODEL_PRICING: dict[str, dict[str, float]] = {
    "gemini-2.0-flash-exp": {"input": 0.0, "output": 0.0},  # Free during preview
    "gemini-2.0-flash": {"input": 0.1, "output": 0.4},
    "gemini-1.5-pro": {"input": 1.25, "output": 5.0},
    "gemini-1.5-flash": {"input": 0.075, "output": 0.3},
    "gemini-1.0-pro": {"input": 0.5, "output": 1.5},
}


class GoogleProvider(BaseLLMProvider):
    """Google Gemini API provider.

    Access to Gemini models:
    - Gemini 2.0 Flash (fast multimodal)
    - Gemini 1.5 Pro (high capability)
    - Gemini 1.5 Flash (fast/cheap)
    """

    BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

    def __init__(self, config: ProviderConfig) -> None:
        super().__init__(config)
        self._client: httpx.AsyncClient | None = None

    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.GOOGLE

    async def init(self) -> None:
        """Initialize the HTTP client."""
        if self._initialized:
            return

        self._client = httpx.AsyncClient(
            base_url=self.config.api_base or self.BASE_URL,
            headers={"Content-Type": "application/json"},
            timeout=self.config.timeout,
        )
        self._initialized = True
        logger.info("Google Gemini provider initialized")

    async def shutdown(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
        self._initialized = False
        logger.info("Google Gemini provider shutdown")

    def _estimate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost in USD based on model pricing."""
        for key, pricing in MODEL_PRICING.items():
            if key in model.lower():
                input_cost = (input_tokens / 1_000_000) * pricing["input"]
                output_cost = (output_tokens / 1_000_000) * pricing["output"]
                return input_cost + output_cost
        return (input_tokens + output_tokens) / 1_000_000 * 0.5

    def _convert_messages(
        self, messages: list[dict[str, str]]
    ) -> tuple[str | None, list[dict[str, Any]]]:
        """Convert OpenAI-style messages to Gemini format.

        Returns:
            Tuple of (system_instruction, contents)
        """
        system_instruction = None
        contents = []

        for msg in messages:
            role = msg["role"]
            content = msg["content"]

            if role == "system":
                system_instruction = content
            elif role == "user":
                contents.append({"role": "user", "parts": [{"text": content}]})
            elif role == "assistant":
                contents.append({"role": "model", "parts": [{"text": content}]})

        return system_instruction, contents

    async def _do_chat(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float,
        max_tokens: int,
        **kwargs: Any,
    ) -> ChatResponse:
        """Execute Gemini generateContent API call."""
        if self._client is None:
            await self.init()

        # Strip provider prefix if present
        clean_model = model.replace("google/", "")

        # Convert messages to Gemini format
        system_instruction, contents = self._convert_messages(messages)

        # Build request
        payload: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }

        if system_instruction:
            payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}

        # Add optional parameters
        if "top_p" in kwargs and kwargs["top_p"] is not None:
            payload["generationConfig"]["topP"] = kwargs["top_p"]
        if "stop" in kwargs and kwargs["stop"] is not None:
            payload["generationConfig"]["stopSequences"] = kwargs["stop"]

        url = f"/models/{clean_model}:generateContent"
        params = {"key": self.config.api_key}

        start_time = time.perf_counter()

        response = await self._client.post(url, json=payload, params=params)
        response.raise_for_status()

        latency_ms = (time.perf_counter() - start_time) * 1000

        data = response.json()

        # Extract response text
        text = ""
        candidates = data.get("candidates", [])
        if candidates:
            content = candidates[0].get("content", {})
            parts = content.get("parts", [])
            for part in parts:
                if "text" in part:
                    text += part["text"]

        # Get token counts from usage metadata
        usage = data.get("usageMetadata", {})
        input_tokens = usage.get("promptTokenCount", 0)
        output_tokens = usage.get("candidatesTokenCount", 0)

        # Determine finish reason
        finish_reason = "unknown"
        if candidates:
            finish_reason = candidates[0].get("finishReason", "unknown").lower()

        return ChatResponse(
            text=text,
            model=clean_model,
            provider="google",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            finish_reason=finish_reason,
            cost_usd=self._estimate_cost(clean_model, input_tokens, output_tokens),
            latency_ms=latency_ms,
            raw_response=data,
        )
