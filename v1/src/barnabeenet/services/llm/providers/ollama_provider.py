"""Ollama LLM provider implementation.

Local LLM inference using Ollama.
See: https://github.com/ollama/ollama/blob/main/docs/api.md
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


class OllamaProvider(BaseLLMProvider):
    """Ollama local LLM provider.

    Provides fast local inference using Ollama with models like:
    - llama3.2:3b (fast, good for simple tasks)
    - llama3.2:1b (fastest, basic tasks)
    - phi3:mini (fast, good reasoning)
    - mistral:7b (balanced quality/speed)
    """

    DEFAULT_URL = "http://localhost:11434"

    def __init__(self, config: ProviderConfig) -> None:
        super().__init__(config)
        self._client: httpx.AsyncClient | None = None

    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.LOCAL

    async def init(self) -> None:
        """Initialize the HTTP client."""
        if self._initialized:
            return

        base_url = self.config.api_base or self.DEFAULT_URL

        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={"Content-Type": "application/json"},
            timeout=self.config.timeout,
        )
        self._initialized = True
        logger.info(f"Ollama provider initialized at {base_url}")

    async def shutdown(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
        self._initialized = False
        logger.info("Ollama provider shutdown")

    async def _do_chat(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float,
        max_tokens: int,
        **kwargs: Any,
    ) -> ChatResponse:
        """Execute Ollama chat completion.
        
        Uses the /api/chat endpoint for chat-style completions.
        """
        if self._client is None:
            await self.init()

        # Strip provider prefix if present (e.g., "ollama/llama3.2:3b" -> "llama3.2:3b")
        clean_model = model.replace("ollama/", "").replace("local/", "")

        payload: dict[str, Any] = {
            "model": clean_model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        start_time = time.perf_counter()

        try:
            response = await self._client.post("/api/chat", json=payload)
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.error(f"Ollama API error: {e.response.status_code} - {e.response.text}")
            raise
        except httpx.ConnectError:
            logger.error("Failed to connect to Ollama. Is it running?")
            raise

        latency_ms = (time.perf_counter() - start_time) * 1000

        data = response.json()
        
        # Extract response text
        message = data.get("message", {})
        text = message.get("content", "")
        
        # Ollama provides token counts in the response
        prompt_eval_count = data.get("prompt_eval_count", 0)
        eval_count = data.get("eval_count", 0)

        return ChatResponse(
            text=text,
            model=data.get("model", clean_model),
            provider="ollama",
            input_tokens=prompt_eval_count,
            output_tokens=eval_count,
            total_tokens=prompt_eval_count + eval_count,
            finish_reason=data.get("done_reason", "stop"),
            cost_usd=0.0,  # Local inference has no API cost
            latency_ms=latency_ms,
            raw_response=data,
        )

    async def list_models(self) -> list[str]:
        """List available models in Ollama."""
        if self._client is None:
            await self.init()

        try:
            response = await self._client.get("/api/tags")
            response.raise_for_status()
            data = response.json()
            return [m["name"] for m in data.get("models", [])]
        except Exception as e:
            logger.error(f"Failed to list Ollama models: {e}")
            return []

    async def is_available(self) -> bool:
        """Check if Ollama is running and reachable."""
        try:
            if self._client is None:
                await self.init()
            response = await self._client.get("/api/tags")
            return response.status_code == 200
        except Exception:
            return False
