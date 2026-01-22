"""Agent Orchestrator - Coordinates the full request processing pipeline.

The orchestrator handles the complete flow from voice input to response:
1. MetaAgent classifies intent and evaluates context
2. Routes to appropriate agent (Instant, Action, Interaction)
3. MemoryAgent retrieves relevant context and stores new memories
4. Executes device actions via Home Assistant
5. Generates final response for TTS

This is the "brain" that connects all agents into a coherent system.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

from barnabeenet.agents.action import ActionAgent

if TYPE_CHECKING:
    from barnabeenet.services.homeassistant.client import HomeAssistantClient
from barnabeenet.agents.instant import InstantAgent
from barnabeenet.agents.interaction import InteractionAgent
from barnabeenet.agents.memory import MemoryAgent, MemoryOperation
from barnabeenet.agents.meta import (
    ClassificationResult,
    IntentCategory,
    MetaAgent,
)
from barnabeenet.services.activity_log import get_activity_logger
from barnabeenet.services.llm.openrouter import OpenRouterClient
from barnabeenet.services.metrics_store import get_metrics_store
from barnabeenet.services.pipeline_signals import PipelineLogger, SignalType

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
    5. Execute device actions via Home Assistant
    6. Return response for TTS
    """

    def __init__(
        self,
        llm_client: OpenRouterClient | None = None,
        config: OrchestratorConfig | None = None,
        pipeline_logger: PipelineLogger | None = None,
        ha_client: HomeAssistantClient | None = None,
    ) -> None:
        """Initialize the orchestrator.

        Args:
            llm_client: Shared LLM client for all agents.
            config: Optional configuration overrides.
            pipeline_logger: Logger for pipeline signals (for dashboard).
            ha_client: Home Assistant client for action execution.
        """
        self.config = config or OrchestratorConfig()
        self._llm_client = llm_client
        self._pipeline_logger = pipeline_logger
        self._ha_client: HomeAssistantClient | None = ha_client

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
            from barnabeenet.config import get_settings
            from barnabeenet.services.llm.openrouter import AgentModelConfig

            settings = get_settings()

            # First try to get API key from encrypted provider config (dashboard-configured)
            api_key = await self._get_provider_api_key("openrouter")

            # Fall back to environment variable if not in provider config
            if not api_key:
                api_key = settings.llm.openrouter_api_key

            if api_key:
                # Use settings for model configuration
                model_config = AgentModelConfig.from_settings(settings.llm)
                self._llm_client = OpenRouterClient(
                    api_key=api_key,
                    model_config=model_config,
                    site_url=settings.llm.openrouter_site_url,
                    site_name=settings.llm.openrouter_site_name,
                )
                await self._llm_client.init()
                logger.info("Created shared LLM client (from provider config or settings)")
            else:
                logger.warning(
                    "No API key found in provider config or environment. Agents will use fallback responses."
                )

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

    async def _get_provider_api_key(self, provider: str) -> str | None:
        """Get API key from encrypted provider config.

        Args:
            provider: Provider name (e.g., 'openrouter')

        Returns:
            Decrypted API key or None if not configured
        """
        try:
            import os

            import redis.asyncio as redis

            from barnabeenet.services.secrets import get_secrets_service

            # Get Redis connection
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
            redis_client = redis.from_url(redis_url, decode_responses=True)

            # Use the singleton secrets service
            secrets_service = await get_secrets_service(redis_client)

            # Get secrets for this provider
            provider_secrets = await secrets_service.get_secrets_for_provider(provider)

            await redis_client.aclose()

            if provider_secrets:
                # Look for the API key (stored as {provider}_api_key)
                api_key = provider_secrets.get(f"{provider}_api_key")
                if api_key:
                    logger.info(f"Found {provider} API key in provider config")
                    return api_key

            return None
        except Exception as e:
            logger.debug(f"Could not get provider API key from config: {e}")
            return None

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

        # Start activity trace
        activity_logger = get_activity_logger()
        trace_id = ctx.trace_id or f"trace_{uuid.uuid4().hex[:8]}"
        ctx.trace_id = trace_id
        await activity_logger.start_trace(
            trace_id=trace_id,
            user_input=text,
            speaker=speaker,
            room=room,
            input_type="voice",
        )

        # Start pipeline trace
        if self._pipeline_logger:
            self._pipeline_logger.start_trace(
                trace_id=ctx.trace_id,
                input_text=text,
                input_type="voice",
                speaker=speaker,
                room=room,
            )

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

            # Log error signal
            if self._pipeline_logger:
                await self._pipeline_logger.log_signal(
                    trace_id=ctx.trace_id,
                    signal_type=SignalType.ERROR,
                    summary=f"Pipeline error: {str(e)}",
                    success=False,
                    error=str(e),
                )
            ctx.agent_response = {"error": str(e)}

        total_ms = (time.perf_counter() - total_start) * 1000
        ctx.stage_timings["total"] = total_ms

        # Complete pipeline trace
        if self._pipeline_logger:
            agent_name = ctx.agent_response.get("_agent_name") if ctx.agent_response else None
            intent_val = ctx.classification.intent.value if ctx.classification else None
            confidence = ctx.classification.confidence if ctx.classification else None

            # Extract error details from agent response
            error_info = ctx.agent_response.get("error") if ctx.agent_response else None
            has_error = error_info is not None
            error_str = None
            if error_info:
                # Format error string with all relevant details
                if isinstance(error_info, dict):
                    error_parts = []
                    if error_info.get("agent"):
                        error_parts.append(f"Agent: {error_info['agent']}")
                    if error_info.get("model"):
                        error_parts.append(f"Model: {error_info['model']}")
                    if error_info.get("type"):
                        error_parts.append(f"Error: {error_info['type']}")
                    if error_info.get("status_code"):
                        error_parts.append(f"Status: {error_info['status_code']}")
                    if error_info.get("message"):
                        error_parts.append(f"Details: {error_info['message'][:200]}")
                    error_str = " | ".join(error_parts)
                else:
                    # error_info is a string
                    error_str = str(error_info)

            await self._pipeline_logger.complete_trace(
                trace_id=ctx.trace_id,
                response_text=ctx.response_text,
                response_type="tts",
                success=not has_error,
                error=error_str,
                agent_used=agent_name,
                intent=intent_val,
                intent_confidence=confidence,
                ha_actions=ctx.actions_taken if ctx.actions_taken else None,
                memories_retrieved=ctx.retrieved_memories if ctx.retrieved_memories else None,
            )

        # Complete activity trace
        error_info = ctx.agent_response.get("error") if ctx.agent_response else None
        error_str = None
        if error_info:
            if isinstance(error_info, dict):
                # Structured error from agents like InteractionAgent
                error_parts = [f"{k}: {v}" for k, v in error_info.items() if v is not None]
                error_str = " | ".join(error_parts)
            else:
                # Simple string error
                error_str = str(error_info)

        await activity_logger.complete_trace(
            trace_id=trace_id,
            response=ctx.response_text,
            success=error_info is None,
            error=error_str,
        )

        # Record pipeline latency for metrics graphs
        try:
            metrics_store = await get_metrics_store()
            await metrics_store.record_latency(
                "pipeline",
                total_ms,
                {"intent": ctx.classification.intent.value if ctx.classification else None},
            )
            if "classification" in ctx.stage_timings:
                await metrics_store.record_latency(
                    "llm", ctx.stage_timings["classification"], {"stage": "classification"}
                )
        except Exception as e:
            logger.debug(f"Failed to record pipeline metrics: {e}")

        return self._build_response(ctx)

    async def _classify(self, ctx: RequestContext) -> None:
        """Stage 1: Classify intent with MetaAgent (with HA context for better device detection)."""
        start = time.perf_counter()

        # Get lightweight HA context (entity names/domains only, no states)
        ha_context_dict = {}
        try:
            from barnabeenet.services.homeassistant.context import get_ha_context_service

            context_service = await get_ha_context_service()
            ha_context = await context_service.get_context_for_meta_agent()
            ha_context_dict = {
                "entity_names": ha_context.entity_names,
                "entity_domains": ha_context.entity_domains,
                "area_names": ha_context.area_names,
            }
        except Exception as e:
            logger.debug("Could not get HA context for classification: %s", e)

        # Call classify() directly to get ClassificationResult object
        ctx.classification = await self._meta_agent.classify(
            ctx.text,
            {
                "speaker": ctx.speaker,
                "room": ctx.room,
                "conversation_id": ctx.conversation_id,
            },
            ha_context=ha_context_dict,
        )

        latency_ms = (time.perf_counter() - start) * 1000
        ctx.stage_timings["classification"] = latency_ms

        # Log to activity logger
        if ctx.classification and ctx.trace_id:
            activity_logger = get_activity_logger()
            await activity_logger.add_step(
                trace_id=ctx.trace_id,
                agent="meta",
                action="classified",
                summary=f"Intent: {ctx.classification.intent.value} ({ctx.classification.confidence:.0%})",
                detail=f"Sub-category: {ctx.classification.sub_category or 'none'}",
                duration_ms=latency_ms,
            )

        # Log classification signal (existing pipeline logger)
        if self._pipeline_logger and ctx.classification:
            await self._pipeline_logger.log_signal(
                trace_id=ctx.trace_id,
                signal_type=SignalType.META_CLASSIFY,
                summary=f"Intent: {ctx.classification.intent.value} ({ctx.classification.confidence:.0%})",
                latency_ms=latency_ms,
                success=True,
                extra_data={
                    "intent": ctx.classification.intent.value,
                    "confidence": ctx.classification.confidence,
                    "sub_category": ctx.classification.sub_category,
                },
            )

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

        latency_ms = (time.perf_counter() - start) * 1000
        ctx.stage_timings["memory_retrieval"] = latency_ms

        # Log to activity logger
        if ctx.trace_id:
            activity_logger = get_activity_logger()
            await activity_logger.add_step(
                trace_id=ctx.trace_id,
                agent="memory",
                action="retrieved",
                summary=f"Retrieved {len(ctx.retrieved_memories)} relevant memories",
                detail=f"Query: {queries.primary_query[:80]}..."
                if queries.primary_query and len(queries.primary_query) > 80
                else queries.primary_query,
                duration_ms=latency_ms,
            )

        # Log memory retrieval signal (existing pipeline logger)
        if self._pipeline_logger:
            await self._pipeline_logger.log_signal(
                trace_id=ctx.trace_id,
                signal_type=SignalType.MEMORY_RETRIEVE,
                summary=f"Retrieved {len(ctx.retrieved_memories)} memories",
                latency_ms=latency_ms,
                success=True,
                extra_data={
                    "query": queries.primary_query[:100] if queries.primary_query else None,
                    "count": len(ctx.retrieved_memories),
                },
            )

        logger.debug(f"Retrieved {len(ctx.retrieved_memories)} memories")

    async def _get_profile_context(
        self, speaker: str | None, room: str | None
    ) -> dict[str, Any] | None:
        """Get profile context for the current speaker.

        Returns profile context dict with public and optionally private profile blocks
        based on privacy zone (room). Returns None if no profile found.

        Includes real-time location data from Home Assistant if available.
        """
        if not speaker:
            return None

        try:
            import os

            import redis.asyncio as aioredis

            from barnabeenet.services.profiles import PrivacyZone, get_profile_service

            # Get Redis client for profile storage
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
            redis_client = aioredis.from_url(redis_url, decode_responses=True)

            # Pass both Redis and HA client
            profile_service = await get_profile_service(
                redis_client=redis_client, ha_client=self._ha_client
            )

            # Map room to privacy zone
            # Private rooms (bedrooms, offices) get full private context
            private_rooms = {"bedroom", "office", "study", "bathroom"}
            room_lower = (room or "").lower()
            if any(r in room_lower for r in private_rooms):
                privacy_zone = PrivacyZone.PRIVATE_ROOM
            else:
                privacy_zone = PrivacyZone.COMMON_AREA_ALONE

            context = await profile_service.get_profile_context(
                speaker_id=speaker,
                conversation_participants=[speaker],  # Single participant
                privacy_zone=privacy_zone,
            )

            if context:
                logger.debug(
                    f"Retrieved profile context for {speaker} ({context.context_type}) in {room}"
                )
                return context.model_dump()
            return None

        except Exception as e:
            logger.warning(f"Failed to get profile context for {speaker}: {e}")
            return None

    async def _get_mentioned_profiles(
        self, text: str, speaker: str | None
    ) -> list[dict[str, Any]] | None:
        """Look up profiles for any family members mentioned in the text.

        This allows Barnabee to answer questions about family members
        using their profile data, including real-time location.

        Args:
            text: The user's input text
            speaker: Current speaker (excluded from results)

        Returns:
            List of profile summaries for mentioned family members
        """
        try:
            import os

            import redis.asyncio as aioredis

            from barnabeenet.services.profiles import PrivacyZone, get_profile_service

            # Get Redis client for profile storage
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
            redis_client = aioredis.from_url(redis_url, decode_responses=True)

            # Get HA client for location lookups (may not be available)
            ha_client = self._ha_client
            if ha_client is None:
                # Try to get the global HA client
                try:
                    from barnabeenet.api.routes.homeassistant import (
                        get_ha_client as get_global_ha_client,
                    )

                    ha_client = await get_global_ha_client()
                except Exception:
                    pass  # HA client not available, location won't be included

            # Pass both Redis and HA client for real-time location data
            profile_service = await get_profile_service(
                redis_client=redis_client, ha_client=ha_client
            )

            # Get all profiles
            all_profiles = await profile_service.get_all_profiles()
            if not all_profiles:
                return None

            # Find mentions in the text (case-insensitive)
            text_lower = text.lower()
            mentioned = []

            for profile in all_profiles:
                member_id = profile.member_id.lower()
                name = profile.name.lower()
                # Also check first name only for natural speech ("where is Elizabeth")
                first_name = name.split()[0] if " " in name else name

                # Skip the speaker (we already have their context)
                if speaker and member_id == speaker.lower():
                    continue

                # Check if member is mentioned by ID, full name, or first name
                # Use word boundary check for first name to avoid false positives
                id_match = member_id in text_lower
                name_match = name in text_lower
                first_name_match = f" {first_name}" in f" {text_lower}"

                if id_match or name_match or first_name_match:
                    # Get their profile context including location
                    context = await profile_service.get_profile_context(
                        speaker_id=profile.member_id,
                        conversation_participants=[profile.member_id],
                        privacy_zone=PrivacyZone.COMMON_AREA_OCCUPIED,  # Only public info
                    )

                    # Create summary with location data
                    profile_summary = {
                        "member_id": profile.member_id,
                        "name": profile.name,
                        "relationship": profile.relationship_to_primary.value
                        if hasattr(profile.relationship_to_primary, "value")
                        else str(profile.relationship_to_primary),
                        "communication_style": profile.public.communication_style,
                        "interests": profile.public.interests,
                        "preferences": profile.public.preferences,
                    }

                    # Add location if available
                    if context and context.location:
                        profile_summary["location"] = context.location.model_dump()

                    mentioned.append(profile_summary)

            return mentioned if mentioned else None

        except Exception as e:
            logger.warning(f"Failed to get mentioned profiles: {e}")
            return None

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

        # Add profile context if speaker is identified
        if ctx.speaker:
            profile_context = await self._get_profile_context(ctx.speaker, ctx.room)
            if profile_context:
                agent_context["profile"] = profile_context

        # Look up profiles for any family members mentioned in the text
        mentioned_profiles = await self._get_mentioned_profiles(ctx.text, ctx.speaker)
        if mentioned_profiles:
            agent_context["mentioned_profiles"] = mentioned_profiles

        # Log routing decision
        if self._pipeline_logger:
            await self._pipeline_logger.log_signal(
                trace_id=ctx.trace_id,
                signal_type=SignalType.AGENT_ROUTE,
                summary=f"Routing to {intent.value} agent",
                success=True,
                extra_data={"intent": intent.value},
            )

        # Route based on intent
        if intent == IntentCategory.INSTANT:
            ctx.agent_response = await self._instant_agent.handle_input(ctx.text, agent_context)
            agent_name = "instant"

        elif intent == IntentCategory.ACTION:
            # Get HA context just-in-time for Action Agent (entity states for device control)
            try:
                from barnabeenet.services.homeassistant.context import get_ha_context_service

                context_service = await get_ha_context_service(self._ha_client)
                # Extract potential entity names from text for targeted loading
                # For now, pass None to load states when needed during resolution
                ha_action_context = await context_service.get_context_for_action_agent(None)
                agent_context["ha_context"] = {
                    "entity_names": ha_action_context.entity_names,
                    "entity_domains": ha_action_context.entity_domains,
                    "area_names": ha_action_context.area_names,
                    "entity_states": ha_action_context.entity_states,  # Loaded just-in-time
                    "entity_details": {
                        eid: {
                            "entity_id": meta.entity_id,
                            "domain": meta.domain,
                            "friendly_name": meta.friendly_name,
                            "area_id": meta.area_id,
                        }
                        for eid, meta in ha_action_context.entity_details.items()
                    },
                }
            except Exception as e:
                logger.debug("Could not get HA context for Action Agent: %s", e)
                agent_context["ha_context"] = {}

            # Check for compound commands (e.g., "turn on X and turn off Y")
            from barnabeenet.agents.parsing.compound_parser import CompoundCommandParser

            parser = CompoundCommandParser()
            parsed = parser.parse(ctx.text)

            if parsed.is_compound and len(parsed.segments) > 1:
                # Handle compound command - execute each segment
                agent_name = "action"
                all_results = []
                all_actions = []
                failed_any = False

                for segment in parsed.segments:
                    # Use raw_text if available - it preserves the original phrasing
                    # which is important for entity resolution (e.g., "office light"
                    # should resolve to "light.office_switch" not "any light in office")
                    # Only add location if raw_text is not available (fallback)
                    if segment.raw_text:
                        segment_text = segment.raw_text
                    else:
                        segment_text = f"{segment.action} {segment.target_noun}"
                        if segment.location:
                            segment_text += f" in {segment.location}"

                    # Parse and execute each segment
                    segment_response = await self._action_agent.handle_input(
                        segment_text, agent_context
                    )

                    if segment_response.get("action"):
                        action_spec = segment_response["action"]
                        all_actions.append(action_spec)
                        ctx.actions_taken.append(action_spec)

                        # Execute via HA
                        execution_result = await self._execute_ha_action(action_spec, ctx)
                        all_results.append(
                            {
                                "segment": segment_text,
                                "action": action_spec,
                                "result": execution_result,
                            }
                        )
                        if not execution_result.get("success"):
                            failed_any = True

                # Build combined response
                successful = [r for r in all_results if r["result"].get("success")]
                failed = [r for r in all_results if not r["result"].get("success")]

                if not failed:
                    response_text = f"Done! I executed {len(successful)} commands."
                elif not successful:
                    response_text = f"I couldn't execute any of the {len(all_results)} commands."
                else:
                    response_text = (
                        f"Partially done: {len(successful)} succeeded, {len(failed)} failed."
                    )

                ctx.agent_response = {
                    "_agent_name": "action",
                    "response": response_text,
                    "actions": all_actions,
                    "compound_results": all_results,
                    "success": not failed_any,
                }
            else:
                # Single command - original flow
                ctx.agent_response = await self._action_agent.handle_input(ctx.text, agent_context)
                agent_name = "action"
                # Track device actions (only if action field exists - timer commands don't have this)
                if ctx.agent_response.get("action"):
                    action_spec = ctx.agent_response["action"]
                    ctx.actions_taken.append(action_spec)

                    # Execute the action via Home Assistant
                    execution_result = await self._execute_ha_action(action_spec, ctx)

                    # Store execution result for trace details
                    ctx.agent_response["_execution_result"] = execution_result

                    # Update response based on execution result
                    if not execution_result.get("executed"):
                        # Action not executed - tell user why
                        error_msg = execution_result.get("message", "unknown error")
                        ctx.agent_response["response"] = (
                            f"I understood you want to {action_spec.get('service', 'do something')}, "
                            f"but I couldn't do it: {error_msg}. "
                            "Check Home Assistant connection in Configuration."
                        )
                    elif not execution_result.get("success"):
                        # Action failed to execute
                        ctx.agent_response["response"] = execution_result.get(
                            "error", "Sorry, I couldn't complete that action."
                        )
                    # Add execution info to action
                    action_spec["executed"] = execution_result.get("executed", False)
                    action_spec["execution_message"] = execution_result.get("message", "")

                    # Log HA action
                    if self._pipeline_logger:
                        await self._pipeline_logger.log_signal(
                            trace_id=ctx.trace_id,
                            signal_type=SignalType.HA_SERVICE_CALL
                            if execution_result.get("executed")
                            else SignalType.HA_ACTION,
                            summary=f"Action: {action_spec.get('service', 'unknown')} - {'Executed' if execution_result.get('success') else 'Not executed'}",
                            success=execution_result.get("success", False),
                            extra_data={
                                **action_spec,
                                "execution_result": execution_result,
                            },
                        )
                # Timer commands and other non-action responses don't need HA execution

        elif intent == IntentCategory.MEMORY:
            # Direct memory operation - determine operation from sub_category
            sub_category = ctx.classification.sub_category if ctx.classification else None
            if sub_category == "store":
                operation = MemoryOperation.STORE
            elif sub_category == "forget":
                operation = MemoryOperation.FORGET
            else:
                operation = MemoryOperation.RETRIEVE

            agent_context["operation"] = operation
            ctx.agent_response = await self._memory_agent.handle_input(ctx.text, agent_context)
            agent_name = "memory"

        elif intent == IntentCategory.EMERGENCY:
            # Emergency: Use interaction agent with urgency flag
            agent_context["emergency"] = True
            ctx.agent_response = await self._interaction_agent.handle_input(ctx.text, agent_context)
            agent_name = "interaction"

        elif intent == IntentCategory.SELF_IMPROVEMENT:
            # Self-improvement: Route to Self-Improvement Agent
            import asyncio

            from barnabeenet.agents.self_improvement import get_self_improvement_agent

            agent_name = "self_improvement"
            try:
                si_agent = await get_self_improvement_agent()
                if not si_agent.is_available():
                    ctx.agent_response = {
                        "_agent_name": agent_name,
                        "response": "Sorry, the self-improvement system isn't available right now. "
                        "Claude Code CLI needs to be installed and authenticated.",
                        "error": "Claude Code not available",
                    }
                else:
                    # Start the improvement in background (like the API does)
                    async def run_improvement() -> None:
                        async for _event in si_agent.improve(request=ctx.text):
                            pass  # Events broadcast via Redis

                    asyncio.create_task(run_improvement())

                    # Wait briefly for session to be created
                    await asyncio.sleep(0.5)

                    # Get the latest session
                    sessions = si_agent.get_all_sessions()
                    if sessions:
                        latest = sessions[-1]
                        ctx.agent_response = {
                            "_agent_name": agent_name,
                            "response": f"I'll work on that improvement. Session {latest['session_id']} started. "
                            f"Check the Self-Improvement dashboard for progress.",
                            "session_id": latest["session_id"],
                            "status": latest["status"],
                        }
                    else:
                        ctx.agent_response = {
                            "_agent_name": agent_name,
                            "response": "I started working on that improvement but couldn't get the session info. "
                            "Check the Self-Improvement dashboard.",
                        }
            except Exception as e:
                logger.exception("Self-improvement agent error")
                ctx.agent_response = {
                    "_agent_name": agent_name,
                    "response": f"Sorry, I couldn't start the improvement: {e}. "
                    "Please check if Claude Code is configured correctly.",
                    "error": str(e),
                }

        else:
            # CONVERSATION, QUERY, UNKNOWN → Interaction Agent
            # Get HA context just-in-time for Interaction Agent (only if query mentions entities)
            try:
                from barnabeenet.services.homeassistant.context import get_ha_context_service

                context_service = await get_ha_context_service(self._ha_client)
                ha_interaction_context = await context_service.get_context_for_interaction_agent(
                    ctx.text
                )
                agent_context["ha_context"] = {
                    "entity_names": ha_interaction_context.entity_names,
                    "entity_domains": ha_interaction_context.entity_domains,
                    "area_names": ha_interaction_context.area_names,
                    "entity_states": ha_interaction_context.entity_states,  # Only mentioned entities
                    "entity_details": {
                        eid: {
                            "entity_id": meta.entity_id,
                            "domain": meta.domain,
                            "friendly_name": meta.friendly_name,
                            "area_id": meta.area_id,
                        }
                        for eid, meta in ha_interaction_context.entity_details.items()
                    },
                }
            except Exception as e:
                logger.debug("Could not get HA context for Interaction Agent: %s", e)
                agent_context["ha_context"] = {}

            ctx.agent_response = await self._interaction_agent.handle_input(ctx.text, agent_context)
            agent_name = "interaction"

        # Extract response text
        ctx.response_text = ctx.agent_response.get("response", "")
        ctx.agent_response["_agent_name"] = agent_name

        latency_ms = (time.perf_counter() - start) * 1000
        ctx.stage_timings["agent_handling"] = latency_ms

        # Log to activity logger
        if ctx.trace_id:
            activity_logger = get_activity_logger()
            await activity_logger.add_step(
                trace_id=ctx.trace_id,
                agent=agent_name,
                action="responded",
                summary=f"{agent_name.title()} agent: {ctx.response_text[:60]}..."
                if len(ctx.response_text) > 60
                else f"{agent_name.title()} agent: {ctx.response_text}",
                detail=f"Intent: {intent.value}",
                duration_ms=latency_ms,
            )

        # Log agent response (existing pipeline logger)
        if self._pipeline_logger:
            # Map agent name to signal type
            signal_map = {
                "instant": SignalType.AGENT_INSTANT,
                "action": SignalType.AGENT_ACTION,
                "interaction": SignalType.AGENT_INTERACTION,
                "memory": SignalType.AGENT_MEMORY,
            }
            signal_type = signal_map.get(agent_name, SignalType.AGENT_ROUTE)

            await self._pipeline_logger.log_signal(
                trace_id=ctx.trace_id,
                signal_type=signal_type,
                summary=f"{agent_name.title()}: {ctx.response_text[:80]}..."
                if len(ctx.response_text) > 80
                else f"{agent_name.title()}: {ctx.response_text}",
                latency_ms=latency_ms,
                success=True,
                extra_data={
                    "agent": agent_name,
                    "response_length": len(ctx.response_text),
                },
            )

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

    async def _execute_ha_action(
        self, action_spec: dict[str, Any], ctx: RequestContext
    ) -> dict[str, Any]:
        """Execute an action via Home Assistant.

        Supports both single entity and batch (multi-entity) operations.

        Args:
            action_spec: Action specification from ActionAgent
            ctx: Request context for logging

        Returns:
            Dict with execution result (success, executed, message, error)
        """
        # Check if HA client is available
        if self._ha_client is None:
            # Try to get the global HA client
            try:
                from barnabeenet.api.routes.homeassistant import get_ha_client

                self._ha_client = await get_ha_client()
            except Exception as e:
                logger.warning("Could not get HA client: %s", e)

        if self._ha_client is None:
            logger.info("Home Assistant client not configured")
            return {
                "executed": False,
                "success": False,
                "message": "Home Assistant not configured",
            }

        # Verify connection is alive (will auto-reconnect if stale)
        if not await self._ha_client.ensure_connected():
            logger.info("Home Assistant not connected, action not executed")
            return {
                "executed": False,
                "success": False,
                "message": "Home Assistant not connected - check Configuration",
            }

        # Check if this is a batch operation
        is_batch = action_spec.get("is_batch", False)
        if is_batch:
            return await self._execute_batch_action(action_spec, ctx)

        # Single entity operation
        return await self._execute_single_action(action_spec, ctx)

    async def _execute_batch_action(
        self, action_spec: dict[str, Any], ctx: RequestContext
    ) -> dict[str, Any]:
        """Execute a batch action on multiple entities.

        Uses HA's native floor/area targeting when possible for efficiency.
        Falls back to individual entity calls when needed.

        Args:
            action_spec: Action specification with target_area and device type
            ctx: Request context for logging

        Returns:
            Dict with execution results for all entities
        """
        from barnabeenet.services.homeassistant.smart_resolver import (
            FLOOR_ALIASES,
            SmartEntityResolver,
        )

        # HA client is guaranteed to be connected at this point
        assert self._ha_client is not None

        # Get action details
        entity_name = action_spec.get("entity_name", "")  # device type like "lights", "blinds"
        target_area = action_spec.get("target_area")
        service = action_spec.get("service")
        service_data = action_spec.get("service_data", {})
        domain = action_spec.get("domain")

        # Try to use HA's native targeting (more efficient)
        # Check if we can use floor_id or area_id targeting
        target: dict[str, Any] | None = None
        target_desc = ""

        if not target_area:
            # "all the blinds" / "all lights" - target all floors
            all_floors = list(FLOOR_ALIASES.keys())
            if all_floors:
                target = {"floor_id": all_floors}
                target_desc = "all floors"
                logger.info("Batch action using floor targeting: %s on %s", service, all_floors)
        else:
            # Check if target_area is a floor reference
            target_area_lower = target_area.lower()
            resolver = SmartEntityResolver(self._ha_client)
            floor_id = resolver.resolve_floor(target_area_lower)

            if floor_id:
                # It's a floor reference like "downstairs"
                target = {"floor_id": [floor_id]}
                target_desc = f"floor: {floor_id}"
                logger.info("Batch action using floor targeting: %s on %s", service, floor_id)
            else:
                # Try area targeting
                area = resolver.resolve_area(target_area)
                if area:
                    target = {"area_id": [area.id]}
                    target_desc = f"area: {area.id}"
                    logger.info("Batch action using area targeting: %s on %s", service, area.id)

        # If we have a target, use HA's native targeting
        if target and service:
            try:
                result = await self._ha_client.call_service(
                    service,
                    target=target,
                    **service_data,
                )

                if result.success:
                    # Get count of affected entities from response
                    affected = (
                        result.response_data.get("affected_states", [])
                        if result.response_data
                        else []
                    )
                    count = len(affected) if affected else 0
                    message = f"Successfully controlled {entity_name}"
                    if target_area:
                        message += f" {target_area}"
                    elif count:
                        message += f" ({count} entities)"

                    logger.info(
                        "Batch action via %s successful, affected %d entities",
                        target_desc,
                        count,
                    )

                    return {
                        "executed": True,
                        "success": True,
                        "message": message,
                        "target": target,
                        "target_desc": target_desc,
                        "affected_count": count,
                    }
                else:
                    logger.warning("Batch action via %s failed: %s", target_desc, result.message)
                    # Fall through to entity-by-entity execution
            except Exception as e:
                logger.warning("Batch action via %s failed with exception: %s", target_desc, e)
                # Fall through to entity-by-entity execution

        # Fallback: resolve individual entities and call each one
        logger.info("Falling back to entity-by-entity execution")
        resolver = SmartEntityResolver(self._ha_client)

        # Build the query for the resolver
        if target_area:
            query = f"{entity_name} in {target_area}"
        else:
            query = f"all {entity_name}"

        logger.info("Resolving batch action: %s", query)

        # Use smart resolver to find matching entities
        resolved = resolver.resolve(query, domain)

        if not resolved.entities:
            error_msg = resolved.error or f"No {entity_name} found"
            if target_area:
                error_msg += f" in {target_area}"
            logger.warning("Batch resolution failed: %s", error_msg)
            return {
                "executed": False,
                "success": False,
                "message": error_msg,
                "error": error_msg,
            }

        # Execute action on each entity
        results = []
        success_count = 0
        fail_count = 0

        for entity in resolved.entities:
            # Adapt service to entity's actual domain if needed
            entity_domain = entity.entity_id.split(".")[0]
            adapted_service = self._adapt_service_to_domain(service or "", entity_domain)

            try:
                result = await self._ha_client.call_service(
                    adapted_service,
                    entity_id=entity.entity_id,
                    **service_data,
                )
                if result.success:
                    success_count += 1
                    results.append(
                        {
                            "entity_id": entity.entity_id,
                            "success": True,
                        }
                    )
                else:
                    fail_count += 1
                    results.append(
                        {
                            "entity_id": entity.entity_id,
                            "success": False,
                            "error": result.message,
                        }
                    )
            except Exception as e:
                fail_count += 1
                results.append(
                    {
                        "entity_id": entity.entity_id,
                        "success": False,
                        "error": str(e),
                    }
                )

        # Build response
        total = len(resolved.entities)
        if success_count == total:
            message = f"Successfully controlled {total} {entity_name}"
            if target_area:
                message += f" in {target_area}"
        elif success_count > 0:
            message = f"Controlled {success_count}/{total} {entity_name}"
            if target_area:
                message += f" in {target_area}"
        else:
            message = f"Failed to control {entity_name}"
            if target_area:
                message += f" in {target_area}"

        logger.info("Batch action complete: %s/%s successful", success_count, total)

        return {
            "executed": True,
            "success": success_count > 0,
            "message": message,
            "total_entities": total,
            "success_count": success_count,
            "fail_count": fail_count,
            "entity_ids": [e.entity_id for e in resolved.entities],
            "results": results,
        }

    async def _execute_single_action(
        self, action_spec: dict[str, Any], ctx: RequestContext
    ) -> dict[str, Any]:
        """Execute an action on a single entity.

        Args:
            action_spec: Action specification from ActionAgent
            ctx: Request context for logging

        Returns:
            Dict with execution result (success, executed, message, error)
        """
        # HA client is guaranteed to be connected at this point
        assert self._ha_client is not None

        # Get service and entity info from action spec
        service = action_spec.get("service")
        entity_name = action_spec.get("entity_name", "")
        entity_id = action_spec.get("entity_id")
        service_data = action_spec.get("service_data", {})

        if not service:
            logger.warning("No service specified in action")
            return {
                "executed": False,
                "success": False,
                "message": "No service specified",
            }

        # Resolve entity_id - search both specified domain AND alternative domains
        # then pick the best match. This handles cases where:
        # - "office light" → switch.office_switch_light (switch controlling a light)
        # - ActionAgent guessed wrong domain
        domain = action_spec.get("domain")
        if entity_name:
            # Collect all candidate matches across relevant domains
            candidates: list[tuple[float, Any]] = []

            # Search specified domain
            entity = self._ha_client.resolve_entity(entity_name, domain)
            if entity:
                score = entity.match_score(entity_name)
                candidates.append((score, entity))
                logger.debug(
                    "Found in %s domain: %s (score=%.2f)",
                    domain,
                    entity.entity_id,
                    score,
                )

            # Also search alternative domains (lights often controlled by switches)
            alternative_domains = self._get_alternative_domains(domain, entity_name)
            for alt_domain in alternative_domains:
                alt_entity = self._ha_client.resolve_entity(entity_name, alt_domain)
                if alt_entity:
                    score = alt_entity.match_score(entity_name)
                    candidates.append((score, alt_entity))
                    logger.debug(
                        "Found in %s domain: %s (score=%.2f)",
                        alt_domain,
                        alt_entity.entity_id,
                        score,
                    )

            # Pick the best match
            if candidates:
                candidates.sort(key=lambda x: x[0], reverse=True)
                entity = candidates[0][1]
                best_score = candidates[0][0]

                # Log if we chose from alternative domain
                entity_domain = entity.entity_id.split(".")[0] if "." in entity.entity_id else None
                if entity_domain and entity_domain != domain:
                    logger.info(
                        "Best match from alternative domain %s: %s (score=%.2f)",
                        entity_domain,
                        entity.entity_id,
                        best_score,
                    )
            else:
                # Try without domain restriction as last resort
                entity = self._ha_client.resolve_entity(entity_name, None)
                if entity:
                    logger.info(
                        "Found entity with no domain restriction: %s",
                        entity.entity_id,
                    )

            if entity:
                entity_id = entity.entity_id
                # Update service to match the actual entity domain
                actual_domain = entity.entity_id.split(".")[0] if "." in entity.entity_id else None
                if actual_domain and actual_domain != domain:
                    service = self._adapt_service_to_domain(service, actual_domain)
                    action_spec["service"] = service
                    action_spec["entity_id"] = entity_id
                    logger.info(
                        "Adapted service from %s domain to %s: %s",
                        domain,
                        actual_domain,
                        service,
                    )
                logger.info("Resolved '%s' to entity_id: %s", entity_name, entity_id)
            else:
                logger.warning("Could not resolve entity: %s", entity_name)
                return {
                    "executed": False,
                    "success": False,
                    "message": f"Could not find device: {entity_name}",
                    "error": f"No entity matching '{entity_name}' found",
                }

        # Execute the service call
        try:
            logger.info(
                "Executing HA service: %s on %s with data %s",
                service,
                entity_id,
                service_data,
            )
            result = await self._ha_client.call_service(
                service, entity_id=entity_id, **service_data
            )

            if result.success:
                logger.info("HA service call successful: %s on %s", service, entity_id)
                return {
                    "executed": True,
                    "success": True,
                    "message": result.message,
                    "entity_id": entity_id,
                }
            else:
                logger.warning("HA service call failed: %s", result.message)
                return {
                    "executed": True,
                    "success": False,
                    "message": result.message,
                    "error": result.message,
                }
        except Exception as e:
            logger.exception("HA service call error: %s", e)
            return {
                "executed": True,
                "success": False,
                "message": f"Error executing action: {e}",
                "error": str(e),
            }

    def _get_alternative_domains(self, domain: str | None, entity_name: str) -> list[str]:
        """Get alternative domains to search when primary domain doesn't match.

        Many devices can control lights but are in different domains:
        - switch: Smart plugs, wall switches controlling lights
        - input_boolean: Virtual switches
        - automation: Can be toggled
        """
        # Domain alternatives - lights and switches are often interchangeable
        alternatives: dict[str, list[str]] = {
            "light": ["switch", "input_boolean"],
            "switch": ["light", "input_boolean"],
            "fan": ["switch"],
            "cover": ["switch"],
        }

        # Check if entity name contains hints about the actual device type
        name_lower = entity_name.lower()
        result = alternatives.get(domain or "", [])

        # If name contains "light" but domain is switch, prioritize finding it
        if "light" in name_lower and domain != "switch":
            if "switch" not in result:
                result.insert(0, "switch")

        return result

    def _adapt_service_to_domain(self, service: str, target_domain: str) -> str:
        """Adapt a service call to work with a different domain.

        For example, light.turn_on -> switch.turn_on when the entity is a switch.
        Only adapts services that are compatible across domains.
        Domain-specific services (like cover.open_cover) are NOT adapted.
        """
        if "." not in service:
            return service

        original_domain, action = service.split(".", 1)

        # Only adapt services that are compatible across domains
        # Domain-specific actions should NOT be adapted
        compatible_actions = {"turn_on", "turn_off", "toggle"}

        if action in compatible_actions and target_domain != original_domain:
            return f"{target_domain}.{action}"

        # For domain-specific actions (open_cover, close_cover, lock, unlock, etc.),
        # keep the original service - these only work with their native domain
        return service

    def _build_response(self, ctx: RequestContext) -> dict[str, Any]:
        """Build the final response dict."""
        # Generate routing reason for trace details
        routing_reason = None
        pattern_matched = None
        if ctx.classification:
            from barnabeenet.models.pipeline_trace import generate_routing_reason

            # Get the matched pattern from classification (if available)
            pattern_matched = ctx.classification.matched_pattern

            routing_reason = generate_routing_reason(
                intent=ctx.classification.intent.value,
                confidence=ctx.classification.confidence,
                pattern_matched=pattern_matched,
                sub_category=ctx.classification.sub_category,
            )

        # Extract context evaluation if available
        context_evaluation = None
        if ctx.classification and ctx.classification.context:
            context_evaluation = {
                "emotional_tone": ctx.classification.context.emotional_tone.value,
                "urgency_level": ctx.classification.context.urgency_level.value,
                "empathy_needed": ctx.classification.context.empathy_needed,
            }

        # Extract memory queries if available
        memory_queries = None
        if ctx.classification and ctx.classification.memory_queries:
            mq = ctx.classification.memory_queries
            memory_queries = [mq.primary_query] + mq.secondary_queries

        # Extract parsed segments and service calls from action response
        parsed_segments = None
        service_calls = None
        resolved_targets = None
        action_agent_mode = None
        ha_state_changes = None
        if ctx.agent_response and ctx.agent_response.get("_agent_name") == "action":
            action_data = ctx.agent_response.get("action")
            execution_result = ctx.agent_response.get("_execution_result", {})

            # Get whether action agent used rule-based or LLM parsing
            action_agent_mode = "rule-based"  # Default - action agent uses rule-based first

            if action_data:
                # Build service call info with full execution details
                service_call = {
                    "service": action_data.get("service"),
                    "domain": action_data.get("domain"),
                    "entity_id": action_data.get("entity_id"),
                    "entity_name": action_data.get("entity_name"),
                    "is_batch": action_data.get("is_batch", False),
                    "service_data": action_data.get("service_data", {}),
                }

                # Add execution details
                if execution_result:
                    service_call["executed"] = execution_result.get("executed", False)
                    service_call["success"] = execution_result.get("success", False)
                    service_call["affected_count"] = execution_result.get("affected_count")

                    # Include the actual target used (floor_id, area_id, etc.)
                    if execution_result.get("target"):
                        service_call["target"] = execution_result.get("target")
                    service_call["target_desc"] = execution_result.get("target_desc")

                service_calls = [service_call]

                # Build resolved targets
                if action_data.get("entity_id") or action_data.get("entity_ids"):
                    resolved_targets = [
                        {
                            "target_type": "area" if action_data.get("target_area") else "entity",
                            "area": action_data.get("target_area"),
                            "entity_id": action_data.get("entity_id"),
                            "entity_ids": action_data.get("entity_ids"),
                        }
                    ]

            # Get recent HA state changes that occurred after action execution
            # These show what actually changed in Home Assistant (visible in HA activity)
            if self._ha_client and execution_result.get("executed"):
                try:
                    # Get state changes that happened after the action started
                    # (within last 5 seconds to catch immediate changes)
                    from datetime import timedelta
                    cutoff_time = ctx.started_at - timedelta(seconds=5)
                    
                    recent_changes = []
                    for change in self._ha_client.get_recent_state_changes(limit=20, since=cutoff_time):
                        # Filter to relevant domains and entities that users care about
                        domain = change.entity_id.split(".")[0] if "." in change.entity_id else "unknown"
                        if domain in ("light", "switch", "fan", "cover", "climate", "lock", "media_player", "vacuum"):
                            # Get friendly name from entity registry if available
                            friendly_name = change.entity_id
                            entity = self._ha_client._entity_registry.get(change.entity_id)
                            if entity:
                                friendly_name = entity.friendly_name
                            
                            recent_changes.append({
                                "entity_id": change.entity_id,
                                "friendly_name": friendly_name,
                                "domain": domain,
                                "old_state": change.old_state,
                                "new_state": change.new_state,
                                "timestamp": change.timestamp.isoformat(),
                            })
                    
                    if recent_changes:
                        ha_state_changes = recent_changes
                        logger.debug("Including %d HA state changes in response", len(recent_changes))
                except Exception as e:
                    logger.debug("Could not get HA state changes for response: %s", e)

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
            "llm_details": ctx.agent_response.get("llm_details") if ctx.agent_response else None,
            # Trace details for observability
            "routing_reason": routing_reason,
            "pattern_matched": pattern_matched,
            "meta_processing_time_ms": ctx.stage_timings.get("classification"),
            "context_evaluation": context_evaluation,
            "memory_queries": memory_queries,
            "memories_data": [{"content": m} for m in ctx.retrieved_memories]
            if ctx.retrieved_memories
            else None,
            "parsed_segments": parsed_segments,
            "resolved_targets": resolved_targets,
            "service_calls": service_calls,
            "action_agent_mode": action_agent_mode,
            "ha_state_changes": ha_state_changes,  # State changes visible in HA activity
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

    def set_ha_client(self, ha_client: HomeAssistantClient | None) -> None:
        """Set the Home Assistant client.

        This is primarily useful for testing with mock clients.

        Args:
            ha_client: The HA client to use, or None to clear.
        """
        self._ha_client = ha_client


# Global orchestrator instance
_global_orchestrator: AgentOrchestrator | None = None


def get_orchestrator() -> AgentOrchestrator:
    """Get the global orchestrator instance."""
    global _global_orchestrator
    if _global_orchestrator is None:
        _global_orchestrator = AgentOrchestrator()
    return _global_orchestrator


def reset_orchestrator() -> None:
    """Reset the global orchestrator instance.

    This is primarily useful for testing to ensure a clean state.
    """
    global _global_orchestrator
    _global_orchestrator = None


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
    "reset_orchestrator",
]
