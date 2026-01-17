# BarnabeeNet Family Profile System

**Document Version:** 1.0  
**Last Updated:** January 17, 2026  
**Author:** Thom Fife  
**Purpose:** Dynamic family member profile system inspired by SkyrimNet's NPC biography architecture

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Profile Data Structure](#profile-data-structure)
3. [Profile Update Triggers](#profile-update-triggers)
4. [Profile Generation Prompt](#profile-generation-prompt)
5. [Public vs Private Blocks](#public-vs-private-blocks)
6. [Profile Storage Schema](#profile-storage-schema)
7. [Diff Preview System](#diff-preview-system)
8. [Integration with Existing Systems](#integration-with-existing-systems)
9. [Implementation Roadmap](#implementation-roadmap)

---

## Executive Summary

Based on analysis of SkyrimNet's dynamic NPC biography system and BarnabeeNet's existing architecture, this document specifies a **Profile Agent** pattern that mirrors SkyrimNet's Character Profile agent. The key insight from SkyrimNet is that dynamic profiles are:

1. **Generated infrequently** (not per-interaction)
2. **Triggered by accumulated events** (not real-time)
3. **Structured into logical blocks** (identity, personality, relationships, goals, speech)
4. **Viewable/editable via web UI** with diff previews before applying changes

This directly translates to BarnabeeNet's need for family member profiles that evolve based on observed patterns while maintaining privacy boundaries.

### SkyrimNet Character Bio Structure Reference

SkyrimNet organizes character biographies into numbered submodule prompts:

```
prompts/submodules/character_bio/
├── 0001_identity.prompt      # Name, race, gender, basic facts
├── 0002_personality.prompt   # Traits, temperament, values
├── 0003_relationships.prompt # Connections to other NPCs
├── 0004_goals.prompt         # Motivations, desires
└── 0005_speech.prompt        # How they communicate
```

---

## Profile Data Structure

### Core Profile Classes

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class FamilyMemberProfile:
    """Dynamic profile for a family member, inspired by SkyrimNet's NPC biographies."""
    
    # === IDENTITY (Immutable, set during enrollment) ===
    member_id: str                    # "thom", "elizabeth", "penelope"
    name: str                         # Display name
    relationship_to_primary: str      # "self", "spouse", "child", "parent", "guest"
    enrollment_date: datetime
    
    # === PUBLIC BLOCK (Safe to reference in any context) ===
    # These can be shared with other family members or used in multi-person scenarios
    public: "PublicProfileBlock"
    
    # === PRIVATE BLOCK (Only for direct interactions with this person) ===
    # Never exposed to other family members, used only when speaker_id matches
    private: "PrivateProfileBlock"
    
    # === METADATA ===
    version: int = 1                  # Increments on each update
    last_updated: datetime = field(default_factory=datetime.now)
    update_triggers: list[str] = field(default_factory=list)  # What caused last regeneration
    pending_update: "ProfileDiff | None" = None  # Staged changes awaiting approval


@dataclass
class PublicProfileBlock:
    """Information safe to share across family interactions."""
    
    # Schedule patterns (aggregated, not specific)
    schedule_summary: str = ""
    # e.g., "Usually home by 6pm on weekdays. Works from home on Fridays."
    
    typical_locations: dict[str, str] = field(default_factory=dict)
    # e.g., {"morning_weekday": "office", "evening": "living_room", "weekend": "garage"}
    
    # Learned preferences (device/environment related)
    preferences: dict[str, Any] = field(default_factory=dict)
    # e.g., {
    #     "temperature": {"preferred": 68, "context": "when working"},
    #     "lighting": {"preferred": "warm", "context": "evening"},
    #     "music": {"genres": ["jazz", "classical"], "context": "working"},
    # }
    
    # Topics of interest (safe to mention)
    interests: list[str] = field(default_factory=list)
    # e.g., ["woodworking", "home automation", "coffee"]
    
    # Communication style summary
    communication_style: str = ""
    # e.g., "Prefers direct, concise responses. Uses technical terminology comfortably."
    
    # Home role context
    household_responsibilities: list[str] = field(default_factory=list)
    # e.g., ["primary_tech_support", "morning_routine_coordinator"]


@dataclass
class PrivateProfileBlock:
    """Sensitive information only used in direct, private interactions."""
    
    # Emotional/stress patterns (Barnabee's observations)
    emotional_patterns: str = ""
    # e.g., "Often stressed on Monday mornings. More relaxed after exercise."
    
    # Personal goals mentioned in conversations
    goals_mentioned: list["GoalEntry"] = field(default_factory=list)
    # e.g., [
    #     GoalEntry(goal="finish garage workshop", mentioned_date=..., status="in_progress"),
    #     GoalEntry(goal="read more books", mentioned_date=..., status="ongoing"),
    # ]
    
    # Relationship notes (Barnabee's perspective, like SkyrimNet's first-person memory)
    relationship_notes: str = ""
    # e.g., "Thom values his quiet morning coffee time. He appreciates when I 
    #        don't interrupt unless urgent. He's mentioned wanting to be more 
    #        present with the kids in the evenings."
    
    # Sensitive topics to handle carefully
    sensitive_topics: list[str] = field(default_factory=list)
    # e.g., ["work deadlines", "sleep quality"] - topics that may need gentle handling
    
    # Health/wellness observations (if shared)
    wellness_notes: str | None = None
    # e.g., "Has mentioned back pain when sitting too long. Appreciates standing 
    #        desk reminders."
    
    # Private preferences (not to share with others)
    private_preferences: dict[str, Any] = field(default_factory=dict)
    # e.g., {"wake_time": "5:30am", "bedtime_target": "10:30pm"}


@dataclass
class GoalEntry:
    """A goal mentioned by a family member."""
    goal: str
    mentioned_date: datetime
    last_referenced: datetime = field(default_factory=datetime.now)
    status: str = "mentioned"  # "mentioned", "in_progress", "completed", "abandoned"
    context: str | None = None  # Where/when this was discussed
```

### Guest Profile (Restricted)

```python
@dataclass
class GuestProfile:
    """Minimal profile for visitors - no personal information exposed."""
    
    guest_id: str                     # Generated UUID
    display_name: str | None = None   # "Guest" or provided name
    visit_start: datetime = field(default_factory=datetime.now)
    visit_end: datetime | None = None
    
    # Very limited public info
    allowed_commands: list[str] = field(default_factory=list)  # Pre-approved command patterns
    allowed_rooms: list[str] = field(default_factory=list)     # Rooms they can control
    
    # No private block - guests get no personalization
    # No emotional tracking, no goals, no relationship notes
    
    introduced_by: str | None = None  # Member who introduced the guest
```

---

## Profile Update Triggers

Drawing from SkyrimNet's time-segmented memory generation (which consolidates events into cohesive narratives rather than storing every interaction), BarnabeeNet profiles should update based on accumulated significance, not real-time changes.

### Trigger Definitions

```python
from datetime import timedelta


@dataclass
class ProfileUpdateTrigger:
    """Defines when a profile regeneration should be triggered."""
    
    trigger_type: str
    description: str
    threshold: Any
    last_triggered: datetime | None = None


PROFILE_UPDATE_TRIGGERS = [
    # 1. Event accumulation threshold
    ProfileUpdateTrigger(
        trigger_type="significant_event_count",
        description="3+ significant events involving this person since last update",
        threshold=3,
    ),
    
    # 2. Time-based minimum refresh (like SkyrimNet's segment duration)
    ProfileUpdateTrigger(
        trigger_type="weekly_refresh",
        description="At least 7 days since last profile regeneration",
        threshold=timedelta(days=7),
    ),
    
    # 3. Explicit user feedback
    ProfileUpdateTrigger(
        trigger_type="explicit_instruction",
        description="User says 'Remember that I...' or 'I prefer...'",
        threshold=1,  # Single occurrence triggers
    ),
    
    # 4. Preference contradiction detected
    ProfileUpdateTrigger(
        trigger_type="preference_conflict",
        description="New behavior contradicts stored preference 2+ times",
        threshold=2,
    ),
    
    # 5. Major life event mentioned
    ProfileUpdateTrigger(
        trigger_type="major_life_event",
        description="Job change, family event, health update, move, etc.",
        threshold=1,  # Single mention triggers
    ),
    
    # 6. Relationship change
    ProfileUpdateTrigger(
        trigger_type="relationship_change",
        description="New family member, role change, guest becoming regular",
        threshold=1,
    ),
]
```

### Event Significance Classification

```python
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class EventSignificanceClassifier:
    """Determines which events should contribute to profile updates."""
    
    SIGNIFICANT_EVENT_TYPES = {
        # High significance - single occurrence counts
        "explicit_preference_statement": 3.0,  # "I prefer the lights dim"
        "goal_mentioned": 3.0,                 # "I'm trying to exercise more"
        "emotional_disclosure": 3.0,           # "I've been stressed about..."
        "schedule_change": 2.0,                # "I'm working from home Fridays now"
        "health_mention": 3.0,                 # "My back has been bothering me"
        
        # Medium significance - accumulates
        "repeated_behavior_pattern": 1.0,      # Same action 3+ times
        "time_preference_observed": 1.0,       # Consistent timing patterns
        "room_preference_observed": 1.0,       # Location patterns
        
        # Low significance - contributes to patterns but doesn't trigger alone
        "routine_command": 0.1,                # Standard device control
        "information_query": 0.1,              # Questions to Barnabee
    }
    
    def __init__(self, hass: "HomeAssistant", config: dict) -> None:
        """Initialize classifier."""
        self.hass = hass
        self.config = config
    
    async def classify_event(
        self, 
        event: dict,
        member_id: str,
    ) -> tuple[str, float]:
        """Classify an event and return (event_type, significance_score)."""
        
        # Use lightweight LLM or rule-based classification
        event_type = await self._detect_event_type(event)
        significance = self.SIGNIFICANT_EVENT_TYPES.get(event_type, 0.1)
        
        return event_type, significance
    
    async def _detect_event_type(self, event: dict) -> str:
        """Detect the type of event from its content."""
        
        text = event.get("user_input", "").lower()
        
        # Rule-based detection for common patterns
        if any(phrase in text for phrase in ["i prefer", "i like", "i want"]):
            return "explicit_preference_statement"
        
        if any(phrase in text for phrase in ["i'm trying to", "my goal", "i want to"]):
            return "goal_mentioned"
        
        if any(phrase in text for phrase in ["stressed", "worried", "anxious", "tired"]):
            return "emotional_disclosure"
        
        if any(phrase in text for phrase in ["from now on", "starting", "my new schedule"]):
            return "schedule_change"
        
        if any(phrase in text for phrase in ["my back", "headache", "feeling sick", "doctor"]):
            return "health_mention"
        
        # Default to routine command
        return "routine_command"
    
    def should_trigger_update(
        self,
        member_id: str,
        accumulated_significance: float,
        last_update: datetime,
        explicit_triggers: list[str],
    ) -> tuple[bool, list[str]]:
        """Determine if profile update should be triggered."""
        
        triggers_fired = []
        
        # Check each trigger condition
        if accumulated_significance >= 3.0:
            triggers_fired.append("significant_event_count")
        
        if datetime.now() - last_update > timedelta(days=7):
            triggers_fired.append("weekly_refresh")
        
        if "explicit_instruction" in explicit_triggers:
            triggers_fired.append("explicit_instruction")
        
        if "major_life_event" in explicit_triggers:
            triggers_fired.append("major_life_event")
        
        return len(triggers_fired) > 0, triggers_fired
```

---

## Profile Generation Prompt

This is the LLM prompt that analyzes recent memories, events, and existing profile to generate/update profile sections.

### Profile Generation Agent Configuration

```yaml
# config/llm.yaml
profile_generation:
  model: "openai/gpt-4o-mini"  # Good at structured output, cost-effective
  temperature: 0.3             # Low temperature for consistency
  max_tokens: 2000
  response_format: "json"      # Enforce JSON output
```

### Profile Generation Prompt Template

```jinja2
{# prompts/profile/generate_profile.prompt #}

You are the Profile Agent for BarnabeeNet, a family home AI assistant. Your task is to 
analyze recent interactions, events, and memories to generate or update a family member's 
profile. You observe the family from Barnabee's first-person perspective.

## Current Profile (if exists)
{% if existing_profile %}
{{ existing_profile | tojson(indent=2) }}
{% else %}
No existing profile - this is initial generation.
{% endif %}

## Family Member Identity
- Member ID: {{ member_id }}
- Name: {{ name }}
- Relationship: {{ relationship }}
- Enrolled: {{ enrollment_date }}

## Recent Events (Last {{ event_window_days }} Days)
{% for event in recent_events %}
[{{ event.timestamp }}] {{ event.type }}: {{ event.description }}
{% if event.significance > 1.0 %}  ⭐ High significance{% endif %}
{% endfor %}

## Recent Conversations (Last {{ conversation_count }} interactions)
{% for conv in recent_conversations %}
---
[{{ conv.timestamp }}] {{ conv.room }}
User: {{ conv.user_input }}
Barnabee: {{ conv.response }}
{% if conv.extracted_intent %}Intent: {{ conv.extracted_intent }}{% endif %}
{% endfor %}

## Existing Semantic Facts About This Person
{% for fact in semantic_facts %}
- {{ fact.predicate }}: {{ fact.object }} (confidence: {{ fact.confidence }})
{% endfor %}

## Recent Memories (Barnabee's First-Person Observations)
{% for memory in relevant_memories %}
- {{ memory.content }} [{{ memory.memory_type }}, importance: {{ memory.importance }}]
{% endfor %}

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

Respond with ONLY valid JSON matching this schema:

```json
{
  "public": {
    "schedule_summary": "string - general schedule patterns observed",
    "typical_locations": {"time_period": "room"},
    "preferences": {
      "category": {"preferred": "value", "context": "when/where"}
    },
    "interests": ["list of topics they care about"],
    "communication_style": "string - how they prefer to interact",
    "household_responsibilities": ["roles in the home"]
  },
  "private": {
    "emotional_patterns": "string - stress patterns, mood observations",
    "goals_mentioned": [
      {
        "goal": "string",
        "mentioned_date": "ISO date",
        "status": "mentioned|in_progress|completed|abandoned",
        "context": "where/when discussed"
      }
    ],
    "relationship_notes": "string - Barnabee's first-person observations about relationship",
    "sensitive_topics": ["topics to handle carefully"],
    "wellness_notes": "string or null - health/wellness observations if shared",
    "private_preferences": {"key": "value"}
  },
  "update_summary": "Brief description of what changed and why",
  "confidence_notes": "Any uncertainties or things to verify"
}
```
```

### Profile Diff Generation Prompt

```jinja2
{# prompts/profile/generate_diff.prompt #}

Compare the existing profile with the proposed updates and generate a human-readable diff.

## Existing Profile
{{ existing_profile | tojson(indent=2) }}

## Proposed Profile
{{ proposed_profile | tojson(indent=2) }}

Generate a diff summary with:
1. ADDED: New information not in existing profile
2. CHANGED: Modified values (show old → new)
3. REMOVED: Information no longer present
4. UNCHANGED: Key sections that stayed the same

Format as a clear, readable summary for the dashboard UI. Include the reasoning for 
significant changes based on the triggering events.
```

---

## Public vs Private Blocks

This section defines the critical privacy boundaries for profile context injection.

### Context Injection Rules

```python
class ProfileContextInjector:
    """Determines which profile blocks to inject based on conversation context."""
    
    def __init__(self, profile_store: "ProfileStore") -> None:
        """Initialize injector."""
        self.profile_store = profile_store
    
    async def get_profile_context(
        self,
        speaker_id: str,
        conversation_participants: list[str],
        privacy_zone: str,
    ) -> dict:
        """Get appropriate profile context for the current interaction."""
        
        profile = await self.profile_store.get_profile(speaker_id)
        
        if profile is None:
            return self._get_guest_context()
        
        context = {
            "member_id": profile.member_id,
            "name": profile.name,
        }
        
        # RULE 1: Always include public block for identified speakers
        context["public"] = profile.public.__dict__
        
        # RULE 2: Include private block ONLY if:
        #   - Single speaker (no other family members present)
        #   - AND not in a "common area with others" state
        #   - AND speaker is directly interacting (not overheard)
        is_private_context = (
            len(conversation_participants) == 1 and
            privacy_zone not in ["common_area_occupied", "guest_present"] and
            speaker_id == conversation_participants[0]
        )
        
        if is_private_context:
            context["private"] = profile.private.__dict__
            context["context_type"] = "private"
        else:
            context["context_type"] = "public_only"
        
        return context
    
    def _get_guest_context(self) -> dict:
        """Minimal context for unidentified speakers."""
        return {
            "member_id": "guest",
            "name": "Guest",
            "context_type": "guest",
            "public": {
                "communication_style": "Be polite and helpful with basic requests.",
                "preferences": {},
                "interests": [],
            },
            # No private block for guests
        }
```

### Privacy Zone Definitions

| Privacy Zone | Description | Private Block Access |
|--------------|-------------|---------------------|
| `private_room` | Speaker alone in their room | ✅ Yes |
| `common_area_alone` | Speaker alone in shared space | ✅ Yes |
| `common_area_occupied` | Multiple family members present | ❌ No |
| `guest_present` | Guest in the home | ❌ No |
| `children_present` | Children in earshot | ❌ No (for adult private info) |

### Prompt Template Integration

```jinja2
{# prompts/dialogue/context_injection.prompt #}

## Speaking With: {{ profile.name }}

{% if profile.context_type == "private" %}
{# Full context for private conversation #}
### Known Preferences
{{ profile.public.preferences | format_preferences }}

### Communication Style
{{ profile.public.communication_style }}

### Recent Context (Private)
{{ profile.private.emotional_patterns }}

### Goals They've Mentioned
{% for goal in profile.private.goals_mentioned if goal.status != "completed" %}
- {{ goal.goal }} ({{ goal.status }})
{% endfor %}

### Relationship Notes
{{ profile.private.relationship_notes }}

{% elif profile.context_type == "public_only" %}
{# Limited context when others present #}
### Known Preferences
{{ profile.public.preferences | format_preferences }}

### Communication Style
{{ profile.public.communication_style }}

{# Do NOT include emotional patterns, goals, or relationship notes #}

{% else %}
{# Guest context - minimal #}
Speaking with a guest. Be helpful with basic requests. 
Do not assume any personal information.
{% endif %}
```

---

## Profile Storage Schema

Extending BarnabeeNet's existing SQLite schema.

### Database Tables

```sql
-- ============================================
-- FAMILY MEMBER PROFILES (Dynamic Biographies)
-- ============================================

CREATE TABLE IF NOT EXISTS family_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    relationship_to_primary TEXT NOT NULL,
    
    -- Profile content (JSON blobs for flexibility)
    public_block TEXT NOT NULL,           -- JSON: PublicProfileBlock
    private_block TEXT NOT NULL,          -- JSON: PrivateProfileBlock
    
    -- Versioning (like SkyrimNet's dynamic_bios)
    version INTEGER DEFAULT 1,
    
    -- Timestamps
    enrollment_date DATETIME NOT NULL,
    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
    next_scheduled_update DATETIME,
    
    -- Update tracking
    update_triggers TEXT,                 -- JSON: list of trigger types
    accumulated_significance REAL DEFAULT 0.0,
    
    -- Pending changes (diff preview)
    pending_update TEXT,                  -- JSON: ProfileDiff or null
    pending_update_generated DATETIME,
    
    FOREIGN KEY (member_id) REFERENCES speaker_profiles(user_id)
);

CREATE INDEX IF NOT EXISTS idx_profiles_member ON family_profiles(member_id);
CREATE INDEX IF NOT EXISTS idx_profiles_next_update ON family_profiles(next_scheduled_update);


-- ============================================
-- PROFILE VERSION HISTORY
-- ============================================

CREATE TABLE IF NOT EXISTS profile_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    
    -- Snapshot of profile at this version
    public_block TEXT NOT NULL,
    private_block TEXT NOT NULL,
    
    -- What triggered this version
    update_triggers TEXT,                 -- JSON: list of triggers
    update_summary TEXT,                  -- LLM-generated summary of changes
    
    -- Timestamps
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (member_id) REFERENCES family_profiles(member_id),
    UNIQUE(member_id, version)
);

CREATE INDEX IF NOT EXISTS idx_history_member ON profile_history(member_id);


-- ============================================
-- SIGNIFICANT EVENTS FOR PROFILE UPDATES
-- ============================================

CREATE TABLE IF NOT EXISTS profile_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id TEXT NOT NULL,
    
    -- Event details
    event_type TEXT NOT NULL,
    event_description TEXT NOT NULL,
    significance_score REAL NOT NULL,
    
    -- Source tracking
    source_conversation_id INTEGER,
    source_type TEXT,                     -- "conversation", "sensor", "calendar"
    
    -- Status
    processed BOOLEAN DEFAULT FALSE,      -- Has this been included in a profile update?
    
    -- Timestamps
    occurred_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (member_id) REFERENCES family_profiles(member_id),
    FOREIGN KEY (source_conversation_id) REFERENCES conversations(id)
);

CREATE INDEX IF NOT EXISTS idx_events_member_unprocessed 
    ON profile_events(member_id, processed) WHERE processed = FALSE;


-- ============================================
-- GUEST PROFILES (Temporary)
-- ============================================

CREATE TABLE IF NOT EXISTS guest_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guest_id TEXT NOT NULL UNIQUE,
    display_name TEXT,
    
    -- Access control
    allowed_commands TEXT,                -- JSON: list of patterns
    allowed_rooms TEXT,                   -- JSON: list of rooms
    
    -- Visit tracking
    visit_start DATETIME NOT NULL,
    visit_end DATETIME,
    
    -- Minimal settings
    introduced_by TEXT,                   -- Member who introduced the guest
    
    FOREIGN KEY (introduced_by) REFERENCES family_profiles(member_id)
);

CREATE INDEX IF NOT EXISTS idx_guests_active 
    ON guest_profiles(visit_end) WHERE visit_end IS NULL;
```

---

## Diff Preview System

Following SkyrimNet's web UI pattern for viewing and editing dynamic bios.

### Profile Diff Data Structure

```python
@dataclass
class ProfileDiff:
    """Represents changes between profile versions."""
    
    member_id: str
    from_version: int
    to_version: int
    
    # Categorized changes
    additions: list["DiffEntry"] = field(default_factory=list)
    modifications: list["DiffEntry"] = field(default_factory=list)
    removals: list["DiffEntry"] = field(default_factory=list)
    
    # Metadata
    generated_at: datetime = field(default_factory=datetime.now)
    triggering_events: list[str] = field(default_factory=list)
    llm_summary: str = ""
    confidence_notes: str | None = None


@dataclass
class DiffEntry:
    """A single change in the profile."""
    
    block: str                # "public" or "private"
    field_path: str           # e.g., "preferences.temperature.preferred"
    old_value: Any | None = None
    new_value: Any | None = None
    reason: str = ""          # Why this changed
```

### Diff Generation Implementation

```python
class ProfileDiffGenerator:
    """Generates human-readable diffs between profile versions."""
    
    def __init__(self, llm_client: "LLMClient") -> None:
        """Initialize diff generator."""
        self.llm = llm_client
    
    async def generate_diff(
        self,
        existing: FamilyMemberProfile,
        proposed: FamilyMemberProfile,
        triggering_events: list[dict],
    ) -> ProfileDiff:
        """Generate a detailed diff between profiles."""
        
        additions = []
        modifications = []
        removals = []
        
        # Compare public blocks
        self._compare_blocks(
            existing.public.__dict__,
            proposed.public.__dict__,
            "public",
            additions,
            modifications,
            removals,
        )
        
        # Compare private blocks
        self._compare_blocks(
            existing.private.__dict__,
            proposed.private.__dict__,
            "private",
            additions,
            modifications,
            removals,
        )
        
        # Generate LLM summary of changes
        summary = await self._generate_summary(
            additions, modifications, removals, triggering_events
        )
        
        return ProfileDiff(
            member_id=existing.member_id,
            from_version=existing.version,
            to_version=existing.version + 1,
            additions=additions,
            modifications=modifications,
            removals=removals,
            generated_at=datetime.now(),
            triggering_events=[e.get("type", "unknown") for e in triggering_events],
            llm_summary=summary,
        )
    
    def _compare_blocks(
        self,
        old: dict,
        new: dict,
        block_name: str,
        additions: list,
        modifications: list,
        removals: list,
    ) -> None:
        """Recursively compare two dictionaries."""
        
        all_keys = set(old.keys()) | set(new.keys())
        
        for key in all_keys:
            old_val = old.get(key)
            new_val = new.get(key)
            field_path = f"{block_name}.{key}"
            
            if old_val is None and new_val is not None:
                additions.append(DiffEntry(
                    block=block_name,
                    field_path=field_path,
                    old_value=None,
                    new_value=new_val,
                    reason="New information learned",
                ))
            elif old_val is not None and new_val is None:
                removals.append(DiffEntry(
                    block=block_name,
                    field_path=field_path,
                    old_value=old_val,
                    new_value=None,
                    reason="Information no longer relevant",
                ))
            elif old_val != new_val:
                if isinstance(old_val, dict) and isinstance(new_val, dict):
                    # Recurse into nested dicts
                    self._compare_blocks(
                        old_val, new_val, field_path,
                        additions, modifications, removals
                    )
                else:
                    modifications.append(DiffEntry(
                        block=block_name,
                        field_path=field_path,
                        old_value=old_val,
                        new_value=new_val,
                        reason="Updated based on recent observations",
                    ))
    
    async def _generate_summary(
        self,
        additions: list[DiffEntry],
        modifications: list[DiffEntry],
        removals: list[DiffEntry],
        triggering_events: list[dict],
    ) -> str:
        """Generate a human-readable summary of changes."""
        
        parts = []
        
        if additions:
            parts.append(f"Added {len(additions)} new observations")
        if modifications:
            parts.append(f"Updated {len(modifications)} existing entries")
        if removals:
            parts.append(f"Removed {len(removals)} outdated entries")
        
        if triggering_events:
            event_types = set(e.get("type", "unknown") for e in triggering_events)
            parts.append(f"Triggered by: {', '.join(event_types)}")
        
        return ". ".join(parts) + "." if parts else "No significant changes."
```

### Dashboard API Integration

```python
class ProfileDashboardAPI:
    """API endpoints for the profile management dashboard."""
    
    def __init__(self, profile_store: "ProfileStore") -> None:
        """Initialize dashboard API."""
        self.profile_store = profile_store
    
    async def get_pending_updates(self) -> list[dict]:
        """Get all profiles with pending updates awaiting review."""
        
        profiles = await self.profile_store.get_profiles_with_pending_updates()
        
        return [
            {
                "member_id": p.member_id,
                "name": p.name,
                "current_version": p.version,
                "pending_diff": p.pending_update,
                "generated_at": p.pending_update_generated,
                "triggers": p.update_triggers,
            }
            for p in profiles
        ]
    
    async def preview_diff(self, member_id: str) -> dict:
        """Get detailed diff preview for a specific profile."""
        
        profile = await self.profile_store.get_profile(member_id)
        
        if profile is None:
            raise ValueError(f"Profile not found: {member_id}")
        
        if profile.pending_update is None:
            raise ValueError("No pending update for this profile")
        
        diff = profile.pending_update
        
        return {
            "member_id": member_id,
            "name": profile.name,
            "summary": diff.llm_summary,
            "changes": {
                "additions": [self._format_entry(e) for e in diff.additions],
                "modifications": [self._format_entry(e) for e in diff.modifications],
                "removals": [self._format_entry(e) for e in diff.removals],
            },
            "triggering_events": diff.triggering_events,
            "confidence_notes": diff.confidence_notes,
        }
    
    async def approve_update(self, member_id: str) -> dict:
        """Apply the pending profile update."""
        
        profile = await self.profile_store.get_profile(member_id)
        
        if profile is None:
            raise ValueError(f"Profile not found: {member_id}")
        
        # Archive current version
        await self.profile_store.archive_version(profile)
        
        # Apply pending update
        updated_profile = await self.profile_store.apply_pending_update(member_id)
        
        return {
            "success": True,
            "new_version": updated_profile.version,
            "message": f"Profile updated to version {updated_profile.version}",
        }
    
    async def reject_update(self, member_id: str, reason: str | None = None) -> dict:
        """Reject and discard the pending profile update."""
        
        await self.profile_store.clear_pending_update(member_id, reason)
        
        return {
            "success": True,
            "message": "Pending update discarded",
        }
    
    async def manual_edit(self, member_id: str, changes: dict) -> dict:
        """Allow manual editing of profile fields."""
        
        # Validate changes don't violate schema
        validated = self._validate_manual_changes(changes)
        
        # Apply and increment version
        await self.profile_store.apply_manual_changes(member_id, validated)
        
        return {
            "success": True,
            "message": "Manual changes applied",
        }
    
    def _format_entry(self, entry: DiffEntry) -> dict:
        """Format a diff entry for the UI."""
        return {
            "block": entry.block,
            "field": entry.field_path,
            "old": entry.old_value,
            "new": entry.new_value,
            "reason": entry.reason,
            "block_display": "🌐 Public" if entry.block == "public" else "🔒 Private",
        }
    
    def _validate_manual_changes(self, changes: dict) -> dict:
        """Validate manual changes against schema."""
        # Add validation logic here
        return changes
```

---

## Integration with Existing Systems

### Profile Agent Implementation

```python
from agents.base import BaseAgent, AgentType


class ProfileAgent(BaseAgent):
    """
    Agent responsible for generating and updating family member profiles.
    
    Inspired by SkyrimNet's Character Profile (Bio) agent:
    - Runs infrequently (not per-interaction)
    - Generates structured profiles from accumulated events
    - Produces diffs for human review before applying
    """
    
    AGENT_TYPE = AgentType.PROFILE
    
    def __init__(
        self,
        hass: "HomeAssistant",
        config: dict,
        llm_client: "LLMClient",
        profile_store: "ProfileStore",
        memory_manager: "MemoryManager",
    ) -> None:
        """Initialize Profile Agent."""
        super().__init__(hass, config)
        self.llm = llm_client
        self.profile_store = profile_store
        self.memory = memory_manager
        self.diff_generator = ProfileDiffGenerator(llm_client)
        self.classifier = EventSignificanceClassifier(hass, config)
        
        # Schedule periodic checks
        self._update_check_interval = timedelta(hours=6)
    
    async def check_for_updates(self) -> list[tuple[str, list[str]]]:
        """Check all profiles for needed updates."""
        
        members_to_update = []
        
        for profile in await self.profile_store.get_all_profiles():
            accumulated = await self.profile_store.get_accumulated_significance(
                profile.member_id
            )
            explicit_triggers = await self.profile_store.get_explicit_triggers(
                profile.member_id
            )
            
            should_update, triggers = self.classifier.should_trigger_update(
                member_id=profile.member_id,
                accumulated_significance=accumulated,
                last_update=profile.last_updated,
                explicit_triggers=explicit_triggers,
            )
            
            if should_update:
                members_to_update.append((profile.member_id, triggers))
        
        return members_to_update
    
    async def generate_profile_update(
        self,
        member_id: str,
        triggers: list[str],
    ) -> ProfileDiff:
        """Generate a profile update for review."""
        
        # Gather context
        existing = await self.profile_store.get_profile(member_id)
        
        if existing is None:
            raise ValueError(f"Profile not found: {member_id}")
        
        recent_events = await self.profile_store.get_unprocessed_events(member_id)
        recent_conversations = await self.memory.episodic.async_get_recent(
            speaker_id=member_id, limit=20
        )
        semantic_facts = await self.memory.semantic.async_get_facts(
            subject=member_id, limit=30
        )
        relevant_memories = await self.memory.episodic.async_search(
            query=f"observations about {existing.name}",
            speaker_id=member_id,
            limit=10,
        )
        
        # Generate new profile via LLM
        proposed = await self._generate_via_llm(
            existing=existing,
            recent_events=recent_events,
            recent_conversations=recent_conversations,
            semantic_facts=semantic_facts,
            relevant_memories=relevant_memories,
        )
        
        # Generate diff
        diff = await self.diff_generator.generate_diff(
            existing=existing,
            proposed=proposed,
            triggering_events=recent_events,
        )
        
        # Store as pending
        await self.profile_store.set_pending_update(member_id, diff, proposed)
        
        return diff
    
    async def _generate_via_llm(
        self,
        existing: FamilyMemberProfile,
        **context,
    ) -> FamilyMemberProfile:
        """Use LLM to generate updated profile."""
        
        # Render prompt template
        prompt = await self._render_prompt(
            "profile/generate_profile.prompt",
            existing_profile=existing,
            member_id=existing.member_id,
            name=existing.name,
            relationship=existing.relationship_to_primary,
            enrollment_date=existing.enrollment_date,
            event_window_days=30,
            **context,
        )
        
        response = await self.llm.complete(
            prompt=prompt,
            model_type="profile_generation",
        )
        
        # Parse JSON response into profile
        return self._parse_profile_response(response, existing)
    
    def _parse_profile_response(
        self,
        response: str,
        existing: FamilyMemberProfile,
    ) -> FamilyMemberProfile:
        """Parse LLM JSON response into profile object."""
        import json
        
        data = json.loads(response)
        
        # Create new profile with updated blocks
        return FamilyMemberProfile(
            member_id=existing.member_id,
            name=existing.name,
            relationship_to_primary=existing.relationship_to_primary,
            enrollment_date=existing.enrollment_date,
            public=PublicProfileBlock(**data.get("public", {})),
            private=PrivateProfileBlock(**data.get("private", {})),
            version=existing.version,  # Will be incremented on approval
            last_updated=existing.last_updated,
        )
```

### Memory Manager Integration

```python
# Add to MemoryManager class

async def async_get_full_context_for_speaker(
    self,
    speaker_id: str,
    conversation_participants: list[str],
    privacy_zone: str,
    limit: int = 5,
) -> dict:
    """Get comprehensive context including profile for a speaker."""
    
    base_context = await self.async_get_context_for_speaker(speaker_id, limit)
    
    # Add profile context with appropriate privacy filtering
    profile_context = await self.profile_injector.get_profile_context(
        speaker_id=speaker_id,
        conversation_participants=conversation_participants,
        privacy_zone=privacy_zone,
    )
    
    return {
        **base_context,
        "profile": profile_context,
    }
```

---

## Implementation Roadmap

### Phase 1: Foundation (Week 1-2)
- [ ] Create database schema for `family_profiles`, `profile_history`, `profile_events`
- [ ] Implement basic `ProfileStore` with CRUD operations
- [ ] Add profile fields to speaker enrollment flow

### Phase 2: Event Tracking (Week 2-3)
- [ ] Implement `EventSignificanceClassifier`
- [ ] Hook into conversation flow to emit profile events
- [ ] Track accumulated significance scores

### Phase 3: Profile Generation (Week 3-4)
- [ ] Create `ProfileAgent` with LLM integration
- [ ] Implement profile generation prompt
- [ ] Test with single family member

### Phase 4: Diff System (Week 4-5)
- [ ] Implement `ProfileDiffGenerator`
- [ ] Add pending update storage
- [ ] Create diff preview API endpoints

### Phase 5: Dashboard Integration (Week 5-6)
- [ ] Add profile management section to dashboard
- [ ] Implement approve/reject/edit flows
- [ ] Add profile version history view

### Phase 6: Context Injection (Week 6-7)
- [ ] Implement `ProfileContextInjector`
- [ ] Update dialogue prompts to use profile context
- [ ] Test public vs private block isolation

### Phase 7: Guest Profiles (Week 7-8)
- [ ] Implement restricted guest profile system
- [ ] Add guest introduction flow
- [ ] Test permission boundaries

---

## Key Architectural Decisions Summary

| Decision | Rationale | SkyrimNet Precedent |
|----------|-----------|---------------------|
| **Infrequent updates** | Prevents churn, enables human review | Bio agent runs "infrequently" |
| **Event accumulation** | Cohesive narratives, not noise | Time-segmented memory generation |
| **Public/Private blocks** | Privacy without losing personalization | Per-NPC personality/relationship separation |
| **Diff preview** | Human oversight of AI-generated content | Web UI bio editor |
| **First-person notes** | Consistent with Barnabee's personality | NPC memories from their perspective |
| **JSON storage** | Schema flexibility, easy versioning | Dynamic bios as separate files |
| **Separate Profile Agent** | Specialized model, isolated concerns | 7 distinct agent types |

---

## Document History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-01-17 | Initial Family Profile System specification |

---

*This document extends BarnabeeNet_Technical_Architecture.md with the Family Profile System. For memory system details, see the Memory System Architecture section. For feature descriptions, see BarnabeeNet_Features_UseCases.md.*
