"""Tests for OpenRouter client and signal logging."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from barnabeenet.services.llm.openrouter import (
    AgentModelConfig,
    ChatMessage,
    ChatResponse,
    ModelConfig,
    OpenRouterClient,
)
from barnabeenet.services.llm.signals import LLMSignal, SignalLogger


class TestLLMSignal:
    """Tests for LLMSignal model."""

    def test_signal_creation(self) -> None:
        """Test basic signal creation."""
        signal = LLMSignal(
            agent_type="interaction",
            model="anthropic/claude-3.5-sonnet",
            user_input="Hello Barnabee",
        )
        assert signal.agent_type == "interaction"
        assert signal.model == "anthropic/claude-3.5-sonnet"
        assert signal.user_input == "Hello Barnabee"
        assert signal.signal_id is not None
        assert signal.timestamp is not None
        assert signal.success is False  # Default until marked successful

    def test_signal_latency_calculation(self) -> None:
        """Test latency calculation from timestamps."""
        signal = LLMSignal(
            agent_type="meta",
            model="deepseek/deepseek-chat",
            started_at=datetime(2026, 1, 17, 10, 0, 0, tzinfo=UTC),
            completed_at=datetime(2026, 1, 17, 10, 0, 0, 500000, tzinfo=UTC),
        )
        signal.calculate_latency()
        assert signal.latency_ms == 500.0

    def test_signal_serialization(self) -> None:
        """Test signal JSON serialization."""
        signal = LLMSignal(
            agent_type="action",
            model="openai/gpt-4o-mini",
            user_input="Turn on the lights",
            input_tokens=100,
            output_tokens=50,
            cost_usd=0.0001,
            success=True,
        )
        json_str = signal.model_dump_json()
        data = json.loads(json_str)
        assert data["agent_type"] == "action"
        assert data["input_tokens"] == 100
        assert data["cost_usd"] == 0.0001

    def test_signal_with_context(self) -> None:
        """Test signal with injected context."""
        signal = LLMSignal(
            agent_type="interaction",
            model="anthropic/claude-3.5-sonnet",
            injected_context={
                "home_state": {"temperature": 72},
                "speaker_profile": {"name": "Thom"},
                "memories": ["Thom prefers 68°F"],
            },
        )
        assert "home_state" in signal.injected_context
        assert signal.injected_context["speaker_profile"]["name"] == "Thom"


class TestSignalLogger:
    """Tests for SignalLogger."""

    @pytest.fixture
    def logger(self) -> SignalLogger:
        """Create a signal logger without Redis (fallback mode)."""
        return SignalLogger(redis_client=None)

    @pytest.mark.asyncio
    async def test_log_signal_fallback(self, logger: SignalLogger) -> None:
        """Test logging without Redis uses in-memory fallback."""
        signal = LLMSignal(
            agent_type="instant",
            model="deepseek/deepseek-chat",
            user_input="What time is it?",
            input_tokens=50,
            output_tokens=20,
            success=True,
        )
        await logger.log_signal(signal)
        assert len(logger._fallback_logs) == 1
        assert logger._fallback_logs[0].signal_id == signal.signal_id

    @pytest.mark.asyncio
    async def test_get_signal_fallback(self, logger: SignalLogger) -> None:
        """Test retrieving signal from fallback storage."""
        signal = LLMSignal(
            agent_type="meta",
            model="deepseek/deepseek-chat",
        )
        await logger.log_signal(signal)
        retrieved = await logger.get_signal(signal.signal_id)
        assert retrieved is not None
        assert retrieved.signal_id == signal.signal_id

    @pytest.mark.asyncio
    async def test_get_recent_signals(self, logger: SignalLogger) -> None:
        """Test getting recent signals."""
        for i in range(5):
            signal = LLMSignal(
                agent_type="interaction" if i % 2 == 0 else "instant",
                model="test-model",
                user_input=f"Test {i}",
            )
            await logger.log_signal(signal)

        all_signals = await logger.get_recent_signals(count=10)
        assert len(all_signals) == 5

        # Filter by agent type
        interaction_signals = await logger.get_recent_signals(count=10, agent_type="interaction")
        assert len(interaction_signals) == 3

    @pytest.mark.asyncio
    async def test_fallback_log_limit(self, logger: SignalLogger) -> None:
        """Test that fallback log is limited to 1000 entries."""
        for _ in range(1100):
            signal = LLMSignal(agent_type="meta", model="test")
            await logger.log_signal(signal)

        assert len(logger._fallback_logs) == 1000

    @pytest.mark.asyncio
    async def test_log_signal_with_redis(self) -> None:
        """Test logging with Redis client."""
        mock_redis = AsyncMock()
        logger = SignalLogger(redis_client=mock_redis)

        signal = LLMSignal(
            agent_type="action",
            model="openai/gpt-4o-mini",
            input_tokens=100,
            output_tokens=50,
            success=True,
        )
        await logger.log_signal(signal)

        # Should call setex for full signal and xadd for stream
        mock_redis.setex.assert_called_once()
        mock_redis.xadd.assert_called_once()


class TestModelConfig:
    """Tests for model configuration."""

    def test_default_config(self) -> None:
        """Test default model configuration."""
        config = ModelConfig(model="test/model")
        assert config.temperature == 0.7
        assert config.max_tokens == 1000
        assert config.top_p is None

    def test_agent_model_config(self) -> None:
        """Test agent-specific model configurations."""
        config = AgentModelConfig()

        # Meta should be fast/cheap
        assert config.meta.model == "deepseek/deepseek-chat"
        assert config.meta.temperature == 0.3
        assert config.meta.max_tokens == 200

        # Interaction should be high quality
        assert config.interaction.model == "anthropic/claude-3.5-sonnet"
        assert config.interaction.temperature == 0.7
        assert config.interaction.max_tokens == 1500


class TestOpenRouterClient:
    """Tests for OpenRouterClient."""

    @pytest.fixture
    def client(self) -> OpenRouterClient:
        """Create an OpenRouter client with test API key."""
        return OpenRouterClient(api_key="test-api-key")

    def test_client_initialization(self, client: OpenRouterClient) -> None:
        """Test client initialization."""
        assert client.api_key == "test-api-key"
        assert client.model_config is not None
        assert client._client is None  # Not initialized until first call

    def test_get_model_config(self, client: OpenRouterClient) -> None:
        """Test getting model config for agent type."""
        meta_config = client._get_model_config("meta")
        assert meta_config.model == "deepseek/deepseek-chat"

        interaction_config = client._get_model_config("interaction")
        assert interaction_config.model == "anthropic/claude-3.5-sonnet"

        # Unknown agent type falls back to interaction
        unknown_config = client._get_model_config("unknown")
        assert unknown_config.model == "anthropic/claude-3.5-sonnet"

    def test_estimate_cost(self, client: OpenRouterClient) -> None:
        """Test cost estimation."""
        # Claude 3.5 Sonnet: $3/M input, $15/M output
        cost = client._estimate_cost(
            "anthropic/claude-3.5-sonnet",
            input_tokens=1000,
            output_tokens=500,
        )
        expected = (1000 / 1_000_000 * 3.0) + (500 / 1_000_000 * 15.0)
        assert cost == pytest.approx(expected)

        # DeepSeek: $0.14/M input, $0.28/M output
        cost = client._estimate_cost(
            "deepseek/deepseek-chat",
            input_tokens=1000,
            output_tokens=500,
        )
        expected = (1000 / 1_000_000 * 0.14) + (500 / 1_000_000 * 0.28)
        assert cost == pytest.approx(expected)

    @pytest.mark.asyncio
    async def test_chat_success(self, client: OpenRouterClient) -> None:
        """Test successful chat completion."""
        mock_response = {
            "choices": [
                {
                    "message": {"content": "Hello! How can I help you?"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 50,
                "completion_tokens": 10,
                "total_tokens": 60,
            },
            "model": "anthropic/claude-3.5-sonnet",
        }

        with patch.object(client, "_client") as mock_client:
            mock_client.post = AsyncMock(
                return_value=MagicMock(
                    json=lambda: mock_response,
                    raise_for_status=lambda: None,
                )
            )

            response = await client.chat(
                messages=[{"role": "user", "content": "Hello"}],
                agent_type="interaction",
                user_input="Hello",
            )

            assert isinstance(response, ChatResponse)
            assert response.text == "Hello! How can I help you?"
            assert response.input_tokens == 50
            assert response.output_tokens == 10
            assert response.finish_reason == "stop"

    @pytest.mark.asyncio
    async def test_chat_with_messages(self, client: OpenRouterClient) -> None:
        """Test chat with ChatMessage objects."""
        mock_response = {
            "choices": [
                {
                    "message": {"content": "I understand."},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 100, "completion_tokens": 20},
        }

        with patch.object(client, "_client") as mock_client:
            mock_client.post = AsyncMock(
                return_value=MagicMock(
                    json=lambda: mock_response,
                    raise_for_status=lambda: None,
                )
            )

            messages = [
                ChatMessage(role="system", content="You are Barnabee"),
                ChatMessage(role="user", content="Hello"),
            ]

            response = await client.chat(messages, agent_type="interaction")
            assert response.text == "I understand."

    @pytest.mark.asyncio
    async def test_simple_chat(self, client: OpenRouterClient) -> None:
        """Test simple_chat convenience method."""
        mock_response = {
            "choices": [
                {
                    "message": {"content": "It's 72°F and sunny."},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 80, "completion_tokens": 15},
        }

        with patch.object(client, "_client") as mock_client:
            mock_client.post = AsyncMock(
                return_value=MagicMock(
                    json=lambda: mock_response,
                    raise_for_status=lambda: None,
                )
            )

            text = await client.simple_chat(
                "What's the weather?",
                system_prompt="You are a helpful assistant.",
                agent_type="instant",
            )

            assert text == "It's 72°F and sunny."

    @pytest.mark.asyncio
    async def test_init_and_shutdown(self, client: OpenRouterClient) -> None:
        """Test client lifecycle."""
        await client.init()
        assert client._client is not None

        await client.shutdown()
        assert client._client is None


class TestChatMessage:
    """Tests for ChatMessage model."""

    def test_chat_message(self) -> None:
        """Test ChatMessage creation."""
        msg = ChatMessage(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"


class TestChatResponse:
    """Tests for ChatResponse model."""

    def test_chat_response(self) -> None:
        """Test ChatResponse creation."""
        response = ChatResponse(
            text="Hello there!",
            model="test/model",
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
            finish_reason="stop",
            cost_usd=0.001,
            latency_ms=250.0,
        )
        assert response.text == "Hello there!"
        assert response.total_tokens == 150
        assert response.cost_usd == 0.001
