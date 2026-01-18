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
from barnabeenet.services.llm.openrouter import OpenRouterClient
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

            from barnabeenet.services.secrets import SecretsService

            # Get Redis connection
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
            redis_client = redis.from_url(redis_url, decode_responses=True)

            # Create and initialize secrets service
            secrets_service = SecretsService(redis_client)
            await secrets_service.initialize()

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

        # Start pipeline trace
        if self._pipeline_logger:
            await self._pipeline_logger.start_trace(
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

            await self._pipeline_logger.complete_trace(
                trace_id=ctx.trace_id,
                response_text=ctx.response_text,
                response_type="tts",
                success=not ctx.agent_response or "error" not in ctx.agent_response,
                agent_used=agent_name,
                intent=intent_val,
                intent_confidence=confidence,
                ha_actions=ctx.actions_taken if ctx.actions_taken else None,
                memories_retrieved=ctx.retrieved_memories if ctx.retrieved_memories else None,
            )

        return self._build_response(ctx)

    async def _classify(self, ctx: RequestContext) -> None:
        """Stage 1: Classify intent with MetaAgent."""
        start = time.perf_counter()

        # Call classify() directly to get ClassificationResult object
        ctx.classification = await self._meta_agent.classify(
            ctx.text,
            {
                "speaker": ctx.speaker,
                "room": ctx.room,
                "conversation_id": ctx.conversation_id,
            },
        )

        latency_ms = (time.perf_counter() - start) * 1000
        ctx.stage_timings["classification"] = latency_ms

        # Log classification signal
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

        # Log memory retrieval signal
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
            ctx.agent_response = await self._action_agent.handle_input(ctx.text, agent_context)
            agent_name = "action"
            # Track device actions
            if ctx.agent_response.get("action"):
                action_spec = ctx.agent_response["action"]
                ctx.actions_taken.append(action_spec)

                # Execute the action via Home Assistant
                execution_result = await self._execute_ha_action(action_spec, ctx)

                # Update response based on execution result
                if execution_result.get("executed"):
                    if not execution_result.get("success"):
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

        latency_ms = (time.perf_counter() - start) * 1000
        ctx.stage_timings["agent_handling"] = latency_ms

        # Log agent response
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

        if self._ha_client is None or not self._ha_client.connected:
            logger.info("Home Assistant not connected, action not executed")
            return {
                "executed": False,
                "success": False,
                "message": "Home Assistant not connected",
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

        Args:
            action_spec: Action specification with target_area and device type
            ctx: Request context for logging

        Returns:
            Dict with execution results for all entities
        """
        from barnabeenet.services.homeassistant.smart_resolver import SmartEntityResolver

        # HA client is guaranteed to be connected at this point
        assert self._ha_client is not None

        resolver = SmartEntityResolver(self._ha_client)

        # Get action details
        entity_name = action_spec.get("entity_name", "")  # device type like "lights", "blinds"
        target_area = action_spec.get("target_area")
        service = action_spec.get("service")
        service_data = action_spec.get("service_data", {})
        domain = action_spec.get("domain")

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
                    results.append({
                        "entity_id": entity.entity_id,
                        "success": True,
                    })
                else:
                    fail_count += 1
                    results.append({
                        "entity_id": entity.entity_id,
                        "success": False,
                        "error": result.message,
                    })
            except Exception as e:
                fail_count += 1
                results.append({
                    "entity_id": entity.entity_id,
                    "success": False,
                    "error": str(e),
                })

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
        """
        if "." not in service:
            return service

        original_domain, action = service.split(".", 1)

        # Map common actions between domains
        # light and switch share turn_on, turn_off, toggle
        compatible_actions = {"turn_on", "turn_off", "toggle"}

        if action in compatible_actions:
            return f"{target_domain}.{action}"

        # For other actions, try to use the target domain's equivalent
        return f"{target_domain}.{action}"

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
