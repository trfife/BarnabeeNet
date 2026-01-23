"""Profile Service - Manages family member profiles in Redis.

Provides CRUD operations for family profiles with:
- Profile storage and retrieval
- Event tracking for profile updates
- Version history management
- Profile context injection for agents
- Home Assistant person entity integration for real-time location
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from barnabeenet.models.profiles import (
    EVENT_SIGNIFICANCE_SCORES,
    CreateProfileRequest,
    FamilyMemberProfile,
    GuestProfile,
    PersonLocation,
    PrivacyZone,
    PrivateProfileBlock,
    ProfileContextResponse,
    ProfileDiff,
    ProfileEvent,
    ProfileEventType,
    ProfileStatsResponse,
    PublicProfileBlock,
)

if TYPE_CHECKING:
    import redis.asyncio as redis

    from barnabeenet.services.homeassistant.client import HomeAssistantClient

logger = logging.getLogger(__name__)


class ProfileService:
    """Service for managing family member profiles.

    Features:
    - Profile CRUD with Redis storage
    - Event tracking for update triggers
    - Version history management
    - Privacy-aware context injection
    """

    # Redis key prefixes
    PROFILE_PREFIX = "barnabeenet:profile:"
    PROFILE_HISTORY_PREFIX = "barnabeenet:profile_history:"
    PROFILE_EVENT_PREFIX = "barnabeenet:profile_event:"
    GUEST_PREFIX = "barnabeenet:guest:"

    def __init__(
        self,
        redis_client: redis.Redis | None = None,
        ha_client: HomeAssistantClient | None = None,
    ) -> None:
        """Initialize the profile service.

        Args:
            redis_client: Redis client for storage. Falls back to in-memory if None.
            ha_client: Home Assistant client for fetching person location data.
        """
        self._redis = redis_client
        self._ha_client = ha_client
        self._profiles: dict[str, FamilyMemberProfile] = {}  # In-memory fallback
        self._events: dict[str, list[ProfileEvent]] = {}  # In-memory fallback
        self._history: dict[str, list[dict]] = {}  # In-memory fallback
        self._guests: dict[str, GuestProfile] = {}  # In-memory fallback

    def set_ha_client(self, ha_client: HomeAssistantClient | None) -> None:
        """Set or update the Home Assistant client.

        Args:
            ha_client: Home Assistant client for person location data.
        """
        self._ha_client = ha_client

    async def init(self) -> None:
        """Initialize the service and load existing profiles."""
        if self._redis:
            # Load existing profiles from Redis
            try:
                keys = await self._redis.keys(f"{self.PROFILE_PREFIX}*")
                for key in keys:
                    if isinstance(key, bytes):
                        key = key.decode()
                    data = await self._redis.get(key)
                    if data:
                        if isinstance(data, bytes):
                            data = data.decode()
                        member_id = key.replace(self.PROFILE_PREFIX, "")
                        self._profiles[member_id] = FamilyMemberProfile.model_validate_json(data)
                logger.info(f"Loaded {len(self._profiles)} profiles from Redis")
            except Exception as e:
                logger.warning(f"Could not load profiles from Redis: {e}")

    # =========================================================================
    # Profile CRUD
    # =========================================================================

    async def create_profile(self, request: CreateProfileRequest) -> FamilyMemberProfile:
        """Create a new family member profile.

        Args:
            request: Profile creation request

        Returns:
            The created profile

        Raises:
            ValueError: If profile already exists
        """
        if await self.get_profile(request.member_id):
            raise ValueError(f"Profile already exists: {request.member_id}")

        profile = FamilyMemberProfile(
            member_id=request.member_id,
            name=request.name,
            relationship_to_primary=request.relationship,
            enrollment_date=datetime.now(UTC),
            ha_person_entity=request.ha_person_entity,
            public=request.public or PublicProfileBlock(),
            private=request.private or PrivateProfileBlock(),
        )

        await self._save_profile(profile)
        logger.info(f"Created profile for {request.member_id}")
        return profile

    async def get_profile(self, member_id: str) -> FamilyMemberProfile | None:
        """Get a profile by member ID or first name.

        Args:
            member_id: The member's unique identifier OR first name (e.g., "thom")

        Returns:
            The profile or None if not found
        """
        member_id_lower = member_id.lower()

        # Check in-memory cache first (exact match)
        if member_id in self._profiles:
            return self._profiles[member_id]

        # Try Redis (exact match)
        if self._redis:
            try:
                data = await self._redis.get(f"{self.PROFILE_PREFIX}{member_id}")
                if data:
                    if isinstance(data, bytes):
                        data = data.decode()
                    profile = FamilyMemberProfile.model_validate_json(data)
                    self._profiles[member_id] = profile
                    return profile
            except Exception as e:
                logger.warning(f"Could not get profile from Redis: {e}")

        # Try fuzzy match by first name (e.g., "thom" -> "thom_fife")
        # First check in-memory profiles
        for profile_id, profile in self._profiles.items():
            name_parts = profile.name.lower().split()
            if name_parts and name_parts[0] == member_id_lower:
                return profile

        # Then check Redis for all profiles
        if self._redis:
            try:
                keys = await self._redis.keys(f"{self.PROFILE_PREFIX}*")
                for key in keys:
                    if isinstance(key, bytes):
                        key = key.decode()
                    data = await self._redis.get(key)
                    if data:
                        if isinstance(data, bytes):
                            data = data.decode()
                        profile = FamilyMemberProfile.model_validate_json(data)
                        name_parts = profile.name.lower().split()
                        if name_parts and name_parts[0] == member_id_lower:
                            self._profiles[profile.member_id] = profile
                            return profile
            except Exception as e:
                logger.warning(f"Could not search profiles by first name: {e}")

        return None

    async def get_all_profiles(self) -> list[FamilyMemberProfile]:
        """Get all profiles.

        Returns:
            List of all profiles
        """
        if self._redis:
            try:
                keys = await self._redis.keys(f"{self.PROFILE_PREFIX}*")
                profiles = []
                for key in keys:
                    if isinstance(key, bytes):
                        key = key.decode()
                    data = await self._redis.get(key)
                    if data:
                        if isinstance(data, bytes):
                            data = data.decode()
                        profiles.append(FamilyMemberProfile.model_validate_json(data))
                return profiles
            except Exception as e:
                logger.warning(f"Could not get profiles from Redis: {e}")

        return list(self._profiles.values())

    async def update_profile(
        self,
        member_id: str,
        public: PublicProfileBlock | None = None,
        private: PrivateProfileBlock | None = None,
        ha_person_entity: str | None = None,
        increment_version: bool = True,
    ) -> FamilyMemberProfile:
        """Update an existing profile.

        Args:
            member_id: The member's ID
            public: New public block (optional)
            private: New private block (optional)
            ha_person_entity: HA person entity ID to link (optional)
            increment_version: Whether to increment version number

        Returns:
            The updated profile

        Raises:
            ValueError: If profile not found
        """
        profile = await self.get_profile(member_id)
        if not profile:
            raise ValueError(f"Profile not found: {member_id}")

        # Archive current version before updating
        if increment_version:
            await self._archive_version(profile)

        # Update fields
        if public:
            profile.public = public
        if private:
            profile.private = private
        if ha_person_entity is not None:
            profile.ha_person_entity = ha_person_entity
        if increment_version:
            profile.version += 1
        profile.last_updated = datetime.now(UTC)

        await self._save_profile(profile)
        logger.info(f"Updated profile {member_id} to version {profile.version}")
        return profile

    async def delete_profile(self, member_id: str) -> bool:
        """Delete a profile.

        Args:
            member_id: The member's ID

        Returns:
            True if deleted, False if not found
        """
        if member_id in self._profiles:
            del self._profiles[member_id]

        if self._redis:
            try:
                result = await self._redis.delete(f"{self.PROFILE_PREFIX}{member_id}")
                return result > 0
            except Exception as e:
                logger.warning(f"Could not delete profile from Redis: {e}")

        return False

    async def _save_profile(self, profile: FamilyMemberProfile) -> None:
        """Save a profile to storage."""
        self._profiles[profile.member_id] = profile

        if self._redis:
            try:
                await self._redis.set(
                    f"{self.PROFILE_PREFIX}{profile.member_id}",
                    profile.model_dump_json(),
                )
            except Exception as e:
                logger.warning(f"Could not save profile to Redis: {e}")

    # =========================================================================
    # Version History
    # =========================================================================

    async def _archive_version(self, profile: FamilyMemberProfile) -> None:
        """Archive the current version before an update."""
        history_entry = {
            "version": profile.version,
            "public": profile.public.model_dump(),
            "private": profile.private.model_dump(),
            "update_triggers": profile.update_triggers,
            "archived_at": datetime.now(UTC).isoformat(),
        }

        # In-memory
        if profile.member_id not in self._history:
            self._history[profile.member_id] = []
        self._history[profile.member_id].append(history_entry)

        # Redis
        if self._redis:
            try:
                key = f"{self.PROFILE_HISTORY_PREFIX}{profile.member_id}"
                await self._redis.rpush(key, json.dumps(history_entry))
            except Exception as e:
                logger.warning(f"Could not archive profile version to Redis: {e}")

    async def get_version_history(self, member_id: str) -> list[dict]:
        """Get version history for a profile.

        Args:
            member_id: The member's ID

        Returns:
            List of historical versions
        """
        if self._redis:
            try:
                key = f"{self.PROFILE_HISTORY_PREFIX}{member_id}"
                entries = await self._redis.lrange(key, 0, -1)
                return [json.loads(e.decode() if isinstance(e, bytes) else e) for e in entries]
            except Exception as e:
                logger.warning(f"Could not get history from Redis: {e}")

        return self._history.get(member_id, [])

    # =========================================================================
    # Profile Events
    # =========================================================================

    async def add_event(
        self,
        member_id: str,
        event_type: ProfileEventType,
        description: str,
        conversation_id: str | None = None,
    ) -> ProfileEvent:
        """Add a profile event for potential update triggering.

        Args:
            member_id: The member this event relates to
            event_type: Type of event
            description: Description of the event
            conversation_id: Source conversation ID

        Returns:
            The created event
        """
        event = ProfileEvent(
            member_id=member_id,
            event_type=event_type,
            description=description,
            significance_score=EVENT_SIGNIFICANCE_SCORES.get(event_type, 0.1),
            source_conversation_id=conversation_id,
        )

        # In-memory
        if member_id not in self._events:
            self._events[member_id] = []
        self._events[member_id].append(event)

        # Redis
        if self._redis:
            try:
                key = f"{self.PROFILE_EVENT_PREFIX}{member_id}"
                await self._redis.rpush(key, event.model_dump_json())
            except Exception as e:
                logger.warning(f"Could not save event to Redis: {e}")

        logger.debug(f"Added event for {member_id}: {event_type.value}")
        return event

    async def get_unprocessed_events(self, member_id: str) -> list[ProfileEvent]:
        """Get unprocessed events for a member.

        Args:
            member_id: The member's ID

        Returns:
            List of unprocessed events
        """
        events = []

        if self._redis:
            try:
                key = f"{self.PROFILE_EVENT_PREFIX}{member_id}"
                raw_events = await self._redis.lrange(key, 0, -1)
                for e in raw_events:
                    data = json.loads(e.decode() if isinstance(e, bytes) else e)
                    event = ProfileEvent.model_validate(data)
                    if not event.processed:
                        events.append(event)
            except Exception as e:
                logger.warning(f"Could not get events from Redis: {e}")
        else:
            events = [e for e in self._events.get(member_id, []) if not e.processed]

        return events

    async def get_accumulated_significance(self, member_id: str) -> float:
        """Get total significance score of unprocessed events.

        Args:
            member_id: The member's ID

        Returns:
            Sum of significance scores
        """
        events = await self.get_unprocessed_events(member_id)
        return sum(e.significance_score for e in events)

    async def mark_events_processed(self, member_id: str) -> int:
        """Mark all events as processed after a profile update.

        Args:
            member_id: The member's ID

        Returns:
            Number of events marked
        """
        # In-memory
        count = 0
        for event in self._events.get(member_id, []):
            if not event.processed:
                event.processed = True
                count += 1

        # Redis - rewrite all events with processed flag
        if self._redis:
            try:
                key = f"{self.PROFILE_EVENT_PREFIX}{member_id}"
                raw_events = await self._redis.lrange(key, 0, -1)
                await self._redis.delete(key)
                for e in raw_events:
                    data = json.loads(e.decode() if isinstance(e, bytes) else e)
                    data["processed"] = True
                    await self._redis.rpush(key, json.dumps(data))
            except Exception as e:
                logger.warning(f"Could not mark events processed in Redis: {e}")

        return count

    # =========================================================================
    # Pending Updates
    # =========================================================================

    async def set_pending_update(
        self,
        member_id: str,
        diff: ProfileDiff,
    ) -> None:
        """Set a pending update for review.

        Args:
            member_id: The member's ID
            diff: The profile diff awaiting approval
        """
        profile = await self.get_profile(member_id)
        if not profile:
            raise ValueError(f"Profile not found: {member_id}")

        profile.pending_update = diff
        profile.pending_update_generated = datetime.now(UTC)
        await self._save_profile(profile)
        logger.info(f"Set pending update for {member_id}")

    async def get_profiles_with_pending_updates(self) -> list[FamilyMemberProfile]:
        """Get all profiles that have pending updates.

        Returns:
            List of profiles with pending updates
        """
        profiles = await self.get_all_profiles()
        return [p for p in profiles if p.pending_update is not None]

    async def apply_pending_update(self, member_id: str) -> FamilyMemberProfile:
        """Apply a pending update to the profile.

        Args:
            member_id: The member's ID

        Returns:
            The updated profile

        Raises:
            ValueError: If no pending update exists
        """
        profile = await self.get_profile(member_id)
        if not profile or not profile.pending_update:
            raise ValueError(f"No pending update for {member_id}")

        diff = profile.pending_update

        # Apply additions and modifications to public block
        public_data = profile.public.model_dump()
        private_data = profile.private.model_dump()

        for entry in diff.additions + diff.modifications:
            path_parts = entry.field_path.split(".")
            if path_parts[0] == "public":
                self._apply_change(public_data, path_parts[1:], entry.new_value)
            elif path_parts[0] == "private":
                self._apply_change(private_data, path_parts[1:], entry.new_value)

        # Apply removals
        for entry in diff.removals:
            path_parts = entry.field_path.split(".")
            if path_parts[0] == "public":
                self._remove_field(public_data, path_parts[1:])
            elif path_parts[0] == "private":
                self._remove_field(private_data, path_parts[1:])

        # Clear pending update and update profile
        profile.pending_update = None
        profile.pending_update_generated = None
        profile.update_triggers = diff.triggering_events

        return await self.update_profile(
            member_id,
            public=PublicProfileBlock.model_validate(public_data),
            private=PrivateProfileBlock.model_validate(private_data),
            increment_version=True,
        )

    async def reject_pending_update(self, member_id: str, reason: str | None = None) -> None:
        """Reject and clear a pending update.

        Args:
            member_id: The member's ID
            reason: Optional rejection reason
        """
        profile = await self.get_profile(member_id)
        if profile:
            profile.pending_update = None
            profile.pending_update_generated = None
            await self._save_profile(profile)
            logger.info(f"Rejected pending update for {member_id}: {reason}")

    def _apply_change(self, data: dict, path: list[str], value: Any) -> None:
        """Apply a change to a nested dictionary path."""
        if len(path) == 1:
            data[path[0]] = value
        elif path:
            if path[0] not in data:
                data[path[0]] = {}
            self._apply_change(data[path[0]], path[1:], value)

    def _remove_field(self, data: dict, path: list[str]) -> None:
        """Remove a field from a nested dictionary path."""
        if len(path) == 1 and path[0] in data:
            del data[path[0]]
        elif len(path) > 1 and path[0] in data:
            self._remove_field(data[path[0]], path[1:])

    # =========================================================================
    # Home Assistant Person Integration
    # =========================================================================

    async def get_person_location(self, ha_person_entity: str) -> PersonLocation | None:
        """Get current location for a Home Assistant person entity.

        Args:
            ha_person_entity: The HA person entity ID (e.g., "person.thom")

        Returns:
            PersonLocation with current state and coordinates, or None if unavailable.
        """
        if not self._ha_client or not ha_person_entity:
            return None

        try:
            state = await self._ha_client.get_state(ha_person_entity)
            if not state:
                return None

            attrs = state.attributes or {}

            # Parse last_changed timestamp
            last_changed = None
            if state.last_changed:
                try:
                    # Handle ISO format timestamp
                    if isinstance(state.last_changed, str):
                        last_changed = datetime.fromisoformat(
                            state.last_changed.replace("Z", "+00:00")
                        )
                    else:
                        last_changed = state.last_changed
                except (ValueError, TypeError):
                    pass

            return PersonLocation(
                state=state.state,
                is_home=state.state.lower() == "home",
                zone=state.state if state.state.lower() not in ("home", "not_home") else None,
                latitude=attrs.get("latitude"),
                longitude=attrs.get("longitude"),
                gps_accuracy=attrs.get("gps_accuracy"),
                last_changed=last_changed,
                source=attrs.get("source"),
            )
        except Exception as e:
            logger.warning(f"Failed to get person location for {ha_person_entity}: {e}")
            return None

    async def get_all_family_locations(self) -> dict[str, PersonLocation]:
        """Get current locations for all family members with HA person entities.

        Returns:
            Dict mapping member_id to their PersonLocation.
        """
        locations: dict[str, PersonLocation] = {}

        for member_id, profile in self._profiles.items():
            if profile.ha_person_entity:
                location = await self.get_person_location(profile.ha_person_entity)
                if location:
                    locations[member_id] = location

        return locations

    # =========================================================================
    # Profile Context (for Agent Injection)
    # =========================================================================

    async def get_profile_context(
        self,
        speaker_id: str,
        conversation_participants: list[str] | None = None,
        privacy_zone: PrivacyZone = PrivacyZone.COMMON_AREA_ALONE,
    ) -> ProfileContextResponse:
        """Get appropriate profile context for agent prompts.

        Args:
            speaker_id: The speaker's member ID
            conversation_participants: List of all participants in the conversation
            privacy_zone: Current privacy context

        Returns:
            Profile context with appropriate privacy filtering and real-time location
        """
        profile = await self.get_profile(speaker_id)

        if not profile:
            # Return guest context
            return ProfileContextResponse(
                member_id="guest",
                name="Guest",
                context_type="guest",
                public={
                    "communication_style": "Be polite and helpful with basic requests.",
                    "preferences": {},
                    "interests": [],
                },
                private=None,
            )

        participants = conversation_participants or [speaker_id]

        # Determine if private context is appropriate
        is_private = (
            len(participants) == 1
            and privacy_zone
            in [
                PrivacyZone.PRIVATE_ROOM,
                PrivacyZone.COMMON_AREA_ALONE,
            ]
            and speaker_id == participants[0]
        )

        # Fetch real-time location from Home Assistant
        location = None
        person_entity_details = None

        # Try to find person entity - first from profile, then by name
        person_entity_id = profile.ha_person_entity
        if not person_entity_id and self._ha_client:
            # Fallback: try to find person entity by name
            # Person entities in HA are typically "person.{name_lowercase}"
            person_entity_id = f"person.{speaker_id.lower()}"
            # Verify it exists
            person_state = await self._ha_client.get_state(person_entity_id)
            if not person_state:
                person_entity_id = None

        if person_entity_id:
            location = await self.get_person_location(person_entity_id)

            # Get person entity details including linked devices and entities
            if self._ha_client:
                try:
                    person_entity_details = await self._ha_client.get_person_entity_details(
                        person_entity_id
                    )
                except Exception as e:
                    logger.debug(f"Could not get person entity details: {e}")

        return ProfileContextResponse(
            member_id=profile.member_id,
            name=profile.name,
            context_type="private" if is_private else "public_only",
            public=profile.public.model_dump(),
            private=profile.private.model_dump() if is_private else None,
            location=location,
            ha_person_entity=profile.ha_person_entity,
            person_entity_details=person_entity_details,
        )

    # =========================================================================
    # Guest Profiles
    # =========================================================================

    async def create_guest(
        self,
        display_name: str | None = None,
        introduced_by: str | None = None,
        allowed_rooms: list[str] | None = None,
    ) -> GuestProfile:
        """Create a guest profile.

        Args:
            display_name: Optional name for the guest
            introduced_by: Member who introduced the guest
            allowed_rooms: Rooms the guest can control

        Returns:
            The created guest profile
        """
        guest_id = f"guest_{datetime.now(UTC).timestamp():.0f}"
        guest = GuestProfile(
            guest_id=guest_id,
            display_name=display_name or "Guest",
            introduced_by=introduced_by,
            allowed_rooms=allowed_rooms or [],
        )

        self._guests[guest_id] = guest

        if self._redis:
            try:
                await self._redis.set(
                    f"{self.GUEST_PREFIX}{guest_id}",
                    guest.model_dump_json(),
                    ex=86400 * 7,  # Expire after 7 days
                )
            except Exception as e:
                logger.warning(f"Could not save guest to Redis: {e}")

        return guest

    async def end_guest_visit(self, guest_id: str) -> None:
        """End a guest's visit.

        Args:
            guest_id: The guest's ID
        """
        if guest_id in self._guests:
            self._guests[guest_id].visit_end = datetime.now(UTC)

        if self._redis:
            try:
                await self._redis.delete(f"{self.GUEST_PREFIX}{guest_id}")
            except Exception as e:
                logger.warning(f"Could not delete guest from Redis: {e}")

    # =========================================================================
    # Statistics
    # =========================================================================

    async def get_stats(self) -> ProfileStatsResponse:
        """Get profile statistics.

        Returns:
            Profile statistics
        """
        profiles = await self.get_all_profiles()
        pending = await self.get_profiles_with_pending_updates()

        # Count by relationship
        by_relationship: dict[str, int] = {}
        oldest_days = 0
        newest_days = float("inf")

        now = datetime.now(UTC)
        for p in profiles:
            rel = p.relationship_to_primary.value
            by_relationship[rel] = by_relationship.get(rel, 0) + 1

            # Enrollment date might not be timezone-aware
            enrollment = p.enrollment_date
            if enrollment.tzinfo is None:
                enrollment = enrollment.replace(tzinfo=UTC)

            days = (now - enrollment).days
            if days > oldest_days:
                oldest_days = days
            if days < newest_days:
                newest_days = days

        # Count unprocessed events
        total_events = 0
        for member_id in [p.member_id for p in profiles]:
            events = await self.get_unprocessed_events(member_id)
            total_events += len(events)

        return ProfileStatsResponse(
            total_profiles=len(profiles),
            pending_updates=len(pending),
            profiles_by_relationship=by_relationship,
            oldest_profile_days=oldest_days,
            newest_profile_days=int(newest_days) if newest_days != float("inf") else 0,
            total_events_unprocessed=total_events,
        )

    # =========================================================================
    # Update Trigger Detection
    # =========================================================================

    async def should_trigger_update(self, member_id: str) -> tuple[bool, list[str]]:
        """Check if a profile update should be triggered.

        Args:
            member_id: The member's ID

        Returns:
            Tuple of (should_update, list of trigger reasons)
        """
        profile = await self.get_profile(member_id)
        if not profile:
            return False, []

        triggers_fired: list[str] = []

        # Check accumulated significance
        significance = await self.get_accumulated_significance(member_id)
        if significance >= 3.0:
            triggers_fired.append("significant_event_count")

        # Check time since last update
        last_update = profile.last_updated
        if last_update.tzinfo is None:
            last_update = last_update.replace(tzinfo=UTC)

        if datetime.now(UTC) - last_update > timedelta(days=7):
            triggers_fired.append("weekly_refresh")

        # Check for explicit instruction events
        events = await self.get_unprocessed_events(member_id)
        for event in events:
            if event.event_type == ProfileEventType.EXPLICIT_PREFERENCE:
                triggers_fired.append("explicit_instruction")
                break

        # Check for major life events
        for event in events:
            if event.event_type in [
                ProfileEventType.HEALTH_MENTION,
                ProfileEventType.SCHEDULE_CHANGE,
            ]:
                if event.significance_score >= 2.0:
                    triggers_fired.append("major_life_event")
                    break

        return len(triggers_fired) > 0, triggers_fired


# =============================================================================
# Singleton Pattern
# =============================================================================

_profile_service: ProfileService | None = None


async def get_profile_service(
    redis_client: redis.Redis | None = None,
    ha_client: HomeAssistantClient | None = None,
) -> ProfileService:
    """Get the singleton profile service.

    Args:
        redis_client: Optional Redis client
        ha_client: Optional Home Assistant client for person location tracking

    Returns:
        The profile service instance
    """
    global _profile_service
    if _profile_service is None:
        _profile_service = ProfileService(redis_client, ha_client)
        await _profile_service.init()
    else:
        # Update clients if provided and not already set
        if redis_client and _profile_service._redis is None:
            _profile_service._redis = redis_client
            logger.info("ProfileService: Redis client updated")
        if ha_client:
            # Always update HA client if provided
            _profile_service.set_ha_client(ha_client)
    return _profile_service
