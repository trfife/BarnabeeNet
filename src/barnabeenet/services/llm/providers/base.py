"""Base classes and protocols for LLM providers.

This module defines the abstract interface that all LLM providers must implement.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from pydantic import BaseModel

if TYPE_CHECKING:
    from barnabeenet.config import LLMSettings

logger = logging.getLogger(__name__)


class ProviderType(str, Enum):
    """Supported LLM provider types."""

    OPENROUTER = "openrouter"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    AZURE = "azure"
    GOOGLE = "google"
    HUGGINGFACE = "huggingface"
    GROK = "grok"
    LOCAL = "local"  # For local models (Ollama, vLLM, etc.)


class ChatMessage(BaseModel):
    """A single message in a chat conversation."""

    role: str  # system, user, assistant
    content: str
    name: str | None = None  # Optional name for multi-agent scenarios


class ChatResponse(BaseModel):
    """Response from a chat completion."""

    text: str
    model: str
    provider: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    finish_reason: str
    cost_usd: float
    latency_ms: float

    # Optional metadata
    raw_response: dict[str, Any] | None = None


class ModelConfig(BaseModel):
    """Configuration for a specific model."""

    model: str
    temperature: float = 0.7
    max_tokens: int = 1000
    top_p: float | None = None
    frequency_penalty: float | None = None
    presence_penalty: float | None = None
    stop: list[str] | None = None


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


class ProviderConfig(BaseModel):
    """Configuration for an LLM provider."""

    provider: ProviderType
    api_key: str | None = None
    api_base: str | None = None  # For custom endpoints (Azure, local, etc.)
    api_version: str | None = None  # For Azure
    organization: str | None = None  # For OpenAI
    deployment_name: str | None = None  # For Azure
    models: AgentModelConfig = AgentModelConfig()
    timeout: float = 60.0
    max_retries: int = 3

    # Provider-specific options
    extra: dict[str, Any] = {}


@dataclass
class SignalContext:
    """Context for signal logging."""

    conversation_id: str | None = None
    trace_id: str | None = None
    user_input: str | None = None
    speaker: str | None = None
    room: str | None = None
    injected_context: dict[str, Any] = field(default_factory=dict)
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@runtime_checkable
class LLMProvider(Protocol):
    """Protocol defining the interface all LLM providers must implement.

    This allows different providers to be used interchangeably.
    """

    @property
    def provider_type(self) -> ProviderType:
        """Return the provider type."""
        ...

    @property
    def is_initialized(self) -> bool:
        """Return whether the provider is initialized."""
        ...

    async def init(self) -> None:
        """Initialize the provider (e.g., create HTTP clients)."""
        ...

    async def shutdown(self) -> None:
        """Clean up resources."""
        ...

    async def chat(
        self,
        messages: list[ChatMessage] | list[dict[str, str]],
        agent_type: str = "interaction",
        *,
        signal_context: SignalContext | None = None,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> ChatResponse:
        """Send a chat completion request.

        Args:
            messages: List of chat messages
            agent_type: Type of agent making request
            signal_context: Context for signal logging
            model: Override default model
            temperature: Override default temperature
            max_tokens: Override default max_tokens
            system_prompt: System prompt
            **kwargs: Provider-specific options

        Returns:
            ChatResponse with text, token counts, cost, and latency
        """
        ...

    def get_model_config(self, agent_type: str) -> ModelConfig:
        """Get model configuration for an agent type."""
        ...


class BaseLLMProvider(ABC):
    """Base class providing common functionality for LLM providers.

    Subclasses must implement:
    - _do_chat(): The actual API call
    - provider_type property
    """

    def __init__(self, config: ProviderConfig) -> None:
        self.config = config
        self._initialized = False

    @property
    @abstractmethod
    def provider_type(self) -> ProviderType:
        """Return the provider type."""
        ...

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    def get_model_config(self, agent_type: str) -> ModelConfig:
        """Get model configuration for an agent type."""
        return getattr(self.config.models, agent_type, self.config.models.interaction)

    @abstractmethod
    async def init(self) -> None:
        """Initialize the provider."""
        ...

    @abstractmethod
    async def shutdown(self) -> None:
        """Clean up resources."""
        ...

    @abstractmethod
    async def _do_chat(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float,
        max_tokens: int,
        **kwargs: Any,
    ) -> ChatResponse:
        """Execute the actual chat API call.

        Subclasses implement this for their specific API.
        """
        ...

    async def chat(
        self,
        messages: list[ChatMessage] | list[dict[str, str]],
        agent_type: str = "interaction",
        *,
        signal_context: SignalContext | None = None,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> ChatResponse:
        """Send a chat completion request with logging.

        This method handles:
        - Message normalization
        - Config resolution
        - Signal logging
        - Calling the provider-specific _do_chat()
        """
        if not self._initialized:
            await self.init()

        # Resolve config
        config = self.get_model_config(agent_type)
        actual_model = model or config.model
        actual_temp = temperature if temperature is not None else config.temperature
        actual_max_tokens = max_tokens or config.max_tokens

        # Normalize messages to dicts
        msg_dicts = []
        for msg in messages:
            if isinstance(msg, ChatMessage):
                msg_dict = {"role": msg.role, "content": msg.content}
                if msg.name:
                    msg_dict["name"] = msg.name
            else:
                msg_dict = dict(msg)
            msg_dicts.append(msg_dict)

        # Import signal logging here to avoid circular imports
        from barnabeenet.services.llm.signals import LLMSignal, get_signal_logger

        # Build signal for logging
        extracted_system = system_prompt
        for msg in msg_dicts:
            if msg["role"] == "system" and extracted_system is None:
                extracted_system = msg["content"]
                break

        signal = LLMSignal(
            agent_type=agent_type,
            model=actual_model,
            temperature=actual_temp,
            max_tokens=actual_max_tokens,
            system_prompt=extracted_system,
            messages=msg_dicts,
            conversation_id=signal_context.conversation_id if signal_context else None,
            trace_id=signal_context.trace_id if signal_context else None,
            user_input=signal_context.user_input if signal_context else None,
            speaker=signal_context.speaker if signal_context else None,
            room=signal_context.room if signal_context else None,
            injected_context=signal_context.injected_context if signal_context else {},
            started_at=signal_context.started_at if signal_context else datetime.now(UTC),
        )

        # Execute the call
        try:
            response = await self._do_chat(
                messages=msg_dicts,
                model=actual_model,
                temperature=actual_temp,
                max_tokens=actual_max_tokens,
                **kwargs,
            )

            # Update signal with response
            signal.response_text = response.text
            signal.completed_at = datetime.now(UTC)
            signal.latency_ms = response.latency_ms
            signal.input_tokens = response.input_tokens
            signal.output_tokens = response.output_tokens
            signal.total_tokens = response.total_tokens
            signal.cost_usd = response.cost_usd
            signal.finish_reason = response.finish_reason
            signal.success = True

        except Exception as e:
            signal.error = str(e)
            signal.success = False
            signal.completed_at = datetime.now(UTC)
            logger.error(f"LLM call failed: {e}")
            raise
        finally:
            # Log signal
            signal_logger = get_signal_logger()
            await signal_logger.log(signal)

        return response
