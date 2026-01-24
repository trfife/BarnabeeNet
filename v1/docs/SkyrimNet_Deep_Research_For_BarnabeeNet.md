# SkyrimNet Deep Architecture Research for BarnabeeNet

**Research Date:** January 16, 2026  
**Purpose:** Comprehensive technical analysis of SkyrimNet's architecture, systems, and patterns to inform BarnabeeNet smart home AI implementation  
**Sources:** GitHub Repository, Official Documentation, Release Notes

---

## Executive Summary

SkyrimNet represents the most sophisticated open implementation of an "alive-feeling" AI agent system. After deep analysis of the codebase, documentation, and release history, this report identifies the specific architectural patterns, data structures, and system designs that make NPCs feel genuinely alive—and how each translates to a smart home AI assistant.

**Key Insight:** The "alive" feeling comes not from a single sophisticated AI, but from the **orchestration of 7 specialized LLM agents**, a **first-person memory architecture**, **real-time environmental awareness**, **visual understanding via OmniSight**, and **comprehensive observability**. Each system is simple individually but creates emergent complexity when combined.

---

## 1. Core Architecture: In-Process Design

### 1.1 Why In-Process Matters

SkyrimNet runs entirely as an **SKSE64 DLL** written in C++ with CommonLibSSE-NG—no external servers, no WSL, no Python middleware. This design choice provides:

| Benefit | Technical Implementation | BarnabeeNet Equivalent |
|---------|-------------------------|------------------------|
| **Direct Memory Access** | Reads game state from RAM | Read Home Assistant state directly |
| **Zero Serialization Overhead** | No JSON/HTTP round-trips for game data | Native HASS API integration |
| **Sub-100ms Latency** | In-process function calls | In-process Python async |
| **Hot-Reload Configuration** | YAML files watched for changes | YAML/JSON config watching |
| **Simplified Deployment** | Single DLL + config files | Single HA custom component |

### 1.2 File Structure

```
SKSE/Plugins/SkyrimNet/
├── SkyrimNet.dll              # Core engine (C++)
├── prompts/                   # Inja templates
│   ├── dialogue_response.prompt
│   ├── player_thoughts.prompt
│   └── submodules/
│       ├── character_bio/     # Per-character context (numbered for ordering)
│       │   ├── 0001_base.prompt
│       │   ├── 0002_personality.prompt
│       │   └── 0003_speech.prompt
│       └── system_head/       # System instructions
├── config/
│   ├── game.yaml              # Core game settings
│   ├── OpenRouter.yaml        # LLM provider config
│   ├── Memory.yaml            # Memory system settings
│   ├── Actions/               # Custom action definitions (YAML)
│   ├── Triggers/              # Custom trigger definitions (YAML)
│   └── Overrides/             # Per-NPC/faction overrides
└── data/
    ├── bios/                  # Static character biographies (3000+ NPCs)
    ├── dynamic_bios/          # AI-generated/updated biographies
    └── memories.db            # SQLite with vector extensions
```

**BarnabeeNet Translation:**
```
custom_components/barnabeenet/
├── __init__.py                # HA integration entry
├── core/
│   ├── bus.py                 # Message bus (Redis Streams)
│   └── context.py             # Request context management
├── agents/                    # Multi-agent system
│   ├── meta_agent.py          # Router/classifier
│   ├── instant_agent.py       # Pattern-matched responses
│   ├── action_agent.py        # Device control
│   ├── interaction_agent.py   # Complex conversations
│   ├── memory_agent.py        # Memory operations
│   └── proactive_agent.py     # Background monitoring
├── prompts/                   # Jinja2 templates
│   ├── dialogue/
│   ├── memory/
│   └── system/
├── config/                    # YAML configurations
│   ├── barnabee.yaml
│   ├── llm.yaml
│   └── overrides/             # Per-room, per-user overrides
└── data/
    └── memories.db            # SQLite + vector search
```

---

## 2. Multi-Agent LLM Architecture (The 7 Agents)

### 2.1 Agent Specialization

SkyrimNet uses **7 distinct LLM configurations**, each optimized for specific cognitive tasks. This is the single most important architectural pattern for creating an "alive" system.

| Agent | Primary Function | Model Requirements | Frequency | Cost Tier |
|-------|-----------------|-------------------|-----------|-----------|
| **Default (Dialogue)** | Generate spoken NPC dialogue | High-quality roleplay model | Per conversation turn | High |
| **GameMaster** | Ambient scene narration, NPC-to-NPC conversation initiation | Same as Default | Background (configurable cooldown) | Medium |
| **Memory Generation** | Summarize recent events into first-person memories | Good summarization | After event segments | Low |
| **Character Profile (Bio)** | Generate/update NPC biographies | JSON parsing capability | Infrequent | Low |
| **Action Evaluation** | Choose gameplay actions tied to dialogue | Context judgment | Post-dialogue | Low |
| **Combat Evaluation** | Battle dialogue and reactions | Fast, inexpensive | High frequency in combat | Lowest |
| **Meta Evaluation** | Mood analysis, speaker selection, emotional context | Lightweight, fast | Very high frequency | Lowest |

### 2.2 Model Selection Strategy

From the documentation and release notes:

```yaml
# Example OpenRouter.yaml configuration
Default:
  model: "anthropic/claude-3.5-sonnet"  # Quality dialogue
  temperature: 0.7
  max_tokens: 2000
  
Combat:
  model: "deepseek/deepseek-v3"  # Fast, cheap
  temperature: 0.8
  max_tokens: 500
  
Memory:
  model: "openai/gpt-4o-mini"  # Good summarization
  temperature: 0.3
  max_tokens: 1000
  
Meta:
  model: "deepseek/deepseek-v3"  # High-frequency, cheap
  temperature: 0.5
  max_tokens: 200
```

**Key Optimization:** Model rotation feature allows comma-separated models that cycle after each generation, preventing staleness and keeping weaker models on-track.

### 2.3 BarnabeeNet Agent Mapping

| SkyrimNet Agent | BarnabeeNet Equivalent | Purpose |
|-----------------|----------------------|---------|
| Default (Dialogue) | **Interaction Agent** | Complex conversations, advice |
| GameMaster | **Proactive Agent** | Ambient observations, proactive suggestions |
| Memory Generation | **Memory Agent** | Summarize daily events into patterns |
| Character Profile | N/A (single entity) | Could update user preference profiles |
| Action Evaluation | **Action Agent** | Determine which home actions to take |
| Combat Evaluation | **Instant Agent** | Fast pattern-matched responses |
| Meta Evaluation | **Meta Agent** | Route requests, determine urgency/mood |

---

## 3. Memory System Architecture

### 3.1 Per-Character First-Person Memory

**Critical Design:** Memories are created from a **first-person, per-character perspective**. Every NPC remembers events differently based on their personality and viewpoint.

```
NPC: Lydia witnesses player defeating dragon
Memory stored: "I watched in awe as my Thane brought down 
               a dragon with nothing but steel and determination. 
               I've never seen such bravery."

NPC: Nazeem witnesses same event
Memory stored: "That adventurer made quite a spectacle fighting 
               some flying lizard. I suppose it was impressive, 
               though I've seen better."
```

### 3.2 Memory Generation Algorithm

From Beta 2 release notes, the memory system uses **time-segmented generation**:

```yaml
Memory:
  min_segment_duration: 10    # Game minutes
  max_segment_duration: 720   # 12 game hours
  max_memories_per_retrieval: 5
  avoid_recent_events: 8      # Don't generate memories for events < 8 minutes old
```

**Result:** Testing showed compression from 518 → 162 memories with nearly same fidelity but significantly more cohesive narratives.

### 3.3 Memory Schema

Each memory contains:

```typescript
interface Memory {
  id: string;                    // Unique identifier
  actor_uuid: string;            // Who holds this memory
  content: string;               // First-person narrative
  type: MemoryType;              // TRAUMA, EXPERIENCE, RELATIONSHIP, etc.
  importance_score: number;      // 0.0-1.0, affects retention/retrieval
  emotion: string;               // Emotional context at creation
  tags: string[];                // Keywords for hybrid retrieval
  embedding: number[];           // MiniLM-L6-v2 384-dim vector
  location: string;              // Where the memory was formed
  actors_involved: string[];     // Other participants
  created_at: timestamp;
  last_accessed: timestamp;      // For decay calculation
}

enum MemoryType {
  TRAUMA = "trauma",             // Highly weighted
  EXPERIENCE = "experience",     // Standard events
  RELATIONSHIP = "relationship", // Social bonds
  KNOWLEDGE = "knowledge",       // Learned facts
  ROUTINE = "routine"            // Behavioral patterns
}
```

### 3.4 Vector-Based Retrieval

**Embedding Model:** MiniLM-L6-v2 (384 dimensions)

**Hybrid Retrieval:**
1. **Semantic Search:** Cosine similarity on embeddings
2. **Keyword/Tag Filtering:** Exact match on tags
3. **Metadata Filtering:** Actor, type, importance threshold
4. **Temporal Weighting:** Recent memories weighted higher
5. **Importance Weighting:** High-importance memories surface more often

**Query Generation:** The Meta Evaluation model generates search queries based on conversation context, ensuring relevant memories are retrieved without explicit user mention.

### 3.5 Temporal Decay

Memories naturally fade based on:
- **Last access time** — Frequently recalled memories persist
- **Importance score** — Critical events resist decay
- **Emotion tag** — Emotionally significant memories persist longer
- **Consolidation** — Related memories merge into behavioral patterns

### 3.6 BarnabeeNet Memory Translation

```python
# barnabee_memory.py
@dataclass
class BarnabeeMemory:
    id: str
    family_member: str           # Who this memory is "about" from Barnabee's view
    content: str                 # First-person narrative
    memory_type: str             # routine, preference, event, relationship
    importance: float            # 0.0-1.0
    room: str                    # Location context
    time_of_day: str             # Morning, afternoon, evening, night
    day_of_week: str             # Weekday vs weekend patterns
    participants: List[str]      # Who was involved
    embedding: List[float]       # Vector for semantic search
    created_at: datetime
    last_accessed: datetime
    
# Example memories Barnabee might form:
"The family usually gathers in the living room around 7pm on weeknights."
"Thom prefers the temperature at 68°F when working in the office."
"Last Tuesday, Thom mentioned being stressed about a work deadline."
"The kids' bedtime routine typically starts around 8:30pm."
```

---

## 4. Event System Architecture

### 4.1 Event Types

SkyrimNet distinguishes between **three event categories**:

| Type | Persistence | Use Case | TTL |
|------|-------------|----------|-----|
| **Short-Lived Events** | Ephemeral (Redis-like) | Real-time context (spells cast, animations) | Configurable (ms) |
| **Persistent Events** | Database | Historical tracking, memory generation | Permanent |
| **Direct Narration** | Triggers immediate response | Force NPCs to react to established facts | N/A |

### 4.2 Event Schema Registry

Custom events are defined via a schema registry:

```papyrus
int function RegisterEventSchema(
    String eventType,           // "custom_spell_learn"
    String displayName,         // "Spell Learned"
    String description,         // "When a character learns a new spell"
    String fieldsJson,          // Schema definition
    String formatTemplatesJson, // Display templates per mode
    bool isEphemeral,           // Auto-cleanup?
    int defaultTTLMs            // Time-to-live
) Global Native
```

**Format Templates:**

```json
{
  "recent_events": "**{{actor}}** learned {{spell_name}} ({{time_desc}})",
  "raw": "{{actor}} learned {{spell_name}}",
  "compact": "{{actor}}: {{spell_name}}",
  "verbose": "{{actor}} learned the {{spell_level}} level spell {{spell_name}} at {{location}}"
}
```

### 4.3 Event History in Context

The dialogue prompt includes recent events:

```yaml
Event_History_Count: 50   # Recent events in context window
```

This gives the LLM awareness of what just happened without consuming the entire context window.

### 4.4 BarnabeeNet Event Translation

```python
# Home Assistant Events → BarnabeeNet Events
EVENT_MAPPINGS = {
    "state_changed": {
        "format": "{{device}} changed from {{old_state}} to {{new_state}}",
        "ttl_ms": 60000,  # 1 minute
        "ephemeral": True
    },
    "motion_detected": {
        "format": "Motion detected in {{room}}",
        "ttl_ms": 30000,
        "ephemeral": True
    },
    "person_home": {
        "format": "{{person}} arrived home",
        "ttl_ms": 0,  # Persistent
        "ephemeral": False
    },
    "calendar_reminder": {
        "format": "Upcoming: {{event_title}} in {{time_until}}",
        "ttl_ms": 300000,
        "ephemeral": True
    }
}
```

---

## 5. Decorator System (Context Injection)

### 5.1 What Are Decorators?

Decorators are **functions callable from within prompts** that inject dynamic context. They're the bridge between static prompt templates and live game/home state.

### 5.2 Built-in Decorators

| Decorator | Usage | Returns |
|-----------|-------|---------|
| `decnpc(UUID)` | `{{ decnpc(npc.UUID).name }}` | NPC attributes (name, race, gender, health, etc.) |
| `has_line_of_sight(UUID1, UUID2)` | `{{ has_line_of_sight(speaker.UUID, player.UUID) }}` | Boolean visibility check |
| `get_selected_quests()` | `{{ get_selected_quests() }}` | Active journal quests |
| `get_crime_gold(faction)` | `{{ get_crime_gold("WhiterunGuardsFaction") }}` | Player's bounty |
| `is_player(UUID)` | `{{ is_player(npc.UUID) }}` | Boolean player check |
| `is_audio_tags_enabled(UUID)` | For TTS engine feature detection | Boolean |

### 5.3 Custom Decorator Registration

```papyrus
int function RegisterDecorator(
    String decoratorID,        // "my_custom_decorator"
    String sourceScript,       // Papyrus script name
    String functionName        // Function implementing logic
) Global Native

// Usage in prompt:
// {{my_custom_decorator(player.UUID)}} → Function MyDecorator(Actor akActor) Global
```

### 5.4 NPC Attribute Access via decnpc()

```jinja
You are roleplaying as {{ decnpc(npc.UUID).name }}, 
a {{ decnpc(npc.UUID).gender }} {{ decnpc(npc.UUID).race }} in Skyrim.
Current health: {{ decnpc(npc.UUID).health }}%
Location: {{ decnpc(npc.UUID).location }}
Currently: {{ decnpc(npc.UUID).activity }} {# sitting, walking, fighting, etc. #}
Relationship to player: {{ decnpc(npc.UUID).relationship }}
```

### 5.5 BarnabeeNet Decorator Translation

```python
# Jinja2 custom filters/functions for BarnabeeNet
@jinja_filter
def home_state(entity_id):
    """{{ 'light.living_room' | home_state }}"""
    return hass.states.get(entity_id)

@jinja_filter  
def room_context(room_name):
    """{{ 'living_room' | room_context }}"""
    return {
        "temperature": get_room_temp(room_name),
        "lights": get_room_lights(room_name),
        "occupancy": get_room_occupancy(room_name),
        "devices_on": get_active_devices(room_name)
    }

@jinja_filter
def family_member(name):
    """{{ 'Thom' | family_member }}"""
    return {
        "location": get_person_location(name),
        "home": is_person_home(name),
        "preferences": get_preferences(name),
        "schedule": get_today_schedule(name)
    }

@jinja_filter
def current_context():
    """{{ current_context() }}"""
    return {
        "time_of_day": get_time_of_day(),
        "day_type": "weekday" if is_weekday() else "weekend",
        "weather": get_weather(),
        "occupancy": get_home_occupancy(),
        "recent_events": get_recent_events(50)
    }
```

---

## 6. Action System Architecture

### 6.1 Action Definition (YAML)

Actions allow NPCs to **do things** after speaking—attack, give items, follow, etc.

```yaml
# SKSE/Plugins/SkyrimNet/config/actions/attack.yaml
name: Attack
description: |
  Use this action to make the speaking NPC immediately attack a specified target.
  Call it when:
  (A) The Player issues a combat order (attack/kill/eliminate/engage); or
  (B) The NPC decides retaliation is necessary.
  Targeting: if a name is given, attack that actor; else attack crosshair target.
  
questEditorId: SkyrimNet_Tools
scriptName: SkyrimNet_AttackAPI
executionFunctionName: Attack

eligibilityScriptName: SkyrimNet_Eligibility
eligibilityFunctionName: CanAttack

triggeringEventTypes:
  - dialogue
  - combat_start
  - threat_detected

parameterMapping:
  - type: dynamic
    name: attacker
    description: The NPC who will attack
  - type: dynamic
    name: target
    description: The target to attack (name or "crosshair")
  - type: static
    value: false
    name: lethal
    description: Whether to use lethal force

enabled: true
defaultPriority: 8
cooldownSeconds: 30
tags:
  - combat
  - aggressive
```

### 6.2 Eligibility Checking

Before an action can be selected, the system checks eligibility:

```papyrus
// SkyrimNet_Eligibility.psc
bool function CanAttack(Actor akActor) Global
    if akActor.IsDead()
        return false
    endif
    if akActor.IsInCombat()
        return true  // Already fighting, can redirect
    endif
    if akActor.GetAV("Health") < 10
        return false  // Too injured
    endif
    return true
endfunction
```

### 6.3 Action Evaluation Flow

```
1. Dialogue generated by Default model
2. Action Evaluation model receives:
   - Recent dialogue
   - Speaker context
   - Available (eligible) actions
   - Current scene state
3. Model outputs action selection + parameters (JSON)
4. System executes action via Papyrus
5. Result fed back into event stream
```

### 6.4 BarnabeeNet Action Translation

```yaml
# barnabeenet/config/actions/adjust_temperature.yaml
name: adjust_temperature
description: |
  Adjust the thermostat temperature for a room or the whole house.
  Use when:
  - User requests temperature change
  - User expresses being hot/cold
  - Proactive adjustment based on schedule
  
service: climate.set_temperature
entity_pattern: climate.{zone}

eligibility:
  conditions:
    - "{{ zone in ['house', 'office', 'bedroom', 'living_room'] }}"
    - "{{ 60 <= temperature <= 80 }}"
    
parameters:
  - name: zone
    type: dynamic
    description: Which zone to adjust (house, office, bedroom, living_room)
  - name: temperature
    type: dynamic
    description: Target temperature in Fahrenheit
  - name: reason
    type: dynamic
    description: Why this adjustment is being made

enabled: true
cooldown_seconds: 60
tags:
  - climate
  - comfort
```

---

## 7. OmniSight Vision System

### 7.1 Purpose

OmniSight gives the LLM **real visual awareness** of the game world through AI-powered image analysis.

### 7.2 Capture Triggers

| Trigger | When | Data Captured |
|---------|------|---------------|
| **Dialogue Start** | Player initiates conversation | Scene context |
| **Location Change** | Enter new cell/area | Architecture, terrain, objects |
| **Hotkey (Click)** | Manual capture | Crosshair target description |
| **Hotkey (Hold)** | Manual capture | Player character description |
| **Background Worker** | Continuous passive | World state changes |

### 7.3 Vision Model Integration

```yaml
OmniSight:
  enabled: true
  model: "openai/gpt-4o-mini"  # Vision-capable model
  max_tokens: 500
  capture_on_dialogue: true
  capture_on_location_change: true
  background_worker: true
  background_interval_seconds: 60
  cost_per_capture: 0.0004  # ~$0.0004, 2500 captures per dollar
```

### 7.4 Description Storage

```
Scene: "The Bannered Mare interior. A crackling fireplace casts 
       warm light across wooden tables. Several patrons sit 
       drinking. The bard plays a lute near the stairs."
       
Location: "WhiterunBanneredMareInterior"
Stored: true
Used in: NPC ambient dialogue, context awareness
```

### 7.5 Item Capture System (Beta 10+)

For equipment descriptions:
- Multi-angle renders of items
- Content hash deduplication (same mesh+texture = shared description)
- Supports weapons, armor, potions, books, etc.

### 7.6 BarnabeeNet Vision Translation

While BarnabeeNet doesn't need "vision" in the same way, similar patterns apply:

```python
# Camera integration for "visual awareness"
class BarnabeeVision:
    """Optional: Process camera feeds for context"""
    
    async def analyze_room_camera(self, room: str) -> dict:
        """Capture and analyze current room state"""
        image = await self.capture_camera(f"camera.{room}")
        description = await self.vision_model.describe(
            image,
            prompt="Describe what you see in this home camera feed. "
                   "Note any people, activities, pets, or unusual conditions."
        )
        return {
            "room": room,
            "description": description,
            "timestamp": datetime.now(),
            "occupancy_detected": self.detect_occupancy(description)
        }
    
    # Could also analyze:
    # - Doorbell camera when someone arrives
    # - Baby monitor for activity
    # - Security cameras for unusual activity
```

---

## 8. Web Dashboard & Observability

### 8.1 Dashboard Features

The web UI at `localhost:8080` provides:

| Section | Purpose | Real-time? |
|---------|---------|------------|
| **Dashboard** | System status, OmniSight preview, nearby NPCs, events | Yes |
| **API Requests** | Every LLM call with input/output/timing/tokens | Yes |
| **Characters** | Bio editor, dynamic bio viewer, actor stats | Live data |
| **Memories** | Search, create, edit, delete memories | Yes |
| **OmniSight** | All captured images with descriptions | Historical |
| **Configuration** | Live config editing with validation | Hot-reload |
| **VastAI** | Cloud GPU instance management | Yes |
| **Trace Explorer** | Waterfall view of request processing | Yes |
| **Event Monitor** | All game events with payload inspection | Yes |

### 8.2 API Request Inspection

Critical for debugging—shows exactly what context was sent to each LLM:

```json
{
  "request_id": "abc123",
  "model_type": "dialogue",
  "model": "anthropic/claude-3.5-sonnet",
  "input_tokens": 2847,
  "output_tokens": 156,
  "latency_ms": 1234,
  "prompt": "You are roleplaying as Lydia...",
  "response": "My Thane, I've been thinking about...",
  "timestamp": "2026-01-16T10:30:00Z"
}
```

### 8.3 Trace Explorer (Beta 9+)

Waterfall visualization showing:
- Memory retrieval duration
- Context building duration
- LLM API call duration
- Post-processing duration
- TTS generation duration
- Total end-to-end time

### 8.4 BarnabeeNet Dashboard Translation

```
BarnabeeNet Dashboard (Grafana + Custom)
├── Home Overview
│   ├── Current occupancy
│   ├── Active devices
│   ├── Recent events stream
│   └── Ambient conditions
├── Conversation Log
│   ├── Full dialogue history
│   ├── Agent routing decisions
│   └── Action executions
├── Memory Browser
│   ├── Semantic search
│   ├── Memory timeline
│   └── Importance distribution
├── Request Inspector
│   ├── All LLM calls
│   ├── Input/output/timing
│   └── Token usage + cost
├── Configuration
│   └── Live editing with validation
└── Trace Viewer
    └── Request processing waterfall
```

---

## 9. Prompt Engineering Patterns

### 9.1 Prompt File Structure

```
prompts/
├── dialogue_response.prompt      # Main dialogue generation
├── player_thoughts.prompt        # Player internal monologue
├── player_transform.prompt       # Transform player input
├── gamemaster.prompt             # Ambient narration
├── memory_generation.prompt      # Create memories from events
├── action_selection.prompt       # Choose post-dialogue actions
└── submodules/
    ├── character_bio/            # Numbered for ordering
    │   ├── 0001_identity.prompt
    │   ├── 0002_personality.prompt
    │   ├── 0003_relationships.prompt
    │   ├── 0004_goals.prompt
    │   └── 0005_speech.prompt
    └── system_head/
        └── 0001_base.prompt
```

### 9.2 Prompt Best Practices (from docs)

**DO:**
- Keep prompts clean and minimal
- Use template variables, not hardcoded values
- Guide tone, don't dictate exact dialogue
- Trust the memory system for history
- Use numbered files for ordering

**DON'T:**
- Overload with redundant instructions
- Write "walls of prose" in system instructions
- Force NPCs to behave unrealistically
- Encode entire lore in prompts
- Ask for narrative control

### 9.3 Example Prompt Structure

```jinja
{# dialogue_response.prompt #}
{% include "submodules/system_head/0001_base.prompt" %}

## Character Information
{% include "submodules/character_bio/" %}

## Current Situation
Location: {{ current_location.description }}
Time: {{ time_desc }}
Weather: {{ weather }}
Nearby: {{ nearby_actors | map(attribute='name') | join(', ') }}

## Recent Events
{% for event in recent_events %}
{{ event | format_event('recent_events') }}
{% endfor %}

## Relevant Memories
{% for memory in retrieved_memories %}
- {{ memory.content }} ({{ memory.emotion }})
{% endfor %}

## Current Conversation
{% for turn in conversation_history %}
{{ turn.speaker }}: {{ turn.text }}
{% endfor %}

Respond as {{ decnpc(npc.UUID).name }} would in this situation.
Keep the response natural and in-character.
```

---

## 10. Trigger System

### 10.1 Trigger Definition

Triggers fire when specific game events occur:

```yaml
# SKSE/Plugins/SkyrimNet/config/triggers/dragon_attack.yaml
name: dragon_attack_response
description: NPCs react when a dragon attacks nearby

trigger_events:
  - animation_event:
      pattern: "DragonLanding*"
  - combat_start:
      actor_race: "DragonRace"

conditions:
  - "{{ distance(event.actor, player) < 1000 }}"
  - "{{ nearby_npcs | length > 0 }}"

actions:
  - type: direct_narration
    content: "A dragon descends from the sky with a thunderous roar!"
  - type: trigger_dialogue
    speaker_selection: "nearest_non_combat"
    mood: "terrified"

cooldown_seconds: 300
enabled: true
```

### 10.2 Event Types for Triggers (Beta 10+)

- **Animation Events** — Character animations
- **Mod Events** — Inter-mod communication
- **Quest Events** — Quest start/stop/objective changes
- **Active Effect Events** — Magic effect application/removal
- **Combat Events** — Combat start/end/hit
- **Death Events** — Actor deaths

### 10.3 BarnabeeNet Trigger Translation

```yaml
# barnabeenet/config/triggers/bedtime_routine.yaml
name: bedtime_routine
description: Proactive bedtime reminders for kids

trigger_events:
  - time:
      after: "20:15"
      before: "20:45"
      days: ["monday", "tuesday", "wednesday", "thursday", "sunday"]
  - state_changed:
      entity: sensor.kids_room_motion
      to: "on"

conditions:
  - "{{ is_school_night() }}"
  - "{{ not already_reminded_today('bedtime') }}"

actions:
  - type: proactive_suggestion
    content: "It's getting close to bedtime for the little ones."
    room: "kids_room"
  
cooldown_seconds: 3600  # Once per night
enabled: true
```

---

## 11. Voice Pipeline

### 11.1 TTS Engine Options

| Engine | Quality | Latency | Voice Cloning | Use Case |
|--------|---------|---------|---------------|----------|
| **Piper** | Good | <100ms | No | Fast responses, low-spec |
| **XTTS** | Excellent | 1-2s | Yes (7-10s samples) | High quality |
| **Zonos** | Studio | 2-3s | Yes | Key characters |
| **ElevenLabs** | Professional | Variable | Yes (API) | Premium quality |

### 11.2 Voice Sample Collection

For XTTS voice cloning:
- **Format:** WAV, Mono, 22050Hz, 16-bit
- **Duration:** 7-10 seconds of clean speech
- **Auto-scanning:** Vanilla game audio automatically parsed
- **Custom samples:** Per-NPC folders supported

### 11.3 Streaming Pipeline

```
User Input → Whisper STT (CUDA in-process)
    ↓
LLM Response (SSE streaming)
    ↓
TTS Generation (streamed to audio queue)
    ↓
Playback + Lip Animation Sync
```

### 11.4 BarnabeeNet Voice Translation

```python
class BarnabeeVoicePipeline:
    def __init__(self):
        self.stt = WhisperSTT(model="base.en")  # Local Whisper
        self.tts_fast = PiperTTS()              # Fast responses
        self.tts_quality = XTTS()               # Quality responses
    
    async def process_voice_input(self, audio: bytes) -> str:
        """STT processing"""
        return await self.stt.transcribe(audio)
    
    async def generate_speech(self, text: str, quality: str = "fast") -> bytes:
        """TTS generation with quality selection"""
        if quality == "fast" or len(text) < 50:
            return await self.tts_fast.synthesize(text)
        else:
            return await self.tts_quality.synthesize(text)
```

---

## 12. Key Architectural Lessons for BarnabeeNet

### 12.1 What Makes SkyrimNet Feel "Alive"

1. **Multi-Agent Specialization** — Different models for different cognitive tasks
2. **First-Person Memory** — Memories from Barnabee's perspective about the family
3. **Temporal Awareness** — Time-of-day, day-of-week, seasonal patterns
4. **Environmental Context** — Rich sensor data injected via decorators
5. **Proactive Behavior** — GameMaster-style ambient observations
6. **Comprehensive Logging** — Ability to see exactly what the AI is "thinking"
7. **Hot-Reload Everything** — Iterate without restarting

### 12.2 Recommended BarnabeeNet Implementation Order

1. **Phase 1: Foundation**
   - Home Assistant integration with state access
   - Basic prompt templates (Jinja2)
   - Single LLM for dialogue
   - SQLite for memory storage

2. **Phase 2: Multi-Agent**
   - Meta Agent for routing
   - Instant Agent for quick responses
   - Action Agent for device control
   - Memory Agent for storage/retrieval

3. **Phase 3: Memory System**
   - Vector embeddings (MiniLM-L6-v2)
   - Importance scoring
   - Temporal decay
   - Semantic retrieval

4. **Phase 4: Observability**
   - Web dashboard
   - Request logging
   - Memory browser
   - Cost tracking

5. **Phase 5: Proactive Intelligence**
   - Trigger system
   - Pattern recognition
   - Proactive suggestions
   - Ambient observations

### 12.3 Technology Stack Recommendations

| Component | SkyrimNet | BarnabeeNet Recommendation |
|-----------|-----------|---------------------------|
| Core Language | C++ | Python (async) |
| Message Bus | In-process | Redis Streams |
| Template Engine | Inja (C++ Jinja) | Jinja2 |
| Memory DB | SQLite + Vector | SQLite + sqlite-vss |
| Embedding Model | MiniLM-L6-v2 | MiniLM-L6-v2 (sentence-transformers) |
| Primary LLM | OpenRouter | OpenRouter |
| Fast LLM | DeepSeek | DeepSeek / Local (Ollama) |
| TTS | Piper/XTTS | Piper (local) |
| STT | Whisper (CUDA) | Whisper (faster-whisper) |
| Dashboard | Custom Web UI | Grafana + Custom |
| Configuration | YAML | YAML |

---

## 13. Conclusion

SkyrimNet's success in making NPCs feel "alive" comes from the careful orchestration of multiple systems—not any single breakthrough. The key patterns are:

1. **Agent Specialization** — Use the right model for each task
2. **First-Person Memory** — Store memories from the entity's perspective
3. **Rich Context Injection** — Decorators that pull live state into prompts
4. **Event-Driven Architecture** — React to state changes naturally
5. **Comprehensive Observability** — See what the AI is thinking
6. **Hot Configuration** — Iterate rapidly without restarts

BarnabeeNet can achieve the same "alive" feeling by implementing these patterns adapted for smart home context. The single most impactful change would be implementing **multi-agent architecture** with specialized models for different task types, combined with **first-person memory** that lets Barnabee remember patterns about each family member from its own perspective.

---

## Appendix A: Key API Functions

```papyrus
// Decorator Management
RegisterDecorator(decoratorID, sourceScript, functionName)

// Action Management
RegisterAction(actionName, description, eligibilityScript, eligibilityFunction,
               executionScript, executionFunction, triggerEvents, category,
               priority, parameterSchema, customCategory, tags)
IsActionRegistered(actionName)
ExecuteAction(actionName, originator, argsJson)

// Event Management
RegisterShortLivedEvent(eventId, eventType, description, data, ttlMs, source, target)
RegisterEvent(eventType, content, originator, target)
RegisterEventSchema(eventType, displayName, description, fields, templates, ephemeral, ttl)

// Dialogue Management
RegisterDialogue(speaker, dialogue)
RegisterDialogueToListener(speaker, listener, dialogue)
DirectNarration(content, originator, target)

// Memory Management
// (Handled internally via Memory Agent)

// LLM Interaction
SendCustomPromptToLLM(promptName, temperature, maxTokens, callbackScript, callbackFunction)

// Utility
GetJsonString(jsonString, key, defaultValue)
GetConfigString(configName, path, defaultValue)
RenderTemplate(templateName, variableName, variableValue)
ParseString(inputStr, variableName, variableValue)

// Hotkey Triggers
TriggerRecordSpeechPressed()
TriggerRecordSpeechReleased(duration)
TriggerTextInput()
TriggerToggleGameMaster()
TriggerPlayerThought()
TriggerPlayerDialogue()
```

---

## Appendix B: Configuration Reference

```yaml
# game.yaml equivalent for BarnabeeNet
barnabee:
  interaction:
    max_distance: 50           # Meters for proactive interaction
    whisper_distance: 10       # Private conversation distance
    
  gamemaster:
    enabled: true
    agent_enabled: true
    cooldown_seconds: 30
    recent_events_count: 50
    nearby_actor_radius: 800
    
  memory:
    min_segment_duration: 10   # Minutes
    max_segment_duration: 720  # 12 hours
    max_memories_retrieval: 5
    importance_threshold: 0.3
    
  voice:
    stt_model: "base.en"
    tts_engine: "piper"
    tts_quality_threshold: 50  # Character count for quality TTS
    
  omnisight:
    enabled: false             # Optional camera integration
    capture_on_interaction: true
    cost_limit_daily: 1.00     # Dollar limit
    
  llm:
    default:
      model: "anthropic/claude-3.5-sonnet"
      temperature: 0.7
      max_tokens: 2000
    meta:
      model: "deepseek/deepseek-v3"
      temperature: 0.5
      max_tokens: 200
    memory:
      model: "openai/gpt-4o-mini"
      temperature: 0.3
      max_tokens: 1000
```

---

*End of Research Document*
