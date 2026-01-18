"""Agent Orchestrator - Coordinates the full request processing pipeline.

The orchestrator handles the complete flow from voice input to response:
1. MetaAgent classifies intent and evaluates context
2. Routes to appropriate agent (Instant, Action, Interaction)
3. MemoryAgent retrieves relevant context and stores new memories
4. Generates final response for TTS

This is the "brain" that connects all agents into a coherent system.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from barnabeenet.agents.action import ActionAgent
from barnabeenet.agents.instant import InstantAgent
from barnabeenet.agents.interaction import InteractionAgent
from barnabeenet.agents.memory import MemoryAgent, MemoryOperation
from barnabeenet.agents.meta import (
    ClassificationResult,
    IntentCategory,
    MetaAgent,
)
from barnabeenet.services.llm.openrouter import OpenRouterClient

logger = logging.getLogger(__name__)


@dataclass
class RequestContext:
    """Context for a single request through the pipeline."""

    # Request identification
    request_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    conversation_id: str | None = None
    trace_id: str | None = None

    # Input data
    text: str = ""
    speaker: str | None = None
    room: str | None = None

    # Timing
    started_at: datetime = field(default_factory=datetime.now)
    stage_timings: dict[str, float] = field(default_factory=dict)

    # Processing state
    classification: ClassificationResult | None = None
    retrieved_memories: list[str] = field(default_factory=list)
    agent_response: dict[str, Any] | None = None

    # Output
    response_text: str = ""
    actions_taken: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class OrchestratorConfig:
    """Configuration for the orchestrator."""

    # Memory retrieval
    enable_memory_retrieval: bool = True
    enable_memory_storage: bool = True
    max_memories_to_retrieve: int = 5

    # Agent timeouts (ms)
    meta_timeout_ms: int = 500
    instant_timeout_ms: int = 100
    action_timeout_ms: int = 2000
    interaction_timeout_ms: int = 5000


class AgentOrchestrator:
    """Orchestrates the full agent pipeline.

    Flow:
    1. MetaAgent: Classify intent, evaluate context, generate memory queries
    2. MemoryAgent: Retrieve relevant memories based on queries
    3. Route to appropriate handler:
       - INSTANT → InstantAgent (no LLM needed)
       - ACTION → ActionAgent (device control)
       - CONVERSATION/QUERY → InteractionAgent (LLM conversation)
       - MEMORY → MemoryAgent (direct memory operations)
    4. MemoryAgent: Store relevant facts from interaction
    5. Return response for TTS
    """

    def __init__(
        self,
        llm_client: OpenRouterClient | None = None,
        config: OrchestratorConfig | None = None,
    ) -> None:
        """Initialize the orchestrator.

        Args:
            llm_client: Shared LLM client for all agents.
            config: Optional configuration overrides.
        """
        self.config = config or OrchestratorConfig()
        self._llm_client = llm_client

        # Agents (initialized lazily or via init())
        self._meta_agent: MetaAgent | None = None
        self._instant_agent: InstantAgent | None = None
        self._action_agent: ActionAgent | None = None
        self._interaction_agent: InteractionAgent | None = None
        self._memory_agent: MemoryAgent | None = None

        self._initialized = False

    async def init(self) -> None:
        """Initialize all agents."""
        if self._initialized:
            return

        logger.info("Initializing AgentOrchestrator...")

        # Create LLM client if not provided
        if self._llm_client is None:
            import os

            api_key = os.environ.get("LLM_OPENROUTER_API_KEY")
            if api_key:
                self._llm_client = OpenRouterClient(api_key=api_key)
                await self._llm_client.init()
                logger.info("Created shared LLM client")

        # Initialize all agents
        self._meta_agent = MetaAgent(llm_client=self._llm_client)
        await self._meta_agent.init()

        self._instant_agent = InstantAgent()
        await self._instant_agent.init()

        self._action_agent = ActionAgent(llm_client=self._llm_client)
        await self._action_agent.init()

        self._interaction_agent = InteractionAgent(llm_client=self._llm_client)
        await self._interaction_agent.init()

        self._memory_agent = MemoryAgent(llm_client=self._llm_client)
        await self._memory_agent.init()

        self._initialized = True
        logger.info("AgentOrchestrator initialized with all agents")

    async def shutdown(self) -> None:
        """Shutdown all agents."""
        if self._meta_agent:
            await self._meta_agent.shutdown()
        if self._instant_agent:
            await self._instant_agent.shutdown()
        if self._action_agent:
            await self._action_agent.shutdown()
        if self._interaction_agent:
            await self._interaction_agent.shutdown()
        if self._memory_agent:
            await self._memory_agent.shutdown()
        if self._llm_client:
            await self._llm_client.shutdown()

        self._initialized = False
        logger.info("AgentOrchestrator shutdown")

    async def process(
        self,
        text: str,
        speaker: str | None = None,
        room: str | None = None,
        conversation_id: str | None = None,
    ) -> dict[str, Any]:
        """Process a request through the full pipeline.

        Args:
            text: User's input text (from STT)
            speaker: Speaker ID if identified
            room: Room where request originated
            conversation_id: ID for conversation tracking

        Returns:
            Dict containing:
                - response: Text response for TTS
                - intent: Classified intent
                - agent: Which agent handled it
                - actions: Any device actions taken
                - timings: Stage-by-stage timing breakdown
                - request_id: Unique request identifier
        """
        if not self._initialized:
            await self.init()

        # Create request context
        ctx = RequestContext(
            text=text,
            speaker=speaker,
            room=room,
            conversation_id=conversation_id or f"conv_{uuid.uuid4().hex[:8]}",
            trace_id=f"trace_{uuid.uuid4().hex[:8]}",
        )

        total_start = time.perf_counter()

        try:
            # Stage 1: Classification
            await self._classify(ctx)

            # Stage 2: Memory retrieval (if enabled and needed)
            if self.config.enable_memory_retrieval:
                await self._retrieve_memories(ctx)

            # Stage 3: Route to appropriate agent
            await self._route_and_handle(ctx)

            # Stage 4: Store memories (if enabled)
            if self.config.enable_memory_storage:
                await self._store_memories(ctx)

        except Exception as e:
            logger.exception(f"Pipeline error: {e}")
            ctx.response_text = "I'm sorry, I encountered an error. Please try again."
            ctx.agent_response = {"error": str(e)}

        total_ms = (time.perf_counter() - total_start) * 1000
        ctx.stage_timings["total"] = total_ms

        return self._build_response(ctx)

    async def _classify(self, ctx: RequestContext) -> None:
        """Stage 1: Classify intent with MetaAgent."""
        start = time.perf_counter()

        result = await self._meta_agent.handle_input(
            ctx.text,
            {
                "speaker": ctx.speaker,
                "room": ctx.room,
                "conversation_id": ctx.conversation_id,
            },
        )

        ctx.classification = result.get("classification")
        ctx.stage_timings["classification"] = (time.perf_counter() - start) * 1000

        logger.debug(
            f"Classified '{ctx.text[:30]}...' as {ctx.classification.intent.value if ctx.classification else 'unknown'}"
        )

    async def _retrieve_memories(self, ctx: RequestContext) -> None:
        """Stage 2: Retrieve relevant memories."""
        if not ctx.classification or not ctx.classification.memory_queries:
            return

        start = time.perf_counter()

        # Use memory queries from MetaAgent
        queries = ctx.classification.memory_queries
        result = await self._memory_agent.handle_input(
            queries.primary_query,
            {
                "operation": MemoryOperation.RETRIEVE,
                "memory_queries": queries,
                "participants": queries.relevant_people,
                "max_results": self.config.max_memories_to_retrieve,
            },
        )

        # Extract memory content strings
        if result.get("memories"):
            ctx.retrieved_memories = [m["content"] for m in result["memories"]]

        ctx.stage_timings["memory_retrieval"] = (time.perf_counter() - start) * 1000

        logger.debug(f"Retrieved {len(ctx.retrieved_memories)} memories")

    async def _route_and_handle(self, ctx: RequestContext) -> None:
        """Stage 3: Route to appropriate agent and handle."""
        start = time.perf_counter()

        if not ctx.classification:
            # Fallback to interaction agent
            intent = IntentCategory.CONVERSATION
        else:
            intent = ctx.classification.intent

        # Build context for agent
        agent_context = {
            "speaker": ctx.speaker,
            "room": ctx.room,
            "conversation_id": ctx.conversation_id,
            "retrieved_memories": ctx.retrieved_memories,
            "meta_context": {
                "emotional_tone": ctx.classification.context.emotional_tone.value
                if ctx.classification and ctx.classification.context
                else "neutral",
                "urgency": ctx.classification.context.urgency_level.value
                if ctx.classification and ctx.classification.context
                else "low",
            }
            if ctx.classification
            else {},
            "sub_category": ctx.classification.sub_category if ctx.classification else None,
        }

        # Route based on intent
        if intent == IntentCategory.INSTANT:
            ctx.agent_response = await self._instant_agent.handle_input(ctx.text, agent_context)
            agent_name = "instant"

        elif intent == IntentCategory.ACTION:
            ctx.agent_response = await self._action_agent.handle_input(ctx.text, agent_context)
            agent_name = "action"
            # Track device actions
            if ctx.agent_response.get("action"):
                ctx.actions_taken.append(ctx.agent_response["action"])

        elif intent == IntentCategory.MEMORY:
            # Direct memory operation
            ctx.agent_response = await self._memory_agent.handle_input(ctx.text, agent_context)
            agent_name = "memory"

        elif intent == IntentCategory.EMERGENCY:
            # Emergency: Use interaction agent with urgency flag
            agent_context["emergency"] = True
            ctx.agent_response = await self._interaction_agent.handle_input(ctx.text, agent_context)
            agent_name = "interaction"

        else:
            # CONVERSATION, QUERY, UNKNOWN → Interaction Agent
            ctx.agent_response = await self._interaction_agent.handle_input(ctx.text, agent_context)
            agent_name = "interaction"

        # Extract response text
        ctx.response_text = ctx.agent_response.get("response", "")
        ctx.agent_response["_agent_name"] = agent_name

        ctx.stage_timings["agent_handling"] = (time.perf_counter() - start) * 1000

        logger.debug(f"Handled by {agent_name} agent")

    async def _store_memories(self, ctx: RequestContext) -> None:
        """Stage 4: Store relevant facts from the interaction."""
        # Only store for conversation-type interactions
        if not ctx.classification:
            return

        intent = ctx.classification.intent
        if intent not in (
            IntentCategory.CONVERSATION,
            IntentCategory.QUERY,
        ):
            return

        start = time.perf_counter()

        # Create event for memory generation
        event = {
            "id": f"event_{ctx.request_id}",
            "type": "conversation",
            "timestamp": ctx.started_at.isoformat(),
            "details": f"User said: {ctx.text}. Barnabee responded: {ctx.response_text}",
            "speaker_id": ctx.speaker,
            "room": ctx.room,
            "context": {
                "intent": intent.value,
                "emotional_tone": ctx.classification.context.emotional_tone.value
                if ctx.classification.context
                else "neutral",
            },
        }

        # Generate memory from event (async, non-blocking for response)
        try:
            await self._memory_agent.handle_input(
                "",
                {
                    "operation": MemoryOperation.GENERATE,
                    "events": [event],
                },
            )
        except Exception as e:
            logger.warning(f"Memory storage failed: {e}")

        ctx.stage_timings["memory_storage"] = (time.perf_counter() - start) * 1000

    def _build_response(self, ctx: RequestContext) -> dict[str, Any]:
        """Build the final response dict."""
        return {
            "response": ctx.response_text,
            "request_id": ctx.request_id,
            "conversation_id": ctx.conversation_id,
            "trace_id": ctx.trace_id,
            "intent": ctx.classification.intent.value if ctx.classification else "unknown",
            "intent_confidence": ctx.classification.confidence if ctx.classification else 0.0,
            "agent": ctx.agent_response.get("_agent_name", "unknown")
            if ctx.agent_response
            else "unknown",
            "speaker": ctx.speaker,
            "room": ctx.room,
            "actions": ctx.actions_taken,
            "memories_used": len(ctx.retrieved_memories),
            "timings": ctx.stage_timings,
        }

    # Convenience methods for direct agent access
    def get_meta_agent(self) -> MetaAgent | None:
        return self._meta_agent

    def get_instant_agent(self) -> InstantAgent | None:
        return self._instant_agent

    def get_action_agent(self) -> ActionAgent | None:
        return self._action_agent

    def get_interaction_agent(self) -> InteractionAgent | None:
        return self._interaction_agent

    def get_memory_agent(self) -> MemoryAgent | None:
        return self._memory_agent


# Global orchestrator instance
_global_orchestrator: AgentOrchestrator | None = None


def get_orchestrator() -> AgentOrchestrator:
    """Get the global orchestrator instance."""
    global _global_orchestrator
    if _global_orchestrator is None:
        _global_orchestrator = AgentOrchestrator()
    return _global_orchestrator


async def process_request(
    text: str,
    speaker: str | None = None,
    room: str | None = None,
    conversation_id: str | None = None,
) -> dict[str, Any]:
    """Convenience function to process a request through the global orchestrator."""
    orchestrator = get_orchestrator()
    return await orchestrator.process(text, speaker, room, conversation_id)


__all__ = [
    "AgentOrchestrator",
    "OrchestratorConfig",
    "RequestContext",
    "get_orchestrator",
    "process_request",
]
