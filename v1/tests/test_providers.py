"""Tests for LLM provider abstraction layer."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from barnabeenet.services.llm.providers import (
    ChatMessage,
    ChatResponse,
    LLMProvider,
    ModelConfig,
    ProviderConfig,
    create_provider,
    create_provider_from_config,
    get_available_providers,
)
from barnabeenet.services.llm.providers.base import (
    AgentModelConfig,
    ProviderType,
    SignalContext,
)

# ============================================================================
# ChatMessage Tests
# ============================================================================


class TestChatMessage:
    """Tests for ChatMessage model."""

    def test_creates_basic_message(self):
        msg = ChatMessage(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"
        assert msg.name is None

    def test_creates_message_with_name(self):
        msg = ChatMessage(role="assistant", content="Hi there", name="barnabee")
        assert msg.name == "barnabee"


# ============================================================================
# ChatResponse Tests
# ============================================================================


class TestChatResponse:
    """Tests for ChatResponse model."""

    def test_creates_response(self):
        response = ChatResponse(
            text="Hello!",
            model="gpt-4o",
            provider="openai",
            input_tokens=10,
            output_tokens=5,
            total_tokens=15,
            finish_reason="stop",
            cost_usd=0.0001,
            latency_ms=123.4,
        )
        assert response.text == "Hello!"
        assert response.model == "gpt-4o"
        assert response.provider == "openai"
        assert response.total_tokens == 15

    def test_includes_raw_response(self):
        response = ChatResponse(
            text="Hi",
            model="test",
            provider="test",
            input_tokens=1,
            output_tokens=1,
            total_tokens=2,
            finish_reason="stop",
            cost_usd=0.0,
            latency_ms=1.0,
            raw_response={"custom": "data"},
        )
        assert response.raw_response == {"custom": "data"}


# ============================================================================
# ModelConfig Tests
# ============================================================================


class TestModelConfig:
    """Tests for ModelConfig."""

    def test_default_values(self):
        config = ModelConfig(model="gpt-4o")
        assert config.model == "gpt-4o"
        assert config.temperature == 0.7
        assert config.max_tokens == 1000
        assert config.top_p is None

    def test_custom_values(self):
        config = ModelConfig(
            model="claude-3-sonnet",
            temperature=0.3,
            max_tokens=500,
            top_p=0.9,
        )
        assert config.temperature == 0.3
        assert config.max_tokens == 500
        assert config.top_p == 0.9


# ============================================================================
# AgentModelConfig Tests
# ============================================================================


class TestAgentModelConfig:
    """Tests for AgentModelConfig."""

    def test_has_all_agent_types(self):
        config = AgentModelConfig()
        assert hasattr(config, "meta")
        assert hasattr(config, "instant")
        assert hasattr(config, "action")
        assert hasattr(config, "interaction")
        assert hasattr(config, "memory")

    def test_different_models_per_agent(self):
        config = AgentModelConfig()
        assert config.meta.model != config.interaction.model

    def test_meta_is_cheap_fast(self):
        config = AgentModelConfig()
        assert config.meta.max_tokens < config.interaction.max_tokens

    def test_custom_config(self):
        config = AgentModelConfig(meta=ModelConfig(model="custom-model", temperature=0.1))
        assert config.meta.model == "custom-model"


# ============================================================================
# ProviderConfig Tests
# ============================================================================


class TestProviderConfig:
    """Tests for ProviderConfig."""

    def test_creates_config(self):
        config = ProviderConfig(
            provider=ProviderType.OPENROUTER,
            api_key="test-key",
        )
        assert config.provider == ProviderType.OPENROUTER
        assert config.api_key == "test-key"
        assert config.timeout == 60.0

    def test_azure_config(self):
        config = ProviderConfig(
            provider=ProviderType.AZURE,
            api_key="azure-key",
            api_base="https://my-resource.openai.azure.com",
            api_version="2024-02-15-preview",
            deployment_name="gpt-4o",
        )
        assert config.api_base == "https://my-resource.openai.azure.com"
        assert config.deployment_name == "gpt-4o"


# ============================================================================
# SignalContext Tests
# ============================================================================


class TestSignalContext:
    """Tests for SignalContext."""

    def test_creates_context(self):
        ctx = SignalContext(
            conversation_id="conv-123",
            trace_id="trace-456",
            speaker="thomas",
            room="living_room",
        )
        assert ctx.conversation_id == "conv-123"
        assert ctx.speaker == "thomas"

    def test_default_values(self):
        ctx = SignalContext()
        assert ctx.conversation_id is None
        assert ctx.injected_context == {}
        assert ctx.started_at is not None


# ============================================================================
# Provider Factory Tests
# ============================================================================


class TestProviderFactory:
    """Tests for provider factory functions."""

    def test_get_available_providers(self):
        providers = get_available_providers()
        assert "openrouter" in providers
        assert "openai" in providers
        assert "anthropic" in providers
        assert "azure" in providers
        assert "google" in providers
        assert "huggingface" in providers
        assert "grok" in providers

    def test_create_openrouter_provider(self):
        provider = create_provider("openrouter", api_key="test-key")
        assert provider.provider_type == ProviderType.OPENROUTER
        assert not provider.is_initialized

    def test_create_openai_provider(self):
        provider = create_provider("openai", api_key="test-key")
        assert provider.provider_type == ProviderType.OPENAI

    def test_create_anthropic_provider(self):
        provider = create_provider("anthropic", api_key="test-key")
        assert provider.provider_type == ProviderType.ANTHROPIC

    def test_create_azure_provider(self):
        provider = create_provider(
            "azure",
            api_key="test-key",
            api_base="https://test.openai.azure.com",
        )
        assert provider.provider_type == ProviderType.AZURE

    def test_create_google_provider(self):
        provider = create_provider("google", api_key="test-key")
        assert provider.provider_type == ProviderType.GOOGLE

    def test_create_grok_provider(self):
        provider = create_provider("grok", api_key="test-key")
        assert provider.provider_type == ProviderType.GROK

    def test_create_huggingface_provider(self):
        provider = create_provider("huggingface", api_key="test-key")
        assert provider.provider_type == ProviderType.HUGGINGFACE

    def test_create_with_enum(self):
        provider = create_provider(ProviderType.OPENAI, api_key="test-key")
        assert provider.provider_type == ProviderType.OPENAI

    def test_unknown_provider_raises(self):
        with pytest.raises(ValueError, match="Unknown provider"):
            create_provider("unknown-provider", api_key="test")

    def test_create_with_custom_models(self):
        models = AgentModelConfig(meta=ModelConfig(model="custom-meta", temperature=0.1))
        provider = create_provider("openrouter", api_key="test", models=models)
        config = provider.get_model_config("meta")
        assert config.model == "custom-meta"


class TestProviderFactoryFromConfig:
    """Tests for create_provider_from_config."""

    def test_create_from_dict(self):
        config = {
            "provider": "openrouter",
            "api_key": "test-key",
        }
        provider = create_provider_from_config(config)
        assert provider.provider_type == ProviderType.OPENROUTER

    def test_create_with_models(self):
        config = {
            "provider": "openai",
            "api_key": "test-key",
            "models": {
                "meta": {"model": "gpt-4o-mini", "temperature": 0.1},
            },
        }
        provider = create_provider_from_config(config)
        meta_config = provider.get_model_config("meta")
        assert meta_config.model == "gpt-4o-mini"

    def test_api_key_from_env(self):
        with patch.dict("os.environ", {"OPENAI_API_KEY": "env-key"}):
            config = {"provider": "openai"}
            provider = create_provider_from_config(config)
            assert provider.config.api_key == "env-key"


# ============================================================================
# Provider Protocol Tests
# ============================================================================


class TestLLMProviderProtocol:
    """Tests that providers implement the protocol correctly."""

    def test_openrouter_is_provider(self):
        provider = create_provider("openrouter", api_key="test")
        assert isinstance(provider, LLMProvider)

    def test_openai_is_provider(self):
        provider = create_provider("openai", api_key="test")
        assert isinstance(provider, LLMProvider)

    def test_anthropic_is_provider(self):
        provider = create_provider("anthropic", api_key="test")
        assert isinstance(provider, LLMProvider)


# ============================================================================
# Provider Init/Shutdown Tests
# ============================================================================


class TestProviderLifecycle:
    """Tests for provider initialization and shutdown."""

    @pytest.mark.asyncio
    async def test_init_and_shutdown(self):
        provider = create_provider("openrouter", api_key="test")
        assert not provider.is_initialized

        await provider.init()
        assert provider.is_initialized

        await provider.shutdown()
        assert not provider.is_initialized

    @pytest.mark.asyncio
    async def test_init_is_idempotent(self):
        provider = create_provider("openrouter", api_key="test")
        await provider.init()
        await provider.init()  # Should not fail
        assert provider.is_initialized
        await provider.shutdown()


# ============================================================================
# Model Config Resolution Tests
# ============================================================================


class TestModelConfigResolution:
    """Tests for get_model_config method."""

    def test_returns_correct_config(self):
        provider = create_provider("openrouter", api_key="test")
        meta_config = provider.get_model_config("meta")
        interaction_config = provider.get_model_config("interaction")

        assert meta_config.model != interaction_config.model

    def test_falls_back_to_interaction(self):
        provider = create_provider("openrouter", api_key="test")
        unknown_config = provider.get_model_config("unknown_agent")
        interaction_config = provider.get_model_config("interaction")

        assert unknown_config.model == interaction_config.model


# ============================================================================
# Integration Tests (Mocked)
# ============================================================================


class TestProviderChat:
    """Tests for chat method with mocked HTTP."""

    @pytest.mark.asyncio
    async def test_chat_returns_response(self):
        provider = create_provider("openrouter", api_key="test")

        # Mock the HTTP client
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Hello!"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            "model": "test-model",
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(provider, "_client") as mock_client:
            mock_client.post = AsyncMock(return_value=mock_response)
            provider._initialized = True

            # Mock signal logger at the point of import
            with patch("barnabeenet.services.llm.signals.get_signal_logger") as mock_logger:
                mock_logger.return_value.log = AsyncMock()

                response = await provider.chat(
                    messages=[{"role": "user", "content": "Hi"}],
                    agent_type="meta",
                )

        assert response.text == "Hello!"
        assert response.provider == "openrouter"

    @pytest.mark.asyncio
    async def test_chat_with_signal_context(self):
        provider = create_provider("openrouter", api_key="test")

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Response"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 3},
            "model": "test",
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(provider, "_client") as mock_client:
            mock_client.post = AsyncMock(return_value=mock_response)
            provider._initialized = True

            with patch("barnabeenet.services.llm.signals.get_signal_logger") as mock_logger:
                mock_logger.return_value.log = AsyncMock()

                ctx = SignalContext(
                    conversation_id="conv-123",
                    speaker="thomas",
                )

                response = await provider.chat(
                    messages=[{"role": "user", "content": "Test"}],
                    agent_type="interaction",
                    signal_context=ctx,
                )

        assert response is not None
