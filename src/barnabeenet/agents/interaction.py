"""Interaction Agent - Complex multi-turn conversations.

The Interaction Agent handles complex conversations that require:
- Multi-turn dialogue with context retention
- LLM-powered responses with the Barnabee persona
- Memory retrieval for personalization
- Family-aware and child-appropriate responses

This is the "personality" agent - it uses the highest quality model
for engaging, helpful, and contextually appropriate responses.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

from barnabeenet.agents.base import Agent
from barnabeenet.services.llm.openrouter import ChatMessage, OpenRouterClient

if TYPE_CHECKING:
    import redis.asyncio as redis

logger = logging.getLogger(__name__)

# Redis key prefix for conversation contexts
REDIS_CONVERSATION_PREFIX = "barnabeenet:conversation:"


@dataclass
class ConversationTurn:
    """A single turn in a conversation."""

    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    speaker: str | None = None  # Family member ID if known

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "speaker": self.speaker,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ConversationTurn":
        """Create from dict."""
        return cls(
            role=data["role"],
            content=data["content"],
            timestamp=datetime.fromisoformat(data["timestamp"]) if data.get("timestamp") else datetime.now(),
            speaker=data.get("speaker"),
        )


@dataclass
class ConversationContext:
    """Context for a conversation."""

    conversation_id: str | None = None
    speaker: str | None = None  # Family member ID
    room: str | None = None  # Room location
    history: list[ConversationTurn] = field(default_factory=list)
    retrieved_memories: list[str] = field(default_factory=list)
    meta_context: dict[str, Any] | None = None  # From MetaAgent
    time_of_day: str = "day"  # morning, afternoon, evening, night
    children_present: bool = False  # For child-appropriate responses
    loaded_conversations: list[dict[str, Any]] = field(default_factory=list)  # Past conversations loaded
    recall_candidates: list[Any] = field(default_factory=list)  # Conversation summaries for user selection
    last_activity: datetime = field(default_factory=datetime.now)  # For session timeout

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict for Redis persistence."""
        return {
            "conversation_id": self.conversation_id,
            "speaker": self.speaker,
            "room": self.room,
            "history": [turn.to_dict() for turn in self.history],
            "retrieved_memories": self.retrieved_memories,
            "meta_context": self.meta_context,
            "time_of_day": self.time_of_day,
            "children_present": self.children_present,
            "loaded_conversations": self.loaded_conversations,
            "last_activity": self.last_activity.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ConversationContext":
        """Create from dict (for Redis deserialization)."""
        history = [ConversationTurn.from_dict(t) for t in data.get("history", [])]
        last_activity = data.get("last_activity")
        if isinstance(last_activity, str):
            last_activity = datetime.fromisoformat(last_activity)
        else:
            last_activity = datetime.now()

        return cls(
            conversation_id=data.get("conversation_id"),
            speaker=data.get("speaker"),
            room=data.get("room"),
            history=history,
            retrieved_memories=data.get("retrieved_memories", []),
            meta_context=data.get("meta_context"),
            time_of_day=data.get("time_of_day", "day"),
            children_present=data.get("children_present", False),
            loaded_conversations=data.get("loaded_conversations", []),
            last_activity=last_activity,
        )


@dataclass
class InteractionConfig:
    """Configuration for the Interaction Agent."""

    # Conversation settings
    max_history_turns: int = 10  # Keep last N turns in context
    max_memories: int = 5  # Max retrieved memories to include

    # Persona settings
    persona_name: str = "Barnabee"
    persona_style: str = "helpful assistant"

    # Response settings
    max_response_length: int = 300  # Characters, for speech appropriateness
    child_mode_max_words: int = 50  # Shorter responses for children

    # Child family members (for age-appropriate filtering)
    child_members: frozenset[str] = frozenset({"penelope", "xander", "zachary", "viola"})

    # Parent family members (have super user access to audit log)
    parent_members: frozenset[str] = frozenset({"thom", "elizabeth"})


# Patterns that indicate super user audit log access
SUPER_USER_PATTERNS = [
    r"show\s+(?:me\s+)?(?:all|the)\s+(?:audit\s+)?(?:logs?|conversations?|history)",
    r"what\s+(?:did\s+)?(?:everyone|the kids?|they)\s+(?:say|talk about|discuss)",
    r"show\s+(?:me\s+)?deleted\s+(?:conversations?|messages?)",
    r"show\s+(?:me\s+)?alerts?",
    r"parent(?:al)?\s+access",
    r"audit\s+(?:log|mode|access)",
    r"full\s+(?:history|log|access)",
]

# Patterns for cross-device conversation handoff
CROSS_DEVICE_PATTERNS = [
    r"continue\s+(?:the\s+)?conversation\s+(?:I\s+was\s+having\s+)?(?:on|from)\s+(?:my\s+)?(\w+)",
    r"pick\s+up\s+(?:where\s+I\s+left\s+off\s+)?(?:on|from)\s+(?:my\s+)?(\w+)",
    r"what\s+(?:was\s+I|were\s+we)\s+(?:talking|discussing)\s+about\s+(?:on|in)\s+(?:the\s+)?(\w+)",
    r"resume\s+(?:my\s+)?(?:conversation\s+)?(?:from\s+)?(?:the\s+)?(\w+)",
]

# Patterns for forgetting memories
FORGET_PATTERNS = [
    r"forget\s+that",
    r"forget\s+(?:about\s+)?(?:the\s+)?(?:last\s+)?(?:conversation|memory)",
    r"delete\s+(?:that|this)\s+(?:conversation|memory)",
    r"don'?t\s+remember\s+that",
    r"erase\s+(?:that|this)",
]

# Pattern for forgetting specific topics
import re

FORGET_TOPIC_PATTERN = re.compile(
    r"forget\s+(?:about\s+)?(?:the\s+)?(.+?)\s+conversation",
    re.IGNORECASE
)

SUPER_USER_PATTERNS_COMPILED = [
    re.compile(pattern, re.IGNORECASE) for pattern in SUPER_USER_PATTERNS
]
CROSS_DEVICE_PATTERNS_COMPILED = [
    re.compile(pattern, re.IGNORECASE) for pattern in CROSS_DEVICE_PATTERNS
]
FORGET_PATTERNS_COMPILED = [
    re.compile(pattern, re.IGNORECASE) for pattern in FORGET_PATTERNS
]


# Barnabee's core persona - injected into system prompt
BARNABEE_PERSONA = """You are Barnabee, the AI assistant for the Fife family household.

## Your Personality
- Helpful and straightforward
- Patient, especially with children
- No gimmicks, puns, or theatrical personality
- Just a capable, reliable assistant

## Communication Style
- Keep responses brief and to the point (1-2 sentences when possible)
- Talk naturally, like a normal person
- Don't use fancy language or act like a butler
- For children, use simpler language
- Just answer the question directly

## CRITICAL Guidelines - Memory and Personal Information
- NEVER make up or guess personal information, preferences, or past conversations
- If asked about something you weren't told, say "I don't have that information stored" or "I don't recall you telling me that"
- Only reference information from the "Relevant History" section below - nothing else
- If there's no Relevant History section or it's empty, you have NO stored memories about the user
- Don't pretend to remember things - it's better to honestly say you don't know
- If someone asks "do you remember..." and you have no relevant memory, say so clearly

## Other Guidelines
- Never reveal you're an AI unless directly asked
- Don't over-explain or be verbose - this is for speech
- If unsure about a topic, ask for clarification rather than guessing
- Be helpful but respect privacy boundaries"""

# Time-of-day greetings for natural conversation
TIME_GREETINGS = {
    "morning": "this fine morning",
    "afternoon": "this afternoon",
    "evening": "this evening",
    "night": "at this late hour",
}


class InteractionAgent(Agent):
    """Agent for complex multi-turn conversations.

    Uses LLM (Claude/GPT-4) for high-quality conversational responses.
    Integrates with memory retrieval for personalization.
    """

    name = "interaction"

    def __init__(
        self,
        llm_client: OpenRouterClient | None = None,
        config: InteractionConfig | None = None,
    ) -> None:
        """Initialize the Interaction Agent.

        Args:
            llm_client: Optional OpenRouter client. If not provided,
                will attempt to create from environment.
            config: Optional configuration overrides.
        """
        self._llm_client = llm_client
        self._owns_client = llm_client is None
        self.config = config or InteractionConfig()
        self._conversations: dict[str, ConversationContext] = {}
        self._initialized = False
        self._context_manager = None
        self._redis_client: "redis.Redis | None" = None

    async def _get_redis_client(self) -> "redis.Redis | None":
        """Get Redis client for context persistence."""
        if self._redis_client is not None:
            return self._redis_client

        try:
            from barnabeenet.main import app_state
            if hasattr(app_state, "redis_client") and app_state.redis_client:
                self._redis_client = app_state.redis_client
                return self._redis_client
        except Exception:
            pass
        return None

    async def _save_context_to_redis(self, conv_ctx: ConversationContext) -> bool:
        """Save conversation context to Redis for persistence across restarts.

        Args:
            conv_ctx: The conversation context to save

        Returns:
            True if saved successfully, False otherwise
        """
        redis_client = await self._get_redis_client()
        if not redis_client or not conv_ctx.conversation_id:
            return False

        try:
            key = f"{REDIS_CONVERSATION_PREFIX}{conv_ctx.conversation_id}"
            data = json.dumps(conv_ctx.to_dict())
            # Set with 24 hour expiration (conversations expire after 24h of inactivity)
            await redis_client.setex(key, 86400, data)
            logger.debug(f"Saved conversation context to Redis: {conv_ctx.conversation_id}")
            return True
        except Exception as e:
            logger.warning(f"Failed to save conversation to Redis: {e}")
            return False

    async def _load_context_from_redis(self, conversation_id: str) -> ConversationContext | None:
        """Load conversation context from Redis.

        Args:
            conversation_id: The conversation ID to load

        Returns:
            ConversationContext if found, None otherwise
        """
        redis_client = await self._get_redis_client()
        if not redis_client:
            return None

        try:
            key = f"{REDIS_CONVERSATION_PREFIX}{conversation_id}"
            data = await redis_client.get(key)
            if data:
                ctx_dict = json.loads(data)
                ctx = ConversationContext.from_dict(ctx_dict)
                logger.debug(f"Loaded conversation context from Redis: {conversation_id}")
                return ctx
        except Exception as e:
            logger.warning(f"Failed to load conversation from Redis: {e}")

        return None

    async def _delete_context_from_redis(self, conversation_id: str) -> bool:
        """Delete conversation context from Redis.

        Args:
            conversation_id: The conversation ID to delete

        Returns:
            True if deleted successfully, False otherwise
        """
        redis_client = await self._get_redis_client()
        if not redis_client:
            return False

        try:
            key = f"{REDIS_CONVERSATION_PREFIX}{conversation_id}"
            await redis_client.delete(key)
            logger.debug(f"Deleted conversation context from Redis: {conversation_id}")
            return True
        except Exception as e:
            logger.warning(f"Failed to delete conversation from Redis: {e}")
            return False

    async def init(self) -> None:
        """Initialize the agent."""
        if self._initialized:
            return

        if self._llm_client is None:
            from barnabeenet.config import get_settings
            from barnabeenet.services.llm.openrouter import AgentModelConfig

            settings = get_settings()
            api_key = settings.llm.openrouter_api_key
            if api_key:
                model_config = AgentModelConfig.from_settings(settings.llm)
                self._llm_client = OpenRouterClient(
                    api_key=api_key,
                    model_config=model_config,
                    site_url=settings.llm.openrouter_site_url,
                    site_name=settings.llm.openrouter_site_name,
                )
                await self._llm_client.init()
                logger.info("InteractionAgent created LLM client from settings")
            else:
                logger.warning(
                    "No LLM client provided and LLM_OPENROUTER_API_KEY not set. "
                    "Agent will return fallback responses."
                )

        # Initialize conversation context manager
        try:
            from barnabeenet.services.conversation import ConversationContextManager
            from barnabeenet.services.memory.storage import get_memory_storage

            memory_storage = get_memory_storage()
            self._context_manager = ConversationContextManager(
                memory_storage=memory_storage,
                llm_client=self._llm_client,
            )
            logger.info("Conversation context manager initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize context manager: {e}")
            self._context_manager = None

        self._initialized = True
        logger.info("InteractionAgent initialized")

    async def shutdown(self) -> None:
        """Clean up resources."""
        if self._owns_client and self._llm_client:
            await self._llm_client.shutdown()
        self._conversations.clear()
        self._initialized = False
        logger.info("InteractionAgent shutdown")

    async def handle_input(
        self, text: str, context: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Handle a conversation message.

        Args:
            text: User's message
            context: Additional context including:
                - conversation_id: ID for conversation tracking
                - speaker: Family member ID
                - room: Room location
                - retrieved_memories: Pre-retrieved memories
                - meta_context: Context from MetaAgent
                - emotional_tone: Detected emotional tone
                - children_present: Whether children are in the room

        Returns:
            Dict with response and metadata
        """
        start_time = time.perf_counter()
        ctx = context or {}

        # Build conversation context (loads from Redis if server restarted)
        conv_ctx = await self._get_or_create_context(ctx)

        # Track conversation start time and source
        if self._context_manager:
            self._context_manager.track_conversation_start(
                conv_ctx.conversation_id or "unknown",
                conv_ctx.room,
            )

        # Check for super user (parent) audit log access
        # This must be checked BEFORE regular recall to handle "show all conversations" etc.
        if self._is_super_user_request(text):
            super_result = await self._handle_super_user_recall(text, conv_ctx)
            if super_result:
                return super_result

        # Check for cross-device conversation handoff
        cross_device_result = await self._handle_cross_device_handoff(text, conv_ctx)
        if cross_device_result:
            return cross_device_result

        # Check for forget/delete memory commands
        forget_result = await self._handle_forget_command(text, conv_ctx)
        if forget_result:
            return forget_result

        # Check for "tell me more" to expand recall results
        expand_result = await self._handle_expand_recall(text, conv_ctx)
        if expand_result:
            return expand_result

        # Check for conversation recall requests or selection
        if self._context_manager:
            # Check if user is selecting from recall candidates
            if hasattr(conv_ctx, "recall_candidates") and conv_ctx.recall_candidates:
                selection_result = await self._handle_recall_selection(text, conv_ctx)
                if selection_result:
                    return selection_result

            # Check if this is a new recall request
            if self._is_recall_request(text):
                recall_result = await self._handle_conversation_recall(text, conv_ctx, ctx)
                if recall_result:
                    return recall_result

        # Add the user's message to history
        conv_ctx.history.append(
            ConversationTurn(
                role="user",
                content=text,
                speaker=conv_ctx.speaker,
            )
        )

        # Check for child-appropriate mode
        is_child = conv_ctx.speaker in self.config.child_members
        children_present = ctx.get("children_present", False) or is_child
        conv_ctx.children_present = children_present

        # Generate response
        llm_details = None
        error_info = None
        if self._llm_client:
            llm_result = await self._generate_llm_response(text, conv_ctx, ctx)
            response_text = llm_result["text"]
            llm_details = llm_result.get("llm_details")
            error_info = llm_result.get("error")  # LLM call error if any
        else:
            response_text = self._generate_fallback_response(text, conv_ctx)
            error_info = {
                "type": "ConfigurationError",
                "message": "No LLM API key configured",
                "status_code": None,
                "model": None,
                "agent": "interaction",
            }

        # Add assistant response to history
        conv_ctx.history.append(ConversationTurn(role="assistant", content=response_text))

        # Trim history if needed (after both user and assistant turns added)
        max_len = self.config.max_history_turns * 2
        if len(conv_ctx.history) > max_len:
            conv_ctx.history = conv_ctx.history[-max_len:]

        # Persist context to Redis for server restart survival
        await self._persist_context(conv_ctx)

        latency_ms = (time.perf_counter() - start_time) * 1000

        return {
            "response": response_text,
            "agent": self.name,
            "conversation_id": conv_ctx.conversation_id,
            "speaker": conv_ctx.speaker,
            "turn_count": len([t for t in conv_ctx.history if t.role == "user"]),
            "used_llm": self._llm_client is not None and error_info is None,
            "child_mode": children_present,
            "latency_ms": latency_ms,
            "llm_details": llm_details,
            "error": error_info,
        }

    async def _get_or_create_context(self, ctx: dict[str, Any]) -> ConversationContext:
        """Get existing conversation or create new one.

        Checks memory first, then Redis, then creates new.
        Persists to Redis for survival across restarts.
        """
        conv_id = ctx.get("conversation_id") or f"conv_{id(ctx)}"

        # Check in-memory cache first
        if conv_id in self._conversations:
            conv_ctx = self._conversations[conv_id]
            # Update with any new context
            if ctx.get("retrieved_memories"):
                conv_ctx.retrieved_memories = ctx["retrieved_memories"]
            if ctx.get("meta_context"):
                conv_ctx.meta_context = ctx["meta_context"]
            # Update last activity time
            conv_ctx.last_activity = datetime.now()
            return conv_ctx

        # Try to load from Redis (for server restart recovery)
        conv_ctx = await self._load_context_from_redis(conv_id)
        if conv_ctx:
            # Update with new context from this request
            if ctx.get("retrieved_memories"):
                conv_ctx.retrieved_memories = ctx["retrieved_memories"]
            if ctx.get("meta_context"):
                conv_ctx.meta_context = ctx["meta_context"]
            conv_ctx.last_activity = datetime.now()
            # Cache in memory
            self._conversations[conv_id] = conv_ctx
            logger.debug(f"Restored conversation from Redis: {conv_id} with {len(conv_ctx.history)} turns")
            return conv_ctx

        # Create new context
        conv_ctx = ConversationContext(
            conversation_id=conv_id,
            speaker=ctx.get("speaker"),
            room=ctx.get("room"),
            retrieved_memories=ctx.get("retrieved_memories", []),
            meta_context=ctx.get("meta_context"),
            time_of_day=ctx.get("time_of_day", "day"),
            last_activity=datetime.now(),
        )
        self._conversations[conv_id] = conv_ctx

        return conv_ctx

    async def _persist_context(self, conv_ctx: ConversationContext) -> None:
        """Persist conversation context to Redis after each turn."""
        await self._save_context_to_redis(conv_ctx)

    def _build_system_prompt(self, conv_ctx: ConversationContext, user_ctx: dict[str, Any]) -> str:
        """Build the system prompt with context."""
        # Determine timezone FIRST - default to EST/EDT
        import time
        now = datetime.now()
        current_time = now.strftime("%I:%M %p").lstrip("0")
        current_date = now.strftime("%A, %B %d, %Y")

        tz_name = time.tzname[0] if time.daylight == 0 else time.tzname[1]
        if "EST" in tz_name or "EDT" in tz_name or "Eastern" in tz_name:
            timezone = "Eastern Time (EST/EDT)"
        elif "CST" in tz_name or "CDT" in tz_name or "Central" in tz_name:
            timezone = "Central Time (CST/CDT)"
        else:
            # Default to EST if unknown
            timezone = "Eastern Time (EST/EDT)"

        # Put CRITICAL timezone instruction FIRST, before persona
        parts = [
            "## ⚠️⚠️⚠️ CRITICAL TIMEZONE INSTRUCTION - READ FIRST ⚠️⚠️⚠️",
            f"YOUR CURRENT TIMEZONE: {timezone}",
            f"YOUR CURRENT TIME: {current_time} {timezone}",
            "",
            "ABSOLUTE RULES - FOLLOW THESE EXACTLY:",
            f"1. YOU ARE IN {timezone}. THIS IS YOUR ONLY REFERENCE POINT.",
            "2. NEVER mention 'Central Time', 'Chicago', 'CST', or 'CDT' in ANY response.",
            "3. NEVER say phrases like '1 hour behind Central Time' or 'compared to Central Time'.",
            "4. When calculating times in other timezones:",
            f"   - ALWAYS start from {timezone}",
            f"   - Calculate FROM {timezone}",
            f"   - Example: Current time is {current_time} {timezone}",
            "     * Utah = Mountain Time = 2 hours BEHIND Eastern Time",
            f"     * So Utah time = 2 hours earlier than {current_time}",
            "5. If you think about Central Time, STOP. Recalculate from Eastern Time only.",
            "",
            "---",
            "",
        ]

        # Now add persona
        parts.append(BARNABEE_PERSONA)

        # Add current context
        parts.append("\n## Current Situation")
        parts.append(f"- Current time: {current_time} {timezone}")
        parts.append(f"- Current date: {current_date}")

        # Time-of-day context for tone
        time_phrase = TIME_GREETINGS.get(conv_ctx.time_of_day, "today")
        parts.append(f"- Time of day: {time_phrase}")

        # Speaker context
        if conv_ctx.speaker:
            speaker_name = self._format_speaker_name(conv_ctx.speaker)
            parts.append(f"- Speaking with: {speaker_name}")
        else:
            # Unknown speaker - don't call them "guest", just note timezone
            parts.append("- Speaker: Unknown (defaulting to Eastern Time for time calculations)")

        # Room context
        if conv_ctx.room:
            parts.append(f"- Location: {conv_ctx.room}")

        # Profile context (personalization from Family Profile System)
        profile = user_ctx.get("profile")
        if profile:
            parts.append(self._build_profile_section(profile))

        # Mentioned family members (for answering questions about them)
        mentioned_profiles = user_ctx.get("mentioned_profiles")
        if mentioned_profiles:
            parts.append(self._build_mentioned_profiles_section(mentioned_profiles))

        # Child mode
        if conv_ctx.children_present:
            parts.append(
                "\n## IMPORTANT: Child Present"
                "\n- Use simple, age-appropriate language"
                "\n- Keep responses shorter (1-2 sentences)"
                "\n- Be extra friendly and encouraging"
                "\n- Avoid complex topics or scary content"
            )

        # Emotional tone from MetaAgent
        if conv_ctx.meta_context:
            tone = conv_ctx.meta_context.get("emotional_tone")
            if tone and tone != "neutral":
                parts.append(f"\n- User appears: {tone}")
                if tone in ("stressed", "negative", "urgent"):
                    parts.append("- Respond with extra patience and empathy")

        # Loaded past conversations
        if hasattr(conv_ctx, "loaded_conversations") and conv_ctx.loaded_conversations:
            parts.append("\n## Previous Conversations (Loaded for Context)")
            for loaded_conv in conv_ctx.loaded_conversations:
                parts.append(f"- {loaded_conv['summary']} (from {loaded_conv['timestamp'][:10]})")

        # Retrieved memories
        if conv_ctx.retrieved_memories:
            parts.append("\n## Relevant History (ONLY use this information)")
            for memory in conv_ctx.retrieved_memories[: self.config.max_memories]:
                parts.append(f"- {memory}")
        else:
            parts.append(
                "\n## Memory Status: NO RELEVANT MEMORIES"
                "\nYou have NO stored information about this user's preferences, past conversations, "
                "or personal details. If asked about personal things (favorite colors, what they said before, "
                "their preferences, etc.), you MUST say you don't have that information stored. "
                "Do NOT make anything up."
            )

        return "\n".join(parts)

    def _build_profile_section(self, profile: dict[str, Any]) -> str:
        """Build the profile personalization section for the system prompt.

        Args:
            profile: Profile context from ProfileService (ProfileContextResponse as dict)

        Returns:
            Formatted section for system prompt
        """
        parts = ["\n## Speaker Profile"]

        # Add name if available
        name = profile.get("name")
        if name:
            parts.append(f"- Name: {name}")

        # Add real-time location from Home Assistant
        location = profile.get("location")
        if location:
            loc_state = location.get("state", "unknown")
            is_home = location.get("is_home", False)
            if is_home:
                parts.append("- Current location: Home")
            elif loc_state.lower() == "not_home":
                parts.append("- Current location: Away from home")
            else:
                # Zone name like "Work", "School", etc.
                parts.append(f"- Current location: {loc_state}")

            # Add GPS coordinates if available
            lat = location.get("latitude")
            lon = location.get("longitude")
            if lat and lon:
                parts.append(f"- GPS coordinates: {lat:.4f}, {lon:.4f}")

            # Add time since location change
            last_changed = location.get("last_changed")
            if last_changed:
                try:
                    if isinstance(last_changed, str):
                        changed_dt = datetime.fromisoformat(last_changed.replace("Z", "+00:00"))
                    else:
                        changed_dt = last_changed
                    delta = datetime.now(changed_dt.tzinfo or None) - changed_dt
                    minutes = int(delta.total_seconds() / 60)
                    if minutes < 5:
                        parts.append("- Arrived: just now")
                    elif minutes < 60:
                        parts.append(f"- Arrived: {minutes} minutes ago")
                    elif minutes < 1440:  # 24 hours
                        hours = minutes // 60
                        parts.append(f"- Arrived: {hours} hour{'s' if hours > 1 else ''} ago")
                except (ValueError, TypeError):
                    pass

        # Add person entity device information
        ha_person_entity = profile.get("ha_person_entity")
        person_details = profile.get("person_entity_details")
        if person_details:
            parts.append("\n### Person Entity Devices & Entities")

            # Linked devices
            linked_devices = person_details.get("linked_devices", [])
            if linked_devices:
                parts.append(f"- Linked devices: {len(linked_devices)} device(s)")

            # Linked entities (notifications, alarms, location, etc.)
            linked_entities = person_details.get("linked_entities", [])
            if linked_entities:
                # Group by domain
                by_domain: dict[str, list[str]] = {}
                for entity in linked_entities:
                    domain = entity.get("domain", "unknown")
                    friendly_name = entity.get("friendly_name", entity.get("entity_id", "unknown"))
                    if domain not in by_domain:
                        by_domain[domain] = []
                    by_domain[domain].append(friendly_name)

                for domain, names in by_domain.items():
                    parts.append(f"- {domain.title()} entities: {', '.join(names[:5])}")
                    if len(names) > 5:
                        parts.append(f"  (and {len(names) - 5} more)")

            # Home address if available
            address = person_details.get("address")
            if address and address.get("latitude"):
                if address.get("formatted"):
                    parts.append(f"- Home address: {address['formatted']}")
                else:
                    parts.append(f"- Home address coordinates: {address['latitude']:.4f}, {address['longitude']:.4f}")

        # Add explicit instructions for location questions
        if location or person_details:
            parts.append("\n### IMPORTANT: Location Information")
            parts.append("When asked about the speaker's location or address:")
            if location:
                if location.get("is_home"):
                    parts.append("- If they are home, you can say they are at home")
                    if address:
                        parts.append("- You have access to their home address coordinates")
                else:
                    zone = location.get("zone") or location.get("state")
                    if zone:
                        parts.append(f"- They are currently at: {zone}")
                if location.get("latitude") and location.get("longitude"):
                    parts.append(f"- Current GPS coordinates: {location['latitude']:.4f}, {location['longitude']:.4f}")
            if person_details and person_details.get("address"):
                addr = person_details["address"]
                if addr.get("formatted"):
                    parts.append(f"- Home address: {addr['formatted']}")
                else:
                    parts.append(f"- Home address GPS: {addr.get('latitude'):.4f}, {addr.get('longitude'):.4f}")
            parts.append("- Use this information to answer location questions accurately")
            parts.append("- If asked 'where am I' or 'what is my exact location', provide the specific location information above")

        # Add context type indicator
        context_type = profile.get("context_type", "public_only")
        if context_type == "guest":
            # Don't explicitly call them "guest" - just note limited info
            parts.append("- Limited profile information available")
            return "\n".join(parts)

        # Add public profile info
        public = profile.get("public", {})
        if public:
            # Communication style
            comm_style = public.get("communication_style")
            if comm_style:
                parts.append(f"- Communication preference: {comm_style}")

            # Interests
            interests = public.get("interests", [])
            if interests:
                parts.append(f"- Interests: {', '.join(interests[:5])}")

            # Preferences
            prefs = public.get("preferences", {})
            if prefs:
                # Format as compact list
                pref_items = [f"{k}: {v}" for k, v in list(prefs.items())[:5]]
                if pref_items:
                    parts.append(f"- Preferences: {'; '.join(pref_items)}")

        # Add private profile info (only if context allows)
        private = profile.get("private")
        if private and context_type == "private":
            parts.append("\n### Private Context (handle with care)")

            # Personal notes
            personal_notes = private.get("personal_notes")
            if personal_notes:
                parts.append(f"- Personal notes: {personal_notes[:200]}")

            # Goals
            goals = private.get("goals", [])
            active_goals = [g for g in goals if g.get("status") == "active"][:3]
            if active_goals:
                goals_text = "; ".join(g.get("description", "") for g in active_goals)
                parts.append(f"- Active goals: {goals_text}")

            # Sensitive topics to avoid
            avoid = private.get("topics_to_avoid", [])
            if avoid:
                parts.append(f"- Topics to handle carefully: {', '.join(avoid[:3])}")

        return "\n".join(parts)

    def _build_mentioned_profiles_section(self, profiles: list[dict[str, Any]]) -> str:
        """Build section with info about mentioned family members.

        This allows Barnabee to answer questions about family members
        using their profile data, including real-time location.

        Args:
            profiles: List of profile dicts for mentioned family members

        Returns:
            Formatted section for system prompt
        """
        parts = ["\n## Family Member Information"]
        parts.append("The following family members were mentioned. Use this information to answer:")

        for profile in profiles:
            name = profile.get("name", profile.get("member_id", "Unknown"))
            parts.append(f"\n### {name}")

            relationship = profile.get("relationship")
            if relationship:
                parts.append(f"- Relationship: {relationship}")

            # Real-time location from Home Assistant (critical for "where is X?" queries)
            location = profile.get("location")
            if location:
                loc_state = location.get("state", "unknown")
                is_home = location.get("is_home", False)
                if is_home:
                    parts.append("- Current location: Home")
                elif loc_state.lower() == "not_home":
                    parts.append("- Current location: Away from home")
                else:
                    parts.append(f"- Current location: {loc_state}")

                # Add time since location change
                last_changed = location.get("last_changed")
                if last_changed:
                    try:
                        if isinstance(last_changed, str):
                            changed_dt = datetime.fromisoformat(last_changed.replace("Z", "+00:00"))
                        else:
                            changed_dt = last_changed
                        delta = datetime.now(changed_dt.tzinfo or None) - changed_dt
                        minutes = int(delta.total_seconds() / 60)
                        if minutes < 5:
                            parts.append("- Arrived there: just now")
                        elif minutes < 60:
                            parts.append(f"- Arrived there: {minutes} minutes ago")
                        elif minutes < 1440:
                            hours = minutes // 60
                            parts.append(
                                f"- Arrived there: {hours} hour{'s' if hours > 1 else ''} ago"
                            )
                        else:
                            days = minutes // 1440
                            parts.append(
                                f"- At that location for: {days} day{'s' if days > 1 else ''}"
                            )
                    except (ValueError, TypeError):
                        pass
            else:
                parts.append("- Current location: Unknown (no tracking data)")

            comm_style = profile.get("communication_style")
            if comm_style:
                parts.append(f"- Communication style: {comm_style}")

            interests = profile.get("interests", [])
            if interests:
                parts.append(f"- Interests: {', '.join(interests)}")

            prefs = profile.get("preferences", {})
            if prefs:
                pref_items = [f"{k}: {v}" for k, v in list(prefs.items())[:5]]
                if pref_items:
                    parts.append(f"- Preferences: {'; '.join(pref_items)}")

        return "\n".join(parts)

    def _format_speaker_name(self, speaker_id: str) -> str:
        """Format speaker ID into display name."""
        # Map of known family members
        family_names = {
            "thom": "Thom (Dad)",
            "sarah": "Sarah (Mom)",
            "penelope": "Penelope",
            "xander": "Xander",
            "zachary": "Zachary",
            "viola": "Viola",
        }
        return family_names.get(speaker_id, speaker_id.title())

    async def _build_messages(
        self,
        current_text: str,
        conv_ctx: ConversationContext,
        system_prompt: str,
    ) -> list[ChatMessage]:
        """Build the message list for the LLM with context management."""
        messages = [ChatMessage(role="system", content=system_prompt)]

        # Convert history to message format
        history_messages = []
        for turn in conv_ctx.history[:-1]:  # Exclude just-added user message
            history_messages.append({"role": turn.role, "content": turn.content})

        # Manage context (summarize if needed)
        if self._context_manager:
            optimized_messages, summary = await self._context_manager.manage_context(
                conv_ctx,
                system_prompt,
                [{"role": "system", "content": system_prompt}] + history_messages + [{"role": "user", "content": current_text}],
            )
            # Convert back to ChatMessage objects
            messages = []
            for msg in optimized_messages:
                if msg["role"] == "system" and msg != optimized_messages[0]:
                    # Additional system message (summary)
                    messages.append(ChatMessage(role="system", content=msg["content"]))
                else:
                    messages.append(ChatMessage(role=msg["role"], content=msg["content"]))
        else:
            # No context management - use all history
            for turn in conv_ctx.history[:-1]:
                messages.append(ChatMessage(role=turn.role, content=turn.content))

        # Add current user message
        messages.append(ChatMessage(role="user", content=current_text))

        return messages

    async def _generate_llm_response(
        self,
        text: str,
        conv_ctx: ConversationContext,
        user_ctx: dict[str, Any],
    ) -> dict[str, Any]:
        """Generate response using LLM.

        Returns:
            Dict with:
                - text: Response text
                - llm_details: Dict with model, tokens, cost, messages, response
        """
        assert self._llm_client is not None  # Caller checks this

        system_prompt = self._build_system_prompt(conv_ctx, user_ctx)
        messages = await self._build_messages(text, conv_ctx, system_prompt)

        try:
            response = await self._llm_client.chat(
                messages=messages,
                agent_type="interaction",
                conversation_id=conv_ctx.conversation_id,
                user_input=text,
                speaker=conv_ctx.speaker,
                room=conv_ctx.room,
                injected_context={
                    "time_of_day": conv_ctx.time_of_day,
                    "child_mode": conv_ctx.children_present,
                    "memory_count": len(conv_ctx.retrieved_memories),
                    "turn_count": len(conv_ctx.history),
                },
            )

            response_text = response.text.strip()

            # Post-process for length if needed
            if conv_ctx.children_present:
                response_text = self._truncate_for_children(response_text)

            # Build LLM details for debugging
            llm_details = {
                "model": response.model,
                "input_tokens": response.input_tokens,
                "output_tokens": response.output_tokens,
                "cost_usd": response.cost_usd,
                "llm_latency_ms": response.latency_ms,
                "messages_sent": [
                    {
                        "role": m.role,
                        "content": m.content[:500] + "..." if len(m.content) > 500 else m.content,
                    }
                    for m in messages
                ],
                "response_text": response.text,
            }

            return {"text": response_text, "llm_details": llm_details}

        except Exception as e:
            logger.error(f"LLM request failed: {e}")
            error_type = type(e).__name__
            error_detail = str(e)
            # Extract HTTP status if available
            status_code = getattr(e, "status_code", None) or getattr(
                getattr(e, "response", None), "status_code", None
            )

            return {
                "text": self._generate_llm_error_response(error_type, error_detail, status_code),
                "llm_details": None,
                "error": {
                    "type": error_type,
                    "message": error_detail,
                    "status_code": status_code,
                    "model": self._llm_client.model_config.interaction.model
                    if self._llm_client
                    else None,
                    "agent": "interaction",
                },
            }

    def _truncate_for_children(self, text: str) -> str:
        """Truncate response for child-appropriate length."""
        words = text.split()
        if len(words) <= self.config.child_mode_max_words:
            return text

        # Find a sentence boundary near the word limit
        truncated = " ".join(words[: self.config.child_mode_max_words])

        # Try to end at a sentence boundary
        for punct in [".", "!", "?"]:
            if punct in truncated:
                last_idx = truncated.rfind(punct)
                if last_idx > len(truncated) // 2:
                    return truncated[: last_idx + 1]

        return truncated + "..."

    def _generate_llm_error_response(
        self, error_type: str, error_detail: str, status_code: int | None
    ) -> str:
        """Generate a user-friendly error message for LLM failures."""
        model_name = (
            self._llm_client.model_config.interaction.model if self._llm_client else "unknown"
        )

        if status_code == 401:
            return f"LLM authentication failed - your API key may be invalid. Model: {model_name}"
        elif status_code == 402:
            return f"LLM billing error - check your account balance. Model: {model_name}"
        elif status_code == 403:
            return f"LLM access denied - API key may not have access to {model_name}"
        elif status_code == 404:
            return f"LLM model not found: {model_name}. Check if the model name is correct."
        elif status_code == 429:
            return f"LLM rate limit exceeded. Try again in a moment. Model: {model_name}"
        elif status_code and status_code >= 500:
            return f"LLM service error ({status_code}). The provider may be having issues. Model: {model_name}"
        elif "timeout" in error_detail.lower():
            return f"LLM request timed out. Model: {model_name}"
        elif "connection" in error_detail.lower():
            return f"Could not connect to LLM provider. Check your network. Model: {model_name}"
        else:
            return f"LLM error: {error_type} - {error_detail[:100]}. Model: {model_name}"

    def _generate_fallback_response(self, text: str, conv_ctx: ConversationContext) -> str:
        """Generate a fallback response when LLM is unavailable."""
        speaker = conv_ctx.speaker or "there"
        speaker_name = self._format_speaker_name(speaker) if speaker != "there" else "there"

        # Simple pattern-based fallbacks
        text_lower = text.lower()

        if any(word in text_lower for word in ["hello", "hi", "hey"]):
            return f"Hello {speaker_name}! How can I help you?"

        if any(word in text_lower for word in ["thanks", "thank you"]):
            return "You're most welcome! Is there anything else you need?"

        if "how are you" in text_lower:
            return "I'm doing quite well, thank you for asking! How can I assist you?"

        if any(word in text_lower for word in ["bye", "goodbye", "see you"]):
            return f"Goodbye {speaker_name}! Have a wonderful day."

        # Specific error: No LLM configured
        return (
            "I can't answer that right now - no LLM API key is configured. "
            "Please set up an API key in the Configuration page (OpenRouter, OpenAI, etc.)."
        )

    def get_conversation(self, conversation_id: str) -> ConversationContext | None:
        """Get a conversation by ID."""
        return self._conversations.get(conversation_id)

    async def clear_conversation(self, conversation_id: str) -> bool:
        """Clear a conversation's history from memory and Redis."""
        cleared = False
        if conversation_id in self._conversations:
            del self._conversations[conversation_id]
            cleared = True

        # Also delete from Redis
        await self._delete_context_from_redis(conversation_id)

        return cleared

    def get_active_conversations(self) -> list[str]:
        """Get list of active conversation IDs."""
        return list(self._conversations.keys())

    def _is_recall_request(self, text: str) -> bool:
        """Check if user is asking to recall a past conversation."""
        text_lower = text.lower()
        recall_keywords = [
            "remember what we were talking about",
            "remember our conversation",
            "what were we discussing",
            "continue our conversation",
            "yesterday we talked",
            "earlier we discussed",
        ]
        return any(keyword in text_lower for keyword in recall_keywords)

    async def _handle_conversation_recall(
        self,
        text: str,
        conv_ctx: ConversationContext,
        user_ctx: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Handle conversation recall request.

        Returns response dict if handled, None if not a recall request.
        """
        if not self._context_manager:
            return None

        try:
            # Search for past conversations GLOBALLY
            # Names in the query are treated as search terms, not filters
            # E.g., "what did Elizabeth say about dinner" searches all conversations
            summaries = await self._context_manager.recall_conversations(
                query=text,
                speaker=conv_ctx.speaker,  # For context, not filtering
                room=conv_ctx.room,
                limit=5,
                global_search=True,  # Search all conversations, not just this speaker's
            )

            if not summaries:
                # No past conversations found
                return {
                    "response": "I don't have any past conversations stored that match that. We can start fresh!",
                    "agent": self.name,
                    "conversation_id": conv_ctx.conversation_id,
                    "speaker": conv_ctx.speaker,
                    "turn_count": len(conv_ctx.history),
                    "used_llm": False,
                    "latency_ms": 0,
                }

            # Present options to user
            if len(summaries) == 1:
                # Single match - load it directly
                summary = summaries[0]
                await self._context_manager.load_conversation_into_context(
                    summary.conversation_id,
                    conv_ctx,
                )
                return {
                    "response": f"I found our conversation about: {summary.summary}. Let's continue from there!",
                    "agent": self.name,
                    "conversation_id": conv_ctx.conversation_id,
                    "speaker": conv_ctx.speaker,
                    "turn_count": len(conv_ctx.history),
                    "used_llm": False,
                    "latency_ms": 0,
                }
            else:
                # Multiple matches - ask user to choose
                options_text = "\n".join(
                    f"{i+1}. {s.summary[:100]}..." for i, s in enumerate(summaries[:3])
                )
                response = f"I found {len(summaries)} past conversations. Which one did you mean?\n\n{options_text}\n\nJust say the number or describe which one."

                # Store summaries in context for follow-up
                conv_ctx.recall_candidates = summaries

                return {
                    "response": response,
                    "agent": self.name,
                    "conversation_id": conv_ctx.conversation_id,
                    "speaker": conv_ctx.speaker,
                    "turn_count": len(conv_ctx.history),
                    "used_llm": False,
                    "latency_ms": 0,
                }

        except Exception as e:
            logger.error(f"Conversation recall failed: {e}")
            return None

    async def _handle_recall_selection(
        self,
        text: str,
        conv_ctx: ConversationContext,
    ) -> dict[str, Any] | None:
        """Handle user selection from recall candidates."""
        if not hasattr(conv_ctx, "recall_candidates") or not conv_ctx.recall_candidates:
            return None

        # Try to match selection (number or description)
        text_lower = text.lower().strip()

        # Check for number selection
        import re
        number_match = re.search(r'\b(\d+)\b', text)
        if number_match:
            selection_num = int(number_match.group(1))
            if 1 <= selection_num <= len(conv_ctx.recall_candidates):
                selected = conv_ctx.recall_candidates[selection_num - 1]
                await self._context_manager.load_conversation_into_context(
                    selected.conversation_id,
                    conv_ctx,
                )
                conv_ctx.recall_candidates = []  # Clear candidates
                return {
                    "response": f"Got it! I've loaded our conversation about: {selected.summary}. Let's continue!",
                    "agent": self.name,
                    "conversation_id": conv_ctx.conversation_id,
                    "speaker": conv_ctx.speaker,
                    "turn_count": len(conv_ctx.history),
                    "used_llm": False,
                    "latency_ms": 0,
                }

        # Try semantic matching
        for candidate in conv_ctx.recall_candidates:
            if any(word in text_lower for word in candidate.summary.lower().split()[:5]):
                await self._context_manager.load_conversation_into_context(
                    candidate.conversation_id,
                    conv_ctx,
                )
                conv_ctx.recall_candidates = []
                return {
                    "response": f"Perfect! I've loaded our conversation about: {candidate.summary}. Let's continue!",
                    "agent": self.name,
                    "conversation_id": conv_ctx.conversation_id,
                    "speaker": conv_ctx.speaker,
                    "turn_count": len(conv_ctx.history),
                    "used_llm": False,
                    "latency_ms": 0,
                }

        return None

    def _is_super_user_request(self, text: str) -> bool:
        """Check if this is a super user audit log request.

        Only available to parents (thom, elizabeth).
        """
        for pattern in SUPER_USER_PATTERNS_COMPILED:
            if pattern.search(text):
                return True
        return False

    async def _handle_super_user_recall(
        self,
        text: str,
        conv_ctx: ConversationContext,
    ) -> dict[str, Any] | None:
        """Handle super user (parent) audit log access.

        This allows parents to:
        - View all conversations including "deleted" ones
        - See alert history
        - Search the full audit log

        Only available to parent family members (thom, elizabeth).
        """
        # Verify speaker is a parent
        if not conv_ctx.speaker or conv_ctx.speaker.lower() not in self.config.parent_members:
            return {
                "response": "I'm sorry, but that feature is only available to parents.",
                "agent": self.name,
                "conversation_id": conv_ctx.conversation_id,
                "speaker": conv_ctx.speaker,
                "turn_count": len(conv_ctx.history),
                "used_llm": False,
                "latency_ms": 0,
            }

        try:
            from barnabeenet.services.audit.log import get_audit_log

            audit_log = get_audit_log()

            # Determine what type of query this is
            text_lower = text.lower()

            # Check for alerts request
            if "alert" in text_lower or "concern" in text_lower:
                alerts = await audit_log.get_alerts(limit=10)

                if not alerts:
                    return {
                        "response": "Good news! There are no parental alerts in the system.",
                        "agent": self.name,
                        "conversation_id": conv_ctx.conversation_id,
                        "speaker": conv_ctx.speaker,
                        "turn_count": len(conv_ctx.history),
                        "used_llm": False,
                        "latency_ms": 0,
                    }

                # Format alerts
                alert_summaries = []
                for alert in alerts[:5]:
                    time_str = alert.timestamp.strftime("%b %d, %I:%M %p")
                    alert_summaries.append(
                        f"- {alert.speaker or 'Unknown'} ({time_str}): \"{alert.user_text[:50]}...\""
                    )

                response = f"Found {len(alerts)} alerts. Most recent:\n" + "\n".join(alert_summaries)
                response += "\n\nSay 'tell me more' for full details."

                # Store for expansion
                conv_ctx.last_recall_results = alerts
                conv_ctx.last_recall_ids = [a.entry_id for a in alerts]

                return {
                    "response": response,
                    "agent": self.name,
                    "conversation_id": conv_ctx.conversation_id,
                    "speaker": conv_ctx.speaker,
                    "turn_count": len(conv_ctx.history),
                    "used_llm": False,
                    "latency_ms": 0,
                    "audit_results": alerts,
                }

            # Check for deleted conversations
            if "delete" in text_lower:
                results = await audit_log.search(
                    query=None,
                    include_deleted=True,  # Super user mode
                    limit=20,
                )

                # Filter to just deleted entries
                deleted = [e for e in results if e.was_deleted]

                if not deleted:
                    return {
                        "response": "There are no deleted conversations in the audit log.",
                        "agent": self.name,
                        "conversation_id": conv_ctx.conversation_id,
                        "speaker": conv_ctx.speaker,
                        "turn_count": len(conv_ctx.history),
                        "used_llm": False,
                        "latency_ms": 0,
                    }

                summaries = []
                for entry in deleted[:5]:
                    time_str = entry.timestamp.strftime("%b %d, %I:%M %p")
                    summaries.append(
                        f"- {entry.speaker or 'Unknown'} ({time_str}): \"{entry.user_text[:40]}...\""
                    )

                response = f"Found {len(deleted)} deleted conversations:\n" + "\n".join(summaries)

                return {
                    "response": response,
                    "agent": self.name,
                    "conversation_id": conv_ctx.conversation_id,
                    "speaker": conv_ctx.speaker,
                    "turn_count": len(conv_ctx.history),
                    "used_llm": False,
                    "latency_ms": 0,
                    "audit_results": deleted,
                }

            # General audit log search
            # Extract search terms (remove common words)
            search_query = text_lower
            for remove in ["show", "me", "all", "the", "audit", "log", "history", "conversations"]:
                search_query = search_query.replace(remove, "")
            search_query = search_query.strip()

            results = await audit_log.search(
                query=search_query if search_query else None,
                include_deleted=True,  # Super user sees everything
                limit=20,
            )

            if not results:
                return {
                    "response": "No conversations found matching your search.",
                    "agent": self.name,
                    "conversation_id": conv_ctx.conversation_id,
                    "speaker": conv_ctx.speaker,
                    "turn_count": len(conv_ctx.history),
                    "used_llm": False,
                    "latency_ms": 0,
                }

            summaries = []
            for entry in results[:5]:
                time_str = entry.timestamp.strftime("%b %d, %I:%M %p")
                deleted_marker = " [DELETED]" if entry.was_deleted else ""
                alert_marker = " ⚠️" if entry.triggered_alert else ""
                summaries.append(
                    f"- {entry.speaker or 'Unknown'} ({time_str}){deleted_marker}{alert_marker}: \"{entry.user_text[:40]}...\""
                )

            response = f"Found {len(results)} conversations:\n" + "\n".join(summaries)

            return {
                "response": response,
                "agent": self.name,
                "conversation_id": conv_ctx.conversation_id,
                "speaker": conv_ctx.speaker,
                "turn_count": len(conv_ctx.history),
                "used_llm": False,
                "latency_ms": 0,
                "audit_results": results,
            }

        except Exception as e:
            logger.error(f"Super user recall failed: {e}")
            return {
                "response": f"I encountered an error accessing the audit log: {e}",
                "agent": self.name,
                "conversation_id": conv_ctx.conversation_id,
                "speaker": conv_ctx.speaker,
                "turn_count": len(conv_ctx.history),
                "used_llm": False,
                "latency_ms": 0,
            }

    async def _handle_cross_device_handoff(
        self,
        text: str,
        conv_ctx: ConversationContext,
    ) -> dict[str, Any] | None:
        """Handle cross-device conversation handoff.

        Allows users to say "continue the conversation from my phone" to
        load a conversation from another device into the current context.
        """
        # Check if this is a cross-device request
        device_name = None
        for pattern in CROSS_DEVICE_PATTERNS_COMPILED:
            match = pattern.search(text)
            if match:
                device_name = match.group(1).lower()
                break

        if not device_name:
            return None

        try:
            from barnabeenet.services.audit.log import get_audit_log

            audit_log = get_audit_log()

            # Map common device names to room identifiers
            device_mappings = {
                "phone": ["phone", "mobile"],
                "kitchen": ["kitchen", "lenovo"],
                "office": ["office"],
                "bedroom": ["bedroom"],
                "living": ["living", "livingroom", "living_room"],
                "dashboard": ["dashboard", "web"],
            }

            # Find matching rooms
            search_rooms = device_mappings.get(device_name, [device_name])

            # Search for recent conversations from that device
            results = []
            for room in search_rooms:
                room_results = await audit_log.search(
                    room=room,
                    include_deleted=False,
                    limit=10,
                )
                results.extend(room_results)

            if not results:
                return {
                    "response": f"I couldn't find any recent conversations from {device_name}. "
                               "Try being more specific about which device.",
                    "agent": self.name,
                    "conversation_id": conv_ctx.conversation_id,
                    "speaker": conv_ctx.speaker,
                    "turn_count": len(conv_ctx.history),
                    "used_llm": False,
                    "latency_ms": 0,
                }

            # Sort by timestamp and get the most recent conversation
            results.sort(key=lambda e: e.timestamp, reverse=True)

            # Group by conversation_id to find distinct conversations
            conversations: dict[str, list] = {}
            for entry in results:
                if entry.conversation_id not in conversations:
                    conversations[entry.conversation_id] = []
                conversations[entry.conversation_id].append(entry)

            if len(conversations) == 1:
                # Only one conversation, load it directly
                conv_id = list(conversations.keys())[0]
                entries = conversations[conv_id]

                # Load conversation into current context
                for entry in sorted(entries, key=lambda e: e.timestamp):
                    conv_ctx.history.append(ConversationTurn(
                        role="user",
                        content=entry.user_text,
                        speaker=entry.speaker,
                    ))
                    if entry.assistant_response:
                        conv_ctx.history.append(ConversationTurn(
                            role="assistant",
                            content=entry.assistant_response,
                        ))

                return {
                    "response": f"I've loaded your conversation from {device_name}. "
                               f"We were discussing: {entries[0].user_text[:50]}... "
                               "Go ahead and continue!",
                    "agent": self.name,
                    "conversation_id": conv_ctx.conversation_id,
                    "speaker": conv_ctx.speaker,
                    "turn_count": len(conv_ctx.history),
                    "used_llm": False,
                    "latency_ms": 0,
                    "handoff_from": device_name,
                }

            # Multiple conversations - present options
            options = []
            conv_list = list(conversations.items())[:3]  # Max 3 for voice
            for i, (conv_id, entries) in enumerate(conv_list, 1):
                first_entry = min(entries, key=lambda e: e.timestamp)
                options.append(f"{i}. \"{first_entry.user_text[:40]}...\"")

            # Store candidates for selection
            conv_ctx.handoff_candidates = conv_list

            return {
                "response": f"I found {len(conversations)} conversations from {device_name}. "
                           f"Which one?\n" + "\n".join(options),
                "agent": self.name,
                "conversation_id": conv_ctx.conversation_id,
                "speaker": conv_ctx.speaker,
                "turn_count": len(conv_ctx.history),
                "used_llm": False,
                "latency_ms": 0,
            }

        except Exception as e:
            logger.error(f"Cross-device handoff failed: {e}")
            return None

    async def _handle_forget_command(
        self,
        text: str,
        conv_ctx: ConversationContext,
    ) -> dict[str, Any] | None:
        """Handle forget/delete memory commands.

        Supports:
        - "forget that" - marks the last recalled memory as deleted
        - "forget about the [topic] conversation" - searches and deletes matching
        """
        text_lower = text.lower()

        # Check for simple forget patterns
        is_forget = any(p.search(text_lower) for p in FORGET_PATTERNS_COMPILED)

        # Check for topic-specific forget
        topic_match = FORGET_TOPIC_PATTERN.search(text)

        if not is_forget and not topic_match:
            return None

        try:
            from barnabeenet.services.audit.log import get_audit_log

            audit_log = get_audit_log()

            if topic_match:
                # Forget specific topic
                topic = topic_match.group(1).strip()

                # Search for conversations about this topic
                results = await audit_log.search(
                    query=topic,
                    include_deleted=False,
                    limit=5,
                )

                if not results:
                    return {
                        "response": f"I couldn't find any conversations about '{topic}' to forget.",
                        "agent": self.name,
                        "conversation_id": conv_ctx.conversation_id,
                        "speaker": conv_ctx.speaker,
                        "turn_count": len(conv_ctx.history),
                        "used_llm": False,
                        "latency_ms": 0,
                    }

                # Mark all matching as deleted
                deleted_count = 0
                for entry in results:
                    if await audit_log.mark_as_deleted(entry.entry_id):
                        deleted_count += 1

                return {
                    "response": f"Done! I've forgotten {deleted_count} conversation(s) about '{topic}'.",
                    "agent": self.name,
                    "conversation_id": conv_ctx.conversation_id,
                    "speaker": conv_ctx.speaker,
                    "turn_count": len(conv_ctx.history),
                    "used_llm": False,
                    "latency_ms": 0,
                    "deleted_count": deleted_count,
                }

            # Simple "forget that" - forget the last recalled or mentioned memory
            if hasattr(conv_ctx, "last_recall_ids") and conv_ctx.last_recall_ids:
                deleted_count = 0
                for entry_id in conv_ctx.last_recall_ids:
                    if await audit_log.mark_as_deleted(entry_id):
                        deleted_count += 1

                conv_ctx.last_recall_ids = []

                return {
                    "response": "Done! I've forgotten that conversation.",
                    "agent": self.name,
                    "conversation_id": conv_ctx.conversation_id,
                    "speaker": conv_ctx.speaker,
                    "turn_count": len(conv_ctx.history),
                    "used_llm": False,
                    "latency_ms": 0,
                }

            # No specific target - forget the last few turns of current conversation
            return {
                "response": "What would you like me to forget? You can say 'forget about the [topic] conversation' "
                           "to forget specific conversations.",
                "agent": self.name,
                "conversation_id": conv_ctx.conversation_id,
                "speaker": conv_ctx.speaker,
                "turn_count": len(conv_ctx.history),
                "used_llm": False,
                "latency_ms": 0,
            }

        except Exception as e:
            logger.error(f"Forget command failed: {e}")
            return None

    async def _handle_expand_recall(
        self,
        text: str,
        conv_ctx: ConversationContext,
    ) -> dict[str, Any] | None:
        """Handle 'tell me more' to expand recall results.

        When recall returns brief summaries, users can say 'tell me more'
        or 'more details' to get the full conversation.
        """
        text_lower = text.lower().strip()

        expand_phrases = [
            "tell me more",
            "more details",
            "expand",
            "full conversation",
            "what else",
            "go on",
        ]

        if not any(phrase in text_lower for phrase in expand_phrases):
            return None

        # Check if we have expandable results
        if not hasattr(conv_ctx, "last_recall_results") or not conv_ctx.last_recall_results:
            return None

        try:
            from barnabeenet.services.audit.log import get_audit_log

            audit_log = get_audit_log()

            # Get full details of the last recall results
            details = []
            for entry in conv_ctx.last_recall_results[:3]:  # Limit to 3 for voice
                time_str = entry.timestamp.strftime("%B %d at %I:%M %p")
                details.append(
                    f"**{entry.speaker or 'Someone'}** ({time_str}):\n"
                    f"  Asked: \"{entry.user_text}\"\n"
                    f"  Response: \"{entry.assistant_response[:150]}...\""
                )

            response = "Here are the full details:\n\n" + "\n\n".join(details)

            # Clear the expandable results
            conv_ctx.last_recall_results = []

            return {
                "response": response,
                "agent": self.name,
                "conversation_id": conv_ctx.conversation_id,
                "speaker": conv_ctx.speaker,
                "turn_count": len(conv_ctx.history),
                "used_llm": False,
                "latency_ms": 0,
            }

        except Exception as e:
            logger.error(f"Expand recall failed: {e}")
            return None


__all__ = [
    "InteractionAgent",
    "InteractionConfig",
    "ConversationContext",
    "ConversationTurn",
    "BARNABEE_PERSONA",
]
