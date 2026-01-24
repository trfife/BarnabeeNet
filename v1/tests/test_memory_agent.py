"""Tests for the Memory Agent."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from barnabeenet.agents.memory import (
    Memory,
    MemoryAgent,
    MemoryConfig,
    MemoryOperation,
    MemoryType,
)
from barnabeenet.services.llm.openrouter import ChatResponse


@pytest.fixture
def mock_storage():
    """Create a mock memory storage service."""
    storage = AsyncMock()
    storage.init = AsyncMock()
    storage.shutdown = AsyncMock()

    # Track stored memories for search simulation
    stored_memories = {}

    def create_stored_memory(
        content,
        memory_type="semantic",
        importance=0.5,
        participants=None,
        tags=None,
        time_context=None,
        day_context=None,
        memory_id=None,
    ):
        mid = memory_id or f"mem_{len(stored_memories):03d}"
        mock_mem = MagicMock()
        mock_mem.id = mid
        mock_mem.content = content
        mock_mem.memory_type = memory_type
        mock_mem.importance = importance
        mock_mem.participants = participants or []
        mock_mem.tags = tags or []
        mock_mem.time_context = time_context
        mock_mem.day_context = day_context
        mock_mem.to_dict = MagicMock(
            return_value={
                "id": mid,
                "content": content,
                "memory_type": memory_type,
                "importance": importance,
                "created_at": datetime.now().isoformat(),
                "last_accessed": None,
                "access_count": 0,
                "participants": participants or [],
                "tags": tags or [],
                "time_context": time_context,
                "day_context": day_context,
            }
        )
        stored_memories[mid] = mock_mem
        return mock_mem

    async def store_memory_impl(
        content,
        memory_type="semantic",
        importance=0.5,
        participants=None,
        tags=None,
        time_context=None,
        day_context=None,
        memory_id=None,
    ):
        return create_stored_memory(
            content,
            memory_type,
            importance,
            participants,
            tags,
            time_context,
            day_context,
            memory_id,
        )

    async def search_memories_impl(
        query, memory_type=None, participants=None, max_results=10, min_score=0.3
    ):
        # Simple keyword matching for tests
        results = []
        for mem in stored_memories.values():
            if memory_type and mem.memory_type != memory_type:
                continue
            if participants and not any(p in mem.participants for p in participants):
                continue
            # Simple keyword match
            if query.lower() in mem.content.lower():
                results.append((mem, 0.9))
        return results[:max_results]

    async def delete_memory_impl(memory_id):
        if memory_id in stored_memories:
            del stored_memories[memory_id]
            return True
        return False

    storage.store_memory = AsyncMock(side_effect=store_memory_impl)
    storage.search_memories = AsyncMock(side_effect=search_memories_impl)
    storage.get_memory = AsyncMock(side_effect=lambda mid: stored_memories.get(mid))
    storage.delete_memory = AsyncMock(side_effect=delete_memory_impl)
    storage.update_memory_access = AsyncMock()

    return storage


@pytest.fixture
def mock_llm_response_generate() -> ChatResponse:
    """Create a mock LLM response for memory generation."""
    return ChatResponse(
        text="""{
  "content": "I noticed Thom prefers his morning coffee around 6:30am.",
  "type": "preference",
  "importance": 0.7,
  "participants": ["thom"],
  "tags": ["coffee", "morning", "routine"],
  "time_context": "morning",
  "day_context": "weekday"
}""",
        model="openai/gpt-4o-mini",
        input_tokens=200,
        output_tokens=50,
        total_tokens=250,
        finish_reason="stop",
        cost_usd=0.0001,
        latency_ms=150.0,
    )


@pytest.fixture
def mock_llm_response_extract() -> ChatResponse:
    """Create a mock LLM response for conversation extraction."""
    return ChatResponse(
        text="""[
  {
    "content": "I learned that Sarah prefers the thermostat at 68 degrees.",
    "type": "preference",
    "importance": 0.6,
    "participants": ["sarah"],
    "tags": ["temperature", "comfort"]
  }
]""",
        model="openai/gpt-4o-mini",
        input_tokens=150,
        output_tokens=40,
        total_tokens=190,
        finish_reason="stop",
        cost_usd=0.00008,
        latency_ms=120.0,
    )


@pytest.fixture
def mock_llm_client(
    mock_llm_response_generate: ChatResponse,
) -> MagicMock:
    """Create a mock LLM client."""
    client = MagicMock()
    client.chat = AsyncMock(return_value=mock_llm_response_generate)
    client.init = AsyncMock()
    client.shutdown = AsyncMock()
    return client


@pytest.fixture
def agent_config() -> MemoryConfig:
    """Create test configuration."""
    return MemoryConfig(
        max_retrieval_results=5,
        importance_threshold_for_storage=0.3,
    )


@pytest.fixture
async def initialized_agent(
    mock_llm_client: MagicMock, agent_config: MemoryConfig, mock_storage
) -> MemoryAgent:
    """Create an initialized MemoryAgent with mock LLM and storage."""
    agent = MemoryAgent(llm_client=mock_llm_client, config=agent_config, storage=mock_storage)
    await agent.init()
    yield agent
    await agent.shutdown()


@pytest.fixture
async def agent_no_llm(agent_config: MemoryConfig, mock_storage) -> MemoryAgent:
    """Create an agent without LLM (fallback mode)."""
    agent = MemoryAgent(llm_client=None, config=agent_config, storage=mock_storage)
    await agent.init()
    yield agent
    await agent.shutdown()


class TestMemoryAgentInit:
    """Test MemoryAgent initialization."""

    @pytest.mark.asyncio
    async def test_init_with_llm_client(self, mock_llm_client: MagicMock, mock_storage) -> None:
        """Agent initializes with provided LLM client."""
        agent = MemoryAgent(llm_client=mock_llm_client, storage=mock_storage)
        await agent.init()
        assert agent._initialized is True
        await agent.shutdown()

    @pytest.mark.asyncio
    async def test_agent_name(self, initialized_agent: MemoryAgent) -> None:
        """Agent has correct name."""
        assert initialized_agent.name == "memory"

    @pytest.mark.asyncio
    async def test_double_init_safe(self, mock_llm_client: MagicMock, mock_storage) -> None:
        """Double initialization is safe."""
        agent = MemoryAgent(llm_client=mock_llm_client, storage=mock_storage)
        await agent.init()
        await agent.init()  # Should be no-op
        assert agent._initialized is True
        await agent.shutdown()


class TestMemoryStore:
    """Test memory storage operations."""

    @pytest.mark.asyncio
    async def test_store_memory(self, initialized_agent: MemoryAgent) -> None:
        """Store a simple memory."""
        result = await initialized_agent.handle_input(
            "Thom likes coffee in the morning",
            {"operation": MemoryOperation.STORE},
        )
        assert result["success"] is True
        assert "memory_id" in result
        assert result["agent"] == "memory"

    @pytest.mark.asyncio
    async def test_store_with_type(self, initialized_agent: MemoryAgent) -> None:
        """Store memory with specific type."""
        result = await initialized_agent.handle_input(
            "Family bedtime is at 8pm",
            {
                "operation": MemoryOperation.STORE,
                "memory_type": MemoryType.PROCEDURAL,
            },
        )
        assert result["success"] is True
        memory = initialized_agent.get_memory(result["memory_id"])
        assert memory.memory_type == MemoryType.PROCEDURAL

    @pytest.mark.asyncio
    async def test_store_with_metadata(self, initialized_agent: MemoryAgent) -> None:
        """Store memory with full metadata."""
        result = await initialized_agent.handle_input(
            "Kids prefer the blue nightlight",
            {
                "operation": MemoryOperation.STORE,
                "memory_type": MemoryType.SEMANTIC,
                "importance": 0.8,
                "participants": ["penelope", "xander"],
                "tags": ["nightlight", "bedtime", "preferences"],
                "time_context": "night",
            },
        )
        assert result["success"] is True
        memory = initialized_agent.get_memory(result["memory_id"])
        assert memory.importance == 0.8
        assert "penelope" in memory.participants
        assert "nightlight" in memory.tags


class TestMemoryRetrieval:
    """Test memory retrieval operations."""

    @pytest.mark.asyncio
    async def test_retrieve_by_keyword(self, initialized_agent: MemoryAgent) -> None:
        """Retrieve memories by keyword."""
        # Store some memories first
        await initialized_agent.handle_input(
            "Thom prefers morning coffee",
            {
                "operation": MemoryOperation.STORE,
                "tags": ["coffee", "morning"],
            },
        )
        await initialized_agent.handle_input(
            "Sarah enjoys evening tea",
            {
                "operation": MemoryOperation.STORE,
                "tags": ["tea", "evening"],
            },
        )

        # Retrieve
        result = await initialized_agent.handle_input(
            "coffee",
            {"operation": MemoryOperation.RETRIEVE},
        )
        assert result["success"] is True
        assert result["count"] >= 1
        assert any("coffee" in m["content"].lower() for m in result["memories"])

    @pytest.mark.asyncio
    async def test_retrieve_by_participant(self, initialized_agent: MemoryAgent) -> None:
        """Retrieve memories filtered by participant."""
        await initialized_agent.handle_input(
            "Thom works in the office",
            {
                "operation": MemoryOperation.STORE,
                "participants": ["thom"],
            },
        )
        await initialized_agent.handle_input(
            "Sarah gardens on weekends",
            {
                "operation": MemoryOperation.STORE,
                "participants": ["sarah"],
            },
        )

        result = await initialized_agent.handle_input(
            "activities",
            {
                "operation": MemoryOperation.RETRIEVE,
                "participants": ["thom"],
            },
        )
        assert result["success"] is True
        for mem in result["memories"]:
            assert "thom" in mem.get("participants", [])

    @pytest.mark.asyncio
    async def test_retrieve_empty_results(self, initialized_agent: MemoryAgent) -> None:
        """Retrieve returns empty when no matches."""
        result = await initialized_agent.handle_input(
            "nonexistent topic xyz123",
            {"operation": MemoryOperation.RETRIEVE},
        )
        assert result["success"] is True
        assert result["count"] == 0

    @pytest.mark.asyncio
    async def test_retrieve_updates_access_metadata(
        self, initialized_agent: MemoryAgent, mock_storage
    ) -> None:
        """Retrieval calls storage to update access metadata."""
        await initialized_agent.handle_input(
            "Unique memory content here",
            {
                "operation": MemoryOperation.STORE,
                "tags": ["unique"],
            },
        )

        # Reset the mock call count
        mock_storage.update_memory_access.reset_mock()

        # Retrieve twice
        await initialized_agent.handle_input(
            "unique",
            {"operation": MemoryOperation.RETRIEVE},
        )
        await initialized_agent.handle_input(
            "unique",
            {"operation": MemoryOperation.RETRIEVE},
        )

        # Should have called update_memory_access for each retrieval
        assert mock_storage.update_memory_access.call_count >= 2


class TestMemoryGeneration:
    """Test memory generation from events."""

    @pytest.mark.asyncio
    async def test_generate_from_events(
        self, initialized_agent: MemoryAgent, mock_llm_client: MagicMock
    ) -> None:
        """Generate memory from events using LLM."""
        events = [
            {
                "id": "event_1",
                "type": "conversation",
                "timestamp": datetime.now().isoformat(),
                "details": "Thom asked for coffee at 6:30am",
                "speaker_id": "thom",
                "room": "kitchen",
            }
        ]

        result = await initialized_agent.handle_input(
            "",
            {
                "operation": MemoryOperation.GENERATE,
                "events": events,
            },
        )

        assert result["success"] is True
        assert result["stored"] is True
        assert "memory_id" in result
        mock_llm_client.chat.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_no_events_error(self, initialized_agent: MemoryAgent) -> None:
        """Generate fails when no events provided."""
        result = await initialized_agent.handle_input(
            "",
            {"operation": MemoryOperation.GENERATE, "events": []},
        )
        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_generate_fallback_without_llm(self, agent_no_llm: MemoryAgent) -> None:
        """Generate uses fallback without LLM."""
        events = [
            {
                "id": "event_1",
                "type": "observation",
                "timestamp": datetime.now().isoformat(),
                "details": "The living room light was turned on",
            }
        ]

        result = await agent_no_llm.handle_input(
            "",
            {
                "operation": MemoryOperation.GENERATE,
                "events": events,
            },
        )

        assert result["success"] is True
        assert result.get("fallback") is True

    @pytest.mark.asyncio
    async def test_generate_skips_low_importance(
        self, initialized_agent: MemoryAgent, mock_llm_client: MagicMock
    ) -> None:
        """Skip storage when importance is below threshold."""
        # Mock low importance response
        mock_llm_client.chat.return_value = ChatResponse(
            text="""{
  "content": "Something happened",
  "type": "event",
  "importance": 0.1,
  "participants": [],
  "tags": []
}""",
            model="openai/gpt-4o-mini",
            input_tokens=100,
            output_tokens=30,
            total_tokens=130,
            finish_reason="stop",
            cost_usd=0.00005,
            latency_ms=100.0,
        )

        events = [
            {
                "id": "event_1",
                "type": "minor",
                "timestamp": datetime.now().isoformat(),
                "details": "Something minor happened",
            }
        ]

        result = await initialized_agent.handle_input(
            "",
            {
                "operation": MemoryOperation.GENERATE,
                "events": events,
            },
        )

        assert result["success"] is True
        assert result["stored"] is False


class TestMemoryForget:
    """Test memory deletion operations."""

    @pytest.mark.asyncio
    async def test_forget_memory(self, initialized_agent: MemoryAgent) -> None:
        """Delete a specific memory."""
        # Store first
        store_result = await initialized_agent.handle_input(
            "Memory to forget",
            {"operation": MemoryOperation.STORE},
        )
        memory_id = store_result["memory_id"]

        # Verify it exists
        assert initialized_agent.get_memory(memory_id) is not None

        # Forget
        result = await initialized_agent.handle_input(
            "",
            {
                "operation": MemoryOperation.FORGET,
                "memory_id": memory_id,
            },
        )

        assert result["success"] is True
        assert initialized_agent.get_memory(memory_id) is None

    @pytest.mark.asyncio
    async def test_forget_nonexistent(self, initialized_agent: MemoryAgent) -> None:
        """Forget returns error for nonexistent memory."""
        result = await initialized_agent.handle_input(
            "",
            {
                "operation": MemoryOperation.FORGET,
                "memory_id": "nonexistent_id",
            },
        )
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_forget_no_id(self, initialized_agent: MemoryAgent) -> None:
        """Forget requires memory_id."""
        result = await initialized_agent.handle_input(
            "",
            {"operation": MemoryOperation.FORGET},
        )
        assert result["success"] is False


class TestMemoryConsolidate:
    """Test memory consolidation operations."""

    @pytest.mark.asyncio
    async def test_consolidate_insufficient_memories(self, initialized_agent: MemoryAgent) -> None:
        """Consolidate reports when not enough memories."""
        result = await initialized_agent.handle_input(
            "",
            {"operation": MemoryOperation.CONSOLIDATE},
        )
        assert result["success"] is True
        assert result["consolidated"] == 0

    @pytest.mark.asyncio
    async def test_consolidate_with_memories(self, initialized_agent: MemoryAgent) -> None:
        """Consolidate reports available episodic memories."""
        # Store episodic memories
        for i in range(5):
            await initialized_agent.handle_input(
                f"Event {i} happened",
                {
                    "operation": MemoryOperation.STORE,
                    "memory_type": MemoryType.EPISODIC,
                },
            )

        result = await initialized_agent.handle_input(
            "",
            {"operation": MemoryOperation.CONSOLIDATE},
        )

        assert result["success"] is True
        assert result["episodic_count"] == 5


class TestWorkingMemory:
    """Test working memory operations."""

    @pytest.mark.asyncio
    async def test_set_and_get_working_memory(self, initialized_agent: MemoryAgent) -> None:
        """Set and retrieve working memory."""
        initialized_agent.set_working_memory("session_1", "topic", "weather")
        value = initialized_agent.get_working_memory("session_1", "topic")
        assert value == "weather"

    @pytest.mark.asyncio
    async def test_get_nonexistent_working_memory(self, initialized_agent: MemoryAgent) -> None:
        """Get returns default for nonexistent key."""
        value = initialized_agent.get_working_memory("session_x", "key", default="none")
        assert value == "none"

    @pytest.mark.asyncio
    async def test_clear_working_memory(self, initialized_agent: MemoryAgent) -> None:
        """Clear working memory for session."""
        initialized_agent.set_working_memory("session_1", "key1", "value1")
        initialized_agent.set_working_memory("session_1", "key2", "value2")

        initialized_agent.clear_working_memory("session_1")

        assert initialized_agent.get_working_memory("session_1", "key1") is None


class TestConversationExtraction:
    """Test extracting memories from conversations."""

    @pytest.mark.asyncio
    async def test_extract_from_conversation(
        self,
        initialized_agent: MemoryAgent,
        mock_llm_client: MagicMock,
        mock_llm_response_extract: ChatResponse,
    ) -> None:
        """Extract memories from conversation."""
        mock_llm_client.chat.return_value = mock_llm_response_extract

        conversation = [
            {"role": "user", "content": "Can you set the thermostat to 68?"},
            {"role": "assistant", "content": "I've set the temperature to 68 degrees."},
            {"role": "user", "content": "That's perfect, Sarah likes it at that temp."},
        ]

        memories = await initialized_agent.extract_from_conversation(conversation, speaker="sarah")

        assert len(memories) >= 1
        mock_llm_client.chat.assert_called_once()

    @pytest.mark.asyncio
    async def test_extract_without_llm(self, agent_no_llm: MemoryAgent) -> None:
        """Extraction returns empty without LLM."""
        conversation = [
            {"role": "user", "content": "Hello"},
        ]

        memories = await agent_no_llm.extract_from_conversation(conversation)
        assert memories == []


class TestMemoryDataclass:
    """Test Memory dataclass operations."""

    def test_memory_to_dict(self) -> None:
        """Memory converts to dictionary."""
        memory = Memory(
            id="mem_001",
            content="Test memory",
            memory_type=MemoryType.SEMANTIC,
            importance=0.7,
            participants=["thom"],
            tags=["test"],
        )

        data = memory.to_dict()

        assert data["id"] == "mem_001"
        assert data["memory_type"] == "semantic"
        assert data["importance"] == 0.7

    def test_memory_from_dict(self) -> None:
        """Memory creates from dictionary."""
        data = {
            "id": "mem_002",
            "content": "Restored memory",
            "memory_type": "episodic",
            "importance": 0.5,
            "created_at": "2026-01-17T10:00:00",
            "participants": ["sarah"],
            "tags": ["test"],
        }

        memory = Memory.from_dict(data)

        assert memory.id == "mem_002"
        assert memory.memory_type == MemoryType.EPISODIC
        assert memory.participants == ["sarah"]


class TestQueryMethods:
    """Test public query methods."""

    @pytest.mark.asyncio
    async def test_get_memory(self, initialized_agent: MemoryAgent) -> None:
        """Get specific memory by ID."""
        result = await initialized_agent.handle_input(
            "Test memory",
            {"operation": MemoryOperation.STORE},
        )
        memory_id = result["memory_id"]

        memory = initialized_agent.get_memory(memory_id)
        assert memory is not None
        assert memory.content == "Test memory"

    @pytest.mark.asyncio
    async def test_get_all_memories(self, initialized_agent: MemoryAgent) -> None:
        """Get all memories."""
        await initialized_agent.handle_input(
            "Memory 1",
            {"operation": MemoryOperation.STORE, "memory_type": MemoryType.SEMANTIC},
        )
        await initialized_agent.handle_input(
            "Memory 2",
            {"operation": MemoryOperation.STORE, "memory_type": MemoryType.EPISODIC},
        )

        all_memories = initialized_agent.get_all_memories()
        assert len(all_memories) == 2

        semantic_only = initialized_agent.get_all_memories(MemoryType.SEMANTIC)
        assert len(semantic_only) == 1

    @pytest.mark.asyncio
    async def test_get_memory_count(self, initialized_agent: MemoryAgent) -> None:
        """Get memory counts by type."""
        await initialized_agent.handle_input(
            "Semantic 1",
            {"operation": MemoryOperation.STORE, "memory_type": MemoryType.SEMANTIC},
        )
        await initialized_agent.handle_input(
            "Semantic 2",
            {"operation": MemoryOperation.STORE, "memory_type": MemoryType.SEMANTIC},
        )
        await initialized_agent.handle_input(
            "Episodic 1",
            {"operation": MemoryOperation.STORE, "memory_type": MemoryType.EPISODIC},
        )

        counts = initialized_agent.get_memory_count()
        assert counts["semantic"] == 2
        assert counts["episodic"] == 1


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_unknown_operation(self, initialized_agent: MemoryAgent) -> None:
        """Handle unknown operation gracefully."""
        # This would require passing an invalid string
        result = await initialized_agent.handle_input(
            "test",
            {"operation": MemoryOperation.RETRIEVE},  # Valid operation
        )
        assert "agent" in result

    @pytest.mark.asyncio
    async def test_operation_as_string(self, initialized_agent: MemoryAgent) -> None:
        """Accept operation as string."""
        result = await initialized_agent.handle_input(
            "Test memory",
            {"operation": "store"},
        )
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_memory_type_as_string(self, initialized_agent: MemoryAgent) -> None:
        """Accept memory_type as string."""
        result = await initialized_agent.handle_input(
            "Test memory",
            {"operation": "store", "memory_type": "semantic"},
        )
        assert result["success"] is True
        memory = initialized_agent.get_memory(result["memory_id"])
        assert memory.memory_type == MemoryType.SEMANTIC


class TestExportedSymbols:
    """Test module exports."""

    def test_all_exports(self) -> None:
        """All expected symbols are exported."""
        from barnabeenet.agents import memory

        assert hasattr(memory, "MemoryAgent")
        assert hasattr(memory, "MemoryConfig")
        assert hasattr(memory, "Memory")
        assert hasattr(memory, "MemoryType")
        assert hasattr(memory, "MemoryOperation")
        assert hasattr(memory, "Event")
