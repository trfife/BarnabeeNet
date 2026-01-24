"""Azure OpenAI LLM provider implementation.

Access to OpenAI models via Azure's infrastructure.
See: https://learn.microsoft.com/en-us/azure/ai-services/openai/reference
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

# Azure OpenAI pricing varies by region and deployment
# These are rough estimates (USD per 1M tokens)
MODEL_PRICING: dict[str, dict[str, float]] = {
    "gpt-4o": {"input": 2.5, "output": 10.0},
    "gpt-4o-mini": {"input": 0.15, "output": 0.6},
    "gpt-4": {"input": 30.0, "output": 60.0},
    "gpt-35-turbo": {"input": 0.5, "output": 1.5},
}


class AzureOpenAIProvider(BaseLLMProvider):
    """Azure OpenAI API provider.

    Access to OpenAI models through Azure infrastructure.
    Requires:
    - api_base: Your Azure endpoint (e.g., https://your-resource.openai.azure.com)
    - api_key: Your Azure API key
    - api_version: API version (e.g., 2024-02-15-preview)
    - deployment_name: Your deployment name

    The deployment_name maps to the model you deployed in Azure.
    """

    def __init__(self, config: ProviderConfig) -> None:
        super().__init__(config)
        self._client: httpx.AsyncClient | None = None

        # Validate required config
        if not config.api_base:
            raise ValueError("Azure OpenAI requires api_base (endpoint URL)")
        if not config.api_version:
            config.api_version = "2024-02-15-preview"

    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.AZURE

    async def init(self) -> None:
        """Initialize the HTTP client."""
        if self._initialized:
            return

        self._client = httpx.AsyncClient(
            base_url=self.config.api_base.rstrip("/"),
            headers={
                "api-key": self.config.api_key,
                "Content-Type": "application/json",
            },
            timeout=self.config.timeout,
        )
        self._initialized = True
        logger.info(f"Azure OpenAI provider initialized: {self.config.api_base}")

    async def shutdown(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
        self._initialized = False
        logger.info("Azure OpenAI provider shutdown")

    def _estimate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost in USD based on model pricing."""
        # Try to match model name to pricing
        for key, pricing in MODEL_PRICING.items():
            if key in model.lower():
                input_cost = (input_tokens / 1_000_000) * pricing["input"]
                output_cost = (output_tokens / 1_000_000) * pricing["output"]
                return input_cost + output_cost
        # Default pricing
        return (input_tokens + output_tokens) / 1_000_000 * 2.0

    def _get_deployment_name(self, model: str) -> str:
        """Get Azure deployment name from model config.

        If deployment_name is set in config, use it.
        Otherwise, try to derive from model name.
        """
        if self.config.deployment_name:
            return self.config.deployment_name

        # Map common model names to typical deployment names
        model_lower = model.lower()
        if "gpt-4o-mini" in model_lower:
            return "gpt-4o-mini"
        elif "gpt-4o" in model_lower:
            return "gpt-4o"
        elif "gpt-4" in model_lower:
            return "gpt-4"
        elif "gpt-35" in model_lower or "gpt-3.5" in model_lower:
            return "gpt-35-turbo"

        # Fallback: use model name as deployment name
        return model.replace("azure/", "").replace("openai/", "")

    async def _do_chat(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float,
        max_tokens: int,
        **kwargs: Any,
    ) -> ChatResponse:
        """Execute Azure OpenAI chat completion."""
        if self._client is None:
            await self.init()

        deployment = self._get_deployment_name(model)

        payload: dict[str, Any] = {
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        # Add optional parameters
        for key in ["top_p", "frequency_penalty", "presence_penalty", "stop"]:
            if key in kwargs and kwargs[key] is not None:
                payload[key] = kwargs[key]

        # Azure uses deployment in URL path
        url = f"/openai/deployments/{deployment}/chat/completions"
        params = {"api-version": self.config.api_version}

        start_time = time.perf_counter()

        response = await self._client.post(url, json=payload, params=params)
        response.raise_for_status()

        latency_ms = (time.perf_counter() - start_time) * 1000

        data = response.json()
        choice = data["choices"][0]
        usage = data.get("usage", {})

        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)

        return ChatResponse(
            text=choice["message"]["content"],
            model=data.get("model", deployment),
            provider="azure",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            finish_reason=choice.get("finish_reason", "unknown"),
            cost_usd=self._estimate_cost(deployment, input_tokens, output_tokens),
            latency_ms=latency_ms,
            raw_response=data,
        )
