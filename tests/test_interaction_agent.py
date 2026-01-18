"""Tests for the Interaction Agent."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from barnabeenet.agents.interaction import (
    InteractionAgent,
    InteractionConfig,
)
from barnabeenet.services.llm.openrouter import ChatResponse


@pytest.fixture
def mock_llm_response() -> ChatResponse:
    """Create a mock LLM response."""
    return ChatResponse(
        text="Hello! How can I help you today?",
        model="anthropic/claude-3.5-sonnet",
        input_tokens=100,
        output_tokens=20,
        total_tokens=120,
        finish_reason="stop",
        cost_usd=0.0005,
        latency_ms=150.0,
    )


@pytest.fixture
def mock_llm_client(mock_llm_response: ChatResponse) -> MagicMock:
    """Create a mock LLM client."""
    client = MagicMock()
    client.chat = AsyncMock(return_value=mock_llm_response)
    client.init = AsyncMock()
    client.shutdown = AsyncMock()
    return client


@pytest.fixture
def agent_config() -> InteractionConfig:
    """Create test configuration."""
    return InteractionConfig(
        max_history_turns=5,
        max_memories=3,
        child_mode_max_words=30,
    )


@pytest.fixture
async def initialized_agent(
    mock_llm_client: MagicMock, agent_config: InteractionConfig
) -> InteractionAgent:
    """Create an initialized InteractionAgent with mock LLM."""
    agent = InteractionAgent(llm_client=mock_llm_client, config=agent_config)
    await agent.init()
    yield agent
    await agent.shutdown()


@pytest.fixture
async def agent_no_llm(agent_config: InteractionConfig) -> InteractionAgent:
    """Create an agent without LLM (fallback mode)."""
    agent = InteractionAgent(llm_client=None, config=agent_config)
    # Don't set API key to ensure fallback mode
    with patch.dict("os.environ", {}, clear=True):
        await agent.init()
    yield agent
    await agent.shutdown()


class TestInteractionAgentInit:
    """Test InteractionAgent initialization."""

    @pytest.mark.asyncio
    async def test_init_with_llm_client(self, mock_llm_client: MagicMock) -> None:
        """Agent initializes with provided LLM client."""
        agent = InteractionAgent(llm_client=mock_llm_client)
        await agent.init()
        assert agent._initialized is True
        await agent.shutdown()

    @pytest.mark.asyncio
    async def test_init_without_llm_logs_warning(self) -> None:
        """Agent logs warning when no LLM available."""
        agent = InteractionAgent(llm_client=None)
        with patch.dict("os.environ", {}, clear=True):
            await agent.init()
        assert agent._llm_client is None
        await agent.shutdown()

    @pytest.mark.asyncio
    async def test_double_init_safe(self, mock_llm_client: MagicMock) -> None:
        """Double initialization is safe."""
        agent = InteractionAgent(llm_client=mock_llm_client)
        await agent.init()
        await agent.init()  # Should be no-op
        assert agent._initialized is True
        await agent.shutdown()

    @pytest.mark.asyncio
    async def test_agent_name(self, initialized_agent: InteractionAgent) -> None:
        """Agent has correct name."""
        assert initialized_agent.name == "interaction"


class TestBasicConversation:
    """Test basic conversation handling."""

    @pytest.mark.asyncio
    async def test_simple_message_returns_response(
        self, initialized_agent: InteractionAgent
    ) -> None:
        """Simple message returns a response."""
        result = await initialized_agent.handle_input("Hello Barnabee", {})
        assert "response" in result
        assert result["agent"] == "interaction"

    @pytest.mark.asyncio
    async def test_response_includes_metadata(self, initialized_agent: InteractionAgent) -> None:
        """Response includes expected metadata."""
        result = await initialized_agent.handle_input("How are you?", {})
        assert "conversation_id" in result
        assert "latency_ms" in result
        assert "used_llm" in result
        assert result["used_llm"] is True

    @pytest.mark.asyncio
    async def test_turn_count_increments(self, initialized_agent: InteractionAgent) -> None:
        """Turn count increments with each message."""
        ctx = {"conversation_id": "test_conv_1"}

        result1 = await initialized_agent.handle_input("First message", ctx)
        assert result1["turn_count"] == 1

        result2 = await initialized_agent.handle_input("Second message", ctx)
        assert result2["turn_count"] == 2

    @pytest.mark.asyncio
    async def test_llm_called_with_correct_agent_type(
        self, initialized_agent: InteractionAgent, mock_llm_client: MagicMock
    ) -> None:
        """LLM is called with 'interaction' agent type."""
        await initialized_agent.handle_input("Test message", {})
        mock_llm_client.chat.assert_called_once()
        call_kwargs = mock_llm_client.chat.call_args.kwargs
        assert call_kwargs["agent_type"] == "interaction"


class TestConversationContext:
    """Test conversation context handling."""

    @pytest.mark.asyncio
    async def test_speaker_passed_to_llm(
        self, initialized_agent: InteractionAgent, mock_llm_client: MagicMock
    ) -> None:
        """Speaker context is passed to LLM."""
        await initialized_agent.handle_input(
            "Hello", {"speaker": "thom", "conversation_id": "ctx_test"}
        )
        call_kwargs = mock_llm_client.chat.call_args.kwargs
        assert call_kwargs["speaker"] == "thom"

    @pytest.mark.asyncio
    async def test_room_passed_to_llm(
        self, initialized_agent: InteractionAgent, mock_llm_client: MagicMock
    ) -> None:
        """Room context is passed to LLM."""
        await initialized_agent.handle_input(
            "Hello", {"room": "living room", "conversation_id": "room_test"}
        )
        call_kwargs = mock_llm_client.chat.call_args.kwargs
        assert call_kwargs["room"] == "living room"

    @pytest.mark.asyncio
    async def test_conversation_persists(self, initialized_agent: InteractionAgent) -> None:
        """Conversation context persists across messages."""
        ctx = {"conversation_id": "persist_test", "speaker": "sarah"}

        await initialized_agent.handle_input("First message", ctx)
        conv = initialized_agent.get_conversation("persist_test")

        assert conv is not None
        assert conv.speaker == "sarah"
        assert len(conv.history) == 2  # User message + assistant response

    @pytest.mark.asyncio
    async def test_retrieved_memories_included(
        self, initialized_agent: InteractionAgent, mock_llm_client: MagicMock
    ) -> None:
        """Retrieved memories are included in context."""
        memories = ["Thom likes coffee in the morning", "Family dinner at 6pm"]
        await initialized_agent.handle_input(
            "What's my schedule?",
            {"retrieved_memories": memories, "conversation_id": "mem_test"},
        )

        # Check that memories appear in the system prompt
        call_args = mock_llm_client.chat.call_args
        messages = call_args.kwargs.get("messages", call_args.args[0] if call_args.args else [])
        system_message = next(
            (m for m in messages if (m.role if hasattr(m, "role") else m.get("role")) == "system"),
            None,
        )
        assert system_message is not None
        system_content = (
            system_message.content
            if hasattr(system_message, "content")
            else system_message.get("content")
        )
        assert "coffee in the morning" in system_content


class TestChildMode:
    """Test child-appropriate responses."""

    @pytest.mark.asyncio
    async def test_child_speaker_enables_child_mode(
        self, initialized_agent: InteractionAgent
    ) -> None:
        """Child speaker automatically enables child mode."""
        result = await initialized_agent.handle_input(
            "Hello!", {"speaker": "penelope", "conversation_id": "child_test"}
        )
        assert result["child_mode"] is True

    @pytest.mark.asyncio
    async def test_children_present_enables_child_mode(
        self, initialized_agent: InteractionAgent
    ) -> None:
        """children_present flag enables child mode."""
        result = await initialized_agent.handle_input(
            "Hello!",
            {"speaker": "thom", "children_present": True, "conversation_id": "kids_test"},
        )
        assert result["child_mode"] is True

    @pytest.mark.asyncio
    async def test_child_mode_mentioned_in_system_prompt(
        self, initialized_agent: InteractionAgent, mock_llm_client: MagicMock
    ) -> None:
        """Child mode adds appropriate instructions to system prompt."""
        await initialized_agent.handle_input(
            "Tell me a story",
            {"speaker": "xander", "conversation_id": "child_prompt_test"},
        )

        call_args = mock_llm_client.chat.call_args
        messages = call_args.kwargs.get("messages", call_args.args[0] if call_args.args else [])
        system_message = next(
            (m for m in messages if (m.role if hasattr(m, "role") else m.get("role")) == "system"),
            None,
        )
        system_content = (
            system_message.content
            if hasattr(system_message, "content")
            else system_message.get("content")
        )
        assert "Child Present" in system_content

    @pytest.mark.asyncio
    async def test_truncate_for_children(self, initialized_agent: InteractionAgent) -> None:
        """Responses are truncated appropriately for children."""
        # Create a long response
        long_response = "This is a very long response. " * 20

        truncated = initialized_agent._truncate_for_children(long_response)

        # Should be shorter than original
        assert len(truncated.split()) <= initialized_agent.config.child_mode_max_words + 5


class TestFallbackMode:
    """Test fallback responses when LLM unavailable."""

    @pytest.mark.asyncio
    async def test_fallback_on_greeting(self, agent_no_llm: InteractionAgent) -> None:
        """Fallback handles greetings."""
        result = await agent_no_llm.handle_input("Hello!", {})
        assert "Hello" in result["response"]
        assert result["used_llm"] is False

    @pytest.mark.asyncio
    async def test_fallback_on_thanks(self, agent_no_llm: InteractionAgent) -> None:
        """Fallback handles thank you."""
        result = await agent_no_llm.handle_input("Thank you so much!", {})
        assert "welcome" in result["response"].lower()

    @pytest.mark.asyncio
    async def test_fallback_on_how_are_you(self, agent_no_llm: InteractionAgent) -> None:
        """Fallback handles how are you."""
        result = await agent_no_llm.handle_input("How are you today?", {})
        assert "well" in result["response"].lower() or "doing" in result["response"].lower()

    @pytest.mark.asyncio
    async def test_fallback_on_goodbye(self, agent_no_llm: InteractionAgent) -> None:
        """Fallback handles goodbye."""
        result = await agent_no_llm.handle_input("Goodbye!", {})
        assert "bye" in result["response"].lower() or "day" in result["response"].lower()

    @pytest.mark.asyncio
    async def test_fallback_on_question(self, agent_no_llm: InteractionAgent) -> None:
        """Fallback handles unknown questions gracefully."""
        result = await agent_no_llm.handle_input("What's the weather like?", {})
        assert "response" in result
        assert "apologize" in result["response"].lower() or "trouble" in result["response"].lower()

    @pytest.mark.asyncio
    async def test_fallback_uses_speaker_name(self, agent_no_llm: InteractionAgent) -> None:
        """Fallback uses speaker name when available."""
        result = await agent_no_llm.handle_input(
            "Hello!", {"speaker": "thom", "conversation_id": "name_test"}
        )
        assert "Thom" in result["response"]


class TestConversationManagement:
    """Test conversation lifecycle management."""

    @pytest.mark.asyncio
    async def test_get_conversation_returns_none_for_unknown(
        self, initialized_agent: InteractionAgent
    ) -> None:
        """get_conversation returns None for unknown ID."""
        conv = initialized_agent.get_conversation("nonexistent")
        assert conv is None

    @pytest.mark.asyncio
    async def test_clear_conversation(self, initialized_agent: InteractionAgent) -> None:
        """clear_conversation removes conversation."""
        ctx = {"conversation_id": "clear_test"}
        await initialized_agent.handle_input("Hello", ctx)

        assert initialized_agent.get_conversation("clear_test") is not None
        result = initialized_agent.clear_conversation("clear_test")
        assert result is True
        assert initialized_agent.get_conversation("clear_test") is None

    @pytest.mark.asyncio
    async def test_clear_nonexistent_returns_false(
        self, initialized_agent: InteractionAgent
    ) -> None:
        """clear_conversation returns False for nonexistent conversation."""
        result = initialized_agent.clear_conversation("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_get_active_conversations(self, initialized_agent: InteractionAgent) -> None:
        """get_active_conversations returns list of IDs."""
        await initialized_agent.handle_input("Hello", {"conversation_id": "active_1"})
        await initialized_agent.handle_input("Hi", {"conversation_id": "active_2"})

        active = initialized_agent.get_active_conversations()
        assert "active_1" in active
        assert "active_2" in active


class TestHistoryManagement:
    """Test conversation history handling."""

    @pytest.mark.asyncio
    async def test_history_trimmed_when_exceeds_max(
        self, initialized_agent: InteractionAgent
    ) -> None:
        """History is trimmed when it exceeds max turns."""
        ctx = {"conversation_id": "history_trim_test"}

        # Send more messages than max_history_turns * 2
        for i in range(15):
            await initialized_agent.handle_input(f"Message {i}", ctx)

        conv = initialized_agent.get_conversation("history_trim_test")
        # Should be trimmed to max_history_turns * 2 (config is 5, so max 10)
        assert len(conv.history) <= initialized_agent.config.max_history_turns * 2


class TestSystemPrompt:
    """Test system prompt construction."""

    @pytest.mark.asyncio
    async def test_persona_in_system_prompt(
        self, initialized_agent: InteractionAgent, mock_llm_client: MagicMock
    ) -> None:
        """Barnabee persona is included in system prompt."""
        await initialized_agent.handle_input("Hello", {})

        call_args = mock_llm_client.chat.call_args
        messages = call_args.kwargs.get("messages", call_args.args[0] if call_args.args else [])
        system_message = next(
            (m for m in messages if (m.role if hasattr(m, "role") else m.get("role")) == "system"),
            None,
        )
        system_content = (
            system_message.content
            if hasattr(system_message, "content")
            else system_message.get("content")
        )
        assert "Barnabee" in system_content

    @pytest.mark.asyncio
    async def test_time_context_in_prompt(
        self, initialized_agent: InteractionAgent, mock_llm_client: MagicMock
    ) -> None:
        """Time of day context is included."""
        await initialized_agent.handle_input(
            "Hello", {"time_of_day": "morning", "conversation_id": "time_test"}
        )

        call_args = mock_llm_client.chat.call_args
        messages = call_args.kwargs.get("messages", call_args.args[0] if call_args.args else [])
        system_message = next(
            (m for m in messages if (m.role if hasattr(m, "role") else m.get("role")) == "system"),
            None,
        )
        system_content = (
            system_message.content
            if hasattr(system_message, "content")
            else system_message.get("content")
        )
        assert "morning" in system_content

    @pytest.mark.asyncio
    async def test_emotional_tone_in_prompt(
        self, initialized_agent: InteractionAgent, mock_llm_client: MagicMock
    ) -> None:
        """Emotional tone from meta context affects prompt."""
        await initialized_agent.handle_input(
            "I'm having a bad day",
            {
                "meta_context": {"emotional_tone": "stressed"},
                "conversation_id": "emotion_test",
            },
        )

        call_args = mock_llm_client.chat.call_args
        messages = call_args.kwargs.get("messages", call_args.args[0] if call_args.args else [])
        system_message = next(
            (m for m in messages if (m.role if hasattr(m, "role") else m.get("role")) == "system"),
            None,
        )
        system_content = (
            system_message.content
            if hasattr(system_message, "content")
            else system_message.get("content")
        )
        assert "stressed" in system_content
        assert "empathy" in system_content.lower()


class TestLLMErrorHandling:
    """Test error handling when LLM fails."""

    @pytest.mark.asyncio
    async def test_llm_error_falls_back(
        self, initialized_agent: InteractionAgent, mock_llm_client: MagicMock
    ) -> None:
        """LLM error falls back to fallback response."""
        mock_llm_client.chat.side_effect = Exception("API error")

        result = await initialized_agent.handle_input("Hello", {})

        # Should still return a response (fallback)
        assert "response" in result
        assert len(result["response"]) > 0


class TestFamilyNameFormatting:
    """Test family member name formatting."""

    @pytest.mark.asyncio
    async def test_known_family_members_formatted(
        self, initialized_agent: InteractionAgent
    ) -> None:
        """Known family members are formatted correctly."""
        names = {
            "thom": "Thom (Dad)",
            "sarah": "Sarah (Mom)",
            "penelope": "Penelope",
            "xander": "Xander",
            "zachary": "Zachary",
            "viola": "Viola",
        }
        for speaker_id, expected in names.items():
            formatted = initialized_agent._format_speaker_name(speaker_id)
            assert formatted == expected

    @pytest.mark.asyncio
    async def test_unknown_name_titlecased(self, initialized_agent: InteractionAgent) -> None:
        """Unknown names are titlecased."""
        formatted = initialized_agent._format_speaker_name("guest_user")
        assert formatted == "Guest_User"


class TestExportedSymbols:
    """Test module exports."""

    def test_all_exports(self) -> None:
        """All expected symbols are exported."""
        from barnabeenet.agents import interaction

        assert hasattr(interaction, "InteractionAgent")
        assert hasattr(interaction, "InteractionConfig")
        assert hasattr(interaction, "ConversationContext")
        assert hasattr(interaction, "ConversationTurn")
        assert hasattr(interaction, "BARNABEE_PERSONA")
