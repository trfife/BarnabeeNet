"""Tests for AgentOrchestrator - the full request pipeline."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from barnabeenet.agents.meta import (
    ClassificationResult,
    ContextEvaluation,
    EmotionalTone,
    IntentCategory,
    MemoryQuerySet,
    UrgencyLevel,
)
from barnabeenet.agents.orchestrator import (
    AgentOrchestrator,
    OrchestratorConfig,
    RequestContext,
    get_orchestrator,
    process_request,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_llm_client():
    """Create a mock LLM client."""
    client = AsyncMock()
    client.complete = AsyncMock(
        return_value={
            "content": "Test response",
            "model": "test-model",
            "usage": {"prompt_tokens": 10, "completion_tokens": 20},
        }
    )
    client.init = AsyncMock()
    client.shutdown = AsyncMock()
    return client


@pytest.fixture
def config():
    """Default orchestrator config."""
    return OrchestratorConfig(
        enable_memory_retrieval=False,  # Disable for simpler tests
        enable_memory_storage=False,
    )


@pytest.fixture
def mock_classification():
    """Create a mock classification result."""
    return ClassificationResult(
        intent=IntentCategory.CONVERSATION,
        confidence=0.95,
        sub_category="general",
        context=ContextEvaluation(
            emotional_tone=EmotionalTone.NEUTRAL,
            urgency_level=UrgencyLevel.LOW,
            empathy_needed=False,
        ),
        memory_queries=MemoryQuerySet(
            primary_query="test query",
            topic_tags=["test"],
            relevant_people=[],
        ),
    )


# ============================================================================
# RequestContext Tests
# ============================================================================


class TestRequestContext:
    """Tests for RequestContext dataclass."""

    def test_creates_unique_request_id(self):
        ctx1 = RequestContext()
        ctx2 = RequestContext()
        assert ctx1.request_id != ctx2.request_id

    def test_request_id_is_short_uuid(self):
        ctx = RequestContext()
        assert len(ctx.request_id) == 8

    def test_stores_input_text(self):
        ctx = RequestContext(text="hello barnabee")
        assert ctx.text == "hello barnabee"

    def test_stores_speaker_and_room(self):
        ctx = RequestContext(speaker="thomas", room="living_room")
        assert ctx.speaker == "thomas"
        assert ctx.room == "living_room"

    def test_has_empty_default_collections(self):
        ctx = RequestContext()
        assert ctx.stage_timings == {}
        assert ctx.retrieved_memories == []
        assert ctx.actions_taken == []

    def test_records_start_time(self):
        ctx = RequestContext()
        assert ctx.started_at is not None


# ============================================================================
# OrchestratorConfig Tests
# ============================================================================


class TestOrchestratorConfig:
    """Tests for OrchestratorConfig."""

    def test_default_values(self):
        config = OrchestratorConfig()
        assert config.enable_memory_retrieval is True
        assert config.enable_memory_storage is True
        assert config.max_memories_to_retrieve == 5

    def test_custom_values(self):
        config = OrchestratorConfig(
            enable_memory_retrieval=False,
            max_memories_to_retrieve=10,
        )
        assert config.enable_memory_retrieval is False
        assert config.max_memories_to_retrieve == 10


# ============================================================================
# AgentOrchestrator Initialization Tests
# ============================================================================


class TestOrchestratorInit:
    """Tests for orchestrator initialization."""

    @pytest.mark.asyncio
    async def test_init_with_llm_client(self, mock_llm_client, config):
        orch = AgentOrchestrator(llm_client=mock_llm_client, config=config)
        assert orch._llm_client == mock_llm_client
        assert not orch._initialized

    @pytest.mark.asyncio
    async def test_init_creates_agents(self, config):
        orch = AgentOrchestrator(config=config)

        # Create mock agent classes that return AsyncMock instances
        def make_mock_agent_class():
            mock_instance = AsyncMock()
            mock_instance.init = AsyncMock()
            mock_instance.shutdown = AsyncMock()
            mock_class = MagicMock(return_value=mock_instance)
            return mock_class

        with patch.multiple(
            "barnabeenet.agents.orchestrator",
            MetaAgent=make_mock_agent_class(),
            InstantAgent=make_mock_agent_class(),
            ActionAgent=make_mock_agent_class(),
            InteractionAgent=make_mock_agent_class(),
            MemoryAgent=make_mock_agent_class(),
        ):
            await orch.init()
            assert orch._initialized

    @pytest.mark.asyncio
    async def test_init_is_idempotent(self, config):
        orch = AgentOrchestrator(config=config)

        def make_mock_agent_class():
            mock_instance = AsyncMock()
            mock_instance.init = AsyncMock()
            mock_instance.shutdown = AsyncMock()
            mock_class = MagicMock(return_value=mock_instance)
            return mock_class

        with patch.multiple(
            "barnabeenet.agents.orchestrator",
            MetaAgent=make_mock_agent_class(),
            InstantAgent=make_mock_agent_class(),
            ActionAgent=make_mock_agent_class(),
            InteractionAgent=make_mock_agent_class(),
            MemoryAgent=make_mock_agent_class(),
        ):
            await orch.init()
            await orch.init()  # Should not fail
            assert orch._initialized

    @pytest.mark.asyncio
    async def test_shutdown_cleans_up(self, config):
        orch = AgentOrchestrator(config=config)

        # Create mock agents
        orch._meta_agent = AsyncMock()
        orch._instant_agent = AsyncMock()
        orch._action_agent = AsyncMock()
        orch._interaction_agent = AsyncMock()
        orch._memory_agent = AsyncMock()
        orch._llm_client = AsyncMock()
        orch._initialized = True

        await orch.shutdown()

        orch._meta_agent.shutdown.assert_called_once()
        orch._instant_agent.shutdown.assert_called_once()
        orch._action_agent.shutdown.assert_called_once()
        orch._interaction_agent.shutdown.assert_called_once()
        orch._memory_agent.shutdown.assert_called_once()
        assert not orch._initialized


# ============================================================================
# Pipeline Flow Tests
# ============================================================================


class TestPipelineFlow:
    """Tests for the full pipeline flow."""

    @pytest.mark.asyncio
    async def test_process_returns_response_dict(self, config):
        orch = AgentOrchestrator(config=config)
        orch._initialized = True

        # Mock all agents
        orch._meta_agent = AsyncMock()
        orch._meta_agent.classify = AsyncMock(
            return_value=ClassificationResult(
                intent=IntentCategory.INSTANT,
                confidence=0.99,
                sub_category="greeting",
            )
        )

        orch._instant_agent = AsyncMock()
        orch._instant_agent.handle_input = AsyncMock(return_value={"response": "Good morning!"})

        result = await orch.process("good morning")

        assert "response" in result
        assert "request_id" in result
        assert "intent" in result
        assert "agent" in result
        assert "timings" in result

    @pytest.mark.asyncio
    async def test_routes_instant_to_instant_agent(self, config):
        orch = AgentOrchestrator(config=config)
        orch._initialized = True

        orch._meta_agent = AsyncMock()
        orch._meta_agent.classify = AsyncMock(
            return_value=ClassificationResult(
                intent=IntentCategory.INSTANT,
                confidence=0.99,
                sub_category="greeting",
            )
        )

        orch._instant_agent = AsyncMock()
        orch._instant_agent.handle_input = AsyncMock(return_value={"response": "Hello!"})

        result = await orch.process("hello")

        assert result["agent"] == "instant"
        orch._instant_agent.handle_input.assert_called_once()

    @pytest.mark.asyncio
    async def test_routes_action_to_action_agent(self, config):
        orch = AgentOrchestrator(config=config)
        orch._initialized = True

        orch._meta_agent = AsyncMock()
        orch._meta_agent.classify = AsyncMock(
            return_value=ClassificationResult(
                intent=IntentCategory.ACTION,
                confidence=0.95,
                sub_category="light_control",
            )
        )

        orch._action_agent = AsyncMock()
        orch._action_agent.handle_input = AsyncMock(
            return_value={
                "response": "Lights turned on",
                "action": {"type": "light_control", "target": "living_room"},
            }
        )

        result = await orch.process("turn on the lights")

        assert result["agent"] == "action"
        assert len(result["actions"]) == 1
        orch._action_agent.handle_input.assert_called_once()

    @pytest.mark.asyncio
    async def test_routes_conversation_to_interaction_agent(self, config):
        orch = AgentOrchestrator(config=config)
        orch._initialized = True

        orch._meta_agent = AsyncMock()
        orch._meta_agent.classify = AsyncMock(
            return_value=ClassificationResult(
                intent=IntentCategory.CONVERSATION,
                confidence=0.90,
                sub_category="general",
            )
        )

        orch._interaction_agent = AsyncMock()
        orch._interaction_agent.handle_input = AsyncMock(
            return_value={"response": "I'm doing well, sir."}
        )

        result = await orch.process("how are you today")

        assert result["agent"] == "interaction"
        orch._interaction_agent.handle_input.assert_called_once()

    @pytest.mark.asyncio
    async def test_routes_query_to_interaction_agent(self, config):
        orch = AgentOrchestrator(config=config)
        orch._initialized = True

        orch._meta_agent = AsyncMock()
        orch._meta_agent.classify = AsyncMock(
            return_value=ClassificationResult(
                intent=IntentCategory.QUERY,
                confidence=0.92,
                sub_category="factual",
            )
        )

        orch._interaction_agent = AsyncMock()
        orch._interaction_agent.handle_input = AsyncMock(
            return_value={"response": "The capital of France is Paris."}
        )

        result = await orch.process("what is the capital of France")

        assert result["agent"] == "interaction"

    @pytest.mark.asyncio
    async def test_routes_memory_to_memory_agent(self, config):
        orch = AgentOrchestrator(config=config)
        orch._initialized = True

        orch._meta_agent = AsyncMock()
        orch._meta_agent.classify = AsyncMock(
            return_value=ClassificationResult(
                intent=IntentCategory.MEMORY,
                confidence=0.95,
                sub_category="recall",
            )
        )

        orch._memory_agent = AsyncMock()
        orch._memory_agent.handle_input = AsyncMock(
            return_value={"response": "I remember that yesterday..."}
        )

        result = await orch.process("do you remember what we talked about yesterday")

        assert result["agent"] == "memory"
        orch._memory_agent.handle_input.assert_called_once()

    @pytest.mark.asyncio
    async def test_routes_emergency_with_flag(self, config):
        orch = AgentOrchestrator(config=config)
        orch._initialized = True

        orch._meta_agent = AsyncMock()
        orch._meta_agent.classify = AsyncMock(
            return_value=ClassificationResult(
                intent=IntentCategory.EMERGENCY,
                confidence=0.99,
                sub_category="fire",
            )
        )

        orch._interaction_agent = AsyncMock()
        orch._interaction_agent.handle_input = AsyncMock(
            return_value={"response": "Activating emergency protocols!"}
        )

        result = await orch.process("there's a fire!")

        assert result["agent"] == "interaction"
        # Verify emergency flag was passed
        call_args = orch._interaction_agent.handle_input.call_args
        assert call_args[0][1].get("emergency") is True


# ============================================================================
# Memory Integration Tests
# ============================================================================


class TestMemoryIntegration:
    """Tests for memory retrieval and storage."""

    @pytest.mark.asyncio
    async def test_retrieves_memories_when_enabled(self):
        config = OrchestratorConfig(
            enable_memory_retrieval=True,
            enable_memory_storage=False,
        )
        orch = AgentOrchestrator(config=config)
        orch._initialized = True

        # Mock agents
        orch._meta_agent = AsyncMock()
        orch._meta_agent.classify = AsyncMock(
            return_value=ClassificationResult(
                intent=IntentCategory.CONVERSATION,
                confidence=0.90,
                memory_queries=MemoryQuerySet(
                    primary_query="family preferences",
                    topic_tags=["family"],
                    relevant_people=["thomas"],
                ),
            )
        )

        orch._memory_agent = AsyncMock()
        orch._memory_agent.handle_input = AsyncMock(
            return_value={
                "memories": [
                    {"content": "Thomas likes coffee"},
                    {"content": "Family dinner on Sundays"},
                ]
            }
        )

        orch._interaction_agent = AsyncMock()
        orch._interaction_agent.handle_input = AsyncMock(return_value={"response": "Hello!"})

        result = await orch.process("hello")

        # Memory agent should have been called for retrieval
        orch._memory_agent.handle_input.assert_called()
        assert result["memories_used"] == 2

    @pytest.mark.asyncio
    async def test_skips_memory_when_disabled(self):
        config = OrchestratorConfig(
            enable_memory_retrieval=False,
            enable_memory_storage=False,
        )
        orch = AgentOrchestrator(config=config)
        orch._initialized = True

        orch._meta_agent = AsyncMock()
        orch._meta_agent.classify = AsyncMock(
            return_value=ClassificationResult(
                intent=IntentCategory.INSTANT,
                confidence=0.99,
            )
        )

        orch._instant_agent = AsyncMock()
        orch._instant_agent.handle_input = AsyncMock(return_value={"response": "Hello!"})

        result = await orch.process("hello")

        assert result["memories_used"] == 0

    @pytest.mark.asyncio
    async def test_stores_memory_for_conversations(self):
        config = OrchestratorConfig(
            enable_memory_retrieval=False,
            enable_memory_storage=True,
        )
        orch = AgentOrchestrator(config=config)
        orch._initialized = True

        orch._meta_agent = AsyncMock()
        orch._meta_agent.classify = AsyncMock(
            return_value=ClassificationResult(
                intent=IntentCategory.CONVERSATION,
                confidence=0.90,
                context=ContextEvaluation(
                    emotional_tone=EmotionalTone.POSITIVE,
                    urgency_level=UrgencyLevel.LOW,
                    empathy_needed=False,
                ),
            )
        )

        orch._interaction_agent = AsyncMock()
        orch._interaction_agent.handle_input = AsyncMock(
            return_value={"response": "That's wonderful news!"}
        )

        orch._memory_agent = AsyncMock()
        orch._memory_agent.handle_input = AsyncMock(return_value={})

        await orch.process("I got a promotion today!")

        # Memory agent should be called for storage
        calls = orch._memory_agent.handle_input.call_args_list
        # Should have at least one call for storage
        assert len(calls) >= 1


# ============================================================================
# Context Passing Tests
# ============================================================================


class TestContextPassing:
    """Tests for context being passed through pipeline."""

    @pytest.mark.asyncio
    async def test_passes_speaker_to_agents(self, config):
        orch = AgentOrchestrator(config=config)
        orch._initialized = True

        orch._meta_agent = AsyncMock()
        orch._meta_agent.classify = AsyncMock(
            return_value=ClassificationResult(
                intent=IntentCategory.INSTANT,
                confidence=0.99,
            )
        )

        orch._instant_agent = AsyncMock()
        orch._instant_agent.handle_input = AsyncMock(return_value={"response": "Hello Thomas!"})

        await orch.process("hello", speaker="thomas")

        # Check speaker was passed to instant agent
        call_args = orch._instant_agent.handle_input.call_args
        assert call_args[0][1]["speaker"] == "thomas"

    @pytest.mark.asyncio
    async def test_passes_room_to_agents(self, config):
        orch = AgentOrchestrator(config=config)
        orch._initialized = True

        orch._meta_agent = AsyncMock()
        orch._meta_agent.classify = AsyncMock(
            return_value=ClassificationResult(
                intent=IntentCategory.ACTION,
                confidence=0.95,
            )
        )

        orch._action_agent = AsyncMock()
        orch._action_agent.handle_input = AsyncMock(return_value={"response": "Done!"})

        await orch.process("turn on the light", room="kitchen")

        call_args = orch._action_agent.handle_input.call_args
        assert call_args[0][1]["room"] == "kitchen"

    @pytest.mark.asyncio
    async def test_passes_conversation_id(self, config):
        orch = AgentOrchestrator(config=config)
        orch._initialized = True

        orch._meta_agent = AsyncMock()
        orch._meta_agent.classify = AsyncMock(
            return_value=ClassificationResult(
                intent=IntentCategory.CONVERSATION,
                confidence=0.90,
            )
        )

        orch._interaction_agent = AsyncMock()
        orch._interaction_agent.handle_input = AsyncMock(return_value={"response": "Hello!"})

        result = await orch.process("hello", conversation_id="conv_existing123")

        assert result["conversation_id"] == "conv_existing123"
        call_args = orch._interaction_agent.handle_input.call_args
        assert call_args[0][1]["conversation_id"] == "conv_existing123"

    @pytest.mark.asyncio
    async def test_generates_conversation_id_if_missing(self, config):
        orch = AgentOrchestrator(config=config)
        orch._initialized = True

        orch._meta_agent = AsyncMock()
        orch._meta_agent.classify = AsyncMock(
            return_value=ClassificationResult(
                intent=IntentCategory.INSTANT,
                confidence=0.99,
            )
        )

        orch._instant_agent = AsyncMock()
        orch._instant_agent.handle_input = AsyncMock(return_value={"response": "Hello!"})

        result = await orch.process("hello")

        assert result["conversation_id"] is not None
        assert result["conversation_id"].startswith("conv_")


# ============================================================================
# Timing Tests
# ============================================================================


class TestTimings:
    """Tests for timing tracking."""

    @pytest.mark.asyncio
    async def test_records_classification_timing(self, config):
        orch = AgentOrchestrator(config=config)
        orch._initialized = True

        orch._meta_agent = AsyncMock()
        orch._meta_agent.classify = AsyncMock(
            return_value=ClassificationResult(
                intent=IntentCategory.INSTANT,
                confidence=0.99,
            )
        )

        orch._instant_agent = AsyncMock()
        orch._instant_agent.handle_input = AsyncMock(return_value={"response": "Hi!"})

        result = await orch.process("hi")

        assert "classification" in result["timings"]
        assert result["timings"]["classification"] >= 0

    @pytest.mark.asyncio
    async def test_records_agent_handling_timing(self, config):
        orch = AgentOrchestrator(config=config)
        orch._initialized = True

        orch._meta_agent = AsyncMock()
        orch._meta_agent.classify = AsyncMock(
            return_value=ClassificationResult(
                intent=IntentCategory.INSTANT,
                confidence=0.99,
            )
        )

        orch._instant_agent = AsyncMock()
        orch._instant_agent.handle_input = AsyncMock(return_value={"response": "Hi!"})

        result = await orch.process("hi")

        assert "agent_handling" in result["timings"]
        assert result["timings"]["agent_handling"] >= 0

    @pytest.mark.asyncio
    async def test_records_total_timing(self, config):
        orch = AgentOrchestrator(config=config)
        orch._initialized = True

        orch._meta_agent = AsyncMock()
        orch._meta_agent.classify = AsyncMock(
            return_value=ClassificationResult(
                intent=IntentCategory.INSTANT,
                confidence=0.99,
            )
        )

        orch._instant_agent = AsyncMock()
        orch._instant_agent.handle_input = AsyncMock(return_value={"response": "Hi!"})

        result = await orch.process("hi")

        assert "total" in result["timings"]
        assert result["timings"]["total"] >= result["timings"]["classification"]


# ============================================================================
# Error Handling Tests
# ============================================================================


class TestErrorHandling:
    """Tests for error handling in the pipeline."""

    @pytest.mark.asyncio
    async def test_handles_classification_error_gracefully(self, config):
        orch = AgentOrchestrator(config=config)
        orch._initialized = True

        orch._meta_agent = AsyncMock()
        orch._meta_agent.classify = AsyncMock(side_effect=Exception("LLM Error"))

        result = await orch.process("hello")

        assert "error" in result["response"].lower()
        assert "agent" in result

    @pytest.mark.asyncio
    async def test_handles_agent_error_gracefully(self, config):
        orch = AgentOrchestrator(config=config)
        orch._initialized = True

        orch._meta_agent = AsyncMock()
        orch._meta_agent.classify = AsyncMock(
            return_value=ClassificationResult(
                intent=IntentCategory.ACTION,
                confidence=0.95,
            )
        )

        orch._action_agent = AsyncMock()
        orch._action_agent.handle_input = AsyncMock(side_effect=Exception("Device Error"))

        result = await orch.process("turn on the light")

        assert "error" in result["response"].lower()


# ============================================================================
# Global Orchestrator Tests
# ============================================================================


class TestGlobalOrchestrator:
    """Tests for global orchestrator functions."""

    def test_get_orchestrator_returns_instance(self):
        # Reset global
        import barnabeenet.agents.orchestrator as orch_module

        orch_module._global_orchestrator = None

        orch = get_orchestrator()
        assert orch is not None
        assert isinstance(orch, AgentOrchestrator)

    def test_get_orchestrator_returns_same_instance(self):
        import barnabeenet.agents.orchestrator as orch_module

        orch_module._global_orchestrator = None

        orch1 = get_orchestrator()
        orch2 = get_orchestrator()
        assert orch1 is orch2

    @pytest.mark.asyncio
    async def test_process_request_convenience_function(self):
        import barnabeenet.agents.orchestrator as orch_module

        # Create mock orchestrator
        mock_orch = AsyncMock()
        mock_orch.process = AsyncMock(return_value={"response": "Hello!"})
        orch_module._global_orchestrator = mock_orch

        result = await process_request("hello")

        assert result["response"] == "Hello!"
        mock_orch.process.assert_called_once()


# ============================================================================
# Agent Accessor Tests
# ============================================================================


class TestAgentAccessors:
    """Tests for agent accessor methods."""

    def test_get_meta_agent(self, config):
        orch = AgentOrchestrator(config=config)
        assert orch.get_meta_agent() is None

        orch._meta_agent = MagicMock()
        assert orch.get_meta_agent() is not None

    def test_get_instant_agent(self, config):
        orch = AgentOrchestrator(config=config)
        assert orch.get_instant_agent() is None

        orch._instant_agent = MagicMock()
        assert orch.get_instant_agent() is not None

    def test_get_action_agent(self, config):
        orch = AgentOrchestrator(config=config)
        assert orch.get_action_agent() is None

        orch._action_agent = MagicMock()
        assert orch.get_action_agent() is not None

    def test_get_interaction_agent(self, config):
        orch = AgentOrchestrator(config=config)
        assert orch.get_interaction_agent() is None

        orch._interaction_agent = MagicMock()
        assert orch.get_interaction_agent() is not None

    def test_get_memory_agent(self, config):
        orch = AgentOrchestrator(config=config)
        assert orch.get_memory_agent() is None

        orch._memory_agent = MagicMock()
        assert orch.get_memory_agent() is not None


# ============================================================================
# Intent Confidence Tests
# ============================================================================


class TestIntentConfidence:
    """Tests for intent confidence in responses."""

    @pytest.mark.asyncio
    async def test_includes_intent_confidence(self, config):
        orch = AgentOrchestrator(config=config)
        orch._initialized = True

        orch._meta_agent = AsyncMock()
        orch._meta_agent.classify = AsyncMock(
            return_value=ClassificationResult(
                intent=IntentCategory.INSTANT,
                confidence=0.95,
            )
        )

        orch._instant_agent = AsyncMock()
        orch._instant_agent.handle_input = AsyncMock(return_value={"response": "Hi!"})

        result = await orch.process("hi")

        assert result["intent_confidence"] == 0.95

    @pytest.mark.asyncio
    async def test_zero_confidence_on_missing_classification(self, config):
        orch = AgentOrchestrator(config=config)
        orch._initialized = True

        orch._meta_agent = AsyncMock()
        orch._meta_agent.classify = AsyncMock(
            return_value=ClassificationResult(intent=IntentCategory.UNKNOWN, confidence=0.0)
        )

        orch._interaction_agent = AsyncMock()
        orch._interaction_agent.handle_input = AsyncMock(return_value={"response": "Hi!"})

        result = await orch.process("something")

        assert result["intent_confidence"] == 0.0


# ============================================================================
# Fallback Behavior Tests
# ============================================================================


class TestFallbackBehavior:
    """Tests for fallback when classification fails."""

    @pytest.mark.asyncio
    async def test_falls_back_to_interaction_on_unknown(self, config):
        orch = AgentOrchestrator(config=config)
        orch._initialized = True

        orch._meta_agent = AsyncMock()
        orch._meta_agent.classify = AsyncMock(
            return_value=ClassificationResult(
                intent=IntentCategory.UNKNOWN,
                confidence=0.3,
            )
        )

        orch._interaction_agent = AsyncMock()
        orch._interaction_agent.handle_input = AsyncMock(
            return_value={"response": "I'm not sure I understand."}
        )

        result = await orch.process("asdf gibberish")

        assert result["agent"] == "interaction"

    @pytest.mark.asyncio
    async def test_falls_back_to_interaction_on_no_classification(self, config):
        orch = AgentOrchestrator(config=config)
        orch._initialized = True

        orch._meta_agent = AsyncMock()
        orch._meta_agent.classify = AsyncMock(
            return_value=ClassificationResult(intent=IntentCategory.UNKNOWN, confidence=0.0)
        )

        orch._interaction_agent = AsyncMock()
        orch._interaction_agent.handle_input = AsyncMock(return_value={"response": "Hello!"})

        result = await orch.process("hello")

        assert result["agent"] == "interaction"
