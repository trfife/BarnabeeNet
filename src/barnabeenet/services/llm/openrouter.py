"""OpenRouter API client for BarnabeeNet.

Provides LLM access with full signal logging for dashboard observability.
Supports multiple model configurations per agent type (SkyrimNet pattern).
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import httpx
from pydantic import BaseModel

from barnabeenet.services.llm.cache import get_llm_cache
from barnabeenet.services.llm.signals import LLMSignal, get_signal_logger

if TYPE_CHECKING:
    from barnabeenet.config import LLMSettings

logger = logging.getLogger(__name__)

# OpenRouter pricing (USD per 1M tokens) - updated as of Jan 2026
# These are estimates; actual pricing from OpenRouter API response
MODEL_PRICING: dict[str, dict[str, float]] = {
    "anthropic/claude-3.5-sonnet": {"input": 3.0, "output": 15.0},
    "anthropic/claude-3-haiku": {"input": 0.25, "output": 1.25},
    "openai/gpt-4o": {"input": 2.5, "output": 10.0},
    "openai/gpt-4o-mini": {"input": 0.15, "output": 0.6},
    "deepseek/deepseek-chat": {"input": 0.14, "output": 0.28},
    "deepseek/deepseek-reasoner": {"input": 0.55, "output": 2.19},
    "google/gemini-2.0-flash-001": {"input": 0.1, "output": 0.4},
    "meta-llama/llama-3.3-70b-instruct": {"input": 0.3, "output": 0.3},
}


class ModelConfig(BaseModel):
    """Configuration for a specific model."""

    model: str
    temperature: float = 0.7
    max_tokens: int = 1000
    top_p: float | None = None
    frequency_penalty: float | None = None
    presence_penalty: float | None = None


class AgentModelConfig(BaseModel):
    """Model configuration per agent type.

    Different agents use different models based on their needs:
    - meta: Fast/cheap for high-frequency routing decisions
    - instant: Fast/cheap for simple pattern-matched responses
    - action: Medium tier for device control decisions
    - interaction: Quality model for complex conversations
    - memory: Good summarization for memory generation

    Note: These are fallback defaults. Use from_settings() to load from config.
    """

    meta: ModelConfig = ModelConfig(
        model="deepseek/deepseek-chat",
        temperature=0.3,
        max_tokens=200,
    )
    instant: ModelConfig = ModelConfig(
        model="deepseek/deepseek-chat",
        temperature=0.5,
        max_tokens=300,
    )
    action: ModelConfig = ModelConfig(
        model="openai/gpt-4o-mini",
        temperature=0.3,
        max_tokens=500,
    )
    interaction: ModelConfig = ModelConfig(
        model="anthropic/claude-3.5-sonnet",
        temperature=0.7,
        max_tokens=1500,
    )
    memory: ModelConfig = ModelConfig(
        model="openai/gpt-4o-mini",
        temperature=0.3,
        max_tokens=800,
    )

    @classmethod
    def from_settings(cls, settings: LLMSettings) -> AgentModelConfig:
        """Create model config from application settings."""
        return cls(
            meta=ModelConfig(
                model=settings.meta_model,
                temperature=settings.meta_temperature,
                max_tokens=settings.meta_max_tokens,
            ),
            instant=ModelConfig(
                model=settings.instant_model,
                temperature=settings.instant_temperature,
                max_tokens=settings.instant_max_tokens,
            ),
            action=ModelConfig(
                model=settings.action_model,
                temperature=settings.action_temperature,
                max_tokens=settings.action_max_tokens,
            ),
            interaction=ModelConfig(
                model=settings.interaction_model,
                temperature=settings.interaction_temperature,
                max_tokens=settings.interaction_max_tokens,
            ),
            memory=ModelConfig(
                model=settings.memory_model,
                temperature=settings.memory_temperature,
                max_tokens=settings.memory_max_tokens,
            ),
        )


class ChatMessage(BaseModel):
    """A single message in a chat conversation."""

    role: str  # system, user, assistant
    content: str


class ChatResponse(BaseModel):
    """Response from a chat completion."""

    text: str
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    finish_reason: str
    cost_usd: float
    latency_ms: float


class OpenRouterClient:
    """OpenRouter API client with full signal logging.

    Every request is logged with complete context for dashboard visibility.
    Supports streaming and non-streaming completions.
    """

    BASE_URL = "https://openrouter.ai/api/v1"

    def __init__(
        self,
        api_key: str,
        model_config: AgentModelConfig | None = None,
        site_url: str = "https://barnabeenet.local",
        site_name: str = "BarnabeeNet",
    ) -> None:
        self.api_key = api_key
        self.model_config = model_config or AgentModelConfig()
        self.site_url = site_url
        self.site_name = site_name
        self._client: httpx.AsyncClient | None = None
        self._signal_logger = get_signal_logger()
        self._cache = get_llm_cache()

    async def init(self) -> None:
        """Initialize the HTTP client."""
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "HTTP-Referer": self.site_url,
                "X-Title": self.site_name,
                "Content-Type": "application/json",
            },
            timeout=60.0,
        )
        logger.info("OpenRouter client initialized")

    async def shutdown(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
        logger.info("OpenRouter client shutdown")

    def _get_model_config(self, agent_type: str) -> ModelConfig:
        """Get model configuration for an agent type."""
        return getattr(self.model_config, agent_type, self.model_config.interaction)

    def _estimate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost in USD based on model pricing."""
        pricing = MODEL_PRICING.get(model, {"input": 1.0, "output": 2.0})
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        return input_cost + output_cost

    async def chat(
        self,
        messages: list[ChatMessage] | list[dict[str, str]],
        agent_type: str = "interaction",
        *,
        # Activity-based configuration (preferred over agent_type)
        activity: str | None = None,
        # Context for signal logging
        conversation_id: str | None = None,
        trace_id: str | None = None,
        user_input: str | None = None,
        speaker: str | None = None,
        room: str | None = None,
        injected_context: dict[str, Any] | None = None,
        # Optional overrides
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        system_prompt: str | None = None,
    ) -> ChatResponse:
        """Send a chat completion request with full signal logging.

        Args:
            messages: List of chat messages
            agent_type: Type of agent making request (legacy, use activity instead)
            activity: Specific LLM activity (e.g., "meta.classify_intent", "interaction.respond")
            conversation_id: ID linking related requests
            trace_id: ID for request tracing
            user_input: Original user input for logging
            speaker: Who is speaking (for logging)
            room: Room context (for logging)
            injected_context: Context that was injected into prompt (for debugging)
            model: Override default model for this agent type
            temperature: Override default temperature
            max_tokens: Override default max_tokens
            system_prompt: System prompt (will be extracted for logging)

        Returns:
            ChatResponse with text, token counts, cost, and latency
        """
        if self._client is None:
            await self.init()

        # Get config: activity-based (preferred) or agent-based (legacy)
        if activity:
            from barnabeenet.services.llm.activities import get_activity_config

            activity_config = get_activity_config(activity)
            actual_model = model or activity_config.model
            actual_temp = temperature if temperature is not None else activity_config.temperature
            actual_max_tokens = max_tokens or activity_config.max_tokens
            config_top_p = activity_config.top_p
            config_freq_penalty = activity_config.frequency_penalty
            config_pres_penalty = activity_config.presence_penalty
        else:
            # Map agent_type to default activity for backward compatibility
            # This ensures dashboard config applies even if agent doesn't pass activity
            from barnabeenet.services.llm.activities import get_activity_config

            agent_to_activity = {
                "meta": "meta.classify_intent",
                "instant": "instant.fallback",
                "action": "action.parse_intent",
                "interaction": "interaction.respond",
                "memory": "memory.generate",
            }
            mapped_activity = agent_to_activity.get(agent_type)
            if mapped_activity:
                activity_config = get_activity_config(mapped_activity)
                actual_model = model or activity_config.model
                actual_temp = (
                    temperature if temperature is not None else activity_config.temperature
                )
                actual_max_tokens = max_tokens or activity_config.max_tokens
                config_top_p = activity_config.top_p
                config_freq_penalty = activity_config.frequency_penalty
                config_pres_penalty = activity_config.presence_penalty
            else:
                # Unknown agent type - use legacy config
                config = self._get_model_config(agent_type)
                actual_model = model or config.model
                actual_temp = temperature if temperature is not None else config.temperature
                actual_max_tokens = max_tokens or config.max_tokens
                config_top_p = config.top_p
                config_freq_penalty = config.frequency_penalty
                config_pres_penalty = config.presence_penalty

        # Normalize messages to dicts
        msg_dicts = []
        extracted_system = system_prompt
        for msg in messages:
            if isinstance(msg, ChatMessage):
                msg_dict = {"role": msg.role, "content": msg.content}
            else:
                msg_dict = msg
            if msg_dict["role"] == "system" and extracted_system is None:
                extracted_system = msg_dict["content"]
            msg_dicts.append(msg_dict)

        # Create signal for logging (include activity if specified)
        signal = LLMSignal(
            agent_type=activity or agent_type,  # Use activity for more granular tracking
            model=actual_model,
            temperature=actual_temp,
            max_tokens=actual_max_tokens,
            system_prompt=extracted_system,
            messages=msg_dicts,
            conversation_id=conversation_id,
            trace_id=trace_id,
            user_input=user_input,
            speaker=speaker,
            room=room,
            injected_context=injected_context or {},
            started_at=datetime.now(UTC),
        )

        # Build request payload
        payload: dict[str, Any] = {
            "model": actual_model,
            "messages": msg_dicts,
            "temperature": actual_temp,
            "max_tokens": actual_max_tokens,
        }
        if config_top_p is not None:
            payload["top_p"] = config_top_p
        if config_freq_penalty is not None:
            payload["frequency_penalty"] = config_freq_penalty
        if config_pres_penalty is not None:
            payload["presence_penalty"] = config_pres_penalty

        start_time = time.perf_counter()

        # Check cache first
        cache_key_text = user_input or (msg_dicts[-1].get("content", "") if msg_dicts else "")
        cached_response = None
        if self._cache and cache_key_text:
            cached_entry = await self._cache.get(
                query_text=cache_key_text,
                agent_type=activity or agent_type,
                model=actual_model,
                temperature=actual_temp,
            )
            if cached_entry:
                # Return cached response
                latency_ms = (time.perf_counter() - start_time) * 1000
                cached_response = ChatResponse(
                    text=cached_entry.response_text,
                    model=cached_entry.model,
                    input_tokens=cached_entry.input_tokens,
                    output_tokens=cached_entry.output_tokens,
                    total_tokens=cached_entry.input_tokens + cached_entry.output_tokens,
                    finish_reason="cache_hit",
                    cost_usd=0.0,  # Cached responses cost nothing
                    latency_ms=latency_ms,
                )

                # Update signal with cached response
                signal.completed_at = datetime.now(UTC)
                signal.response_text = cached_entry.response_text
                signal.response_tokens = cached_entry.output_tokens
                signal.finish_reason = "cache_hit"
                signal.input_tokens = cached_entry.input_tokens
                signal.output_tokens = cached_entry.output_tokens
                signal.total_tokens = cached_entry.input_tokens + cached_entry.output_tokens
                signal.cost_usd = 0.0
                signal.latency_ms = latency_ms
                signal.success = True
                signal.cached = True

                # Log signal for dashboard
                await self._signal_logger.log_signal(signal)

                logger.debug(
                    "LLM cache hit",
                    agent_type=activity or agent_type,
                    model=actual_model,
                    latency_ms=f"{latency_ms:.2f}",
                )

                return cached_response

        try:
            response = await self._client.post("/chat/completions", json=payload)
            response.raise_for_status()
            data = response.json()

            # Extract response data
            choice = data["choices"][0]
            message = choice["message"]
            usage = data.get("usage", {})

            input_tokens = usage.get("prompt_tokens", 0)
            output_tokens = usage.get("completion_tokens", 0)
            total_tokens = usage.get("total_tokens", input_tokens + output_tokens)

            latency_ms = (time.perf_counter() - start_time) * 1000
            cost_usd = self._estimate_cost(actual_model, input_tokens, output_tokens)

            # Update signal with response
            signal.completed_at = datetime.now(UTC)
            signal.response_text = message["content"]
            signal.response_tokens = output_tokens
            signal.finish_reason = choice.get("finish_reason", "unknown")
            signal.input_tokens = input_tokens
            signal.output_tokens = output_tokens
            signal.total_tokens = total_tokens
            signal.cost_usd = cost_usd
            signal.latency_ms = latency_ms
            signal.success = True

            # Log signal for dashboard
            await self._signal_logger.log_signal(signal)

            # Cache the response
            if self._cache and cache_key_text:
                await self._cache.set(
                    query_text=cache_key_text,
                    response_text=message["content"],
                    agent_type=activity or agent_type,
                    model=actual_model,
                    temperature=actual_temp,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cost_usd=cost_usd,
                )

            return ChatResponse(
                text=message["content"],
                model=data.get("model", actual_model),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                finish_reason=choice.get("finish_reason", "unknown"),
                cost_usd=cost_usd,
                latency_ms=latency_ms,
            )

        except httpx.HTTPStatusError as e:
            signal.completed_at = datetime.now(UTC)
            signal.error = str(e)
            signal.error_type = "http_error"
            signal.success = False
            await self._signal_logger.log_signal(signal)
            logger.error("OpenRouter HTTP error: %s", e)
            raise

        except httpx.RequestError as e:
            signal.completed_at = datetime.now(UTC)
            signal.error = str(e)
            signal.error_type = "request_error"
            signal.success = False
            await self._signal_logger.log_signal(signal)
            logger.error("OpenRouter request error: %s", e)
            raise

        except Exception as e:
            signal.completed_at = datetime.now(UTC)
            signal.error = str(e)
            signal.error_type = type(e).__name__
            signal.success = False
            await self._signal_logger.log_signal(signal)
            logger.error("OpenRouter unexpected error: %s", e)
            raise

    async def simple_chat(
        self,
        user_message: str,
        system_prompt: str | None = None,
        agent_type: str = "interaction",
        **kwargs: Any,
    ) -> str:
        """Convenience method for simple single-turn chat.

        Args:
            user_message: The user's message
            system_prompt: Optional system prompt
            agent_type: Type of agent (for model selection)
            **kwargs: Additional arguments passed to chat()

        Returns:
            The assistant's response text
        """
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_message})

        response = await self.chat(
            messages,
            agent_type=agent_type,
            user_input=user_message,
            system_prompt=system_prompt,
            **kwargs,
        )
        return response.text


# Global client instance
_openrouter_client: OpenRouterClient | None = None


def get_openrouter_client() -> OpenRouterClient | None:
    """Get the global OpenRouter client instance."""
    return _openrouter_client


async def init_openrouter_client(api_key: str, **kwargs: Any) -> OpenRouterClient:
    """Initialize the global OpenRouter client."""
    global _openrouter_client
    _openrouter_client = OpenRouterClient(api_key, **kwargs)
    await _openrouter_client.init()
    return _openrouter_client
