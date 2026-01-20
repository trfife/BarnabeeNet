"""Family Profile Models for BarnabeeNet.

Dynamic profile system for family members, inspired by SkyrimNet's NPC biography architecture.
Profiles are generated infrequently (not per-interaction), triggered by accumulated events.
They are structured into public (safe to share) and private (direct interactions only) blocks.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ProfileRelationship(str, Enum):
    """Relationship types to primary user."""

    SELF = "self"
    SPOUSE = "spouse"
    CHILD = "child"
    PARENT = "parent"
    SIBLING = "sibling"
    EXTENDED_FAMILY = "extended_family"
    FAMILY = "family"  # Generic family member (used for HA sync)
    GUEST = "guest"


class GoalStatus(str, Enum):
    """Status of a mentioned goal."""

    MENTIONED = "mentioned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class GoalEntry(BaseModel):
    """A goal mentioned by a family member."""

    goal: str
    mentioned_date: datetime
    last_referenced: datetime | None = None
    status: GoalStatus = GoalStatus.MENTIONED
    context: str | None = None  # Where/when this was discussed


class PublicProfileBlock(BaseModel):
    """Information safe to share across family interactions.

    This block is always injected into context, even when others are present.
    """

    # Schedule patterns (aggregated, not specific times)
    schedule_summary: str = ""
    # e.g., "Usually home by 6pm on weekdays. Works from home on Fridays."

    typical_locations: dict[str, str] = Field(default_factory=dict)
    # e.g., {"morning_weekday": "office", "evening": "living_room", "weekend": "garage"}

    # Learned preferences (device/environment related)
    preferences: dict[str, Any] = Field(default_factory=dict)
    # e.g., {"temperature": {"preferred": 68, "context": "when working"}}

    # Topics of interest (safe to mention)
    interests: list[str] = Field(default_factory=list)
    # e.g., ["woodworking", "home automation", "coffee"]

    # Communication style summary
    communication_style: str = ""
    # e.g., "Prefers direct, concise responses. Uses technical terminology comfortably."

    # Home role context
    household_responsibilities: list[str] = Field(default_factory=list)
    # e.g., ["primary_tech_support", "morning_routine_coordinator"]


class PrivateProfileBlock(BaseModel):
    """Sensitive information only used in direct, private interactions.

    This block is only injected when:
    - Single speaker (no other family members present)
    - Not in a "common area with others" state
    - Speaker is directly interacting (not overheard)
    """

    # Emotional/stress patterns (Barnabee's observations)
    emotional_patterns: str = ""
    # e.g., "Often stressed on Monday mornings. More relaxed after exercise."

    # Personal goals mentioned in conversations
    goals_mentioned: list[GoalEntry] = Field(default_factory=list)

    # Relationship notes (Barnabee's first-person perspective)
    relationship_notes: str = ""
    # e.g., "Thom values his quiet morning coffee time. He appreciates when I
    #        don't interrupt unless urgent."

    # Sensitive topics to handle carefully
    sensitive_topics: list[str] = Field(default_factory=list)
    # e.g., ["work deadlines", "sleep quality"]

    # Health/wellness observations (if shared)
    wellness_notes: str | None = None

    # Private preferences (not to share with others)
    private_preferences: dict[str, Any] = Field(default_factory=dict)
    # e.g., {"wake_time": "5:30am", "bedtime_target": "10:30pm"}


class FamilyMemberProfile(BaseModel):
    """Dynamic profile for a family member.

    Inspired by SkyrimNet's NPC biographies with public/private separation.
    """

    # Identity (Immutable, set during enrollment)
    member_id: str  # "thom", "elizabeth", "penelope"
    name: str  # Display name
    relationship_to_primary: ProfileRelationship
    enrollment_date: datetime

    # Home Assistant Integration
    ha_person_entity: str | None = None  # e.g., "person.thom" - links to HA person for location tracking

    # Profile content
    public: PublicProfileBlock = Field(default_factory=PublicProfileBlock)
    private: PrivateProfileBlock = Field(default_factory=PrivateProfileBlock)

    # Versioning
    version: int = 1
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    update_triggers: list[str] = Field(default_factory=list)

    # Pending changes awaiting approval
    pending_update: ProfileDiff | None = None
    pending_update_generated: datetime | None = None

    class Config:
        json_schema_extra = {
            "example": {
                "member_id": "thom",
                "name": "Thom",
                "relationship_to_primary": "self",
                "enrollment_date": "2026-01-01T00:00:00Z",
                "version": 1,
                "public": {
                    "schedule_summary": "Works from home most days. Usually in office 9am-5pm.",
                    "typical_locations": {"morning": "office", "evening": "living_room"},
                    "preferences": {"temperature": {"preferred": 68}},
                    "interests": ["home automation", "coffee", "woodworking"],
                    "communication_style": "Direct and technical. Appreciates concise responses.",
                    "household_responsibilities": ["tech_support", "evening_routines"],
                },
                "private": {
                    "emotional_patterns": "More relaxed on Fridays. Needs quiet mornings.",
                    "goals_mentioned": [],
                    "relationship_notes": "Values morning coffee ritual. Appreciates proactive notifications.",
                    "sensitive_topics": ["work deadlines"],
                    "wellness_notes": None,
                    "private_preferences": {"wake_time": "6:00am"},
                },
            }
        }


class GuestProfile(BaseModel):
    """Minimal profile for visitors - no personal information exposed."""

    guest_id: str
    display_name: str | None = "Guest"
    visit_start: datetime = Field(default_factory=datetime.utcnow)
    visit_end: datetime | None = None

    # Very limited access
    allowed_commands: list[str] = Field(default_factory=list)  # Pre-approved command patterns
    allowed_rooms: list[str] = Field(default_factory=list)  # Rooms they can control

    # No private block - guests get no personalization
    introduced_by: str | None = None  # Member who introduced the guest


# =============================================================================
# Profile Diff System
# =============================================================================


class DiffEntryType(str, Enum):
    """Type of change in a diff entry."""

    ADDED = "added"
    MODIFIED = "modified"
    REMOVED = "removed"


class DiffEntry(BaseModel):
    """A single change in the profile."""

    block: str  # "public" or "private"
    field_path: str  # e.g., "preferences.temperature.preferred"
    diff_type: DiffEntryType
    old_value: Any | None = None
    new_value: Any | None = None
    reason: str = ""  # Why this changed


class ProfileDiff(BaseModel):
    """Represents changes between profile versions."""

    member_id: str
    from_version: int
    to_version: int

    # Categorized changes
    additions: list[DiffEntry] = Field(default_factory=list)
    modifications: list[DiffEntry] = Field(default_factory=list)
    removals: list[DiffEntry] = Field(default_factory=list)

    # Metadata
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    triggering_events: list[str] = Field(default_factory=list)
    llm_summary: str = ""
    confidence_notes: str | None = None


# =============================================================================
# Profile Events
# =============================================================================


class ProfileEventType(str, Enum):
    """Types of events that can trigger profile updates."""

    EXPLICIT_PREFERENCE = "explicit_preference"
    GOAL_MENTIONED = "goal_mentioned"
    EMOTIONAL_DISCLOSURE = "emotional_disclosure"
    SCHEDULE_CHANGE = "schedule_change"
    HEALTH_MENTION = "health_mention"
    REPEATED_BEHAVIOR = "repeated_behavior"
    TIME_PREFERENCE = "time_preference"
    ROOM_PREFERENCE = "room_preference"
    ROUTINE_COMMAND = "routine_command"
    INFORMATION_QUERY = "information_query"


class ProfileEvent(BaseModel):
    """An event that may contribute to profile updates."""

    id: str = Field(default_factory=lambda: f"event_{datetime.utcnow().timestamp()}")
    member_id: str
    event_type: ProfileEventType
    description: str
    significance_score: float  # How important is this event (0.0-3.0)

    # Source tracking
    source_conversation_id: str | None = None
    source_type: str = "conversation"  # "conversation", "sensor", "calendar"

    # Status
    processed: bool = False  # Has this been included in a profile update?
    occurred_at: datetime = Field(default_factory=datetime.utcnow)


# =============================================================================
# Profile Update Triggers
# =============================================================================


@dataclass
class ProfileUpdateTrigger:
    """Defines when a profile regeneration should be triggered."""

    trigger_type: str
    description: str
    threshold: Any
    last_triggered: datetime | None = None


# Standard triggers matching SkyrimNet pattern
PROFILE_UPDATE_TRIGGERS = [
    # Event accumulation threshold
    ProfileUpdateTrigger(
        trigger_type="significant_event_count",
        description="3+ significant events involving this person since last update",
        threshold=3.0,
    ),
    # Time-based minimum refresh
    ProfileUpdateTrigger(
        trigger_type="weekly_refresh",
        description="At least 7 days since last profile regeneration",
        threshold=timedelta(days=7),
    ),
    # Explicit user feedback
    ProfileUpdateTrigger(
        trigger_type="explicit_instruction",
        description="User says 'Remember that I...' or 'I prefer...'",
        threshold=1,
    ),
    # Preference contradiction detected
    ProfileUpdateTrigger(
        trigger_type="preference_conflict",
        description="New behavior contradicts stored preference 2+ times",
        threshold=2,
    ),
    # Major life event mentioned
    ProfileUpdateTrigger(
        trigger_type="major_life_event",
        description="Job change, family event, health update, move, etc.",
        threshold=1,
    ),
]

# Event significance scores
EVENT_SIGNIFICANCE_SCORES: dict[ProfileEventType, float] = {
    ProfileEventType.EXPLICIT_PREFERENCE: 3.0,
    ProfileEventType.GOAL_MENTIONED: 3.0,
    ProfileEventType.EMOTIONAL_DISCLOSURE: 3.0,
    ProfileEventType.SCHEDULE_CHANGE: 2.0,
    ProfileEventType.HEALTH_MENTION: 3.0,
    ProfileEventType.REPEATED_BEHAVIOR: 1.0,
    ProfileEventType.TIME_PREFERENCE: 1.0,
    ProfileEventType.ROOM_PREFERENCE: 1.0,
    ProfileEventType.ROUTINE_COMMAND: 0.1,
    ProfileEventType.INFORMATION_QUERY: 0.1,
}


# =============================================================================
# Privacy Zones
# =============================================================================


class PrivacyZone(str, Enum):
    """Defines what level of profile context is appropriate."""

    PRIVATE_ROOM = "private_room"  # Speaker alone in their room
    COMMON_AREA_ALONE = "common_area_alone"  # Speaker alone in shared space
    COMMON_AREA_OCCUPIED = "common_area_occupied"  # Multiple family members present
    GUEST_PRESENT = "guest_present"  # Guest in the home
    CHILDREN_PRESENT = "children_present"  # Children in earshot


# =============================================================================
# API Request/Response Models
# =============================================================================


class CreateProfileRequest(BaseModel):
    """Request to create a new family member profile."""

    member_id: str = Field(..., min_length=1, max_length=50, pattern=r"^[a-z0-9_]+$")
    name: str = Field(..., min_length=1, max_length=100)
    relationship: ProfileRelationship = ProfileRelationship.FAMILY  # Default for HA sync

    # Home Assistant integration
    ha_person_entity: str | None = None  # e.g., "person.thom_fife"

    # Optional initial data
    public: PublicProfileBlock | None = None
    private: PrivateProfileBlock | None = None


class UpdateProfileRequest(BaseModel):
    """Request to manually update profile fields."""

    # Home Assistant integration
    ha_person_entity: str | None = None  # e.g., "person.thom_fife"

    public: PublicProfileBlock | None = None
    private: PrivateProfileBlock | None = None


class ProfileResponse(BaseModel):
    """Response containing profile data."""

    profile: FamilyMemberProfile
    has_pending_update: bool = False


class ProfileListResponse(BaseModel):
    """Response containing list of profiles."""

    profiles: list[FamilyMemberProfile]
    total: int


class ProfileDiffResponse(BaseModel):
    """Response containing a profile diff preview."""

    member_id: str
    name: str
    current_version: int
    diff: ProfileDiff
    summary: str


class ProfileStatsResponse(BaseModel):
    """Response containing profile statistics."""

    total_profiles: int
    pending_updates: int
    profiles_by_relationship: dict[str, int]
    oldest_profile_days: int
    newest_profile_days: int
    total_events_unprocessed: int


class PersonLocation(BaseModel):
    """Real-time location info from Home Assistant person entity."""

    state: str  # "home", "not_home", or zone name like "Work"
    is_home: bool
    zone: str | None = None  # Zone name if in a known zone
    latitude: float | None = None
    longitude: float | None = None
    gps_accuracy: int | None = None  # meters
    last_changed: datetime | None = None  # When they arrived/left
    source: str | None = None  # e.g., "device_tracker.thom_phone"


class ProfileContextResponse(BaseModel):
    """Profile context for injection into agent prompts."""

    member_id: str
    name: str
    context_type: str  # "private", "public_only", or "guest"
    public: dict[str, Any]
    private: dict[str, Any] | None = None

    # Real-time data from Home Assistant
    location: PersonLocation | None = None  # Current location from HA person entity
    ha_person_entity: str | None = None  # The HA entity ID for reference


# =============================================================================
# Forward references update
# =============================================================================

# Update forward references for Pydantic v2
FamilyMemberProfile.model_rebuild()
