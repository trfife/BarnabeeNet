"""Conversation context management with summarization and recall.

Manages conversation history with intelligent summarization to keep context
within token limits while maintaining conversation continuity.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from barnabeenet.agents.interaction import ConversationContext, ConversationTurn
    from barnabeenet.services.memory.storage import MemoryStorage
    from barnabeenet.services.llm.openrouter import OpenRouterClient

logger = logging.getLogger(__name__)

# Token estimation: rough approximation (1 token ≈ 4 characters for English)
TOKENS_PER_CHAR = 0.25
# Conservative context limit: start summarizing at 80% of ~50k token context
CONTEXT_TOKEN_LIMIT = 40000  # ~80% of 50k
# Minimum turns before summarizing (keep recent context fresh)
MIN_TURNS_BEFORE_SUMMARY = 8
# Turns to keep in full detail (recent conversation)
RECENT_TURNS_TO_KEEP = 6


@dataclass
class ConversationSummary:
    """Summary of a past conversation."""

    conversation_id: str
    summary: str
    start_time: datetime
    end_time: datetime
    room: str | None
    speaker: str | None
    turn_count: int
    key_topics: list[str] = field(default_factory=list)


def estimate_tokens(text: str) -> int:
    """Estimate token count for text.

    Uses rough approximation: 1 token ≈ 4 characters for English text.
    This is conservative and works reasonably well for most models.
    """
    return int(len(text) * TOKENS_PER_CHAR)


def estimate_message_tokens(messages: list[dict[str, str]]) -> int:
    """Estimate total tokens for a list of messages."""
    total = 0
    for msg in messages:
        # Add overhead for message structure (~10 tokens per message)
        total += 10
        content = msg.get("content", "")
        total += estimate_tokens(content)
    return total


class ConversationContextManager:
    """Manages conversation context with intelligent summarization."""

    def __init__(
        self,
        memory_storage: MemoryStorage | None = None,
        llm_client: OpenRouterClient | None = None,
    ):
        """Initialize context manager.

        Args:
            memory_storage: Memory storage for storing/retrieving summaries.
            llm_client: LLM client for generating summaries.
        """
        self._memory_storage = memory_storage
        self._llm_client = llm_client
        self._conversation_start_times: dict[str, datetime] = {}

    def track_conversation_start(self, conversation_id: str, room: str | None = None) -> None:
        """Track when a conversation started."""
        if conversation_id not in self._conversation_start_times:
            self._conversation_start_times[conversation_id] = datetime.now()
            logger.debug(f"Tracking conversation start: {conversation_id} in {room}")

    def get_conversation_age(self, conversation_id: str) -> timedelta | None:
        """Get how long a conversation has been active."""
        start_time = self._conversation_start_times.get(conversation_id)
        if start_time:
            return datetime.now() - start_time
        return None

    async def manage_context(
        self,
        conv_ctx: Any,  # ConversationContext (avoid circular import)
        system_prompt: str,
        current_messages: list[dict[str, str]],
    ) -> tuple[list[dict[str, str]], str | None]:
        """Manage conversation context, summarizing if needed.

        Args:
            conv_ctx: Current conversation context.
            system_prompt: System prompt text.
            current_messages: Messages to send (including system and current turn).

        Returns:
            Tuple of (optimized_messages, summary_text_if_created)
        """
        # Estimate tokens for current request
        system_tokens = estimate_tokens(system_prompt)
        message_tokens = estimate_message_tokens(current_messages)
        total_estimated = system_tokens + message_tokens

        # Check if we need to summarize
        # Only summarize if:
        # 1. We have enough turns (MIN_TURNS_BEFORE_SUMMARY)
        # 2. AND we're approaching token limit OR have many turns
        if len(conv_ctx.history) < MIN_TURNS_BEFORE_SUMMARY:
            # Not enough turns yet - keep all
            return current_messages, None

        # Check if approaching token limit
        if total_estimated < CONTEXT_TOKEN_LIMIT and len(conv_ctx.history) < MIN_TURNS_BEFORE_SUMMARY * 2:
            # Still within limits - keep all
            return current_messages, None

        # Summarize old turns, keep recent ones
        turns_to_summarize = conv_ctx.history[:-RECENT_TURNS_TO_KEEP]
        recent_turns = conv_ctx.history[-RECENT_TURNS_TO_KEEP:]

        if not turns_to_summarize:
            # Nothing to summarize
            return current_messages, None

        # Generate summary of old turns
        summary = await self._generate_summary(
            turns_to_summarize,
            conv_ctx.conversation_id,
            conv_ctx.speaker,
            conv_ctx.room,
        )

        # Store summary in memory (with content filtering)
        if summary and self._memory_storage:
            # Check if this conversation should be stored
            should_store, reason = await self._should_store_memory(turns_to_summarize)

            if should_store:
                await self._store_conversation_summary(
                    conv_ctx.conversation_id,
                    summary,
                    conv_ctx.speaker,
                    conv_ctx.room,
                    len(turns_to_summarize),
                )
            else:
                logger.info(
                    f"Skipping memory storage for {conv_ctx.conversation_id}: {reason}"
                )

        # Build optimized message list
        optimized_messages = [current_messages[0]]  # System prompt

        # Add summary if created
        if summary:
            optimized_messages.append({
                "role": "system",
                "content": f"## Previous Conversation Summary\n{summary}\n\n(The conversation continued below with recent turns.)",
            })

        # Add recent turns
        for turn in recent_turns:
            optimized_messages.append({
                "role": turn.role,
                "content": turn.content,
            })

        # Add current user message (last in current_messages)
        optimized_messages.append(current_messages[-1])

        # Update conversation context (remove summarized turns)
        conv_ctx.history = recent_turns

        logger.info(
            f"Summarized {len(turns_to_summarize)} turns, kept {len(recent_turns)} recent turns",
            conversation_id=conv_ctx.conversation_id,
        )

        return optimized_messages, summary

    async def _generate_summary(
        self,
        turns: list[Any],  # list[ConversationTurn] (avoid circular import)
        conversation_id: str,
        speaker: str | None,
        room: str | None,
    ) -> str | None:
        """Generate summary of conversation turns using LLM."""
        if not self._llm_client or not turns:
            return None

        try:
            # Build conversation text
            conversation_text = "\n".join(
                f"{turn.role}: {turn.content}" for turn in turns
            )

            prompt = f"""Summarize the following conversation in 2-3 sentences. Focus on key topics discussed, decisions made, and important information shared.

Conversation:
{conversation_text}

Summary:"""

            response = await self._llm_client.simple_chat(
                user_message=prompt,
                agent_type="memory",  # Use memory agent model (cheaper, good at summarization)
            )

            return response.strip()

        except Exception as e:
            logger.error(f"Failed to generate conversation summary: {e}")
            return None

    async def _should_store_memory(
        self,
        conversation: list[Any],  # list[ConversationTurn]
    ) -> tuple[bool, str]:
        """Determine if a conversation should be stored in long-term memory.

        Uses LLM to filter out content that shouldn't be remembered:
        - Arguments or conflicts
        - Embarrassing moments
        - Private health information
        - Financial details
        - Passwords or secrets

        Args:
            conversation: List of conversation turns to analyze

        Returns:
            Tuple of (should_store, reason)
        """
        if not self._llm_client:
            # If no LLM, default to storing
            return True, "No LLM available for filtering"

        if not conversation or len(conversation) < 2:
            return False, "Conversation too short to store"

        try:
            # Build conversation text for analysis
            conversation_text = "\n".join(
                f"{turn.role}: {turn.content}" for turn in conversation[-10:]  # Analyze last 10 turns
            )

            prompt = """Analyze this conversation and decide if it should be stored in long-term memory.

DO NOT STORE conversations that contain:
- Arguments, conflicts, or heated disagreements
- Embarrassing moments or uncomfortable situations
- Private health information or medical details
- Financial information (account numbers, passwords, etc.)
- Passwords, PINs, or security codes
- Relationship problems or personal drama
- Complaints about family members
- Content a person might later regret sharing

DO STORE conversations that contain:
- Preferences and facts about people
- Helpful information for future reference
- Positive memories and experiences
- Practical information (recipes, recommendations, etc.)
- Plans and schedules
- Questions that might be asked again

Conversation:
{conversation_text}

Respond with ONLY one of these:
STORE - if the conversation should be remembered
SKIP - if the conversation should NOT be remembered

Then briefly explain why (max 10 words).

Example response:
STORE - Contains user's food preferences for future meals"""

            response = await self._llm_client.simple_chat(
                user_message=prompt.format(conversation_text=conversation_text),
                agent_type="memory",  # Use memory agent model
            )

            response_upper = response.strip().upper()

            if response_upper.startswith("STORE"):
                reason = response.split("-", 1)[1].strip() if "-" in response else "Approved for storage"
                return True, reason
            else:
                reason = response.split("-", 1)[1].strip() if "-" in response else "Filtered out"
                return False, reason

        except Exception as e:
            logger.error(f"Content filtering failed: {e}")
            # On error, err on the side of privacy - don't store
            return False, f"Filtering error: {e}"

    async def _store_conversation_summary(
        self,
        conversation_id: str,
        summary: str,
        speaker: str | None,
        room: str | None,
        turn_count: int,
    ) -> None:
        """Store conversation summary in memory."""
        if not self._memory_storage:
            return

        try:
            # Create memory content with metadata
            memory_content = f"Conversation summary ({conversation_id}): {summary}"
            if room:
                memory_content += f" [Location: {room}]"

            await self._memory_storage.store_memory(
                content=memory_content,
                memory_type="episodic",
                importance=0.7,  # Conversation summaries are moderately important
                participants=[speaker] if speaker else [],
                tags=["conversation_summary", conversation_id],
                generate_embedding_async=True,  # Generate embedding in background
            )

            logger.debug(f"Stored conversation summary for {conversation_id}")

        except Exception as e:
            logger.error(f"Failed to store conversation summary: {e}")

    async def recall_conversations(
        self,
        query: str,
        speaker: str | None = None,
        room: str | None = None,
        limit: int = 5,
        global_search: bool = True,
    ) -> list[ConversationSummary]:
        """Recall past conversations matching a query.

        By default, searches *all* conversations globally. Names mentioned
        in the query (like "Elizabeth") are treated as search terms, not filters.
        This allows users to ask about conversations other family members had.

        Args:
            query: Search query (e.g., "what did Elizabeth say about dinner?").
            speaker: Optional - the current speaker (used for context, not filtering)
            room: Optional - the current room (used for context, not filtering)
            limit: Maximum results to return.
            global_search: If True (default), search all conversations.
                          If False, filter by speaker.

        Returns:
            List of conversation summaries matching the query.
        """
        if not self._memory_storage:
            return []

        try:
            # Global search: Don't filter by participant, include names as search terms
            # Names in the query (like "Elizabeth") become part of the semantic search
            participants = None if global_search else ([speaker] if speaker else None)

            results = await self._memory_storage.search_memories(
                query=query,
                memory_type="episodic",
                participants=participants,
                max_results=limit * 2,  # Get more, filter by tags
            )

            # Filter to conversation summaries and convert to ConversationSummary
            summaries = []
            for memory, score in results:
                # Check if this is a conversation summary
                if "conversation_summary" in memory.tags:
                    # Extract conversation ID from tags
                    conv_id = None
                    for tag in memory.tags:
                        if tag.startswith("conv_") or len(tag) > 10:
                            conv_id = tag
                            break

                    if conv_id:
                        # Parse summary from content
                        content = memory.content
                        if "Conversation summary" in content:
                            # Extract summary text
                            summary_text = content.split(":", 1)[1] if ":" in content else content
                            # Remove location tag if present
                            if "[Location:" in summary_text:
                                summary_text = summary_text.split("[Location:")[0].strip()

                        summaries.append(
                            ConversationSummary(
                                conversation_id=conv_id,
                                summary=summary_text,
                                start_time=memory.created_at,
                                end_time=memory.last_accessed or memory.created_at,
                                room=room,  # Could extract from content if needed
                                speaker=memory.participants[0] if memory.participants else None,
                                turn_count=0,  # Not stored, would need to enhance
                            )
                        )

            return summaries[:limit]

        except Exception as e:
            logger.error(f"Failed to recall conversations: {e}")
            return []

    async def load_conversation_into_context(
        self,
        conversation_id: str,
        conv_ctx: Any,  # ConversationContext (avoid circular import)
    ) -> bool:
        """Load a past conversation summary into current context.

        Args:
            conversation_id: ID of conversation to load.
            conv_ctx: Current conversation context to merge into.

        Returns:
            True if conversation was found and loaded.
        """
        if not self._memory_storage:
            return False

        try:
            # Search for conversation summary
            results = await self._memory_storage.search_memories(
                query=f"conversation {conversation_id}",
                memory_type="episodic",
                max_results=1,
            )

            if not results:
                return False

            memory, _ = results[0]

            # Check if this is the right conversation
            if conversation_id not in memory.tags:
                return False

            # Add summary as a system message context
            summary_text = memory.content
            if "Conversation summary" in summary_text:
                summary_text = summary_text.split(":", 1)[1] if ":" in summary_text else summary_text
                if "[Location:" in summary_text:
                    summary_text = summary_text.split("[Location:")[0].strip()

            # Store in conversation context metadata for inclusion in prompt
            if not hasattr(conv_ctx, "loaded_conversations"):
                conv_ctx.loaded_conversations = []
            conv_ctx.loaded_conversations.append({
                "conversation_id": conversation_id,
                "summary": summary_text,
                "timestamp": memory.created_at.isoformat(),
            })

            logger.info(f"Loaded conversation {conversation_id} into context")
            return True

        except Exception as e:
            logger.error(f"Failed to load conversation into context: {e}")
            return False
