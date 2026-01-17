# BarnabeeNet Architecture: A Privacy-First, Multi-Agent AI Framework for Superhuman Smart Home Automation

**Version:** 3.1  
**Last Updated:** January 16, 2026  
**Author:** Thom Fife (with contributions from Grok 4, Claude, ChatGPT, and Gemini)  
**Status:** Infrastructure Foundation Phase (Enhanced with Multi-Modal Integrations, Self-Improvement, Wearables, and New Modes like Proxy)

---

## Executive Summary

BarnabeeNet is a privacy-first, locally-processed smart home AI assistant designed to provide Alexa/Google-level responsiveness (<500ms) while maintaining complete data sovereignty. Built on Home Assistant as the automation backbone, BarnabeeNet implements a multi-agent architecture inspired by game AI systems (SkyrimNet) to achieve intelligent routing, personalized responses, and proactive home management. This version incorporates expansions for multi-modal inputs (AR glasses, Bluetooth headsets, Alexa, Lenovo ThinkSmart Views, and Amazfit Cheetah Pro for gesture inputs), self-improvement via "vibe coding" (AI-assisted code/prompt optimization using GitHub Copilot and Azure credits), LLM orchestration via OpenRouter, and new modes like Proxy (for call insertion/summarization).

Key enhancements from version 2.4:
- **Proxy Mode**: Barnabee joins Teams calls as a bot, proxies with voice cloning during absences, and summarizes missed content.
- **Additional Use Cases**: Wellness coaching, habit tracking, idea incubation, family brainstorming, eco-advising, guest hospitality, relationship nurturing, memory replay, ethical auditing, dream interpretation—with discreet triggers (e.g., haptics, gestures).
- **Polling Optimizations**: Refined for gestures (e.g., 500ms intervals for near-real-time); added user-configurable rates in dashboard.
- **Comprehensive Documentation Suite**: Six detailed technical documents covering theory, hardware, features, architecture, implementation, and operations.

The system remains focused on speed (edge processing on Beelink/Proxmox), user feel (human-like empathy with speaker diarization and gesture inputs), and privacy (local-first, no raw data to cloud).

### Core Design Principles

1. **Privacy by Architecture** — Voice and gesture data never leaves the local network unless explicitly requested.
2. **Latency-Obsessed** — Target <500ms end-to-end for common commands, including watch inputs.
3. **Family-Aware** — Speaker recognition and gesture personalization enable permission-based control.
4. **Graceful Degradation** — System remains functional even when cloud services are unavailable.
5. **Cost-Conscious** — Intelligent routing minimizes expensive LLM calls.
6. **Self-Improving** — Barnabee evolves its own prompts, models, and code within scoped boundaries using vibe coding.
7. **Multi-Modal** — Supports AR, voice, touch, and wearable inputs (buttons, twists, motion, choices) for superhuman user experiences.

---

## Hardware Architecture

### Production Server: Beelink Mini PC EQi12 (Always-On)

| Component | Specification | Role |
|-----------|--------------|------|
| CPU | Intel Core 1220P (10C/12T, Max 4.4GHz) | Primary inference, routing, HA core, fast STT/TTS |
| RAM | 24GB LPDDR5 5200MHz | Model loading, state management, Redis caching |
| Storage | 500GB PCIe 4.0 SSD | OS, HA, databases, model cache |
| Network | Dual LAN / WiFi 6 / BT 5.2 | Device communication, Bluetooth headset pairing |
| OS | Proxmox VE | VM isolation for HA, services |
| Power | ~15-25W typical | 24/7 operation optimized |

**Beelink Responsibilities:**
- Home Assistant core + BarnabeeNet custom integration
- Fast routing (Meta Agent, pattern matching)
- Real-time STT (Faster-Whisper small/distil models)
- Local TTS (Piper)
- SQLite/Redis state management
- Short-term conversation memory
- All instant-response handlers
- Bluetooth headset audio processing
- Alexa/ThinkSmart coordination via local network
- Processing wearable inputs (e.g., from Amazfit via Bluetooth/Gadgetbridge polling)
- Polling for proactive monitoring (periodic HA state checks)
- Proxy mode audio processing (e.g., Teams streams)

### Compute Server: Gaming PC (On-Demand Heavy Lifting)

| Component | Specification | Role |
|-----------|--------------|------|
| CPU | Intel Core i9-14900KF | Complex CPU inference |
| GPU | NVIDIA RTX 4070 Ti (12GB VRAM) | Local LLM inference, embeddings |
| RAM | 128GB DDR5 | Large model loading |
| Storage | ~11TB NVMe (Gen4/Gen5) | Model storage, datasets |
| Network | Gigabit Ethernet | API access from Beelink |

**Gaming PC Responsibilities:**
- Heavy LLM inference (local Llama, Mistral, etc.)
- Speaker embedding training and enrollment
- Memory consolidation batch jobs
- Complex multi-turn conversations (when local preferred over cloud)
- Model fine-tuning experiments
- Development and testing environment
- Vibe coding sessions (Copilot integration)
- Azure-offloaded benchmarks (via API)

### Input/Output Devices
- **Even Realities Glasses**: AR input/output for gestures, HUD overlays (e.g., device status visuals), integrated via SDK.
- **Bluetooth Headset**: Private audio input/output, paired via BlueZ for low-latency personal interactions.
- **Alexa Devices**: Voice I/O with multi-room audio, integrated via Amazon SDK.
- **Lenovo ThinkSmart Views**: Flashed with LineageOS (rooted Android), used as touch dashboards and voice hubs.
- **Amazfit Cheetah Pro**: Wearable input for silent gestures (motion, button clicks, crown twists) and interactive notifications with choices. Integrated via Zepp OS SDK or Gadgetbridge for custom apps handling inputs like twisting to select "Yes/No" in Barnabee queries or toggling modes (polling-based detection).

---

## Network Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Home Network                              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────┐  │
│  │   Beelink   │◄──►│  Gaming PC  │    │   Smart Devices     │  │
│  │  (Always On)│    │ (On-Demand) │    │  (Zigbee/Z-Wave/    │  │
│  │             │    │             │    │   WiFi/Matter)      │  │
│  └──────┬──────┘    └─────────────┘    └──────────┬──────────┘  │
│         │                                          │             │
│         ▼                                          ▼             │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │              Home Assistant (Proxmox VM)                     ││
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  ││
│  │  │ BarnabeeNet │  │   Assist    │  │   Device Integrations│  ││
│  │  │ Integration │  │  Pipeline   │  │   (Zigbee2MQTT, etc.)│  ││
│  │  └─────────────┘  └─────────────┘  └─────────────────────┘  ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼ (Optional, Privacy-Controlled)
                    ┌─────────────────┐
                    │   Cloud APIs    │
                    │ (Claude, GPT,   │
                    │  Gemini, Azure, │
                    │  OpenRouter)    │
                    └─────────────────┘
```

- **Multi-Modal Flows**: AR glasses connect via WiFi/Bluetooth to Beelink for real-time overlays; Alexa/ThinkSmart route audio to HA; Amazfit Cheetah Pro connects via Bluetooth for gesture inputs.
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
- `conversation` — Multi-turn dialogue, complex reasoning
- `memory` — Requires personal context retrieval
- `emergency` — Safety-critical (911, alerts)
- `proactive` — Background-triggered notifications
- `evolve` — Self-improvement requests (e.g., "optimize prompts")
- `gesture` — Wearable inputs like motion or choices

#### 2. Instant Response Agent

**Purpose:** Handle predictable requests with zero LLM latency, including simple gesture mappings.

| Attribute | Value |
|-----------|-------|
| Latency Target | <5ms |
| Implementation | Pattern matching + lookup tables |
| Cost per call | $0 |

**Response Types:**
```yaml
time_queries:
  patterns: ["what time", "current time", "time is it"]
  handler: datetime.now().strftime()

date_queries:
  patterns: ["what day", "today's date", "what date"]
  handler: datetime.now().strftime()

greetings:
  patterns: ["hello", "hey barnabee", "good morning"]
  handler: contextual_greeting(time_of_day, user_name)

math_expressions:
  patterns: [regex: r"what is \d+[\+\-\*\/]\d+"]
  handler: safe_eval()

status_queries:
  patterns: ["how are you", "you okay"]
  handler: random_choice(status_responses)

gesture_actions:  # New
  patterns: ["crown_twist_yes", "button_click_confirm"]
  handler: process_choice("yes/confirm")
```

#### 3. Action Agent

**Purpose:** Execute device control and home automation commands, triggered by watch inputs.

| Attribute | Value |
|-----------|-------|
| Latency Target | <100ms total (routing + execution) |
| Model (Cloud) | GPT-4.1-nano / Gemini Flash via OpenRouter |
| Model (Local) | Phi-3.5 with function calling |
| Cost per call | ~$0.0005 |

**Capabilities:**
- Structured output for HA service calls
- Multi-device commands ("turn off all the lights")
- Conditional execution ("if the door is locked, unlock it")
- Scene activation
- Routine triggers
- Gesture-triggered actions (e.g., motion shake to toggle lights)
- Choice-based responses (e.g., notification "Lock door? Yes/No" via watch buttons)

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

wearable_choices:  # New
  - Send notifications with options (e.g., "Adjust temp? Yes/No" via watch buttons)
```

**Family-Safe Constraints:**
- NO automatic door locking (safety hazard)
- NO proactive audio in children's rooms
- Notification-only for security events (human confirms action)
- Rate limiting on non-critical notifications

#### 7. Evolver Agent (Self-Improvement)

**Purpose:** Orchestrate system evolution via vibe coding, benchmarking, and optimizations.

| Attribute | Value |
|-----------|-------|
| Latency Target | N/A (background/scheduled) |
| Model | Claude/GPT via Copilot/Azure |
| Trigger | Manual ("optimize Barnabee") or scheduled (weekly) |

**Capabilities:**
- **Prompt Refinement**: Generate/A-B test prompt variants using Copilot.
- **Model Benchmarking**: Use Azure ML to eval LLMs via OpenRouter (speed, accuracy, cost).
- **Code Enhancements**: Propose PRs for agent code, integrations (e.g., watch gesture mappings).
- **Scope Limits**: Only internal changes; no external APIs without approval.
- **Resources**: Azure credits for evals; Copilot for code gen in VS Code remote.

**Workflow Example:**
1. Monitor metrics (e.g., latency > threshold).
2. Vibe code: "Improve Meta Agent routing for 20% faster classification."
3. Benchmark on Azure: Compare Phi-3.5 vs. new variant.
4. Apply via hot-reload or Git PR.

---

## Voice and Multi-Modal Processing Pipeline

### End-to-End Latency Budget

| Stage | Target | Implementation |
|-------|--------|----------------|
| Wake word detection | 0ms (always listening) | OpenWakeWord (local) |
| Audio capture | ~100ms | Streaming buffer (Bluetooth/Alexa/ThinkSmart) |
| Speech-to-Text | <150ms | Faster-Whisper distil-small |
| Speaker ID | ~20ms | ECAPA-TDNN embeddings |
| Gesture Input | <50ms | Amazfit SDK/Gadgetbridge for motion/button events |
| Meta Agent routing | <20ms | Rule-based + LLM fallback |
| Specialized agent | <200ms (action) / <2s (conversation) | Varies |
| Text-to-Speech | <100ms | Piper (local) |
| AR Overlay (if applicable) | <50ms | Even Realities SDK |
| Watch Notification/Choice | <100ms | Push via Zepp/Gadgetbridge |
| **Total (action)** | **<500ms** | |
| **Total (conversation)** | **<2.5s** | |

### Speech-to-Text Options

Based on 2024-2025 benchmarks for edge deployment:

| Model | WER (clean) | Latency | VRAM | Best For |
|-------|-------------|---------|------|----------|
| Faster-Whisper distil-small | ~8% | ~150ms | ~1GB | Default choice |
| Faster-Whisper small | ~6% | ~200ms | ~2GB | Better accuracy |
| Whisper Large-v3 Turbo | ~3% | ~300ms | ~6GB | When accuracy critical |
| Parakeet TDT 0.6B | ~12% | ~50ms | ~1GB | Lowest latency |
| Moonshine Tiny | ~15% | ~30ms | ~200MB | Edge/mobile |

**Recommended Configuration:**
```yaml
stt:
  primary: faster-whisper
  model: distil-whisper/distil-small.en
  device: cpu  # Beelink handles this fine
  compute_type: int8
  beam_size: 1  # Speed over accuracy for commands

  fallback: whisper-large-v3-turbo  # Gaming PC for complex audio
```

### Speaker Recognition

**Purpose:** Identify who is speaking to enable:
- Personalized responses ("Your calendar shows...")
- Permission-based control (kids can't unlock doors)
- Location context ("turn on the lights" = room speaker is in)
- Privacy (your calendar vs guest queries)

**Technology Selection:**

| Model | EER | Embedding Size | Latency | Notes |
|-------|-----|----------------|---------|-------|
| ECAPA-TDNN | 0.86% | 192-dim | ~20ms | Best accuracy, SpeechBrain |
| Resemblyzer | ~2% | 256-dim | ~15ms | Easier setup |
| TitaNet-Large | ~1% | 192-dim | ~25ms | NVIDIA NeMo |

**Recommended:** SpeechBrain ECAPA-TDNN (pre-trained on VoxCeleb)

```python
# Speaker verification flow
from speechbrain.inference import SpeakerRecognition

verifier = SpeakerRecognition.from_hparams(
    source="speechbrain/spkrec-ecapa-voxceleb"
)

# Enrollment: Store embeddings for each family member
embeddings = {
    "thom": verifier.encode_batch(enrollment_audio_thom),
    "elizabeth": verifier.encode_batch(enrollment_audio_elizabeth),
    "penelope": verifier.encode_batch(enrollment_audio_penelope),
    # ... etc
}

# Runtime: Compare incoming audio
def identify_speaker(audio):
    query_embedding = verifier.encode_batch(audio)
    scores = {
        name: cosine_similarity(query_embedding, emb)
        for name, emb in embeddings.items()
    }
    best_match = max(scores, key=scores.get)
    confidence = scores[best_match]

    if confidence < 0.75:
        return "guest", confidence
    return best_match, confidence
```

**Enrollment UX (Dashboard-Based):**
1. Open BarnabeeNet dashboard on phone/web
2. Select "Add Family Member"
3. Record 5 varied phrases:
   - "Hey Barnabee, what's the weather today"
   - "Turn on the living room lights"
   - "What time is it"
   - "Play some music"
   - "Good morning, how are you"
4. System extracts embeddings, confirms enrollment
5. Optional: Re-enrollment prompt every 6 months (voice changes)

### Text-to-Speech

**Primary:** Piper (local, fast, good quality)

```yaml
tts:
  engine: piper
  voice: en_US-lessac-medium  # Natural, good prosody
  sample_rate: 22050

  # Alternative voices available:
  # - en_US-amy-medium (female, clear)
  # - en_GB-alan-medium (British male)
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
│              └───────────┘                 └──────────────┘ │
│                                                   │         │
└───────────────────────────────────────────────────┼─────────┘
                                                    │
                     ┌──────────────────────────────┴──────┐
                     │         CLOUD BOUNDARY              │
                     │  (Only crosses when necessary)      │
                     │                                     │
                     │  What crosses:                      │
                     │  - Transcribed text (not audio)     │
                     │  - Anonymized context               │
                     │  - No PII unless user-initiated     │
                     │                                     │
                     │  What never crosses:                │
                     │  - Raw audio                        │
                     │  - Speaker embeddings               │
                     │  - Location data                    │
                     │  - Children's interactions          │
                     │  - Gesture raw data                 │
                     └─────────────────────────────────────┘
```

### Audit Trail

Every interaction is logged locally for debugging and transparency:

```sql
CREATE TABLE audit_log (
    id INTEGER PRIMARY KEY,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    session_id TEXT,
    speaker_id TEXT,
    speaker_confidence REAL,

    -- Request
    audio_hash TEXT,  # Hash only, not audio
    transcription TEXT,
    detected_intent TEXT,

    -- Routing
    meta_agent_decision TEXT,
    agent_invoked TEXT,

    -- Processing
    processing_time_ms INTEGER,
    cloud_api_used BOOLEAN,
    cloud_api_name TEXT,

    -- Response
    response_text TEXT,
    action_executed TEXT,

    -- Privacy
    privacy_zone TEXT,
    pii_detected BOOLEAN,

    -- Wearable Inputs
    gesture_type TEXT  # e.g., "crown_twist", "motion_shake"
);
```

---

## Memory System

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     MEMORY SYSTEM                            │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              WORKING MEMORY (Redis)                   │   │
│  │  TTL: 10 minutes | Scope: Current conversation       │   │
│  │                                                       │   │
│  │  session:{user_id}:context → Recent exchanges        │   │
│  │  session:{user_id}:intent → Conversation intent      │   │
│  │  session:{user_id}:entities → Extracted entities     │   │
│  └──────────────────────────────────────────────────────┘   │
│                           │                                  │
│                           ▼ (Consolidation)                  │
│  ┌──────────────────────────────────────────────────────┐   │
│  │             EPISODIC MEMORY (SQLite)                  │   │
│  │  Retention: 30 days | Scope: Specific interactions    │   │
│  │                                                       │   │
│  │  - Timestamped conversation records                   │   │
│  │  - Vector embeddings for semantic search              │   │
│  │  - Linked to speaker_id                               │   │
│  └──────────────────────────────────────────────────────┘   │
│                           │                                  │
│                           ▼ (Extraction)                     │
│  ┌──────────────────────────────────────────────────────┐   │
│  │             SEMANTIC MEMORY (SQLite)                  │   │
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

    UNIQUE(user_id, category, preference_key, context)
);

-- Event log for pattern detection
CREATE TABLE event_log (
    id INTEGER PRIMARY KEY,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    event_type TEXT NOT NULL,
    entity_id TEXT,
    old_state TEXT,
    new_state TEXT,
    triggered_by TEXT,  -- "user", "automation", "schedule"
    user_id TEXT
);

CREATE INDEX idx_events_type_time ON event_log(event_type, timestamp);
```

### Memory Consolidation Pipeline

Runs nightly (or on-demand) to extract patterns:

```python
async def consolidate_memories():
    """
    Batch process recent conversations to:
    1. Extract semantic facts
    2. Detect behavioral patterns
    3. Suggest automations
    4. Archive old episodic memories
    """

    # 1. Extract facts from recent conversations
    recent = await db.fetch("""
        SELECT * FROM conversations
        WHERE timestamp > datetime('now', '-1 day')
        AND processed_for_semantics = FALSE
    """)

    for conv in recent:
        facts = await llm.extract_facts(conv.user_input, conv.assistant_response)
        for fact in facts:
            await db.upsert_semantic_fact(fact)
        await db.mark_processed(conv.id)

    # 2. Detect patterns
    patterns = await detect_behavioral_patterns(
        lookback_days=14,
        min_occurrences=3
    )

    for pattern in patterns:
        if pattern.confidence > 0.8:
            await suggest_automation(pattern)

    # 3. Archive old episodic memories
    await db.execute("""
        DELETE FROM conversations
        WHERE timestamp < datetime('now', '-30 day')
        AND important = FALSE
    """)
```

---

## Home Assistant Integration

### Custom Component Structure

```
custom_components/
└── barnabeenet/
    ├── __init__.py           # Integration setup
    ├── manifest.json         # HA component metadata
    ├── config_flow.py        # UI configuration
    ├── const.py              # Constants
    ├── coordinator.py        # Data update coordinator
    │
    ├── agents/               # Multi-agent system
    │   ├── __init__.py
    │   ├── meta_agent.py     # Router/classifier
    │   ├── instant_agent.py  # Pattern-matched responses
    │   ├── action_agent.py   # Device control
    │   ├── interaction_agent.py  # Complex conversations
    │   ├── memory_agent.py   # Memory operations
    │   ├── proactive_agent.py    # Background monitoring
    │   └── evolver_agent.py      # Self-improvement
    │
    ├── voice/                # Voice processing
    │   ├── __init__.py
    │   ├── stt.py            # Speech-to-text wrapper
    │   ├── tts.py            # Text-to-speech wrapper
    │   ├── speaker_id.py     # Speaker recognition
    │   └── wake_word.py      # Wake word detection
    │
    ├── multimodal/           # AR/Bluetooth/Alexa/ThinkSmart/Wearables
    │   ├── __init__.py
    │   ├── ar_glasses.py     # Even Realities SDK
    │   ├── bluetooth.py      # Headset integration
    │   ├── alexa.py          # Amazon SDK
    │   ├── thinksmart.py     # LineageOS app hooks
    │   └── amazfit.py        # Cheetah Pro SDK/Gadgetbridge for gestures/choices
    │
    ├── memory/               # Memory system
    │   ├── __init__.py
    │   ├── working.py        # Redis short-term
    │   ├── episodic.py       # SQLite conversations
    │   ├── semantic.py       # Extracted facts
    │   └── consolidation.py  # Batch processing
    │
    ├── services/             # HA service definitions
    │   ├── __init__.py
    │   └── services.yaml
    │
    └── frontend/             # Dashboard panel
        ├── panel.js
        └── styles.css
```

### Manifest.json

```json
{
  "domain": "barnabeenet",
  "name": "BarnabeeNet Voice Assistant",
  "version": "3.0.0",
  "documentation": "https://github.com/thomfife/barnabeenet",
  "dependencies": ["conversation", "intent"],
  "codeowners": ["@thomfife"],
  "requirements": [
    "faster-whisper>=0.10.0",
    "speechbrain>=1.0.0",
    "redis>=5.0.0",
    "sentence-transformers>=2.2.0",
    "openrouter>=1.0.0",
    "azure-ml>=2.0.0",
    "gadgetbridge>=0.80.0"  # For Amazfit integration
  ],
  "iot_class": "local_push",
  "config_flow": true
}
```

### Service Definitions

```yaml
# services.yaml
process_voice:
  name: Process Voice Command
  description: Process a voice command through BarnabeeNet
  fields:
    audio_data:
      name: Audio Data
      description: Base64-encoded audio
      required: true
      selector:
        text:
    speaker_hint:
      name: Speaker Hint
      description: Optional speaker ID hint
      required: false
      selector:
        text:

enroll_speaker:
  name: Enroll Speaker
  description: Enroll a new speaker for recognition
  fields:
    name:
      name: Speaker Name
      required: true
      selector:
        text:
    audio_samples:
      name: Audio Samples
      description: List of base64-encoded audio samples
      required: true
      selector:
        object:

query_memory:
  name: Query Memory
  description: Search BarnabeeNet's memory
  fields:
    query:
      name: Query
      required: true
      selector:
        text:
    speaker_id:
      name: Speaker ID
      required: false
      selector:
        text:

evolve_system:
  name: Evolve System
  description: Trigger self-improvement (e.g., optimize prompts)
  fields:
    task:
      name: Task
      description: e.g., "benchmark models"
      required: true
      selector:
        text:

process_gesture:  # New
  name: Process Gesture Input
  description: Handle watch gestures (e.g., twist for choice)
  fields:
    gesture_type:
      name: Gesture Type
      description: e.g., "crown_twist_yes"
      required: true
      selector:
        text:
    context_id:
      name: Context ID
      description: Associated notification/session ID
      required: false
      selector:
        text:
```

---

## Dashboard & Management UI

### Features

The BarnabeeNet dashboard provides:

1. **Real-time Monitoring**
   - Active conversations display
   - Agent routing visualization
   - Latency metrics

2. **Family Management**
   - Speaker enrollment UI
   - Permission configuration
   - Per-user preferences

3. **Memory Browser**
   - Search conversation history
   - View extracted facts
   - Edit/delete memories

4. **System Configuration**
   - Agent model selection
   - Privacy zone configuration
   - Cost tracking and limits

5. **Debug Tools**
   - Audit log viewer
   - Agent decision inspector
   - Performance profiling

6. **Self-Improvement Panel**
   - View evolver proposals/PRs
   - Benchmark results from Azure
   - Approve code changes

7. **Multi-Modal Status**
   - AR glasses connection
   - Device health (Alexa/ThinkSmart)
   - Wearable integration (Amazfit status, gesture mappings)

### Implementation Options

**Option A: HA Custom Panel (Recommended)**
- Native integration with HA
- Single sign-on
- Uses HA's WebSocket for real-time updates

**Option B: Standalone React App**
- More flexibility for complex UI
- Requires separate auth
- Better for mobile-first design

### Dashboard Wireframe

```
┌─────────────────────────────────────────────────────────────┐
│  🐝 BarnabeeNet                    [Thom ▼] [Settings ⚙]   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────┐  ┌─────────────────────────────────┐  │
│  │  QUICK STATS    │  │  RECENT CONVERSATIONS           │  │
│  │                 │  │                                  │  │
│  │  Today: 47 cmds │  │  🕐 2m ago - Thom               │  │
│  │  Avg latency:   │  │  "What's the temperature?"      │  │
│  │    Action: 89ms │  │  → 72°F in living room          │  │
│  │    Query: 1.2s  │  │                                  │  │
│  │                 │  │  🕐 15m ago - Elizabeth          │  │
│  │  Cloud calls: 12│  │  "Turn off the garage lights"   │  │
│  │  Est. cost: $0.02│  │  → Done ✓                       │  │
│  └─────────────────┘  │                                  │  │
│                       │  🕐 1h ago - Penelope            │  │
│  ┌─────────────────┐  │  "Tell me a joke"               │  │
│  │  FAMILY STATUS  │  │  → Why did the scarecrow...     │  │
│  │                 │  └─────────────────────────────────┘  │
│  │  👤 Thom        │                                       │
│  │     Office      │  ┌─────────────────────────────────┐  │
│  │     Last: 2m    │  │  MEMORY INSIGHTS               │  │
│  │                 │  │                                  │  │
│  │  👤 Elizabeth   │  │  📊 Learned this week:          │  │
│  │     Kitchen     │  │  • Thom prefers 68°F when working│  │
│  │     Last: 15m   │  │  • Lights off at 11pm routine   │  │
│  │                 │  │  • Elizabeth's music preference │  │
│  │  👤 Kids (4)    │  │                                  │  │
│  │     Various     │  │  💡 Suggested automation:        │  │
│  └─────────────────┘  │  "Auto-dim lights at sunset?"   │  │
│                       │  [Create] [Dismiss]              │  │
│                       └─────────────────────────────────┘  │
│                                                             │
│  ┌──────────────────────────────┐                           │
│  │  EVOLVER STATUS             │                           │
│  │                             │                           │
│  │  Last Optimization: 1d ago │                           │
│  │  - Prompt improved by 15%   │                           │
│  │  - Model benchmark: Gemini  │                           │
│  │    Flash fastest            │                           │
│  │  [Run Benchmark] [View PRs] │                           │
│  └──────────────────────────────┘                           │
│                                                             │
│  ┌──────────────────────────────┐                           │
│  │  WEARABLE STATUS            │                           │
│  │                             │                           │
│  │  Amazfit Connected: Yes     │                           │
│  │  Last Gesture: Twist (Yes)  │                           │
│  │  Battery: 85%               │                           │
│  │  [Map Gestures] [Test Input]│                           │
│  └──────────────────────────────┘                           │
└─────────────────────────────────────────────────────────────┘
```

---

## Cost Management

### Pricing Model (January 2026)

| Service | Price | Usage Pattern |
|---------|-------|---------------|
| Claude Haiku (routing) | $0.25/1M input | ~$0.0001/call |
| Claude Sonnet (complex) | $3/1M input | ~$0.003/call |
| GPT-4.1-nano (action) | $0.10/1M input | ~$0.0001/call |
| Gemini Flash (fallback) | $0.075/1M input | ~$0.00008/call |
| Deepgram STT | $0.0043/min | Cloud STT backup |
| Azure ML Evals | ~$0.01/run (credits) | Benchmarking |

### Cost Control Strategy

```yaml
cost_controls:
  daily_limit: $1.00

  routing_preference:
    - instant_response  # $0
    - local_llm         # $0
    - cloud_flash       # ~$0.0001
    - cloud_sonnet      # ~$0.003

  degradation_levels:
    green:  # < 50% of daily limit
      all_features: enabled

    yellow:  # 50-80% of daily limit
      interaction_agent: local_only
      cloud_backup: disabled

    red:  # > 80% of daily limit
      complex_queries: "I need to conserve resources. Can you ask a simpler question?"
      action_only: true
```

### Estimated Monthly Costs

**Typical Family Usage (4 adults, 4 kids):**

| Category | Daily Commands | Cost/Command | Daily Cost |
|----------|---------------|--------------|------------|
| Instant responses | 40 | $0 | $0 |
| Action commands | 30 | $0.0001 | $0.003 |
| Simple queries | 15 | $0.001 | $0.015 |
| Complex conversations | 5 | $0.005 | $0.025 |
| Evolutions/Benchmarks | 1 | $0.01 | $0.01 |
| Gesture Inputs | 10 | $0 | $0 |
| **Total** | **101** | | **~$0.053/day** |

**Monthly estimate: ~$1.60** (primarily local; Azure credits cover evals)

---

## Implementation Roadmap

### Phase 1: Infrastructure Foundation (Weeks 1-4)

- [X] HA custom integration skeleton
- [X] SQLite schema + migrations
- [X] Redis configuration
- [ ] Basic STT pipeline (Faster-Whisper)
- [ ] Basic TTS pipeline (Piper)
- [ ] Meta Agent (rule-based routing)
- [ ] Instant Response Agent
- [ ] Action Agent (basic HA service calls)
- [ ] Configuration system (YAML-based)
- [ ] Dashboard panel skeleton

**Deliverable:** Working voice control for basic home commands

### Phase 2: Speaker Recognition & Personalization (Weeks 5-8)

- [ ] ECAPA-TDNN integration
- [ ] Enrollment pipeline
- [ ] Dashboard enrollment UI
- [ ] Permission system
- [ ] Per-user preferences
- [ ] Context injection (location, time)
- [ ] Basic memory retrieval
- [ ] Multi-modal inputs (Bluetooth/Alexa/ThinkSmart flashing)

**Deliverable:** Family members identified, personalized responses

### Phase 3: Memory & Intelligence (Weeks 9-12)

- [ ] Episodic memory storage
- [ ] Semantic fact extraction
- [ ] Vector embeddings for search
- [ ] Memory consolidation pipeline
- [ ] Pattern detection
- [ ] Automation suggestions
- [ ] Memory browser UI
- [ ] AR glasses integration

**Deliverable:** System learns and remembers

### Phase 4: Proactive & Self-Improving Intelligence (Weeks 13-16)

- [ ] Polling monitoring system
- [ ] Proactive Agent rules
- [ ] Notification delivery
- [ ] Rate limiting
- [ ] User feedback loop
- [ ] Family-safe constraints
- [ ] Evolver Agent with vibe coding/Copilot/Azure
- [ ] Amazfit Cheetah Pro integration (gestures, choices via Gadgetbridge/Zepp SDK)

**Deliverable:** Contextually aware proactive assistance, self-evolution, and wearable inputs

### Phase 5: Polish & Optimization (Weeks 17-20)

- [ ] Latency optimization
- [ ] Cost optimization
- [ ] Error handling hardening
- [ ] Fallback chains
- [ ] Documentation
- [ ] Testing suite
- [ ] Performance monitoring

**Deliverable:** Production-ready BarnabeeNet

---

## Risk Assessment

### Technical Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Beelink CPU insufficient for STT | Medium | High | Offload to Gaming PC, use smaller models |
| Speaker recognition unreliable in noise | High | Medium | Fallback to "guest" permissions, require re-speak |
| Memory retrieval latency | Low | Medium | Index optimization, caching |
| HA integration complexity | Medium | High | Start simple, iterate |
| Cloud API costs exceed budget | Low | Low | Aggressive local-first routing |
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
- **Piper** — Fast local TTS
- **LineageOS for ThinkSmart** — Custom Android flashing (XDA/GitHub guides)
- **Even Realities SDK** — AR glasses integration
- **Gadgetbridge** — Open-source bridge for Amazfit inputs

---

## Appendix C: Project Documentation Suite

BarnabeeNet includes comprehensive technical documentation created through collaborative AI review (Claude, ChatGPT, Gemini, Grok 4). These documents provide deep-dive specifications for each aspect of the system.

### Core Documentation (6 Documents)

| Document | Purpose | Key Contents |
|----------|---------|--------------|
| **BarnabeeNet_Theory_Research.md** | Academic foundations and design rationale | Multi-agent systems theory, privacy-first architecture rationale, game AI inspiration (SkyrimNet), academic references, cognitive architecture comparisons |
| **BarnabeeNet_Hardware_Specifications.md** | Complete hardware requirements and configurations | Beelink EQi12 detailed specs, RTX 4070 Ti constraints, input device matrix (AR glasses, Amazfit, ThinkSmart), network architecture, power/thermal analysis, bill of materials, upgrade paths |
| **BarnabeeNet_Features_UseCases.md** | Feature catalog and practical scenarios | 34 detailed use cases across 7 categories, feature complexity ratings, interaction flow examples, privacy zone implications, prioritization framework |
| **BarnabeeNet_Technical_Architecture.md** | Deep technical specifications | Agent system design, message bus architecture, voice pipeline, speaker recognition system, memory architecture, database schemas, API contracts, security architecture |
| **BarnabeeNet_Implementation_Guide.md** | Phase-by-phase build instructions | Prerequisites and environment setup, 5-phase implementation roadmap, technology selection rationale, testing strategies, deployment procedures, checkpoint validation |
| **BarnabeeNet_Operations_Runbook.md** | Day-to-day operations and maintenance | Monitoring and alerting, cost tracking, performance benchmarks, troubleshooting guides, backup/recovery, upgrade procedures, incident response |

### Documentation Structure

```
docs/
├── BarnabeeNet_Theory_Research.md       # WHY: Design philosophy & research
├── BarnabeeNet_Hardware_Specifications.md # WHAT: Physical requirements
├── BarnabeeNet_Features_UseCases.md     # WHAT: Capabilities & scenarios
├── BarnabeeNet_Technical_Architecture.md # HOW: System design
├── BarnabeeNet_Implementation_Guide.md  # HOW: Build instructions
└── BarnabeeNet_Operations_Runbook.md    # HOW: Run & maintain
```

### Recommended Additional Documentation

Based on AI reviewer feedback, the following documents are recommended for future development:

| Document | Priority | Rationale |
|----------|----------|-----------|
| **BarnabeeNet_Security_Policy.md** | 🔴 Critical | Policy Engine design, threat model, privacy controls, permission matrix, consent workflows |
| **BarnabeeNet_API_Reference.md** | 🟠 High | Complete API specs, message contracts, WebSocket schemas, error codes |
| **BarnabeeNet_Testing_Strategy.md** | 🟠 High | Test plans, mocking strategies, CI/CD pipelines, performance benchmarks |
| **BarnabeeNet_Integration_Guide.md** | 🟡 Medium | Teams Proxy setup, Alexa integration, Gadgetbridge configuration, AR glasses SDK |
| **BarnabeeNet_Troubleshooting_Guide.md** | 🟡 Medium | Common issues, debugging flows, recovery procedures, log analysis |
| **BarnabeeNet_Upgrade_Migration.md** | 🟢 Lower | Version migration paths, breaking changes, rollback procedures |

### Key Architectural Recommendations (from AI Review)

The documentation incorporates feedback from four AI reviewers. Key consensus recommendations:

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
