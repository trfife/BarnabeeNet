"""Hugging Face LLM provider implementation.

Access to models via Hugging Face Inference API or Inference Endpoints.
See: https://huggingface.co/docs/api-inference/index
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

# HF Inference API is priced per request or via Inference Endpoints
# These are estimates for common models
MODEL_PRICING: dict[str, dict[str, float]] = {
    "meta-llama/Llama-3.3-70B-Instruct": {"input": 0.3, "output": 0.3},
    "mistralai/Mixtral-8x7B-Instruct-v0.1": {"input": 0.2, "output": 0.2},
    "microsoft/Phi-3-mini-4k-instruct": {"input": 0.1, "output": 0.1},
    "Qwen/Qwen2.5-72B-Instruct": {"input": 0.3, "output": 0.3},
}


class HuggingFaceProvider(BaseLLMProvider):
    """Hugging Face Inference API provider.

    Access to open-source models via:
    - Serverless Inference API (free tier available)
    - Inference Endpoints (dedicated)
    - Local models via TGI/vLLM

    Set api_base to point to:
    - Default: Serverless Inference API
    - Custom endpoint: Your Inference Endpoint URL
    """

    BASE_URL = "https://api-inference.huggingface.co"

    def __init__(self, config: ProviderConfig) -> None:
        super().__init__(config)
        self._client: httpx.AsyncClient | None = None

    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.HUGGINGFACE

    async def init(self) -> None:
        """Initialize the HTTP client."""
        if self._initialized:
            return

        self._client = httpx.AsyncClient(
            base_url=self.config.api_base or self.BASE_URL,
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
            },
            timeout=self.config.timeout,
        )
        self._initialized = True
        logger.info("Hugging Face provider initialized")

    async def shutdown(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
        self._initialized = False
        logger.info("Hugging Face provider shutdown")

    def _estimate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost in USD based on model pricing."""
        pricing = MODEL_PRICING.get(model, {"input": 0.1, "output": 0.1})
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        return input_cost + output_cost

    def _format_chat_prompt(self, messages: list[dict[str, str]]) -> str:
        """Format messages into a chat prompt.

        Many HF models expect specific prompt formats.
        This handles common formats (Llama, Mistral, etc.)
        """
        formatted = ""
        for msg in messages:
            role = msg["role"]
            content = msg["content"]

            if role == "system":
                formatted += f"<|system|>\n{content}</s>\n"
            elif role == "user":
                formatted += f"<|user|>\n{content}</s>\n"
            elif role == "assistant":
                formatted += f"<|assistant|>\n{content}</s>\n"

        # Add assistant prefix for generation
        formatted += "<|assistant|>\n"
        return formatted

    async def _do_chat(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float,
        max_tokens: int,
        **kwargs: Any,
    ) -> ChatResponse:
        """Execute Hugging Face Inference API call.

        HF supports multiple formats:
        1. Chat completion (OpenAI-compatible)
        2. Text generation (prompt-based)

        We try chat completion first, fall back to text generation.
        """
        if self._client is None:
            await self.init()

        # Strip provider prefix if present
        clean_model = model.replace("huggingface/", "").replace("hf/", "")

        # First try OpenAI-compatible chat completions
        # (Available on some Inference Endpoints)
        try:
            return await self._chat_completion(
                messages, clean_model, temperature, max_tokens, **kwargs
            )
        except (httpx.HTTPStatusError, KeyError):
            # Fall back to text generation
            return await self._text_generation(
                messages, clean_model, temperature, max_tokens, **kwargs
            )

    async def _chat_completion(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float,
        max_tokens: int,
        **kwargs: Any,
    ) -> ChatResponse:
        """Try OpenAI-compatible chat completion."""
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        start_time = time.perf_counter()

        response = await self._client.post(f"/models/{model}/v1/chat/completions", json=payload)
        response.raise_for_status()

        latency_ms = (time.perf_counter() - start_time) * 1000

        data = response.json()
        choice = data["choices"][0]
        usage = data.get("usage", {})

        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)

        return ChatResponse(
            text=choice["message"]["content"],
            model=model,
            provider="huggingface",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            finish_reason=choice.get("finish_reason", "unknown"),
            cost_usd=self._estimate_cost(model, input_tokens, output_tokens),
            latency_ms=latency_ms,
            raw_response=data,
        )

    async def _text_generation(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float,
        max_tokens: int,
        **kwargs: Any,
    ) -> ChatResponse:
        """Fall back to text generation API."""
        # Format messages into prompt
        prompt = self._format_chat_prompt(messages)

        payload: dict[str, Any] = {
            "inputs": prompt,
            "parameters": {
                "temperature": temperature,
                "max_new_tokens": max_tokens,
                "return_full_text": False,
            },
        }

        # Add optional parameters
        if "top_p" in kwargs and kwargs["top_p"] is not None:
            payload["parameters"]["top_p"] = kwargs["top_p"]

        start_time = time.perf_counter()

        response = await self._client.post(f"/models/{model}", json=payload)
        response.raise_for_status()

        latency_ms = (time.perf_counter() - start_time) * 1000

        data = response.json()

        # Handle response format
        if isinstance(data, list):
            text = data[0].get("generated_text", "")
        else:
            text = data.get("generated_text", "")

        # Estimate tokens (HF doesn't always return this)
        input_tokens = len(prompt.split()) * 1.3  # Rough estimate
        output_tokens = len(text.split()) * 1.3

        return ChatResponse(
            text=text,
            model=model,
            provider="huggingface",
            input_tokens=int(input_tokens),
            output_tokens=int(output_tokens),
            total_tokens=int(input_tokens + output_tokens),
            finish_reason="stop",
            cost_usd=self._estimate_cost(model, int(input_tokens), int(output_tokens)),
            latency_ms=latency_ms,
            raw_response=data if isinstance(data, dict) else {"results": data},
        )
