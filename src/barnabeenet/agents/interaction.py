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

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from barnabeenet.agents.base import Agent
from barnabeenet.services.llm.openrouter import ChatMessage, OpenRouterClient

logger = logging.getLogger(__name__)


@dataclass
class ConversationTurn:
    """A single turn in a conversation."""

    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    speaker: str | None = None  # Family member ID if known


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

        # Build conversation context
        conv_ctx = self._get_or_create_context(ctx)

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

    def _get_or_create_context(self, ctx: dict[str, Any]) -> ConversationContext:
        """Get existing conversation or create new one."""
        conv_id = ctx.get("conversation_id") or f"conv_{id(ctx)}"

        if conv_id in self._conversations:
            conv_ctx = self._conversations[conv_id]
            # Update with any new context
            if ctx.get("retrieved_memories"):
                conv_ctx.retrieved_memories = ctx["retrieved_memories"]
            if ctx.get("meta_context"):
                conv_ctx.meta_context = ctx["meta_context"]
        else:
            conv_ctx = ConversationContext(
                conversation_id=conv_id,
                speaker=ctx.get("speaker"),
                room=ctx.get("room"),
                retrieved_memories=ctx.get("retrieved_memories", []),
                meta_context=ctx.get("meta_context"),
                time_of_day=ctx.get("time_of_day", "day"),
            )
            self._conversations[conv_id] = conv_ctx

        return conv_ctx

    def _build_system_prompt(self, conv_ctx: ConversationContext, user_ctx: dict[str, Any]) -> str:
        """Build the system prompt with context."""
        parts = [BARNABEE_PERSONA]

        # Add current context
        parts.append("\n## Current Situation")

        # Current date and time (actual values for accurate responses)
        now = datetime.now()
        current_time = now.strftime("%I:%M %p").lstrip("0")
        current_date = now.strftime("%A, %B %d, %Y")
        timezone = "Central Time (Chicago)"  # TODO: Make configurable
        parts.append(f"- Current time: {current_time} {timezone}")
        parts.append(f"- Current date: {current_date}")

        # Time-of-day context for tone
        time_phrase = TIME_GREETINGS.get(conv_ctx.time_of_day, "today")
        parts.append(f"- Time of day: {time_phrase}")

        # Speaker context
        if conv_ctx.speaker:
            speaker_name = self._format_speaker_name(conv_ctx.speaker)
            parts.append(f"- Speaking with: {speaker_name}")

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

        # Add context type indicator
        context_type = profile.get("context_type", "public_only")
        if context_type == "guest":
            parts.append("- Guest user (limited profile information)")
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

    def _build_messages(
        self,
        current_text: str,
        conv_ctx: ConversationContext,
        system_prompt: str,
    ) -> list[ChatMessage]:
        """Build the message list for the LLM."""
        messages = [ChatMessage(role="system", content=system_prompt)]

        # Add conversation history (excluding the just-added user message)
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
        messages = self._build_messages(text, conv_ctx, system_prompt)

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

    def clear_conversation(self, conversation_id: str) -> bool:
        """Clear a conversation's history."""
        if conversation_id in self._conversations:
            del self._conversations[conversation_id]
            return True
        return False

    def get_active_conversations(self) -> list[str]:
        """Get list of active conversation IDs."""
        return list(self._conversations.keys())


__all__ = [
    "InteractionAgent",
    "InteractionConfig",
    "ConversationContext",
    "ConversationTurn",
    "BARNABEE_PERSONA",
]
