# BarnabeeNet: Privacy-First Multi-Agent Smart Home AI

**Version:** 3.2  
**Last Updated:** January 17, 2026  
**Author:** Thom Fife  
**Status:** Architecture & Planning (Pre-Implementation)

---

## Executive Summary

BarnabeeNet is a **privacy-first smart home AI assistant** designed to feel genuinely "alive" while keeping personal data under your control. Unlike commercial alternatives (Alexa, Google Home, Siri), BarnabeeNet processes **voice capture, STT, TTS, and speaker recognition locally** on your own hardware, while leveraging **cloud LLMs (Azure/OpenRouter)** for intelligent responses—combining the privacy of local processing with the power of state-of-the-art language models.

### What Makes BarnabeeNet Different

| Dimension | Commercial Assistants | BarnabeeNet |
|-----------|----------------------|-------------|
| **Privacy** | Cloud-dependent, data harvested | Local-first, data sovereignty |
| **Latency** | Variable (network-dependent) | Consistent <500ms |
| **Personalization** | Account-level | Speaker-level recognition |
| **Memory** | Session-based | Long-term episodic/semantic |
| **Customization** | Limited APIs | Full control |
| **Evolution** | Vendor-controlled | Self-improving |

### Architecture Highlights

- **Multi-Agent System**: Specialized agents (Meta, Instant, Action, Interaction, Memory, Proactive, Evolver) handle different request types with appropriate cost/latency tradeoffs
- **Hybrid Architecture**: STT, TTS, and speaker recognition run locally; LLM reasoning via Azure/OpenRouter for speed and capability
- **Privacy Zones**: Architectural enforcement of no-audio/no-memory zones for children's rooms and bathrooms
- **Self-Improvement**: Evolver Agent proposes optimizations via vibe coding and benchmarking
- **Multi-Modal Input**: Voice, AR glasses (Even Realities G1), wearable (Amazfit Cheetah Pro), touch dashboards (ThinkSmart View)
- **Prompt Engineering**: Modular template system with live context injection via decorators
- **Spatial Awareness**: Room graph enabling location-aware proactive suggestions
- **Adaptive Responses**: Per-listener response tailoring based on speaker, context, and mood

### Hardware Foundation

| Component | Purpose | Always On? |
|-----------|---------|------------|
| **Beelink EQi12** | Edge compute, HA host, STT/TTS | Yes (24/7) |
| **Gaming PC (RTX 4070 Ti)** | Heavy LLM inference, training, vibe coding | No (on-demand) |
| **Even Realities G1** | AR overlays, visual notifications | No (worn) |
| **Amazfit Cheetah Pro** | Gestures, haptics, choices | Yes (worn) |
| **ThinkSmart View** | Touch dashboards, voice satellites | Yes (per-room) |

### Key Design Decisions

- **Home Assistant Core**: Leverage mature ecosystem rather than reinvent device integration
- **OpenRouter for LLMs**: Flexible model switching without vendor lock-in (Sonnet for quality, Flash for speed)
- **Redis + SQLite**: Working memory (ephemeral) + Long-term memory (persistent)
- **ECAPA-TDNN for Speaker ID**: State-of-art speaker verification without cloud
- **Self-Improvement Path**: Gaming PC handles vibe coding, pushing updates to Beelink via Git/Proxmox.

---

## Multi-Agent Architecture

### Agent Hierarchy Overview

BarnabeeNet implements a hierarchical multi-agent system where specialized agents handle different types of requests. This architecture, proven in game AI systems, optimizes for both latency and cost.

```
                    ┌──────────────────┐
                    │   Multi-Modal    │
                    │   Input (AR/     │
                    │   Voice/Touch/   │
                    │   Wearable)      │
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │  Speaker ID +    │
                    │  STT/Gesture     │
                    │  Pipeline        │
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │   Meta Agent     │
                    │  (Router/Triage) │
                    └────────┬─────────┘
           ┌─────────────────┼─────────────────┐
           │                 │                 │
    ┌──────▼──────┐  ┌───────▼───────┐  ┌──────▼──────┐
    │   Instant   │  │    Action     │  │ Interaction │
    │   Response  │  │    Agent      │  │    Agent    │
    │   (~3ms)    │  │   (~30-50ms)  │  │  (~1-3s)    │
    └─────────────┘  └───────────────┘  └─────────────┘
                             │
                    ┌────────▼─────────┐
                    │   Evolver Agent  │
                    │  (Self-Improve)  │
                    └───────────────────┘
```

- **Wearable Inputs in Pipeline**: Gestures (e.g., wrist twist for "Yes", button click for "No") route through the Meta Agent as action intents.

### Agent Specifications

#### 1. Meta Agent (Router)

**Purpose:** Classify incoming requests (including watch gestures) and route to appropriate specialized agent.

| Attribute | Value |
|-----------|-------|
| Latency Target | <20ms |
| Model (Cloud) | Gemini Flash / Claude Haiku via OpenRouter |
| Model (Local) | Rule-based first, Phi-3.5 fallback |
| Cost per call | ~$0.0001 (cloud) / $0 (local) |

**Implementation Strategy:**
```
Phase 1: Rule-based routing (pattern matching + gesture mapping)
  - Keywords: "turn on/off", "set", "what time" → Action Agent
  - Keywords: "what's the weather", "tell me about" → Interaction Agent
  - Exact matches: "time", "date", "hello" → Instant Response
  - Gestures: Twist crown → Select choice; Motion shake → Dismiss; Button click → Confirm

Phase 2: LLM fallback for ambiguous cases
  - Only invoked when confidence < 0.7
  - Returns classification + confidence score
```

**Classification Categories:**
- `instant` — No LLM needed, pattern-matched response
- `action` — Device control, home automation (now includes gesture triggers)
- `query` — Information retrieval (weather, calendar, etc.)
- `conversation` — Multi-turn dialogue requiring context
- `memory` — Personal information retrieval
- `emergency` — Safety-critical (always prioritized)

**Enhanced Capabilities (v3.2+):**
- **Mood Evaluation**: Lightweight sentiment analysis of user input to detect urgency, frustration, or casual tone—adapts routing priority and downstream agent temperature
- **Memory Query Generation**: Automatically generates semantic search queries based on conversation context, ensuring relevant memories are retrieved without explicit user mention
- **Deferred Proactive Evaluation**: Background evaluation loop that assesses environmental triggers at configurable intervals, queuing notifications for approval rather than processing synchronously

See *BarnabeeNet_Technical_Architecture.md §Multi-Agent System Design* for implementation details.

#### 2. Instant Response Agent

**Purpose:** Handle predictable queries with sub-5ms response time, no LLM needed.

| Attribute | Value |
|-----------|-------|
| Latency Target | <5ms |
| Model | None (pattern matching + templates) |
| Cost | $0 |

**Patterns:**
```python
INSTANT_PATTERNS = {
    "time": lambda: f"It's {datetime.now().strftime('%I:%M %p')}",
    "date": lambda: f"Today is {datetime.now().strftime('%A, %B %d')}",
    "hello|hi|hey": lambda name: f"Hello, {name}!" if name else "Hello!",
    r"\d+\s*[\+\-\*\/]\s*\d+": lambda expr: str(safe_eval(expr)),
}
```

#### 3. Action Agent

**Purpose:** Execute device control commands via Home Assistant, including gesture-triggered actions.

| Attribute | Value |
|-----------|-------|
| Latency Target | <100ms (including HA call) |
| Model (Cloud) | Gemini Flash / Claude Haiku |
| Model (Local) | Phi-3.5 / Llama 3.2 3B |
| Cost per call | ~$0.0002 |

**Input Processing:**
- Natural language: "Turn on living room lights to 80%"
- Structured gesture: `{"gesture": "crown_twist_yes", "context_id": "light_confirm_123"}`
- Watch choices: "Confirm action? Yes/No" (choice returned as "Yes/No" via watch buttons)

**Output Schema:**
```json
{
  "action": "call_service",
  "domain": "light",
  "service": "turn_on",
  "target": {
    "entity_id": ["light.living_room", "light.kitchen"]
  },
  "data": {
    "brightness_pct": 80,
    "color_temp_kelvin": 3000
  },
  "confirmation": "Turning on living room and kitchen lights to 80%"
}
```

#### 4. Interaction Agent

**Purpose:** Handle complex conversations, questions, and multi-turn dialogue, with watch choice inputs.

| Attribute | Value |
|-----------|-------|
| Latency Target | <3s (acceptable for complex queries) |
| Model (Cloud) | Claude Sonnet / GPT-4o via OpenRouter |
| Model (Local) | Llama 3.1 8B / Mistral 7B |
| Cost per call | ~$0.003-0.01 |

**Capabilities:**
- Multi-turn conversation with context
- Personal knowledge retrieval (calendar, preferences)
- Complex reasoning and analysis
- Creative responses (stories, jokes, explanations)
- Web search integration (when enabled)
- Emotional detection (voice sentiment via librosa)
- AR integration (e.g., overlay explanations on glasses)
- Watch choices (e.g., "Approve automation? Twist for Yes")

#### 5. Memory Agent

**Purpose:** Manage long-term memory storage, retrieval, and consolidation.

| Attribute | Value |
|-----------|-------|
| Latency Target | <50ms for retrieval |
| Storage | SQLite (persistent) + Redis (ephemeral) |
| Embedding Model | all-MiniLM-L6-v2 (local) |

**Memory Types:**
```yaml
episodic:
  description: Specific events and conversations
  retention: 30 days default
  storage: SQLite with vector embeddings

semantic:
  description: Extracted facts and preferences
  retention: Indefinite (until contradicted)
  storage: SQLite key-value

procedural:
  description: Learned routines and patterns
  retention: Indefinite
  storage: SQLite + HA automations

working:
  description: Current conversation context
  retention: Session (10 min TTL)
  storage: Redis
```

#### 6. Proactive Agent

**Purpose:** Monitor conditions and generate unsolicited notifications.

| Attribute | Value |
|-----------|-------|
| Trigger | Polling-based (periodic HA state checks) |
| Latency Target | N/A (background) |
| Model | Rule-based + lightweight LLM summary |

**Proactive Behaviors:**
```yaml
safety_alerts:
  - Door left open > 10 minutes at night
  - Unusual motion patterns
  - Temperature extremes
  - Water leak detection

convenience_reminders:
  - Calendar events approaching
  - Package delivery detected
  - Weather changes affecting plans

learning_suggestions:
  - Detected patterns → automation suggestions
  - Energy optimization recommendations

wearable_choices:
  - Send notifications with options (e.g., "Adjust temp? Yes/No" via watch buttons)
```

**Family-Safe Constraints:**
- NO automatic door locking (safety hazard)
- NO proactive audio in children's rooms
- Notification-only for security events (human confirms action)
- Rate limiting on non-critical notifications

**Note on Deferred Evaluation:** Proactive triggers are evaluated in a background loop rather than blocking the main request pipeline. Candidate notifications are scored by utility (urgency × relevance × user context) and deferred to a queue. Only notifications exceeding the configured threshold are surfaced. See *BarnabeeNet_Technical_Architecture.md §Proactive Agent* for the evaluation algorithm.

#### 7. Evolver Agent

**Purpose:** Continuously improve system performance through automated optimization.

| Attribute | Value |
|-----------|-------|
| Trigger | Scheduled (nightly) + manual |
| Scope | Internal optimization only |
| Approval | Required for all changes |

**Capabilities:**
- **Prompt Refinement**: A/B test prompt variants using Azure ML for offline evals
- **Model Benchmarking**: Compare LLM performance via Azure ML
- **Code Enhancement**: Propose PRs for agent improvements
- **Pattern Learning**: Discover behavioral patterns for automations

**Boundaries:**
- Changes require user approval
- No external API modifications
- Scoped to internal optimization only
- All proposals logged for audit

---

## Memory System

BarnabeeNet implements a four-tier memory architecture inspired by cognitive science models:

```
┌─────────────────────────────────────────────────────────────┐
│                    MEMORY ARCHITECTURE                       │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              WORKING MEMORY (Redis)                   │   │
│  │  Retention: 10 minutes | Scope: Current session       │   │
│  │                                                       │   │
│  │  - Current conversation context                       │   │
│  │  - Recent commands and responses                      │   │
│  │  - Active session state                               │   │
│  └──────────────────────────────────────────────────────┘   │
│                           │                                  │
│                           ▼ (Consolidation)                  │
│  ┌──────────────────────────────────────────────────────┐   │
│  │            EPISODIC MEMORY (SQLite + Vectors)         │   │
│  │  Retention: 30 days | Scope: Specific events          │   │
│  │                                                       │   │
│  │  - "Yesterday Thom asked about flights to Denver"    │   │
│  │  - "Last Tuesday the kids had soccer practice"       │   │
│  │  - Full conversation logs with embeddings             │   │
│  └──────────────────────────────────────────────────────┘   │
│                           │                                  │
│                           ▼ (Extraction)                     │
│  ┌──────────────────────────────────────────────────────┐   │
│  │            SEMANTIC MEMORY (SQLite Key-Value)         │   │
│  │  Retention: Indefinite | Scope: Facts & Preferences   │   │
│  │                                                       │   │
│  │  - User preferences (lighting, temperature, music)    │   │
│  │  - Learned facts ("Thom likes coffee at 7am")        │   │
│  │  - Relationship knowledge ("Elizabeth is Thom's wife")│   │
│  └──────────────────────────────────────────────────────┘   │
│                           │                                  │
│                           ▼ (Pattern Recognition)            │
│  ┌──────────────────────────────────────────────────────┐   │
│  │            PROCEDURAL MEMORY (HA Automations)         │   │
│  │  Retention: Until modified | Scope: Learned routines  │   │
│  │                                                       │   │
│  │  - "Thom usually turns on office lights at 6:30am"   │   │
│  │  - "Kids' bedtime routine starts at 8pm"             │   │
│  │  - Suggested automations from detected patterns       │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### First-Person Perspective

All memories are stored from Barnabee's perspective, not as objective facts. This design choice (inspired by SkyrimNet's NPC memory architecture) creates more natural recall patterns:

- Instead of: `"User prefers 68°F"` 
- Barnabee stores: `"Thom mentioned he works best when I keep the office at 68°F"`

This perspective enables richer contextual responses and more natural conversation continuity.

### Hybrid Retrieval Algorithm

Memory queries use a hybrid approach combining:

1. **Semantic similarity** (vector cosine distance on embeddings)
2. **Keyword/tag filtering** (exact match on extracted tags)
3. **Temporal weighting** (recent memories scored higher)
4. **Importance weighting** (critical events resist decay)

The Meta Agent generates optimized search queries based on conversation context. See *BarnabeeNet_Technical_Architecture.md §Memory System Architecture* for scoring formulas and thresholds.

### Database Schema

```sql
-- Core conversation storage
CREATE TABLE conversations (
    id INTEGER PRIMARY KEY,
    session_id TEXT NOT NULL,
    speaker_id TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,

    -- Content
    user_input TEXT NOT NULL,
    assistant_response TEXT,

    -- Classification
    intent TEXT,
    agent_used TEXT,

    -- Vector search
    embedding BLOB,  -- 384-dim float32

    -- Metadata
    processing_time_ms INTEGER,
    cloud_used BOOLEAN DEFAULT FALSE
);

CREATE INDEX idx_conversations_speaker ON conversations(speaker_id);
CREATE INDEX idx_conversations_timestamp ON conversations(timestamp);

-- Semantic facts (extracted knowledge)
CREATE TABLE semantic_facts (
    id INTEGER PRIMARY KEY,
    subject TEXT NOT NULL,  -- "thom", "living_room", etc.
    predicate TEXT NOT NULL,  -- "prefers", "located_in", etc.
    object TEXT NOT NULL,  -- "warm lighting", "first floor", etc.
    confidence REAL DEFAULT 1.0,
    source_conversation_id INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_confirmed DATETIME,

    FOREIGN KEY (source_conversation_id) REFERENCES conversations(id)
);

CREATE UNIQUE INDEX idx_semantic_spo ON semantic_facts(subject, predicate, object);

-- User preferences
CREATE TABLE user_preferences (
    id INTEGER PRIMARY KEY,
    user_id TEXT NOT NULL,
    category TEXT NOT NULL,  -- "lighting", "temperature", "music", etc.
    preference_key TEXT NOT NULL,
    preference_value TEXT NOT NULL,
    context TEXT,  -- "morning", "evening", "working", etc.
    confidence REAL DEFAULT 1.0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(user_id, category, preference_key, context)
);
```

---

## Spatial Awareness

BarnabeeNet maintains a **room graph** that models the physical layout of the home, enabling location-aware intelligence:

### Room Graph Structure

```yaml
spatial_graph:
  living_room:
    type: common
    adjacent: [kitchen, hallway, front_porch]
    devices: [light.living_room, climate.main, speaker.living_room]
    context: entertainment, family_gathering
    
  kitchen:
    type: common
    adjacent: [living_room, dining_room, garage]
    devices: [light.kitchen, sensor.kitchen_motion]
    context: cooking, morning_routine
    
  office:
    type: private
    adjacent: [hallway]
    devices: [light.office, climate.office, speaker.office]
    context: work, focus_time
    
  bedroom.master:
    type: private
    adjacent: [hallway, bathroom.master]
    devices: [light.master_bedroom, climate.master]
    context: sleep, relaxation
    
  garage:
    type: utility
    adjacent: [kitchen, driveway]
    devices: [light.garage, cover.garage_door, sensor.garage_motion]
    context: vehicles, storage
```

### Capabilities

| Feature | Description |
|---------|-------------|
| **Proximity Awareness** | Suggestions account for adjacent rooms (e.g., "Kitchen lights are still on" when user is in living room) |
| **Context Propagation** | Room context (work, relaxation, sleep) influences response tone and proactive behavior |
| **Device Grouping** | Natural language commands resolve to room-local devices ("dim the lights" in office → office lights only) |
| **Path Awareness** | Multi-room commands understand adjacency (e.g., "light the path to the bedroom") |
| **Presence Inference** | Motion sensor data combined with room graph for occupancy estimation |

See *BarnabeeNet_Technical_Architecture.md §Spatial Awareness System* for graph implementation and query algorithms.

---

## Override System

BarnabeeNet supports hierarchical overrides for per-user, per-room, and time-based customization—inspired by SkyrimNet's per-NPC/faction override architecture:

### Override Hierarchy

```
config/overrides/
├── users/
│   ├── thom.yaml           # Per-user preferences
│   ├── elizabeth.yaml
│   └── guest.yaml          # Default guest overrides
├── rooms/
│   ├── office.yaml         # Room-specific behavior
│   └── kids_rooms.yaml     # Privacy-zone overrides
└── schedules/
    ├── work_hours.yaml     # Time-based overrides
    └── quiet_hours.yaml
```

### Override Examples

```yaml
# overrides/users/thom.yaml
user_id: thom
preferences:
  response_style: concise      # vs. detailed
  proactive_level: high        # more suggestions
  temperature_unit: fahrenheit
  preferred_model: claude      # for Interaction Agent

# overrides/rooms/office.yaml
room_id: office
overrides:
  focus_mode:
    enabled: true
    suppress_non_urgent: true
    response_style: minimal
  temperature_preference: 68

# overrides/schedules/quiet_hours.yaml
schedule:
  start: "22:00"
  end: "07:00"
overrides:
  tts_volume: 30
  proactive_audio: false
  ar_brightness: low
```

### Merge Priority

1. **Schedule overrides** (time-sensitive, highest priority)
2. **User overrides** (identity-specific)
3. **Room overrides** (location-specific)
4. **System defaults** (lowest priority)

See *BarnabeeNet_Technical_Architecture.md §Override System* for merge logic and YAML schema.

---

## Voice Pipeline

### Speech-to-Text

**Primary:** Faster-Whisper (CTranslate2 optimized)

```yaml
stt:
  model: distil-whisper/distil-small.en  # Optimized for CPU
  device: cpu  # Beelink handles this
  compute_type: int8  # Quantized for speed
  beam_size: 1  # Greedy decoding for latency
  vad_filter: true  # Skip silence
```

**Latency Targets:**
- Wake word detection: <50ms
- STT processing: <300ms
- Total voice-to-text: <500ms

### Speaker Recognition

**Model:** ECAPA-TDNN via SpeechBrain

```yaml
speaker_recognition:
  model: speechbrain/spkrec-ecapa-voxceleb
  threshold: 0.75  # Below = guest mode
  max_speakers: 8  # Family + common guests
  embedding_dim: 192
```

**Enrollment Flow:**
1. User speaks enrollment phrase (3x different sentences)
2. System extracts ECAPA embeddings
3. Averaged embedding stored in SQLite
4. System extracts embeddings, confirms enrollment
5. Optional: Re-enrollment prompt every 6 months (voice changes)

### Text-to-Speech

**Primary:** Kokoro-82M (local, fastest, good quality)

Kokoro replaced Piper based on 2025 research showing:
- Faster processing (<0.3s on CPU vs Piper's ~0.5s)
- Better voice quality for comparable model size
- Apache 2.0 license (commercial-friendly)

```yaml
tts:
  engine: kokoro
  voice: af_bella  # Natural female voice
  speed: 1.0
  sample_rate: 24000  # Kokoro native rate

  # Available voices:
  # - af_bella (female, default)
  # - af_nicole (female, warm)
  # - am_adam (male, clear)
  # - am_michael (male, deep)
```

### Speech-to-Text

**Architecture:** Dual-path with automatic failover

| Path | Model | Hardware | Latency | When Used |
|------|-------|----------|---------|-----------|
| **Primary** | Parakeet TDT 0.6B v2 | Man-of-war GPU | ~20-40ms | GPU available |
| **Fallback** | Distil-Whisper small.en | Beelink CPU | ~150-300ms | GPU unavailable |

```yaml
stt:
  primary:
    engine: parakeet
    model: nvidia/parakeet-tdt-0.6b-v2
    device: cuda
    host: 192.168.86.100  # Man-of-war
    port: 8001
  
  fallback:
    engine: distil-whisper
    model: distil-whisper/distil-small.en
    device: cpu
    compute_type: int8
    beam_size: 1

  routing:
    health_check_interval_sec: 3
    failover_timeout_ms: 100
```

### Multi-Modal Extensions
- **AR Processing**: Even glasses input processed via SDK; e.g., gaze detection routes to Action Agent.
- **Bluetooth/Alexa/ThinkSmart**: Audio diarization across devices; e.g., headset for private TTS.
- **Amazfit Cheetah Pro**: Inputs via buttons (click to confirm), crown (twist to select choices), motion (shake for dismiss/quick action). Notifications with choices (e.g., "Yes/No" buttons on watch screen) for interactive responses. Gesture detection is polling-based (periodic pulls via Gadgetbridge) due to BLE protocol; optimize intervals for near-real-time (e.g., 500ms poll for low latency).

---

## Privacy Architecture

### Privacy Zones

Privacy is enforced at the **architectural level**, not configurable per-request:

```yaml
privacy_zones:
  children_rooms:
    - bedroom.penelope
    - bedroom.xander
    - bedroom.zachary
    - bedroom.viola
    constraints:
      audio_capture: false  # No microphones in these rooms
      memory_retention: false  # Nothing stored from these areas
      proactive_notifications: false  # No unsolicited audio

  bathrooms:
    - bathroom.master
    - bathroom.kids
    constraints:
      audio_capture: false
      presence_only: true  # Only binary occupied/unoccupied
      memory_retention: false

  common_areas:
    - living_room
    - kitchen
    - office
    - garage
    constraints:
      audio_capture: true
      memory_retention: true
      proactive_notifications: true
```

### Data Flow Controls

```
┌─────────────────────────────────────────────────────────────┐
│                    LOCAL PROCESSING                          │
│  ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐     │
│  │  Multi-  │──►│   STT/   │──►│  Agent  │──►│   TTS/  │     │
│  │  Modal   │   │ Gesture  │   │ Routing │   │   AR/   │     │
│  │  Input  │   │ (local)  │   └────┬────┘   │  Watch  │     │
│  └─────────┘   └─────────┘         │         └─────────┘     │
│                                    │                         │
│                    ┌───────────────┴───────────────┐        │
│                    │                               │        │
│              ┌─────▼─────┐                 ┌───────▼──────┐ │
│              │  Action   │                 │ Interaction  │ │
│              │  Agent    │                 │    Agent     │ │
│              │  (local)  │                 │ (cloud opt.) │ │
│              └───────────┘                 └───────────────┘ │
│                                                   │         │
│                                                   ▼         │
│                                          ┌──────────────┐   │
│                                          │  OpenRouter  │   │
│                                          │  (optional)  │   │
│                                          └──────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### User Permissions

```yaml
users:
  thom:
    role: admin
    permissions:
      - all_devices
      - security_controls
      - configuration
      - memory_access
      - evolver_approval

  elizabeth:
    role: admin
    permissions:
      - all_devices
      - security_controls
      - configuration
      - memory_access

  penelope:
    role: teen
    permissions:
      - bedroom_devices
      - common_area_lights
      - entertainment
    restrictions:
      - no_door_locks
      - no_thermostat_override
      - no_security_cameras

  guest:
    role: guest
    permissions:
      - guest_room_lights
      - common_area_lights
      - entertainment
    restrictions:
      - no_door_locks
      - no_security
      - no_memory_access
```

---

## Implementation Roadmap

### Phase 1: Foundation (Weeks 1-2)
- [x] Home Assistant installation and basic setup
- [x] BarnabeeNet VM created (NixOS on Proxmox)
- [ ] Redis + SQLite infrastructure
- [ ] Basic STT pipeline (Distil-Whisper CPU + Parakeet GPU)
- [ ] Basic TTS pipeline (Kokoro)
- [ ] GPU worker on Man-of-war (WSL2 + CUDA)
- [ ] Health check routing system
- [ ] Simple pattern-matching Meta Agent

### Phase 2: Core Agents (Weeks 3-4)
- [ ] Instant Response Agent (patterns + templates)
- [ ] Action Agent (HA service calls)
- [ ] Working Memory (Redis sessions)
- [ ] Basic speaker recognition

### Phase 3: Intelligence (Weeks 5-6)
- [ ] Interaction Agent (OpenRouter integration)
- [ ] Episodic Memory (conversation storage)
- [ ] Semantic Memory (fact extraction)
- [ ] Memory retrieval with embeddings

### Phase 4: Multi-Modal (Weeks 7-8)
- [ ] AR glasses integration (Even Realities SDK)
- [ ] Wearable integration (Amazfit via Gadgetbridge)
- [ ] ThinkSmart dashboard panels
- [ ] Proactive Agent (polling + notifications)

### Phase 5: Self-Improvement (Weeks 9-10)
- [ ] Evolver Agent (vibe coding proposals)
- [ ] Azure ML benchmarking integration
- [ ] A/B testing framework for prompts
- [ ] Automated Git PR workflow

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| STT accuracy insufficient | Medium | High | Start with constrained vocabulary, expand |
| Speaker ID confusion | Medium | Medium | 0.75 threshold, prompt for name, re-enrollment |
| Memory retrieval latency | Low | Medium | Index optimization, caching |
| HA integration complexity | Medium | High | Start simple, iterate |
| Cloud API costs exceed budget | Low | Low | Smart routing, caching, model tiering (Haiku for simple, Sonnet for complex) |
| Vibe Coding Overreach | Medium | Medium | Scoped boundaries, manual approvals |
| Device Flashing Issues (ThinkSmart) | Medium | Low | Follow XDA/LineageOS guides; fallback to stock if needed |
| Gesture Misinterpretation (Amazfit) | Medium | Medium | Calibrate in dashboard; fallback to phone confirmations |
| Polling Overhead | Low | Low | Optimize poll intervals (e.g., 10-30s) to balance responsiveness and CPU load |
| Polling Latency for Gestures | Medium | Low | Shorten intervals (e.g., 500ms); monitor battery; fallback to phone if needed |

### Mitigation Strategies

**STT Performance:**
- Start with distil-whisper-small (optimized for CPU)
- Monitor latency, upgrade to Gaming PC offload if needed
- Implement streaming STT to reduce perceived latency

**Speaker Recognition:**
- Use 0.75 confidence threshold (below = guest)
- Prompt for name on low confidence
- Re-enrollment UI for voice changes
- Multiple enrollment samples per person

**Cost Control:**
- Rule-based Meta Agent by default
- LLM only for genuinely ambiguous cases
- Local Phi-3.5 for most Action/Query routing
- Cloud Sonnet only for complex conversations

**Self-Improvement:**
- Evolver logs all proposals; require user approval for changes.
- Use Azure credits judiciously for benchmarks.

**Wearable Inputs:**
- Use Gadgetbridge for reliable gesture mapping; test for accuracy in various scenarios.

**Polling for Proactive:**
- Use HA's `homeassistant.poll` service with configurable intervals to avoid overload.

**Polling for Gestures:**
- Optimize Gadgetbridge poll rates for balance (latency vs. battery); add user-configurable intervals in dashboard.

---

## Appendix A: Technology Reference

### Key Libraries

| Purpose | Library | Version | Notes |
|---------|---------|---------|-------|
| STT | faster-whisper | 0.10+ | CTranslate2 optimized |
| Speaker ID | speechbrain | 1.0+ | ECAPA-TDNN model |
| Embeddings | sentence-transformers | 2.2+ | all-MiniLM-L6-v2 |
| TTS | piper | 1.2+ | Local synthesis |
| Vector DB | sqlite-vss | 0.1+ | SQLite vector search |
| Cache | redis | 5.0+ | Short-term memory |
| LLM Routing | openrouter | 1.0+ | Model orchestration |
| Self-Improve | azure-ml | 2.0+ | Benchmarking/evals |
| AR | even-realities-sdk | Latest | Glasses integration |
| Bluetooth | bluez | 5.2+ | Headset audio |
| Wearable | gadgetbridge | 0.80+ | Amazfit gestures/choices (polling-based) |

### API Endpoints (Internal)

```
POST /api/barnabeenet/process
  - Audio processing endpoint
  - Returns: transcription, intent, response, audio_url

POST /api/barnabeenet/enroll
  - Speaker enrollment
  - Body: { name, audio_samples[] }

GET /api/barnabeenet/memory/search
  - Memory search
  - Params: q, speaker_id, limit

GET /api/barnabeenet/stats
  - Usage statistics
  - Returns: daily_commands, costs, latencies

WS /api/barnabeenet/stream
  - Real-time conversation stream
  - For dashboard updates

POST /api/barnabeenet/evolve
  - Trigger evolution
  - Body: { task: "benchmark models" }

POST /api/barnabeenet/process_gesture
  - Handle watch input
  - Body: { gesture_type: "crown_twist_yes", context_id: "abc123" }
```

---

## Appendix B: Related Projects

- **SkyrimNet** — Game AI architecture inspiring multi-agent design
- **Home Assistant Assist** — Native HA voice assistant
- **Wyoming Protocol** — HA voice satellite protocol
- **OpenWakeWord** — Local wake word detection
- **Kokoro** — Fast local TTS (replaced Piper)
- **LineageOS for ThinkSmart** — Custom Android flashing (XDA/GitHub guides)
- **Even Realities SDK** — AR glasses integration
- **Gadgetbridge** — Open-source bridge for Amazfit inputs

---

## Appendix C: Project Documentation Suite

BarnabeeNet includes comprehensive technical documentation created through collaborative AI review (Claude, ChatGPT, Gemini, Grok 4). These documents provide deep-dive specifications for each aspect of the system.

### Core Documentation (7 Documents)

| Document | Purpose | Key Contents |
|----------|---------|--------------|
| **BarnabeeNet_Theory_Research.md** | Academic foundations and design rationale | Multi-agent systems theory, privacy-first architecture rationale, game AI inspiration (SkyrimNet), academic references, cognitive architecture comparisons |
| **BarnabeeNet_Hardware_Specifications.md** | Complete hardware requirements and configurations | Beelink EQi12 detailed specs, RTX 4070 Ti constraints, input device matrix (AR glasses, Amazfit, ThinkSmart), network architecture, power/thermal analysis, bill of materials, upgrade paths |
| **BarnabeeNet_Features_UseCases.md** | Feature catalog and practical scenarios | 34 detailed use cases across 7 categories, feature complexity ratings, interaction flow examples, privacy zone implications, prioritization framework |
| **BarnabeeNet_Technical_Architecture.md** | Deep technical specifications | Agent system design, message bus architecture, voice pipeline, speaker recognition system, memory architecture with hybrid retrieval, spatial awareness system, override system, database schemas, API contracts, security architecture, prompt engineering integration |
| **BarnabeeNet_Prompt_Engineering.md** | Prompt template design and best practices | Template structure, decorator system, per-agent prompts, variable injection patterns, A/B testing framework, hot-reload configuration |
| **BarnabeeNet_Implementation_Guide.md** | Phase-by-phase build instructions | Prerequisites and environment setup, 5-phase implementation roadmap, technology selection rationale, testing strategies, deployment procedures, checkpoint validation |
| **BarnabeeNet_Operations_Runbook.md** | Day-to-day operations and maintenance | Monitoring and alerting, cost tracking, performance benchmarks, troubleshooting guides, backup/recovery, upgrade procedures, incident response |

### Documentation Structure

```
docs/
├── BarnabeeNet_Theory_Research.md       # WHY: Design philosophy & research
├── BarnabeeNet_Hardware_Specifications.md # WHAT: Physical requirements
├── BarnabeeNet_Features_UseCases.md     # WHAT: Capabilities & scenarios
├── BarnabeeNet_Technical_Architecture.md # HOW: System design
├── BarnabeeNet_Prompt_Engineering.md    # HOW: Prompt templates & patterns
├── BarnabeeNet_Implementation_Guide.md  # HOW: Build instructions
└── BarnabeeNet_Operations_Runbook.md    # HOW: Run & maintain
```

### Recommended Additional Documentation

As the project evolves, consider adding:
- `BarnabeeNet_Testing_Guide.md` — Unit, integration, and evaluation testing
- `BarnabeeNet_Security_Audit.md` — Detailed security review
- `BarnabeeNet_Troubleshooting.md` — Common issues and solutions

### AI Reviewer Consensus

The documentation suite was reviewed by multiple AI systems (Claude, ChatGPT, Gemini, Grok 4). Key consensus recommendations:

1. **Policy Engine as First-Class Component** — Every action should pass through a central gate with explicit ALLOW/DENY/REQUIRE_CONFIRMATION rules
2. **Message Bus Architecture** — Add Redis Streams or MQTT for agent-to-agent communication and event replay
3. **Undo/Rollback System** — Implement reversibility for all device-affecting actions
4. **Fact Decay in Memory** — Semantic facts should decay over time if not reconfirmed
5. **Multi-Factor for Sensitive Actions** — Combine voice + presence + watch confirmation for security-critical operations
6. **Event-Driven over Polling** — Migrate from polling to event subscriptions where possible

### Documentation Maintenance

- Documents are versioned alongside code releases
- Major architecture changes trigger documentation updates
- Community contributions welcome via pull requests
- AI-assisted review recommended for significant changes

---

## Document History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-08 | Initial architecture |
| 2.0 | 2026-01 | Complete rewrite with research integration (Claude-generated base) |
| 2.1 | 2026-01-15 | Enhanced with multi-modal inputs, self-improvement (Evolver Agent, vibe coding, Azure/Copilot), OpenRouter (Grok 4) |
| 2.2 | 2026-01-15 | Added Amazfit Cheetah Pro for wearable inputs (gestures, choices); updated pipeline, agents, dashboard, roadmap (Grok 4) |
| 2.3 | 2026-01-15 | Updated Proactive Agent to polling-based (periodic checks) per user feedback; minor refinements to risks and roadmap (Grok 4) |
| 2.4 | 2026-01-15 | Clarified polling for Amazfit gestures (pull-based, not trigger); added efficiency notes to risks/mitigations (Grok 4) |
| 3.0 | 2026-01-15 | Added Proxy Mode for Teams calls (voice cloning, summarization); incorporated new use cases/triggers; expanded agents/pipeline for superhuman features (Grok 4) |
| 3.1 | 2026-01-16 | Added comprehensive documentation suite (Appendix C); documented 6 core technical documents; incorporated AI reviewer recommendations; updated executive summary (Claude) |
| 3.2 | 2026-01-17 | Added prompt engineering system reference, spatial awareness section, override system section; enhanced Meta Agent with mood evaluation and memory query generation; documented first-person memory perspective and hybrid retrieval algorithm; updated Appendix C documentation suite to 7 documents (Claude) |

---

*For detailed specifications, see the documentation suite in `docs/`. For theoretical foundations, see BarnabeeNet_Theory_Research.md.*
