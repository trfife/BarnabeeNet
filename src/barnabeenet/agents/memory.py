"""Memory Agent - Memory storage, retrieval, and generation.

The Memory Agent handles:
- Storing facts and observations from conversations
- Retrieving relevant memories by semantic similarity
- Generating first-person memories from Barnabee's perspective
- Consolidating events into meaningful patterns

Memory Types:
- Working: Short-term session context (10 min TTL)
- Episodic: Specific events and interactions (30 day retention)
- Semantic: Facts, preferences, patterns (indefinite)
- Procedural: Routines and processes (indefinite)
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from barnabeenet.agents.base import Agent
from barnabeenet.services.llm.openrouter import ChatMessage, OpenRouterClient

logger = logging.getLogger(__name__)


class MemoryType(Enum):
    """Types of memory with different retention policies."""

    WORKING = "working"  # 10 min TTL, session context
    EPISODIC = "episodic"  # 30 day retention, specific events
    SEMANTIC = "semantic"  # Indefinite, facts and preferences
    PROCEDURAL = "procedural"  # Indefinite, routines and processes


class MemoryOperation(Enum):
    """Memory operations supported by the agent."""

    STORE = "store"  # Store a new memory
    RETRIEVE = "retrieve"  # Query memories
    GENERATE = "generate"  # Generate memory from events
    CONSOLIDATE = "consolidate"  # Batch process for patterns
    FORGET = "forget"  # Delete specific memories


@dataclass
class Memory:
    """A single memory entry."""

    id: str
    content: str
    memory_type: MemoryType
    importance: float = 0.5  # 0.0-1.0 scale
    created_at: datetime = field(default_factory=datetime.now)
    last_accessed: datetime | None = None
    access_count: int = 0
    participants: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    time_context: str | None = None  # morning, afternoon, evening, night
    day_context: str | None = None  # weekday, weekend
    source_event_ids: list[str] = field(default_factory=list)
    embedding: list[float] | None = None  # For semantic search

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "content": self.content,
            "memory_type": self.memory_type.value,
            "importance": self.importance,
            "created_at": self.created_at.isoformat(),
            "last_accessed": self.last_accessed.isoformat() if self.last_accessed else None,
            "access_count": self.access_count,
            "participants": self.participants,
            "tags": self.tags,
            "time_context": self.time_context,
            "day_context": self.day_context,
            "source_event_ids": self.source_event_ids,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Memory:
        """Create Memory from dictionary."""
        return cls(
            id=data["id"],
            content=data["content"],
            memory_type=MemoryType(data["memory_type"]),
            importance=data.get("importance", 0.5),
            created_at=datetime.fromisoformat(data["created_at"]),
            last_accessed=(
                datetime.fromisoformat(data["last_accessed"]) if data.get("last_accessed") else None
            ),
            access_count=data.get("access_count", 0),
            participants=data.get("participants", []),
            tags=data.get("tags", []),
            time_context=data.get("time_context"),
            day_context=data.get("day_context"),
            source_event_ids=data.get("source_event_ids", []),
        )


@dataclass
class Event:
    """An event to be converted into a memory."""

    id: str
    event_type: str
    timestamp: datetime
    details: str
    speaker_id: str | None = None
    room: str | None = None
    context: dict[str, Any] | None = None


@dataclass
class MemoryConfig:
    """Configuration for the Memory Agent."""

    # Working memory
    working_memory_ttl_seconds: int = 600  # 10 minutes

    # Episodic memory
    episodic_retention_days: int = 30

    # Retrieval settings
    max_retrieval_results: int = 10
    min_relevance_score: float = 0.3

    # Generation settings
    max_events_per_generation: int = 10
    importance_threshold_for_storage: float = 0.3

    # Consolidation settings
    consolidation_batch_size: int = 50


# Prompts for memory operations
MEMORY_GENERATION_PROMPT = """You are creating a memory from Barnabee's first-person perspective about events in the Fife household.

## Memory Guidelines
- Write in first person as Barnabee ("I noticed...", "I observed...")
- Focus on patterns, preferences, and meaningful interactions
- Be concise but capture emotional context
- Include relevant temporal markers (time of day, day of week)
- Note who was involved and their apparent state

## Events to Process
{events}

## Response Format
Generate ONE consolidated memory as JSON:
{{
  "content": "<first-person memory narrative - 1-2 sentences>",
  "type": "<routine|preference|event|relationship|pattern>",
  "importance": <0.0-1.0>,
  "participants": ["<person1>", "<person2>"],
  "tags": ["<tag1>", "<tag2>"],
  "time_context": "<morning|afternoon|evening|night>",
  "day_context": "<weekday|weekend>"
}}

## Examples
- {{"content": "I noticed Thom prefers his coffee around 6:30am on weekdays.", "type": "preference", "importance": 0.6, "participants": ["thom"], "tags": ["coffee", "morning", "routine"], "time_context": "morning", "day_context": "weekday"}}
- {{"content": "The kids had a wonderful time playing together this afternoon.", "type": "event", "importance": 0.5, "participants": ["penelope", "xander"], "tags": ["play", "family"], "time_context": "afternoon", "day_context": "weekend"}}

Respond with ONLY the JSON object, no other text."""

MEMORY_EXTRACTION_PROMPT = """Extract factual information from this conversation that would be useful to remember.

## Conversation
{conversation}

## Guidelines
- Focus on preferences, habits, and meaningful facts
- Ignore trivial small talk
- Note any scheduling information
- Identify recurring patterns

## Response Format
Return a JSON array of extracted facts (or empty array if nothing notable):
[
  {{
    "content": "<fact in first person as Barnabee>",
    "type": "<preference|routine|event|relationship>",
    "importance": <0.0-1.0>,
    "participants": ["<person1>"],
    "tags": ["<tag1>"]
  }}
]

Respond with ONLY the JSON array, no other text."""

MEMORY_QUERY_PROMPT = """Based on this query, generate search terms for finding relevant memories.

## Query
{query}

## Guidelines
- Identify key concepts, people, and topics
- Generate semantic variations
- Consider temporal context

## Response Format
Return JSON:
{{
  "search_terms": ["<term1>", "<term2>"],
  "people_filter": ["<person1>"] or null,
  "memory_types": ["<type1>"] or null,
  "time_context": "<morning|afternoon|evening|night>" or null
}}

Respond with ONLY the JSON object."""


class MemoryAgent(Agent):
    """Agent for memory storage, retrieval, and generation.

    Uses LLM (GPT-4o-mini) for memory generation and extraction.
    Provides semantic search over stored memories.
    """

    name = "memory"

    def __init__(
        self,
        llm_client: OpenRouterClient | None = None,
        config: MemoryConfig | None = None,
    ) -> None:
        """Initialize the Memory Agent.

        Args:
            llm_client: Optional OpenRouter client for LLM operations.
            config: Optional configuration overrides.
        """
        self._llm_client = llm_client
        self._owns_client = llm_client is None
        self.config = config or MemoryConfig()

        # In-memory storage (will be replaced with Redis/vector DB)
        self._memories: dict[str, Memory] = {}
        self._working_memory: dict[str, dict[str, Any]] = {}  # session_id -> context

        self._initialized = False
        self._next_memory_id = 1

    async def init(self) -> None:
        """Initialize the agent."""
        if self._initialized:
            return

        if self._llm_client is None:
            import os

            api_key = os.environ.get("LLM_OPENROUTER_API_KEY")
            if api_key:
                self._llm_client = OpenRouterClient(api_key=api_key)
                await self._llm_client.init()
                logger.info("MemoryAgent created LLM client from environment")
            else:
                logger.warning(
                    "No LLM client provided and LLM_OPENROUTER_API_KEY not set. "
                    "Agent will use fallback memory operations."
                )

        self._initialized = True
        logger.info("MemoryAgent initialized")

    async def shutdown(self) -> None:
        """Clean up resources."""
        if self._owns_client and self._llm_client:
            await self._llm_client.shutdown()
        self._memories.clear()
        self._working_memory.clear()
        self._initialized = False
        logger.info("MemoryAgent shutdown")

    async def handle_input(
        self, text: str, context: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Handle a memory-related request.

        Args:
            text: User's message or operation descriptor
            context: Additional context including:
                - operation: MemoryOperation to perform
                - events: List of events for generation
                - query: Search query for retrieval
                - memory_id: ID for specific memory operations
                - session_id: For working memory operations

        Returns:
            Dict with operation results
        """
        start_time = time.perf_counter()
        ctx = context or {}

        operation = ctx.get("operation", MemoryOperation.RETRIEVE)
        if isinstance(operation, str):
            operation = MemoryOperation(operation)

        result: dict[str, Any]

        if operation == MemoryOperation.STORE:
            result = await self._handle_store(text, ctx)
        elif operation == MemoryOperation.RETRIEVE:
            result = await self._handle_retrieve(text, ctx)
        elif operation == MemoryOperation.GENERATE:
            result = await self._handle_generate(ctx)
        elif operation == MemoryOperation.CONSOLIDATE:
            result = await self._handle_consolidate(ctx)
        elif operation == MemoryOperation.FORGET:
            result = await self._handle_forget(ctx)
        else:
            result = {"error": f"Unknown operation: {operation}"}

        latency_ms = (time.perf_counter() - start_time) * 1000

        return {
            **result,
            "agent": self.name,
            "operation": operation.value,
            "latency_ms": latency_ms,
        }

    # =========================================================================
    # Memory Operations
    # =========================================================================

    async def _handle_store(self, text: str, ctx: dict[str, Any]) -> dict[str, Any]:
        """Store a new memory."""
        memory_type = ctx.get("memory_type", MemoryType.SEMANTIC)
        if isinstance(memory_type, str):
            memory_type = MemoryType(memory_type)

        memory = Memory(
            id=self._generate_memory_id(),
            content=text,
            memory_type=memory_type,
            importance=ctx.get("importance", 0.5),
            participants=ctx.get("participants", []),
            tags=ctx.get("tags", []),
            time_context=ctx.get("time_context"),
            day_context=ctx.get("day_context"),
        )

        self._memories[memory.id] = memory

        return {
            "success": True,
            "memory_id": memory.id,
            "memory": memory.to_dict(),
            "response": f"Memory stored: {memory.content[:50]}...",
        }

    async def _handle_retrieve(self, query: str, ctx: dict[str, Any]) -> dict[str, Any]:
        """Retrieve memories relevant to a query."""
        # If explicit memory queries provided (from MetaAgent)
        memory_queries = ctx.get("memory_queries")
        if memory_queries and hasattr(memory_queries, "primary_query"):
            query = memory_queries.primary_query

        # Simple keyword-based retrieval (will be replaced with vector search)
        matches = self._search_memories(
            query,
            memory_type=ctx.get("memory_type"),
            participants=ctx.get("participants"),
            max_results=ctx.get("max_results", self.config.max_retrieval_results),
        )

        # Update access metadata
        now = datetime.now()
        for memory in matches:
            memory.last_accessed = now
            memory.access_count += 1

        return {
            "success": True,
            "query": query,
            "memories": [m.to_dict() for m in matches],
            "count": len(matches),
            "response": self._format_retrieval_response(matches),
        }

    async def _handle_generate(self, ctx: dict[str, Any]) -> dict[str, Any]:
        """Generate a memory from events using LLM."""
        events = ctx.get("events", [])
        if not events:
            return {
                "success": False,
                "error": "No events provided for memory generation",
            }

        # Convert events to Event objects if needed
        event_objs = []
        for e in events[: self.config.max_events_per_generation]:
            if isinstance(e, Event):
                event_objs.append(e)
            else:
                event_objs.append(
                    Event(
                        id=e.get("id", f"event_{len(event_objs)}"),
                        event_type=e.get("type", "unknown"),
                        timestamp=datetime.fromisoformat(e["timestamp"])
                        if isinstance(e.get("timestamp"), str)
                        else e.get("timestamp", datetime.now()),
                        details=e.get("details", ""),
                        speaker_id=e.get("speaker_id"),
                        room=e.get("room"),
                        context=e.get("context"),
                    )
                )

        if not self._llm_client:
            # Fallback: create simple memory from events
            return self._generate_memory_fallback(event_objs)

        # Format events for LLM
        events_text = self._format_events_for_prompt(event_objs)
        prompt = MEMORY_GENERATION_PROMPT.format(events=events_text)

        try:
            response = await self._llm_client.chat(
                messages=[ChatMessage(role="user", content=prompt)],
                agent_type="memory",
            )

            # Parse JSON response
            memory_data = json.loads(response.text)
            memory_type = self._map_memory_type(memory_data.get("type", "event"))

            # Only store if importance meets threshold
            importance = memory_data.get("importance", 0.5)
            if importance < self.config.importance_threshold_for_storage:
                return {
                    "success": True,
                    "stored": False,
                    "reason": "Importance below threshold",
                    "memory_data": memory_data,
                    "response": "Event not significant enough to store.",
                }

            # Create and store memory
            memory = Memory(
                id=self._generate_memory_id(),
                content=memory_data["content"],
                memory_type=memory_type,
                importance=importance,
                participants=memory_data.get("participants", []),
                tags=memory_data.get("tags", []),
                time_context=memory_data.get("time_context"),
                day_context=memory_data.get("day_context"),
                source_event_ids=[e.id for e in event_objs],
            )

            self._memories[memory.id] = memory

            return {
                "success": True,
                "stored": True,
                "memory_id": memory.id,
                "memory": memory.to_dict(),
                "response": f"Memory generated: {memory.content}",
            }

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            return self._generate_memory_fallback(event_objs)
        except Exception as e:
            logger.error(f"Memory generation failed: {e}")
            return self._generate_memory_fallback(event_objs)

    async def _handle_consolidate(self, ctx: dict[str, Any]) -> dict[str, Any]:
        """Consolidate recent memories into patterns."""
        # Get recent episodic memories
        episodic = [m for m in self._memories.values() if m.memory_type == MemoryType.EPISODIC]

        if len(episodic) < 3:
            return {
                "success": True,
                "consolidated": 0,
                "response": "Not enough memories to consolidate.",
            }

        # For now, just report what would be consolidated
        # Real implementation would use LLM to find patterns
        return {
            "success": True,
            "episodic_count": len(episodic),
            "response": f"Found {len(episodic)} episodic memories available for consolidation.",
        }

    async def _handle_forget(self, ctx: dict[str, Any]) -> dict[str, Any]:
        """Forget (delete) specific memories."""
        memory_id = ctx.get("memory_id")
        if not memory_id:
            return {"success": False, "error": "No memory_id provided"}

        if memory_id in self._memories:
            del self._memories[memory_id]
            return {
                "success": True,
                "memory_id": memory_id,
                "response": "Memory has been forgotten.",
            }

        return {
            "success": False,
            "error": f"Memory not found: {memory_id}",
        }

    # =========================================================================
    # Extraction from Conversations
    # =========================================================================

    async def extract_from_conversation(
        self, conversation: list[dict[str, str]], speaker: str | None = None
    ) -> list[Memory]:
        """Extract memories from a conversation.

        Args:
            conversation: List of {role, content} message dicts
            speaker: The primary speaker/user in the conversation

        Returns:
            List of extracted Memory objects
        """
        if not self._llm_client:
            return []

        # Format conversation for LLM
        conv_text = "\n".join(f"{msg['role'].title()}: {msg['content']}" for msg in conversation)
        prompt = MEMORY_EXTRACTION_PROMPT.format(conversation=conv_text)

        try:
            response = await self._llm_client.chat(
                messages=[ChatMessage(role="user", content=prompt)],
                agent_type="memory",
            )

            facts = json.loads(response.text)
            memories = []

            for fact in facts:
                importance = fact.get("importance", 0.5)
                if importance < self.config.importance_threshold_for_storage:
                    continue

                memory = Memory(
                    id=self._generate_memory_id(),
                    content=fact["content"],
                    memory_type=self._map_memory_type(fact.get("type", "semantic")),
                    importance=importance,
                    participants=fact.get("participants", [speaker] if speaker else []),
                    tags=fact.get("tags", []),
                )

                self._memories[memory.id] = memory
                memories.append(memory)

            return memories

        except Exception as e:
            logger.error(f"Conversation extraction failed: {e}")
            return []

    # =========================================================================
    # Working Memory
    # =========================================================================

    def set_working_memory(self, session_id: str, key: str, value: Any) -> None:
        """Set a value in working memory for a session."""
        if session_id not in self._working_memory:
            self._working_memory[session_id] = {}
        self._working_memory[session_id][key] = value

    def get_working_memory(self, session_id: str, key: str, default: Any = None) -> Any:
        """Get a value from working memory."""
        return self._working_memory.get(session_id, {}).get(key, default)

    def clear_working_memory(self, session_id: str) -> None:
        """Clear working memory for a session."""
        if session_id in self._working_memory:
            del self._working_memory[session_id]

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _generate_memory_id(self) -> str:
        """Generate a unique memory ID."""
        memory_id = f"mem_{self._next_memory_id:06d}"
        self._next_memory_id += 1
        return memory_id

    def _search_memories(
        self,
        query: str,
        memory_type: MemoryType | str | None = None,
        participants: list[str] | None = None,
        max_results: int = 10,
    ) -> list[Memory]:
        """Search memories by keyword matching.

        Note: This is a simple implementation. Production would use
        vector similarity search.
        """
        query_lower = query.lower()
        query_words = set(query_lower.split())

        results = []
        for memory in self._memories.values():
            # Type filter
            if memory_type:
                if isinstance(memory_type, str):
                    memory_type = MemoryType(memory_type)
                if memory.memory_type != memory_type:
                    continue

            # Participant filter
            if participants:
                if not any(p in memory.participants for p in participants):
                    continue

            # Keyword matching
            content_lower = memory.content.lower()
            tag_text = " ".join(memory.tags).lower()
            combined = content_lower + " " + tag_text

            # Count matching words
            matches = sum(1 for word in query_words if word in combined)
            if matches > 0:
                results.append((memory, matches))

        # Sort by match count and importance
        results.sort(key=lambda x: (x[1], x[0].importance), reverse=True)

        return [m for m, _ in results[:max_results]]

    def _format_events_for_prompt(self, events: list[Event]) -> str:
        """Format events for LLM prompt."""
        lines = []
        for i, event in enumerate(events, 1):
            lines.append(f"### Event {i}")
            lines.append(f"Time: {event.timestamp.strftime('%I:%M %p on %A')}")
            lines.append(f"Type: {event.event_type}")
            if event.speaker_id:
                lines.append(f"Person: {event.speaker_id}")
            if event.room:
                lines.append(f"Location: {event.room}")
            lines.append(f"Details: {event.details}")
            if event.context:
                lines.append(f"Context: {event.context}")
            lines.append("")
        return "\n".join(lines)

    def _format_retrieval_response(self, memories: list[Memory]) -> str:
        """Format retrieved memories into a response."""
        if not memories:
            return "I don't have any relevant memories about that."

        if len(memories) == 1:
            return f"I recall: {memories[0].content}"

        return f"I found {len(memories)} related memories. " + "; ".join(
            m.content for m in memories[:3]
        )

    def _generate_memory_fallback(self, events: list[Event]) -> dict[str, Any]:
        """Generate simple memory without LLM."""
        if not events:
            return {
                "success": False,
                "error": "No events provided",
            }

        # Create simple summary
        event = events[0]
        content = f"I observed: {event.details}"

        memory = Memory(
            id=self._generate_memory_id(),
            content=content,
            memory_type=MemoryType.EPISODIC,
            importance=0.5,
            participants=[event.speaker_id] if event.speaker_id else [],
            source_event_ids=[e.id for e in events],
        )

        self._memories[memory.id] = memory

        return {
            "success": True,
            "stored": True,
            "memory_id": memory.id,
            "memory": memory.to_dict(),
            "fallback": True,
            "response": f"Memory stored (fallback): {content}",
        }

    def _map_memory_type(self, type_str: str) -> MemoryType:
        """Map string type to MemoryType enum."""
        mapping = {
            "routine": MemoryType.PROCEDURAL,
            "preference": MemoryType.SEMANTIC,
            "event": MemoryType.EPISODIC,
            "relationship": MemoryType.SEMANTIC,
            "pattern": MemoryType.SEMANTIC,
            "working": MemoryType.WORKING,
            "episodic": MemoryType.EPISODIC,
            "semantic": MemoryType.SEMANTIC,
            "procedural": MemoryType.PROCEDURAL,
        }
        return mapping.get(type_str.lower(), MemoryType.EPISODIC)

    # =========================================================================
    # Public Query Methods
    # =========================================================================

    def get_memory(self, memory_id: str) -> Memory | None:
        """Get a specific memory by ID."""
        return self._memories.get(memory_id)

    def get_all_memories(self, memory_type: MemoryType | None = None) -> list[Memory]:
        """Get all memories, optionally filtered by type."""
        if memory_type:
            return [m for m in self._memories.values() if m.memory_type == memory_type]
        return list(self._memories.values())

    def get_memory_count(self) -> dict[str, int]:
        """Get count of memories by type."""
        counts: dict[str, int] = {}
        for memory in self._memories.values():
            type_name = memory.memory_type.value
            counts[type_name] = counts.get(type_name, 0) + 1
        return counts


__all__ = [
    "MemoryAgent",
    "MemoryConfig",
    "Memory",
    "MemoryType",
    "MemoryOperation",
    "Event",
]
