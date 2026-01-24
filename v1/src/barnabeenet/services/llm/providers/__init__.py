"""LLM Provider abstraction layer.

This module provides a pluggable architecture for LLM providers.
Supported providers:
- OpenRouter (default) - access to many models via one API
- OpenAI - direct OpenAI API access
- Anthropic - direct Claude API access
- Azure - Azure OpenAI Service
- Google - Gemini API
- Hugging Face - Inference API and local models
- Grok - xAI API

Usage:
    from barnabeenet.services.llm.providers import create_provider

    # Create from config
    provider = await create_provider("openrouter", api_key="...")

    # Or with full config dict
    provider = await create_provider_from_config({
        "provider": "openrouter",
        "api_key": "...",
        "models": {...}
    })
"""

from .base import (
    ChatMessage,
    ChatResponse,
    LLMProvider,
    ModelConfig,
    ProviderConfig,
)
from .factory import create_provider, create_provider_from_config, get_available_providers

__all__ = [
    "ChatMessage",
    "ChatResponse",
    "LLMProvider",
    "ModelConfig",
    "ProviderConfig",
    "create_provider",
    "create_provider_from_config",
    "get_available_providers",
]
