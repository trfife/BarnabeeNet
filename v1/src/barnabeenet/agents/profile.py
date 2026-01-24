"""Profile Agent - Generates and updates family member profiles.

Inspired by SkyrimNet's Character Profile (Bio) agent:
- Runs infrequently (not per-interaction)
- Generates structured profiles from accumulated events
- Produces diffs for human review before applying

This agent analyzes recent conversations, events, and memories to generate
or update profile sections using an LLM.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from barnabeenet.agents.base import Agent
from barnabeenet.models.profiles import (
    DiffEntry,
    DiffEntryType,
    FamilyMemberProfile,
    PrivateProfileBlock,
    ProfileDiff,
    PublicProfileBlock,
)

if TYPE_CHECKING:
    from barnabeenet.services.llm.openrouter import OpenRouterClient
    from barnabeenet.services.memory.storage import MemoryStorage
    from barnabeenet.services.profiles import ProfileService

logger = logging.getLogger(__name__)


PROFILE_GENERATION_PROMPT = """You are the Profile Agent for BarnabeeNet, a family home AI assistant. Your task is to
analyze recent interactions, events, and memories to generate or update a family member's
profile. You observe the family from Barnabee's first-person perspective.

## Current Profile (if exists)
{existing_profile}

## Family Member Identity
- Member ID: {member_id}
- Name: {name}
- Relationship: {relationship}
- Enrolled: {enrollment_date}

## Recent Events (Last 30 Days)
{recent_events}

## Recent Conversations (Last 20 interactions)
{recent_conversations}

## Relevant Memories (Barnabee's Observations)
{relevant_memories}

---

## Your Task

Generate an updated profile in the following JSON structure. Be observational and factual.
Write relationship_notes from Barnabee's first-person perspective (e.g., "I've noticed that...").

**Important Guidelines:**
1. PUBLIC block: Only include information safe to mention when other family members are present
2. PRIVATE block: Sensitive observations only used when speaking directly with this person
3. Preserve existing accurate information; update only what has changed
4. If uncertain about something, note the uncertainty rather than guessing
5. For goals_mentioned, preserve existing goals and add new ones; mark completed goals

Respond with ONLY valid JSON matching this schema (no markdown, no explanations):

{{
  "public": {{
    "schedule_summary": "string - general schedule patterns observed",
    "typical_locations": {{"time_period": "room"}},
    "preferences": {{
      "category": {{"preferred": "value", "context": "when/where"}}
    }},
    "interests": ["list of topics they care about"],
    "communication_style": "string - how they prefer to interact",
    "household_responsibilities": ["roles in the home"]
  }},
  "private": {{
    "emotional_patterns": "string - stress patterns, mood observations",
    "goals_mentioned": [
      {{
        "goal": "string",
        "mentioned_date": "ISO date",
        "status": "mentioned|in_progress|completed|abandoned",
        "context": "where/when discussed"
      }}
    ],
    "relationship_notes": "string - Barnabee's first-person observations about relationship",
    "sensitive_topics": ["topics to handle carefully"],
    "wellness_notes": "string or null - health/wellness observations if shared",
    "private_preferences": {{"key": "value"}}
  }},
  "update_summary": "Brief description of what changed and why",
  "confidence_notes": "Any uncertainties or things to verify"
}}"""


class ProfileAgent(Agent):
    """Agent responsible for generating and updating family member profiles.

    Features:
    - Runs infrequently (triggered by accumulated events)
    - Generates profiles from conversations, events, memories
    - Creates diffs for human review before applying
    - Supports both full regeneration and incremental updates
    """

    name = "profile"

    def __init__(
        self,
        llm_client: OpenRouterClient | None = None,
        profile_service: ProfileService | None = None,
        memory_storage: MemoryStorage | None = None,
    ) -> None:
        """Initialize the Profile Agent.

        Args:
            llm_client: LLM client for profile generation
            profile_service: Service for profile storage
            memory_storage: Memory storage for retrieving context
        """
        self._llm = llm_client
        self._profile_service = profile_service
        self._memory_storage = memory_storage

    async def init(self) -> None:
        """Initialize the agent."""
        logger.info("ProfileAgent initialized")

    async def shutdown(self) -> None:
        """Shutdown the agent."""
        logger.info("ProfileAgent shutdown")

    async def handle_input(self, text: str, context: dict | None = None) -> dict[str, Any]:
        """Handle profile-related commands.

        This isn't used in the normal agent pipeline - profiles are generated
        via the dedicated generate_profile_update method.
        """
        return {
            "response": "Profile management is handled through the dashboard.",
            "agent": "profile",
        }

    async def check_for_updates(self) -> list[tuple[str, list[str]]]:
        """Check all profiles for needed updates.

        Returns:
            List of (member_id, trigger_reasons) tuples for profiles needing updates
        """
        if not self._profile_service:
            return []

        members_to_update = []
        profiles = await self._profile_service.get_all_profiles()

        for profile in profiles:
            should_update, triggers = await self._profile_service.should_trigger_update(
                profile.member_id
            )
            if should_update:
                members_to_update.append((profile.member_id, triggers))
                logger.info(f"Profile update triggered for {profile.member_id}: {triggers}")

        return members_to_update

    async def generate_profile_update(
        self,
        member_id: str,
        triggers: list[str] | None = None,
    ) -> ProfileDiff | None:
        """Generate a profile update for review.

        Args:
            member_id: The member's ID
            triggers: List of triggers that caused this update

        Returns:
            ProfileDiff with proposed changes, or None if generation fails
        """
        if not self._profile_service:
            logger.error("ProfileService not configured")
            return None

        profile = await self._profile_service.get_profile(member_id)
        if not profile:
            logger.error(f"Profile not found: {member_id}")
            return None

        # Gather context
        recent_events = await self._profile_service.get_unprocessed_events(member_id)
        recent_conversations = await self._get_recent_conversations(member_id)
        relevant_memories = await self._get_relevant_memories(member_id, profile.name)

        # Generate new profile via LLM
        proposed = await self._generate_via_llm(
            existing=profile,
            recent_events=recent_events,
            recent_conversations=recent_conversations,
            relevant_memories=relevant_memories,
        )

        if not proposed:
            logger.warning(f"Failed to generate profile update for {member_id}")
            return None

        # Generate diff
        diff = self._generate_diff(
            existing=profile,
            proposed=proposed,
            triggers=triggers or [],
        )

        # Store as pending update
        await self._profile_service.set_pending_update(member_id, diff)

        # Mark events as processed
        await self._profile_service.mark_events_processed(member_id)

        logger.info(f"Generated profile update for {member_id}: {len(diff.modifications)} changes")
        return diff

    async def _generate_via_llm(
        self,
        existing: FamilyMemberProfile,
        recent_events: list,
        recent_conversations: list,
        relevant_memories: list,
    ) -> FamilyMemberProfile | None:
        """Use LLM to generate updated profile.

        Args:
            existing: Current profile
            recent_events: Recent profile events
            recent_conversations: Recent conversations with this member
            relevant_memories: Related memories

        Returns:
            New profile or None if generation fails
        """
        if not self._llm:
            logger.warning("No LLM client - using simple profile generation")
            return self._generate_simple_profile(existing, recent_events)

        # Format context for prompt
        existing_json = json.dumps(
            {
                "public": existing.public.model_dump(),
                "private": existing.private.model_dump(),
            },
            indent=2,
        )

        events_text = "\n".join(
            f"- [{e.occurred_at.strftime('%Y-%m-%d')}] {e.event_type.value}: {e.description}"
            for e in recent_events[:20]
        )
        if not events_text:
            events_text = "No recent events recorded."

        conversations_text = "\n".join(
            f"- {c.get('timestamp', 'Unknown')}: {c.get('summary', c.get('content', ''))[:200]}"
            for c in recent_conversations[:10]
        )
        if not conversations_text:
            conversations_text = "No recent conversations recorded."

        memories_text = "\n".join(f"- {m.get('content', '')[:200]}" for m in relevant_memories[:10])
        if not memories_text:
            memories_text = "No relevant memories found."

        prompt = PROFILE_GENERATION_PROMPT.format(
            existing_profile=existing_json,
            member_id=existing.member_id,
            name=existing.name,
            relationship=existing.relationship_to_primary.value,
            enrollment_date=existing.enrollment_date.strftime("%Y-%m-%d"),
            recent_events=events_text,
            recent_conversations=conversations_text,
            relevant_memories=memories_text,
        )

        try:
            response = await self._llm.complete(
                prompt=prompt,
                activity="profile.generate",
                max_tokens=2000,
                temperature=0.3,
            )

            # Parse response
            return self._parse_profile_response(response, existing)

        except Exception as e:
            logger.error(f"LLM profile generation failed: {e}")
            return None

    def _generate_simple_profile(
        self,
        existing: FamilyMemberProfile,
        events: list,
    ) -> FamilyMemberProfile:
        """Generate a simple profile update without LLM.

        Used as fallback when no LLM is available.
        """
        # Just return the existing profile - no changes without LLM analysis
        return existing

    def _parse_profile_response(
        self,
        response: str,
        existing: FamilyMemberProfile,
    ) -> FamilyMemberProfile | None:
        """Parse LLM JSON response into profile object.

        Args:
            response: LLM response (should be JSON)
            existing: Existing profile for reference

        Returns:
            New profile or None if parsing fails
        """
        try:
            # Clean up response - remove markdown code blocks if present
            text = response.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

            data = json.loads(text)

            # Extract public block
            public_data = data.get("public", {})
            public = PublicProfileBlock(
                schedule_summary=public_data.get("schedule_summary", ""),
                typical_locations=public_data.get("typical_locations", {}),
                preferences=public_data.get("preferences", {}),
                interests=public_data.get("interests", []),
                communication_style=public_data.get("communication_style", ""),
                household_responsibilities=public_data.get("household_responsibilities", []),
            )

            # Extract private block
            private_data = data.get("private", {})
            private = PrivateProfileBlock(
                emotional_patterns=private_data.get("emotional_patterns", ""),
                goals_mentioned=[],  # Parse goals separately if needed
                relationship_notes=private_data.get("relationship_notes", ""),
                sensitive_topics=private_data.get("sensitive_topics", []),
                wellness_notes=private_data.get("wellness_notes"),
                private_preferences=private_data.get("private_preferences", {}),
            )

            return FamilyMemberProfile(
                member_id=existing.member_id,
                name=existing.name,
                relationship_to_primary=existing.relationship_to_primary,
                enrollment_date=existing.enrollment_date,
                public=public,
                private=private,
                version=existing.version,
                last_updated=existing.last_updated,
            )

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse profile JSON: {e}")
            logger.debug(f"Response was: {response[:500]}")
            return None
        except Exception as e:
            logger.error(f"Failed to create profile from response: {e}")
            return None

    def _generate_diff(
        self,
        existing: FamilyMemberProfile,
        proposed: FamilyMemberProfile,
        triggers: list[str],
    ) -> ProfileDiff:
        """Generate a diff between existing and proposed profiles.

        Args:
            existing: Current profile
            proposed: Proposed new profile
            triggers: What triggered this update

        Returns:
            ProfileDiff with categorized changes
        """
        additions: list[DiffEntry] = []
        modifications: list[DiffEntry] = []
        removals: list[DiffEntry] = []

        # Compare public blocks
        self._compare_blocks(
            existing.public.model_dump(),
            proposed.public.model_dump(),
            "public",
            additions,
            modifications,
            removals,
        )

        # Compare private blocks
        self._compare_blocks(
            existing.private.model_dump(),
            proposed.private.model_dump(),
            "private",
            additions,
            modifications,
            removals,
        )

        # Generate summary
        summary_parts = []
        if additions:
            summary_parts.append(f"Added {len(additions)} new observations")
        if modifications:
            summary_parts.append(f"Updated {len(modifications)} existing entries")
        if removals:
            summary_parts.append(f"Removed {len(removals)} outdated entries")
        if triggers:
            summary_parts.append(f"Triggered by: {', '.join(triggers)}")

        summary = ". ".join(summary_parts) + "." if summary_parts else "No significant changes."

        return ProfileDiff(
            member_id=existing.member_id,
            from_version=existing.version,
            to_version=existing.version + 1,
            additions=additions,
            modifications=modifications,
            removals=removals,
            generated_at=datetime.now(UTC),
            triggering_events=triggers,
            llm_summary=summary,
        )

    def _compare_blocks(
        self,
        old: dict[str, Any],
        new: dict[str, Any],
        block_name: str,
        additions: list[DiffEntry],
        modifications: list[DiffEntry],
        removals: list[DiffEntry],
        path_prefix: str = "",
    ) -> None:
        """Recursively compare two dictionaries and categorize changes.

        Args:
            old: Old data
            new: New data
            block_name: Block name (public/private)
            additions: List to add additions to
            modifications: List to add modifications to
            removals: List to add removals to
            path_prefix: Current path prefix for nested fields
        """
        all_keys = set(old.keys()) | set(new.keys())

        for key in all_keys:
            old_val = old.get(key)
            new_val = new.get(key)
            field_path = f"{path_prefix}{key}" if path_prefix else key
            full_path = f"{block_name}.{field_path}"

            if old_val is None and new_val is not None:
                # Skip empty values
                if new_val in ([], {}, "", None):
                    continue
                additions.append(
                    DiffEntry(
                        block=block_name,
                        field_path=full_path,
                        diff_type=DiffEntryType.ADDED,
                        old_value=None,
                        new_value=new_val,
                        reason="New information learned",
                    )
                )
            elif old_val is not None and new_val is None:
                removals.append(
                    DiffEntry(
                        block=block_name,
                        field_path=full_path,
                        diff_type=DiffEntryType.REMOVED,
                        old_value=old_val,
                        new_value=None,
                        reason="Information no longer relevant",
                    )
                )
            elif old_val != new_val:
                # Skip if both are empty/falsy
                if not old_val and not new_val:
                    continue

                if isinstance(old_val, dict) and isinstance(new_val, dict):
                    # Recurse into nested dicts
                    self._compare_blocks(
                        old_val,
                        new_val,
                        block_name,
                        additions,
                        modifications,
                        removals,
                        f"{field_path}.",
                    )
                else:
                    modifications.append(
                        DiffEntry(
                            block=block_name,
                            field_path=full_path,
                            diff_type=DiffEntryType.MODIFIED,
                            old_value=old_val,
                            new_value=new_val,
                            reason="Updated based on recent observations",
                        )
                    )

    async def _get_recent_conversations(self, member_id: str) -> list[dict]:
        """Get recent conversations for a member.

        Args:
            member_id: The member's ID

        Returns:
            List of conversation summaries
        """
        if not self._memory_storage:
            return []

        try:
            # Search for memories involving this member
            memories = await self._memory_storage.search_memories(
                query=f"conversation with {member_id}",
                memory_type="episodic",
                limit=20,
            )
            return [
                {
                    "timestamp": m.created_at.isoformat()
                    if hasattr(m, "created_at")
                    else "Unknown",
                    "content": m.content if hasattr(m, "content") else str(m),
                }
                for m in memories
            ]
        except Exception as e:
            logger.warning(f"Could not get conversations: {e}")
            return []

    async def _get_relevant_memories(self, member_id: str, name: str) -> list[dict]:
        """Get relevant memories about a member.

        Args:
            member_id: The member's ID
            name: The member's display name

        Returns:
            List of relevant memories
        """
        if not self._memory_storage:
            return []

        try:
            # Search for memories about this person
            memories = await self._memory_storage.search_memories(
                query=f"observations about {name}",
                limit=10,
            )
            return [
                {
                    "content": m.content if hasattr(m, "content") else str(m),
                    "type": m.memory_type if hasattr(m, "memory_type") else "unknown",
                }
                for m in memories
            ]
        except Exception as e:
            logger.warning(f"Could not get memories: {e}")
            return []
