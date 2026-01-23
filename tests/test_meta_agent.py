"""Tests for MetaAgent - intent classification and context evaluation."""

from __future__ import annotations

import pytest

from barnabeenet.agents.meta import (
    EmotionalTone,
    IntentCategory,
    MetaAgent,
    MetaAgentConfig,
    UrgencyLevel,
)


@pytest.fixture
def meta_agent() -> MetaAgent:
    """Create a MetaAgent for testing with hardcoded patterns (no registry)."""
    # Pass logic_registry=None to use hardcoded patterns instead of LogicRegistry
    # This ensures tests run consistently without depending on config files
    agent = MetaAgent(logic_registry=None)
    agent._use_registry = False  # Force hardcoded patterns
    return agent


@pytest.fixture
async def initialized_agent(meta_agent: MetaAgent) -> MetaAgent:
    """Create an initialized MetaAgent with hardcoded patterns."""
    # Temporarily set _logic_registry to prevent init() from loading registry
    meta_agent._logic_registry = None
    await meta_agent.init()
    return meta_agent


# =============================================================================
# Intent Classification Tests - Pattern Matching
# =============================================================================


class TestPatternMatching:
    """Test pattern-based intent classification."""

    @pytest.mark.asyncio
    async def test_time_query_classified_as_instant(self, initialized_agent: MetaAgent) -> None:
        """Time queries should be classified as instant intent."""
        result = await initialized_agent.classify("what time is it")
        assert result.intent == IntentCategory.INSTANT
        assert result.sub_category == "time"
        assert result.confidence >= 0.9

    @pytest.mark.asyncio
    async def test_date_query_classified_as_instant(self, initialized_agent: MetaAgent) -> None:
        """Date queries should be classified as instant intent."""
        result = await initialized_agent.classify("what's the date")
        assert result.intent == IntentCategory.INSTANT
        assert result.sub_category == "date"

    @pytest.mark.asyncio
    async def test_greeting_classified_as_instant(self, initialized_agent: MetaAgent) -> None:
        """Greetings should be classified as instant intent."""
        greetings = ["hello", "hey", "hi", "good morning", "good evening"]
        for greeting in greetings:
            result = await initialized_agent.classify(greeting)
            assert result.intent == IntentCategory.INSTANT, f"Failed for: {greeting}"
            assert result.sub_category == "greeting"

    @pytest.mark.asyncio
    async def test_math_classified_as_instant(self, initialized_agent: MetaAgent) -> None:
        """Simple math should be classified as instant intent."""
        result = await initialized_agent.classify("what's 5 + 3")
        assert result.intent == IntentCategory.INSTANT
        assert result.sub_category == "math"

    @pytest.mark.asyncio
    async def test_turn_on_classified_as_action(self, initialized_agent: MetaAgent) -> None:
        """Device control commands should be classified as action intent."""
        result = await initialized_agent.classify("turn on the lights")
        assert result.intent == IntentCategory.ACTION
        assert result.sub_category == "switch"

    @pytest.mark.asyncio
    async def test_set_temperature_classified_as_action(self, initialized_agent: MetaAgent) -> None:
        """Set commands should be classified as action intent."""
        result = await initialized_agent.classify("set temperature to 72")
        assert result.intent == IntentCategory.ACTION
        assert result.sub_category == "set"

    @pytest.mark.asyncio
    async def test_lock_door_classified_as_action(self, initialized_agent: MetaAgent) -> None:
        """Lock commands should be classified as action intent."""
        result = await initialized_agent.classify("lock the front door")
        assert result.intent == IntentCategory.ACTION
        assert result.sub_category == "lock"

    @pytest.mark.asyncio
    async def test_play_media_classified_as_action(self, initialized_agent: MetaAgent) -> None:
        """Media commands should be classified as action intent."""
        result = await initialized_agent.classify("play some music")
        assert result.intent == IntentCategory.ACTION
        assert result.sub_category == "media"

    @pytest.mark.asyncio
    async def test_remember_classified_as_memory(self, initialized_agent: MetaAgent) -> None:
        """Remember commands should be classified as memory intent."""
        result = await initialized_agent.classify("remember that I like pizza")
        assert result.intent == IntentCategory.MEMORY
        assert result.sub_category == "store"

    @pytest.mark.asyncio
    async def test_recall_classified_as_memory(self, initialized_agent: MetaAgent) -> None:
        """Recall queries should be classified as memory intent."""
        result = await initialized_agent.classify("do you remember my birthday")
        assert result.intent == IntentCategory.MEMORY
        assert result.sub_category == "recall"

    @pytest.mark.asyncio
    async def test_emergency_fire_detected(self, initialized_agent: MetaAgent) -> None:
        """Fire emergency should be detected."""
        result = await initialized_agent.classify("there's smoke in the kitchen")
        assert result.intent == IntentCategory.EMERGENCY
        assert result.sub_category == "fire"

    @pytest.mark.asyncio
    async def test_emergency_medical_detected(self, initialized_agent: MetaAgent) -> None:
        """Medical emergency should be detected."""
        result = await initialized_agent.classify("grandma has fallen and can't get up")
        assert result.intent == IntentCategory.EMERGENCY
        assert result.sub_category == "medical"

    @pytest.mark.asyncio
    async def test_gesture_classified(self, initialized_agent: MetaAgent) -> None:
        """Gesture inputs should be classified correctly."""
        result = await initialized_agent.classify("crown_twist_yes")
        assert result.intent == IntentCategory.GESTURE
        assert result.sub_category == "choice"


# =============================================================================
# Intent Classification Tests - Heuristic
# =============================================================================


class TestHeuristicClassification:
    """Test heuristic-based intent classification."""

    @pytest.mark.asyncio
    async def test_question_classified_as_query(self, initialized_agent: MetaAgent) -> None:
        """Questions should be classified as query intent."""
        result = await initialized_agent.classify("What is the meaning of life?")
        assert result.intent == IntentCategory.QUERY

    @pytest.mark.asyncio
    async def test_how_question_classified_as_query(self, initialized_agent: MetaAgent) -> None:
        """How questions should be classified as query intent."""
        result = await initialized_agent.classify("how do I make pasta?")
        assert result.intent == IntentCategory.QUERY

    @pytest.mark.asyncio
    async def test_conversation_continuation(self, initialized_agent: MetaAgent) -> None:
        """Requests with history should be classified as conversation."""
        context = {"history": [{"role": "user", "content": "hello"}]}
        result = await initialized_agent.classify("tell me more", context)
        assert result.intent == IntentCategory.CONVERSATION

    @pytest.mark.asyncio
    async def test_general_statement_is_conversation(self, initialized_agent: MetaAgent) -> None:
        """General statements should default to conversation."""
        result = await initialized_agent.classify("I had a great day today")
        assert result.intent == IntentCategory.CONVERSATION


# =============================================================================
# Context Evaluation Tests
# =============================================================================


class TestContextEvaluation:
    """Test context and mood evaluation."""

    @pytest.mark.asyncio
    async def test_urgency_detection(self, initialized_agent: MetaAgent) -> None:
        """Urgent keywords should be detected."""
        result = await initialized_agent.classify("I need this immediately please")
        assert result.context is not None
        assert result.context.urgency_level in (UrgencyLevel.HIGH, UrgencyLevel.MEDIUM)

    @pytest.mark.asyncio
    async def test_stress_indicator_detection(self, initialized_agent: MetaAgent) -> None:
        """Stress indicators should be detected."""
        result = await initialized_agent.classify("I'm so frustrated with this")
        assert result.context is not None
        assert len(result.context.stress_indicators) > 0
        assert result.context.emotional_tone == EmotionalTone.STRESSED
        assert result.context.empathy_needed is True

    @pytest.mark.asyncio
    async def test_positive_tone_detection(self, initialized_agent: MetaAgent) -> None:
        """Positive emotional tone should be detected."""
        result = await initialized_agent.classify("thank you so much, that was great!")
        assert result.context is not None
        assert result.context.emotional_tone == EmotionalTone.POSITIVE

    @pytest.mark.asyncio
    async def test_negative_tone_detection(self, initialized_agent: MetaAgent) -> None:
        """Negative emotional tone should be detected."""
        result = await initialized_agent.classify("that's wrong and annoying")
        assert result.context is not None
        assert result.context.emotional_tone == EmotionalTone.NEGATIVE

    @pytest.mark.asyncio
    async def test_confused_tone_detection(self, initialized_agent: MetaAgent) -> None:
        """Confused tone should be detected for certain questions."""
        result = await initialized_agent.classify("what? I'm confused, how does this work?")
        assert result.context is not None
        assert result.context.emotional_tone == EmotionalTone.CONFUSED

    @pytest.mark.asyncio
    async def test_suggested_response_tone(self, initialized_agent: MetaAgent) -> None:
        """Stressed input should suggest calm supportive tone."""
        result = await initialized_agent.classify("I'm so stressed about this")
        assert result.context is not None
        assert result.context.suggested_response_tone == "calm_supportive"

    @pytest.mark.asyncio
    async def test_emergency_urgency_level(self, initialized_agent: MetaAgent) -> None:
        """Emergency should set urgency to EMERGENCY."""
        result = await initialized_agent.classify("help! there's a fire!")
        assert result.context is not None
        assert result.context.urgency_level == UrgencyLevel.EMERGENCY


# =============================================================================
# Memory Query Generation Tests
# =============================================================================


class TestMemoryQueryGeneration:
    """Test memory query generation."""

    @pytest.mark.asyncio
    async def test_memory_queries_generated_for_conversation(
        self, initialized_agent: MetaAgent
    ) -> None:
        """Memory queries should be generated for conversation intents."""
        result = await initialized_agent.classify("tell me about the family vacation")
        assert result.memory_queries is not None
        assert result.memory_queries.primary_query == "tell me about the family vacation"
        assert len(result.memory_queries.topic_tags) > 0

    @pytest.mark.asyncio
    async def test_no_memory_queries_for_instant(self, initialized_agent: MetaAgent) -> None:
        """Memory queries should NOT be generated for instant intents."""
        result = await initialized_agent.classify("what time is it")
        assert result.memory_queries is None

    @pytest.mark.asyncio
    async def test_time_context_extraction(self, initialized_agent: MetaAgent) -> None:
        """Time context should be extracted from text."""
        result = await initialized_agent.classify("what happened yesterday?")
        assert result.memory_queries is not None
        assert result.memory_queries.time_context == "last_day"

    @pytest.mark.asyncio
    async def test_speaker_added_to_relevant_people(self, initialized_agent: MetaAgent) -> None:
        """Speaker should be added to relevant people."""
        context = {"speaker": "Thom"}
        result = await initialized_agent.classify("tell me about dinner plans", context)
        assert result.memory_queries is not None
        assert "Thom" in result.memory_queries.relevant_people


# =============================================================================
# Routing Tests
# =============================================================================


class TestRouting:
    """Test intent to agent routing."""

    @pytest.mark.asyncio
    async def test_instant_routes_to_instant_agent(self, initialized_agent: MetaAgent) -> None:
        """Instant intents should route to instant agent."""
        result = await initialized_agent.classify("what time is it")
        assert result.target_agent == "instant"

    @pytest.mark.asyncio
    async def test_action_routes_to_action_agent(self, initialized_agent: MetaAgent) -> None:
        """Action intents should route to action agent."""
        result = await initialized_agent.classify("turn on the lights")
        assert result.target_agent == "action"

    @pytest.mark.asyncio
    async def test_conversation_routes_to_interaction_agent(
        self, initialized_agent: MetaAgent
    ) -> None:
        """Conversation intents should route to interaction agent."""
        result = await initialized_agent.classify("tell me a story")
        assert result.target_agent == "interaction"

    @pytest.mark.asyncio
    async def test_memory_routes_to_memory_agent(self, initialized_agent: MetaAgent) -> None:
        """Memory intents should route to memory agent."""
        result = await initialized_agent.classify("remember that I like pizza")
        assert result.target_agent == "memory"

    @pytest.mark.asyncio
    async def test_emergency_routes_to_action_agent(self, initialized_agent: MetaAgent) -> None:
        """Emergency intents should route to action agent for immediate response."""
        result = await initialized_agent.classify("there's smoke in the house")
        assert result.target_agent == "action"


# =============================================================================
# Priority Tests
# =============================================================================


class TestPriority:
    """Test priority calculation."""

    @pytest.mark.asyncio
    async def test_emergency_has_highest_priority(self, initialized_agent: MetaAgent) -> None:
        """Emergency intents should have highest priority."""
        result = await initialized_agent.classify("fire in the kitchen!")
        assert result.priority == 10

    @pytest.mark.asyncio
    async def test_action_has_high_priority(self, initialized_agent: MetaAgent) -> None:
        """Action intents should have high priority."""
        result = await initialized_agent.classify("turn on the lights")
        assert result.priority >= 7

    @pytest.mark.asyncio
    async def test_conversation_has_lower_priority(self, initialized_agent: MetaAgent) -> None:
        """Conversation intents should have lower priority."""
        result = await initialized_agent.classify("tell me about your day")
        assert result.priority <= 5

    @pytest.mark.asyncio
    async def test_urgency_boosts_priority(self, initialized_agent: MetaAgent) -> None:
        """Urgency should boost priority."""
        # Use queries that don't trigger emergency patterns
        normal_result = await initialized_agent.classify("can you assist me with dinner")
        urgent_result = await initialized_agent.classify("can you assist me now immediately asap!")
        assert urgent_result.priority > normal_result.priority


# =============================================================================
# handle_input Tests
# =============================================================================


class TestHandleInput:
    """Test the Agent interface handle_input method."""

    @pytest.mark.asyncio
    async def test_handle_input_returns_dict(self, initialized_agent: MetaAgent) -> None:
        """handle_input should return a dictionary."""
        result = await initialized_agent.handle_input("hello")
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_handle_input_contains_intent(self, initialized_agent: MetaAgent) -> None:
        """handle_input result should contain intent."""
        result = await initialized_agent.handle_input("turn on the lights")
        assert "intent" in result
        assert result["intent"] == "action"

    @pytest.mark.asyncio
    async def test_handle_input_contains_target_agent(self, initialized_agent: MetaAgent) -> None:
        """handle_input result should contain target agent."""
        result = await initialized_agent.handle_input("what time is it")
        assert "target_agent" in result
        assert result["target_agent"] == "instant"

    @pytest.mark.asyncio
    async def test_handle_input_contains_processing_time(
        self, initialized_agent: MetaAgent
    ) -> None:
        """handle_input result should contain processing time."""
        result = await initialized_agent.handle_input("hello")
        assert "processing_time_ms" in result
        assert isinstance(result["processing_time_ms"], int)


# =============================================================================
# Configuration Tests
# =============================================================================


class TestConfiguration:
    """Test MetaAgent configuration."""

    @pytest.mark.asyncio
    async def test_custom_config_urgency_keywords(self) -> None:
        """Custom urgency keywords should be used."""
        config = MetaAgentConfig(urgency_keywords=["custom_urgent"])
        agent = MetaAgent(config=config)
        await agent.init()

        result = await agent.classify("this is custom_urgent")
        assert result.context is not None
        assert result.context.urgency_level in (UrgencyLevel.HIGH, UrgencyLevel.MEDIUM)

    @pytest.mark.asyncio
    async def test_disabled_context_evaluation(self) -> None:
        """Context evaluation can be disabled."""
        config = MetaAgentConfig(context_evaluation_enabled=False)
        agent = MetaAgent(config=config)
        await agent.init()

        result = await agent.classify("I'm frustrated")
        assert result.context is None

    @pytest.mark.asyncio
    async def test_disabled_memory_query_generation(self) -> None:
        """Memory query generation can be disabled."""
        config = MetaAgentConfig(memory_query_generation_enabled=False)
        agent = MetaAgent(config=config)
        await agent.init()

        result = await agent.classify("tell me about vacation")
        assert result.memory_queries is None


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_empty_input(self, initialized_agent: MetaAgent) -> None:
        """Empty input should not crash."""
        result = await initialized_agent.classify("")
        assert result.intent == IntentCategory.CONVERSATION

    @pytest.mark.asyncio
    async def test_whitespace_only_input(self, initialized_agent: MetaAgent) -> None:
        """Whitespace-only input should not crash."""
        result = await initialized_agent.classify("   ")
        assert result.intent is not None

    @pytest.mark.asyncio
    async def test_very_long_input(self, initialized_agent: MetaAgent) -> None:
        """Very long input should not crash."""
        long_text = "tell me about " * 100 + "something"
        result = await initialized_agent.classify(long_text)
        assert result.intent is not None

    @pytest.mark.asyncio
    async def test_special_characters(self, initialized_agent: MetaAgent) -> None:
        """Special characters should not crash."""
        result = await initialized_agent.classify("!@#$%^&*()")
        assert result.intent is not None

    @pytest.mark.asyncio
    async def test_unicode_input(self, initialized_agent: MetaAgent) -> None:
        """Unicode input should not crash."""
        result = await initialized_agent.classify("こんにちは 🎉")
        assert result.intent is not None

    @pytest.mark.asyncio
    async def test_uninitialized_agent(self, meta_agent: MetaAgent) -> None:
        """Uninitialized agent should handle requests gracefully."""
        # Pattern matching won't work without init, but should not crash
        result = await meta_agent.classify("some text")
        assert result.intent is not None


# =============================================================================
# Shutdown Tests
# =============================================================================


class TestShutdown:
    """Test agent shutdown."""

    @pytest.mark.asyncio
    async def test_shutdown_clears_patterns(self, initialized_agent: MetaAgent) -> None:
        """Shutdown should clear compiled patterns."""
        await initialized_agent.shutdown()
        assert len(initialized_agent._compiled_patterns) == 0

    @pytest.mark.asyncio
    async def test_reinitialize_after_shutdown(self, initialized_agent: MetaAgent) -> None:
        """Agent should be able to reinitialize after shutdown."""
        await initialized_agent.shutdown()
        await initialized_agent.init()
        result = await initialized_agent.classify("what time is it")
        assert result.intent == IntentCategory.INSTANT
