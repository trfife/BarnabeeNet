"""Factory for creating LLM providers.

This module provides a clean interface for creating providers
based on configuration.
"""

from __future__ import annotations

import logging
from typing import Any

from .base import (
    AgentModelConfig,
    LLMProvider,
    ProviderConfig,
    ProviderType,
)

logger = logging.getLogger(__name__)

# Registry of provider implementations
_PROVIDER_REGISTRY: dict[ProviderType, type] = {}


def _ensure_providers_registered() -> None:
    """Lazy-load provider implementations to avoid import cycles."""
    global _PROVIDER_REGISTRY

    if _PROVIDER_REGISTRY:
        return

    from .anthropic_provider import AnthropicProvider
    from .azure_provider import AzureOpenAIProvider
    from .google_provider import GoogleProvider
    from .grok_provider import GrokProvider
    from .huggingface_provider import HuggingFaceProvider
    from .ollama_provider import OllamaProvider
    from .openai_provider import OpenAIProvider
    from .openrouter_provider import OpenRouterProvider

    _PROVIDER_REGISTRY = {
        ProviderType.OPENROUTER: OpenRouterProvider,
        ProviderType.OPENAI: OpenAIProvider,
        ProviderType.ANTHROPIC: AnthropicProvider,
        ProviderType.AZURE: AzureOpenAIProvider,
        ProviderType.GOOGLE: GoogleProvider,
        ProviderType.GROK: GrokProvider,
        ProviderType.HUGGINGFACE: HuggingFaceProvider,
        ProviderType.LOCAL: OllamaProvider,  # Ollama for local inference
    }


def get_available_providers() -> list[str]:
    """Get list of available provider names."""
    return [p.value for p in ProviderType]


def create_provider(
    provider_type: str | ProviderType,
    *,
    api_key: str | None = None,
    api_base: str | None = None,
    api_version: str | None = None,
    organization: str | None = None,
    deployment_name: str | None = None,
    models: AgentModelConfig | None = None,
    timeout: float = 60.0,
    max_retries: int = 3,
    **extra: Any,
) -> LLMProvider:
    """Create an LLM provider instance.

    Args:
        provider_type: The provider to use (e.g., "openrouter", "openai")
        api_key: API key for the provider
        api_base: Custom API base URL (required for Azure, optional for others)
        api_version: API version (used by Azure)
        organization: Organization ID (used by OpenAI)
        deployment_name: Deployment name (used by Azure)
        models: Model configuration per agent type
        timeout: Request timeout in seconds
        max_retries: Number of retries on failure
        **extra: Provider-specific options

    Returns:
        Configured LLM provider instance (not yet initialized)

    Example:
        # Create OpenRouter provider
        provider = create_provider("openrouter", api_key="YOUR_API_KEY")
        await provider.init()

        # Create Azure provider
        provider = create_provider(
            "azure",
            api_key="YOUR_API_KEY",
            api_base="https://my-resource.openai.azure.com",
            deployment_name="gpt-4o"
        )
    """
    _ensure_providers_registered()

    # Convert string to enum if needed
    if isinstance(provider_type, str):
        try:
            provider_type = ProviderType(provider_type.lower())
        except ValueError as e:
            available = ", ".join(get_available_providers())
            raise ValueError(f"Unknown provider: {provider_type}. Available: {available}") from e

    if provider_type not in _PROVIDER_REGISTRY:
        raise ValueError(f"Provider not implemented: {provider_type}")

    # Build config
    config = ProviderConfig(
        provider=provider_type,
        api_key=api_key,
        api_base=api_base,
        api_version=api_version,
        organization=organization,
        deployment_name=deployment_name,
        models=models or AgentModelConfig(),
        timeout=timeout,
        max_retries=max_retries,
        extra=extra,
    )

    # Create provider instance
    provider_class = _PROVIDER_REGISTRY[provider_type]
    return provider_class(config)


def create_provider_from_config(config: dict[str, Any]) -> LLMProvider:
    """Create an LLM provider from a configuration dictionary.

    This is useful for loading configuration from YAML/JSON files.

    Args:
        config: Dictionary with provider configuration. Must include:
            - provider: Provider type (e.g., "openrouter")
            - api_key: API key (optional, can be from env)

    Returns:
        Configured LLM provider instance

    Example config:
        {
            "provider": "openrouter",
            "api_key": "YOUR_KEY",  # Or use env: LLM_OPENROUTER_API_KEY
            "models": {
                "meta": {"model": "deepseek/deepseek-chat", "temperature": 0.3},
                "interaction": {"model": "anthropic/claude-3.5-sonnet"}
            }
        }
    """
    import os

    provider_type = config.get("provider", "openrouter")

    # Handle API key from environment
    api_key = config.get("api_key")
    if not api_key:
        # Try to get from environment based on provider
        env_vars = {
            "openrouter": "LLM_OPENROUTER_API_KEY",
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "azure": "AZURE_OPENAI_API_KEY",
            "google": "GOOGLE_API_KEY",
            "grok": "GROK_API_KEY",
            "huggingface": "HF_TOKEN",
        }
        env_var = env_vars.get(provider_type.lower())
        if env_var:
            api_key = os.environ.get(env_var)

    # Parse model config
    models = None
    if "models" in config:
        models = AgentModelConfig(**config["models"])

    return create_provider(
        provider_type=provider_type,
        api_key=api_key,
        api_base=config.get("api_base"),
        api_version=config.get("api_version"),
        organization=config.get("organization"),
        deployment_name=config.get("deployment_name"),
        models=models,
        timeout=config.get("timeout", 60.0),
        max_retries=config.get("max_retries", 3),
        **config.get("extra", {}),
    )


# Convenience aliases for common providers
async def create_openrouter(api_key: str, **kwargs: Any) -> LLMProvider:
    """Create and initialize an OpenRouter provider."""
    provider = create_provider(ProviderType.OPENROUTER, api_key=api_key, **kwargs)
    await provider.init()
    return provider


async def create_openai(api_key: str, **kwargs: Any) -> LLMProvider:
    """Create and initialize an OpenAI provider."""
    provider = create_provider(ProviderType.OPENAI, api_key=api_key, **kwargs)
    await provider.init()
    return provider


async def create_anthropic(api_key: str, **kwargs: Any) -> LLMProvider:
    """Create and initialize an Anthropic provider."""
    provider = create_provider(ProviderType.ANTHROPIC, api_key=api_key, **kwargs)
    await provider.init()
    return provider
