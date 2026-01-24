# BarnabeeNet v1.0 Complete Snapshot

**Date:** January 23, 2026  
**Purpose:** Comprehensive reference for rebuilding BarnabeeNet v2.0 greenfield  
**v1.0 Status:** Phases 1-4 complete, 5-6 partial, Phase 7 complete

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [What v1.0 Achieved](#what-v10-achieved)
3. [Architecture Design](#architecture-design)
4. [Codebase Metrics](#codebase-metrics)
5. [Agent System Design](#agent-system-design)
6. [Intent Classification System](#intent-classification-system)
7. [Memory System](#memory-system)
8. [Home Assistant Integration](#home-assistant-integration)
9. [Voice Pipeline](#voice-pipeline)
10. [Dashboard & Observability](#dashboard--observability)
11. [Configuration System](#configuration-system)
12. [Family Profile System](#family-profile-system)
13. [Self-Improvement Agent](#self-improvement-agent)
14. [Logic Browser & AI Correction](#logic-browser--ai-correction)
15. [API Reference](#api-reference)
16. [Performance Metrics](#performance-metrics)
17. [Known Issues & Technical Debt](#known-issues--technical-debt)
18. [Deferred Features (Not Implemented)](#deferred-features-not-implemented)
19. [Key Design Decisions](#key-design-decisions)
20. [What Worked Well](#what-worked-well)
21. [What Didn't Work / Lessons Learned](#what-didnt-work--lessons-learned)
22. [Recommendations for v2.0](#recommendations-for-v20)
23. [How to Get Back to This Point](#how-to-get-back-to-this-point)
24. [Complete File Inventory](#complete-file-inventory)

---

## Executive Summary

BarnabeeNet v1.0 is a **privacy-first, multi-agent AI smart home assistant** built as a standalone FastAPI server that integrates with Home Assistant. It processes voice/text input through a multi-agent pipeline (MetaAgent routing → specialized agents) with local STT/TTS and cloud LLM via OpenRouter.

### Core Value Proposition

| Dimension | BarnabeeNet v1.0 |
|-----------|------------------|
| **Privacy** | Audio stays local; only text to LLM |
| **Latency** | <500ms end-to-end (GPU STT path) |
| **Intelligence** | Multi-agent with memory & personalization |
| **Cost** | Activity-based model selection; free tier support |
| **Observability** | Full pipeline tracing, logic browser, AI correction |

### What's Running

- **VM:** 192.168.86.51:8000 (NixOS, BarnabeeNet server)
- **GPU Worker:** 192.168.86.61:8001 (Man-of-war WSL, Parakeet STT)
- **Redis:** 192.168.86.51:6379 (memory, signals, config)
- **HA Connection:** 192.168.86.60:8123 (2291 entities, 238 devices, 20 areas)

---

## What v1.0 Achieved

### ✅ Fully Working

1. **Voice Pipeline** - STT (GPU/CPU) → Agent → TTS (Kokoro)
2. **Multi-Agent System** - Meta, Instant, Action, Interaction, Memory, Profile
3. **Intent Classification** - Pattern-based + heuristic + LLM fallback
4. **Home Assistant Control** - Device control, area targeting, compound commands
5. **Memory System** - Store/retrieve with vector similarity, diary generation
6. **Family Profiles** - Per-person profiles, privacy zones, LLM-generated updates
7. **Dashboard** - Chat, Memory, Logic, Self-Improve, Logs, Family, HA, Config
8. **Logic Browser** - Editable patterns/routing/overrides, hot-reload
9. **AI Correction** - "Mark as Wrong" → AI analysis → suggestions → apply
10. **Self-Improvement Agent** - Claude Code CLI integration for autonomous fixes
11. **E2E Testing** - Mock HA, entity state assertions
12. **Observability** - Pipeline tracing, waterfall timeline, decision logging

### 🔄 Partially Complete

1. **Azure STT** - Code exists, not heavily tested
2. **ViewAssist Integration** - APIs ready, docs written, not deployed
3. **Mobile Client** - Architecture documented, not built

### ❌ Not Implemented

1. **Proactive Agent** - Spec only
2. **Evolver Agent** - Spec only
3. **Speaker ID from Voice** - Uses HA user/context instead
4. **AR/Wearables** - Placeholder

---

## Architecture Design

### Network Topology

```
┌─────────────────────────────────────────────────────────────┐
│                    Home Network                              │
│                                                              │
│  ┌─────────────────┐         ┌─────────────────────────┐    │
│  │  Battlestation  │         │     Smart Devices       │    │
│  │  (Proxmox)      │◄───────►│  (Zigbee/Z-Wave/WiFi)   │    │
│  │  192.168.86.64  │         └─────────────────────────┘    │
│  │                 │                                         │
│  │  ┌───────────┐  │         ┌─────────────────────────┐    │
│  │  │ BarnabeeNet│  │         │  Home Assistant         │    │
│  │  │ VM        │◄─┼────────►│  192.168.86.60:8123     │    │
│  │  │ .51:8000  │  │         └─────────────────────────┘    │
│  │  └───────────┘  │                                         │
│  └─────────────────┘         ┌─────────────────────────┐    │
│                              │  Man-of-war (GPU)       │    │
│                              │  192.168.86.61:8001     │    │
│                              │  Parakeet STT Worker    │    │
│                              └─────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

### Request Flow

```
User Input (Voice/Text)
        │
        ▼
┌───────────────────────────────────────────────────────────────┐
│ VOICE PIPELINE                                                 │
│                                                                │
│  [Audio] ──► [STT Router] ──► [Text] ──► [Orchestrator]       │
│              GPU/CPU/Azure                      │              │
│                                                 ▼              │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │ ORCHESTRATOR                                             │  │
│  │                                                          │  │
│  │  1. MetaAgent.classify(text) → intent                   │  │
│  │  2. MemoryAgent.retrieve() → context (optional)         │  │
│  │  3. ProfileService.get_context() → personalization      │  │
│  │  4. Route to agent:                                      │  │
│  │     ├── instant  → InstantAgent (time, date, math)      │  │
│  │     ├── action   → ActionAgent (device control)         │  │
│  │     ├── memory   → MemoryAgent (store/recall)           │  │
│  │     └── conversation → InteractionAgent (LLM)           │  │
│  │  5. Execute HA actions (if action intent)               │  │
│  │  6. Store memories (if relevant)                        │  │
│  │  7. Return response                                      │  │
│  └─────────────────────────────────────────────────────────┘  │
│                                                 │              │
│                                                 ▼              │
│  [Response Text] ──► [TTS Kokoro] ──► [Audio]                 │
└───────────────────────────────────────────────────────────────┘
```

### Technology Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| **Runtime** | Python 3.12 | Core application |
| **Framework** | FastAPI | API server |
| **Async** | asyncio + httpx | Non-blocking I/O |
| **Message Bus** | Redis Streams | Inter-service communication |
| **Cache/State** | Redis | Memory, signals, config, secrets |
| **STT (GPU)** | Parakeet TDT 0.6B v2 | ~45ms transcription |
| **STT (CPU)** | Distil-Whisper | ~2400ms fallback |
| **TTS** | Kokoro-82M | 232-537ms synthesis |
| **LLM** | OpenRouter | 12 providers, activity-based |
| **Embeddings** | all-MiniLM-L6-v2 | Sentence embeddings |
| **Secrets** | Fernet (AES-128) | Encrypted API keys |
| **Observability** | Prometheus + Grafana | Metrics |

---

## Codebase Metrics

| Metric | Count |
|--------|-------|
| **Python Files (src)** | 100 |
| **Lines of Code (src)** | 51,057 |
| **Test Files** | 29 |
| **Test Lines** | 11,171 |
| **Tests** | ~690+ (based on CONTEXT.md) |
| **Agent Prompt Files** | 5 |
| **Config YAML Files** | 4 |
| **Documentation Files** | 30+ |

### Directory Structure

```
barnabeenet/
├── src/barnabeenet/           # Main application
│   ├── agents/                # Agent implementations
│   │   ├── action.py          # Device control
│   │   ├── instant.py         # Quick responses
│   │   ├── interaction.py     # LLM conversations
│   │   ├── memory.py          # Memory operations
│   │   ├── meta.py            # Intent classification
│   │   ├── orchestrator.py    # Pipeline coordinator
│   │   ├── profile.py         # Family profiles
│   │   ├── self_improvement.py # Claude Code integration
│   │   └── parsing/           # Compound command parser
│   ├── api/routes/            # FastAPI routes
│   │   ├── chat.py            # Simple chat API
│   │   ├── config.py          # Config management
│   │   ├── dashboard.py       # Dashboard API
│   │   ├── e2e.py             # E2E testing
│   │   ├── homeassistant.py   # HA endpoints
│   │   ├── logic.py           # Logic browser
│   │   ├── memory.py          # Memory API
│   │   ├── profiles.py        # Profile API
│   │   ├── self_improve.py    # Self-improvement API
│   │   └── voice.py           # Voice pipeline
│   ├── core/                  # Core infrastructure
│   │   ├── decision_registry.py
│   │   └── logic_registry.py
│   ├── models/                # Pydantic models
│   │   ├── ha_commands.py     # HA command models
│   │   ├── pipeline_trace.py  # Trace models
│   │   ├── profiles.py        # Profile models
│   │   ├── provider_config.py # LLM provider models
│   │   ├── schemas.py         # Request/response schemas
│   │   └── stt_modes.py       # STT mode enums
│   ├── prompts/               # Agent prompt files
│   │   ├── action_agent.txt
│   │   ├── instant_agent.txt
│   │   ├── interaction_agent.txt
│   │   ├── memory_agent.txt
│   │   └── meta_agent.txt
│   ├── services/              # Service layer
│   │   ├── activity_log.py    # Activity logging
│   │   ├── ai_correction.py   # AI-assisted fixes
│   │   ├── dashboard_service.py
│   │   ├── e2e_tester.py      # E2E test runner
│   │   ├── logic_diagnostics.py
│   │   ├── logic_health.py
│   │   ├── message_bus.py     # Redis Streams
│   │   ├── metrics.py
│   │   ├── metrics_store.py
│   │   ├── pipeline_signals.py
│   │   ├── profiles.py        # ProfileService
│   │   ├── secrets.py         # Encrypted secrets
│   │   ├── timers.py          # Timer management
│   │   ├── voice_pipeline.py
│   │   ├── homeassistant/     # HA integration
│   │   │   ├── client.py
│   │   │   ├── entities.py
│   │   │   ├── resolver.py    # SmartEntityResolver
│   │   │   └── topology.py    # HATopologyService
│   │   ├── llm/               # LLM providers
│   │   │   ├── cache.py
│   │   │   ├── openrouter.py
│   │   │   └── signals.py
│   │   ├── memory/            # Memory storage
│   │   │   └── storage.py
│   │   ├── stt/               # Speech-to-text
│   │   │   ├── azure_stt.py
│   │   │   ├── distil_whisper.py
│   │   │   └── router.py
│   │   └── tts/               # Text-to-speech
│   │       └── kokoro_tts.py
│   ├── static/                # Dashboard UI
│   │   ├── index.html
│   │   ├── app.js
│   │   └── styles.css
│   ├── config.py              # Settings
│   └── main.py                # FastAPI app
├── config/                    # YAML configuration
│   ├── llm.yaml               # LLM model config
│   ├── patterns.yaml          # Intent patterns
│   ├── routing.yaml           # Routing rules
│   └── overrides.yaml         # Behavior overrides
├── tests/                     # Test suite
├── workers/                   # GPU worker
│   └── gpu_stt_worker.py
├── scripts/                   # Deployment scripts
├── ha-integration/            # HA custom component
│   └── custom_components/barnabeenet/
└── docs/                      # Documentation
```

---

## Agent System Design

### Agent Hierarchy

| Agent | Purpose | LLM Required | Latency |
|-------|---------|--------------|---------|
| **MetaAgent** | Intent classification, context eval, memory queries | Yes (fallback) | <20ms pattern, ~500ms LLM |
| **InstantAgent** | Time, date, math, greetings, status | No | ~3ms |
| **ActionAgent** | Device control parsing, HA service calls | No (rule-based) | ~50ms |
| **InteractionAgent** | Complex conversations, personality | Yes | 1-3s |
| **MemoryAgent** | Store, retrieve, forget, diary | Partial | ~50ms retrieve, ~1s store |
| **ProfileAgent** | Generate/update family profiles | Yes | ~2s |

### Agent Orchestrator Flow

```python
async def process_input(text: str, speaker: str = None, room: str = None):
    # 1. Classify intent
    classification = await meta_agent.classify(text)
    
    # 2. Retrieve memories (for conversation/query intents)
    memories = []
    if classification.intent in ["conversation", "query", "memory"]:
        memories = await memory_agent.retrieve(text, speaker)
    
    # 3. Get profile context
    profile_context = await profile_service.get_context(speaker, room)
    
    # 4. Route to agent
    if classification.intent == "instant":
        response = await instant_agent.handle(text)
    elif classification.intent == "action":
        response = await action_agent.handle(text)
        # Execute HA actions
        if response.actions:
            await execute_ha_actions(response.actions)
    elif classification.intent == "memory":
        response = await memory_agent.handle(text, classification.sub_category)
    else:
        response = await interaction_agent.handle(text, memories, profile_context)
    
    # 5. Store memories
    if should_store_memory(classification, response):
        await memory_agent.store(text, response, speaker)
    
    return response
```

### MetaAgent Classification

Three-tier classification:

1. **Pattern Matching** (0ms) - Regex patterns from `config/patterns.yaml`
2. **Heuristic** (~10ms) - Keyword-based classification
3. **LLM Fallback** (~500ms) - OpenRouter when patterns/heuristics fail

```python
# Classification result
@dataclass
class ClassificationResult:
    intent: str          # instant, action, memory, conversation, query
    confidence: float    # 0.0-1.0
    sub_category: str    # e.g., "time", "switch", "store"
    classification_method: str  # pattern, heuristic, llm
    patterns_checked: int
    near_miss_patterns: list[str]
```

### ActionAgent Compound Commands

Handles commands like "turn on the office light and turn on the office fan":

```python
# CompoundCommandParser
segments = parser.parse("turn on the office light and turn on the fan")
# Returns: [
#   CommandSegment(action="turn_on", target="office light", domain="light"),
#   CommandSegment(action="turn_on", target="fan", domain="fan")
# ]

# SmartEntityResolver
for segment in segments:
    entities = resolver.resolve(segment.target, segment.domain)
    # Handles: area aliases, floor mapping, typos, fuzzy matching
```

### InteractionAgent Persona

```
You are Barnabee, the AI assistant for the Fife family household.

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

## Guidelines
- Never reveal you're an AI unless directly asked
- Don't over-explain - keep it short
- If unsure, ask for clarification
- Be helpful but respect privacy boundaries
```

---

## Intent Classification System

### Pattern Groups (`config/patterns.yaml`)

| Group | Count | Examples |
|-------|-------|----------|
| **emergency** | 4 | fire, help, intruder, medical |
| **instant** | 10 | time, date, greeting, math, thanks |
| **action** | 15+ | switch, set, dim, lock, cover, media, timer |
| **memory** | 8 | remember, recall, forget, what did I tell you |
| **query** | 5 | weather, sensor, general questions |
| **gesture** | 3 | tap, double-tap, long-press |

### Known Classification Issues

From `docs/INTENT_CLASSIFICATION_ISSUES.md`:

| Issue | Current | Expected | Priority |
|-------|---------|----------|----------|
| "Tell me the time" | conversation | instant | High |
| "What time?" | query | instant | High |
| "What do I like?" | query | memory | High |
| "What's my preference?" | query | memory | High |
| "Remember: I don't like X" | conversation | memory | Medium |

### Routing Rules (`config/routing.yaml`)

```yaml
intent_routing:
  instant:
    agent: "instant"
    priority: 10
    requires_llm: false
    timeout_ms: 100
  action:
    agent: "action"
    priority: 9
    requires_llm: false
    timeout_ms: 2000
  memory:
    agent: "memory"
    priority: 8
    requires_llm: false
    timeout_ms: 1000
  conversation:
    agent: "interaction"
    priority: 5
    requires_llm: true
    timeout_ms: 5000

confidence_thresholds:
  pattern_match: 0.85
  heuristic: 0.70
  llm_fallback: 0.60
```

---

## Memory System

### Memory Types

| Type | Purpose | Example |
|------|---------|---------|
| **semantic** | Facts and preferences | "Thom's favorite color is blue" |
| **episodic** | Conversation history | "Thom asked about weather at 3pm" |
| **procedural** | Learned routines | "Morning routine includes coffee" |
| **working** | Short-term context | Current conversation state |

### Storage Architecture

```
Redis
├── memory:{id}           # Memory content
├── memory:embedding:{id} # Vector embeddings (binary)
├── memory:index          # Memory index
└── conversation:{id}     # Conversation history
```

### Memory Operations

| Operation | Method | Notes |
|-----------|--------|-------|
| **Store** | `memory_agent.store()` | Generates embedding async |
| **Retrieve** | `memory_agent.retrieve()` | Vector similarity search |
| **Forget** | `memory_agent.forget()` | Soft delete |
| **Diary** | `memory_agent.generate_diary()` | LLM-generated daily summary |

### Vector Search

- **Model:** all-MiniLM-L6-v2 (384 dimensions)
- **Similarity:** Cosine similarity
- **Threshold:** 0.6 minimum relevance
- **Max Results:** 5 memories per query

---

## Home Assistant Integration

### Connection Details

| Property | Value |
|----------|-------|
| **URL** | http://192.168.86.60:8123 |
| **Version** | 2026.1.2 |
| **Entities** | 2291 |
| **Devices** | 238 |
| **Areas** | 20 |
| **Automations** | 6 |
| **Integrations** | 64 |

### Entity Resolution

`SmartEntityResolver` handles:

1. **Fuzzy name matching** - "living room light" → `light.living_room_light`
2. **Area aliases** - "living room" → `living_room`
3. **Floor mapping** - "downstairs" → all first floor areas
4. **Area groups** - "kids rooms" → boys_room + girls_room + playroom
5. **Domain synonyms** - "blinds" → cover domain
6. **Cross-domain search** - searches switch domain for light commands
7. **Typo handling** - "trun", "tunr" → turn; "swtich" → switch

### HA Service Calls

```python
# HATarget - prefers area_id over entity_id
@dataclass
class HATarget:
    area_id: str | None = None
    device_id: str | None = None
    entity_id: str | None = None

# HAServiceCall
@dataclass
class HAServiceCall:
    domain: str      # light, switch, cover, etc.
    service: str     # turn_on, turn_off, toggle, etc.
    target: HATarget
    data: dict = {}  # brightness, temperature, etc.
```

### Timer System

- **Pool:** timer.barnabee_1 through timer.barnabee_10 (HA timer helpers)
- **Types:** ALARM, DEVICE_DURATION, DELAYED_ACTION
- **Parsing:** "5 minutes", "30 seconds", "1 hour"

### HA Custom Integration

Location: `ha-integration/custom_components/barnabeenet/`

- Registers as HA conversation agent
- Auto-detects speaker from HA user
- Auto-detects room from device area
- Config flow with URL setup

---

## Voice Pipeline

### STT Engine Selection

| Engine | Latency | Hardware | Use Case |
|--------|---------|----------|----------|
| **Parakeet** | ~45ms | GPU (RTX 4070 Ti) | Primary |
| **Whisper** | ~2400ms | CPU | Fallback |
| **Azure** | ~300ms | Cloud | Mobile/remote |

### STT Modes

| Mode | Behavior | Use Case |
|------|----------|----------|
| **COMMAND** | Single utterance | Wake word response |
| **REALTIME** | Streaming with interim | Live transcription |
| **AMBIENT** | Batch every 30-60s | Background listening |

### TTS (Kokoro)

- **Voice:** bm_fable (British male)
- **Latency:** 232-537ms
- **Pronunciation Fixes:**
  - Viola → Vyola
  - Xander → Zander

### WebSocket Streaming

```
ws://192.168.86.51:8000/ws/transcribe

// Config message
{"engine": "auto", "language": "en-US", "mode": "command"}

// Send: Binary audio chunks (16kHz PCM)
// Receive: {"type": "partial|final", "text": "...", "is_final": bool}
```

---

## Dashboard & Observability

### Dashboard Pages

| Page | Purpose |
|------|---------|
| **Dashboard** | Home with quick stats, SI sessions |
| **Chat** | Text + voice conversation with Barnabee |
| **Memory** | Memory browser, search, add, diary |
| **Logic** | Pattern/routing/override editor, tester |
| **Self-Improve** | Claude Code session management |
| **Logs** | Performance graphs, log stream |
| **Family** | Profile management |
| **Entities** | "What Barnabee Knows" about HA |
| **Config** | Providers, models, HA, modes |

### Activity Logging

30+ ActivityType enum values:
- `user.input`, `meta.classify`, `action.execute`
- `interaction.respond`, `memory.store`, `memory.retrieve`
- `ha.state_change`, `ha.service_call`, `llm.request`
- `self_improve.start`, `.plan_proposed`, `.committed`

### Pipeline Tracing

```python
@dataclass
class PipelineTrace:
    trace_id: str
    input_text: str
    classification: ClassificationResult
    memories_retrieved: list[Memory]
    agent_used: str
    response: str
    ha_actions: list[HAServiceCall]
    llm_calls: list[LLMSignal]
    total_latency_ms: int
    routing_reason: str
```

### Waterfall Timeline

Visual timeline showing:
- STT duration (orange)
- Meta classification (purple)
- Memory retrieval (green)
- Agent processing (blue)
- HA execution (red)
- TTS synthesis (yellow)

---

## Configuration System

### LLM Configuration (`config/llm.yaml`)

```yaml
# Activity-level config (16+ activities)
activities:
  meta.classify_intent:
    model: "meta-llama/llama-3.3-70b-instruct:free"
    temperature: 0.2
    max_tokens: 150
    priority: speed
  
  interaction.respond:
    model: "meta-llama/llama-3.3-70b-instruct:free"
    temperature: 0.7
    max_tokens: 1500
    priority: quality
  
  memory.generate:
    model: "meta-llama/llama-3.3-70b-instruct:free"
    temperature: 0.3
    max_tokens: 500
    priority: quality
```

### Provider Configuration

12 supported providers:
- OpenRouter, OpenAI, Anthropic, Azure
- Google, xAI, DeepSeek, HuggingFace
- Bedrock, Together, Mistral, Groq

### Secrets Management

- **Encryption:** Fernet (AES-128)
- **Master Key:** `BARNABEENET_MASTER_KEY` env var
- **Storage:** Redis with encrypted values
- **Survives:** Restarts, stored persistently

### Testing/Production Modes

- **Testing Mode:** All free models (Llama 3.3 70B)
- **Production Mode:** Quality models (Claude, GPT-4o)
- **Toggle:** One-click in dashboard
- **Persistence:** Mode and model selections saved per-mode

---

## Family Profile System

### Profile Structure

```python
@dataclass
class FamilyMemberProfile:
    # Identity
    member_id: str           # "thom", "elizabeth"
    name: str
    relationship: str        # "self", "spouse", "child"
    ha_person_entity: str    # "person.thom" for location
    
    # Public (safe to share)
    public: PublicProfileBlock
    # - schedule_summary
    # - typical_locations
    # - preferences
    # - interests
    # - communication_style
    
    # Private (direct interactions only)
    private: PrivateProfileBlock
    # - emotional_patterns
    # - goals_mentioned
    # - relationship_notes
    # - sensitive_topics
    # - private_preferences
```

### Privacy Zones

| Zone | Rooms | Behavior |
|------|-------|----------|
| **Common** | Kitchen, Living Room, Office | Full profile context |
| **Private** | Bedrooms, Bathrooms | Private block only for owner |

### Location Integration

- Links to HA person entities
- Real-time location: home/away/zone
- Arrival time tracking
- Used in responses: "Where is X?", "Is X home?"

---

## Self-Improvement Agent

### Architecture

- **Backend:** Claude Code CLI (headless mode)
- **Models:** "opusplan" mode - Opus for diagnosis, Sonnet for implementation
- **Workflow:** Branch → Diagnose → Plan → Approve → Implement → Test → Commit

### Safety System

```python
@dataclass
class SafetyScore:
    score: float           # 0.0-1.0
    files_affected: int
    safe_paths: list[str]  # config/, docs/, prompts/, tests/
    risky_paths: list[str] # main.py, api/routes/, services/homeassistant/
    auto_approve: bool     # score >= 0.80

# Forbidden paths
FORBIDDEN = ["secrets/", ".env", "*.key", "*.pem"]
```

### Notification Flow

1. **Plan Ready:** HA notification with safety score
2. **Auto-Approved:** HA notification (if safe enough)
3. **Ready to Commit:** HA notification
4. **Committed:** HA notification with summary

### CLI Output API

```
GET /api/v1/self-improve/sessions/{id}/cli-output
→ { messages: [...], operations: [...], thinking: [...] }
```

---

## Logic Browser & AI Correction

### Logic Registry

Hot-reloadable configuration:
- **patterns.yaml** - Intent patterns by group
- **routing.yaml** - Intent→agent mapping, priorities
- **overrides.yaml** - User/room/time behavior modifications

### Pattern Testing

```
POST /api/v1/logic/patterns/test
{
  "text": "turn on the kitchen light",
  "expected_intent": "action"
}
→ {
  "matched": true,
  "pattern": "switch_control",
  "confidence": 0.95,
  "classification_method": "pattern"
}
```

### AI Correction Flow

1. **Mark as Wrong** - Click button on trace
2. **Describe Issue** - wrong_entity, wrong_action, wrong_routing, etc.
3. **AI Analysis** - LLM analyzes trace, suggests fixes
4. **Suggestions** - pattern_modify, entity_alias, routing_change
5. **Test** - Run against historical data
6. **Apply** - Hot-reload into system

### Logic Diagnostics

- **Near-miss detection** - Similar patterns that almost matched
- **Failure tracking** - Why patterns didn't match
- **Suggested patterns** - Auto-generated regex for new patterns
- **Health monitoring** - Consistency, confidence drift

---

## API Reference

### Core Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/chat` | GET/POST | Simple text chat |
| `/api/v1/voice/process` | POST | Text pipeline with trace |
| `/api/v1/voice/pipeline` | POST | Full voice pipeline |
| `/api/v1/input/text` | POST | Quick text input |
| `/api/v1/input/audio` | POST | Audio upload |
| `/ws/transcribe` | WS | Real-time STT |

### Dashboard APIs

| Endpoint | Purpose |
|----------|---------|
| `/api/v1/dashboard/metrics/*` | Performance metrics |
| `/api/v1/activity/*` | Activity logging |
| `/api/v1/memory/*` | Memory CRUD |
| `/api/v1/profiles/*` | Profile management |
| `/api/v1/config/*` | Provider/model config |
| `/api/v1/logic/*` | Pattern/routing editor |
| `/api/v1/self-improve/*` | SI session management |
| `/api/v1/homeassistant/*` | HA status/entities |
| `/api/v1/e2e/*` | E2E test runner |

### WebSocket Endpoints

| Endpoint | Purpose |
|----------|---------|
| `/ws/activity` | Real-time activity stream |
| `/ws/dashboard` | Dashboard updates |
| `/ws/transcribe` | Audio streaming |

---

## Performance Metrics

### Observed Latencies

| Stage | Latency | Notes |
|-------|---------|-------|
| **STT (GPU)** | 45ms | Parakeet TDT |
| **STT (CPU)** | 2400ms | Distil-Whisper |
| **Meta classify (pattern)** | <5ms | Regex match |
| **Meta classify (LLM)** | ~500ms | Fallback |
| **Instant agent** | ~3ms | No LLM |
| **Action agent** | ~50ms | Rule-based |
| **Interaction agent** | 1-3s | LLM call |
| **Memory retrieve** | ~50ms | Vector search |
| **TTS** | 232-537ms | Kokoro |
| **E2E (action path)** | <500ms | GPU STT + fast agent |

### Caching

- **LLM Response Cache:** Semantic similarity >= 0.95, Redis-backed
- **Embedding Cache:** SHA256 hash, 7-day TTL
- **Connection Pooling:** httpx with 20 keepalive, 100 max

---

## Known Issues & Technical Debt

### High Priority

1. **Intent misclassification** - Some phrasings route incorrectly (see Issues doc)
2. **Memory patterns** - "Remember: X" doesn't always classify as memory
3. **Compound command edge cases** - Location extraction sometimes fails

### Medium Priority

4. **Test coverage** - Could be higher in some areas
5. **Error handling** - Some edge cases not gracefully handled
6. **Documentation** - Some docs out of date

### Low Priority

7. **Code duplication** - Some patterns repeated across agents
8. **Async consistency** - Some sync/async mixing

### Technical Debt

- Redis binary client for embeddings (workaround for UTF-8 issues)
- HA token hardcoded fallback (workaround for encryption timing)
- Some global state patterns that could be cleaner

---

## Deferred Features (Not Implemented)

| Feature | Spec Exists | Implementation Status |
|---------|-------------|----------------------|
| **Proactive Agent** | Yes | Not started |
| **Evolver Agent** | Yes | Not started |
| **Speaker ID (ECAPA-TDNN)** | Partial | Using HA user instead |
| **SQLite persistence** | Yes | Using Redis instead |
| **Override system** | Yes | Partial (config only) |
| **AR glasses (G1)** | Yes | Placeholder |
| **Wearable (Amazfit)** | Yes | Placeholder |
| **ThinkSmart View** | Yes | Placeholder |
| **Mobile client** | Architecture doc | Not built |
| **Full ViewAssist deploy** | Integration doc | APIs ready |

### Proactive Agent Spec

Would poll for:
- Safety alerts (windows open when leaving)
- Convenience reminders (preheat oven)
- Learning opportunities (pattern suggestions)

### Evolver Agent Spec

Would handle:
- Prompt optimization
- Model benchmarking
- Code enhancement suggestions

---

## Key Design Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| **FastAPI standalone** | HA integration optional, testable | Good - flexible deployment |
| **Redis for everything** | Simple, fast, single dependency | Good - worked well |
| **Activity-based LLM config** | Granular cost/quality control | Good - very useful |
| **Pattern + heuristic + LLM** | Fast path with fallback | Good - low latency |
| **OpenRouter over LiteLLM** | Simpler, more reliable | Good - stable |
| **Kokoro over Piper** | Faster, better quality | Good - noticeable improvement |
| **GPU worker on Man-of-war** | Leverage existing hardware | Good - 45ms STT |
| **No voice-based speaker ID** | Too complex, HA user works | Acceptable - simpler |
| **Family profiles** | SkyrimNet pattern | Good - personalization works |
| **Self-improvement agent** | Autonomous fixes | Mixed - needs better context |

---

## What Worked Well

### Architecture

1. **Multi-agent separation** - Clean responsibilities
2. **Pattern-first classification** - Fast, predictable
3. **Activity-based LLM config** - Fine-grained control
4. **Pipeline tracing** - Debugging is easy
5. **Hot-reload logic** - No restarts for pattern changes

### Implementation

6. **Redis Streams** - Simple, effective message bus
7. **Fernet encryption** - Secure secrets without complexity
8. **SmartEntityResolver** - Handles real-world entity naming
9. **Compound command parser** - "X and Y" commands work
10. **Dashboard UI** - Good visibility into system state

### Operations

11. **VM deployment** - Stable, survives reboots
12. **E2E testing** - Catches regressions
13. **Mock HA** - Tests without real HA

---

## What Didn't Work / Lessons Learned

### Architecture Issues

1. **Too many features too fast** - Should have stabilized core first
2. **Orchestrator complexity** - Grew too complex, hard to follow
3. **Global state patterns** - Made testing harder
4. **Profile system complexity** - Simpler approach would work

### Implementation Issues

5. **Self-improvement context** - Claude Code needs more architecture context
6. **Intent classification edge cases** - Patterns need continuous refinement
7. **Memory retrieval relevance** - Sometimes retrieves irrelevant memories
8. **Error propagation** - Some errors swallowed silently

### Operational Issues

9. **SSH command hanging** - Required `</dev/null` workaround
10. **Encryption timing** - Master key needs to exist before secrets
11. **HA token persistence** - Required fallback constant

### What to Do Differently in v2.0

1. **Start simpler** - Core voice pipeline, then agents one at a time
2. **Better abstractions** - Clearer service boundaries
3. **Dependency injection** - For testability
4. **Event sourcing** - For activity/memory instead of ad-hoc logging
5. **Simpler profiles** - Basic key-value preferences first
6. **Incremental patterns** - Build pattern library gradually

---

## Recommendations for v2.0

### Architecture

1. **Simpler agent structure** - Maybe just Meta + Executor + Conversation
2. **Event-driven core** - Full event sourcing for all state changes
3. **Plugin system** - Agents/integrations as plugins
4. **Better DI** - Use proper dependency injection framework
5. **Typed configuration** - Pydantic models for all config

### Features to Keep

1. **Activity-based LLM config** - Essential for cost control
2. **Pipeline tracing** - Essential for debugging
3. **Pattern-based classification** - Fast path is important
4. **SmartEntityResolver** - Entity resolution is hard
5. **Dashboard** - Visibility is crucial

### Features to Simplify

1. **Memory system** - Start with simple key-value, add vectors later
2. **Profile system** - Basic preferences, no public/private split
3. **Self-improvement** - Simpler script runner, not full Claude Code
4. **Logic browser** - Edit YAML files directly, hot-reload only

### Features to Drop (Maybe)

1. **Compound commands** - Complex, edge cases everywhere
2. **Diary generation** - Nice but not essential
3. **AI correction** - Manual pattern editing is fine
4. **Multi-provider LLM** - OpenRouter alone is sufficient

### Technology Changes to Consider

1. **SQLite instead of Redis** - For persistence, vector search
2. **Better TTS** - Evaluate newer models
3. **Streaming responses** - Stream LLM to TTS
4. **Mobile-first** - Design API for mobile from start

---

## How to Get Back to This Point

### Environment Setup

1. **VM:** NixOS 24.11 on Proxmox (VM 200)
   - 6 cores, 8GB RAM, 100GB disk
   - Podman rootless with docker-compat

2. **GPU Worker:** WSL2 on Man-of-war
   - Ubuntu 24.04, CUDA 12.4
   - RTX 4070 Ti

3. **Redis:** Container on VM
   - Port 6379, AOF persistence

### Deployment Steps

```bash
# 1. Clone repo
git clone git@github.com:trfife/BarnabeeNet.git
cd BarnabeeNet

# 2. Create venv
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Create .env
cat > .env << 'EOF'
BARNABEENET_MASTER_KEY=<generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())">
REDIS_HOST=localhost
REDIS_PORT=6379
HA_URL=http://192.168.86.60:8123
HA_TOKEN=<from HA long-lived access token>
EOF

# 4. Start Redis
podman-compose -f infrastructure/podman-compose.yml up -d redis

# 5. Run server
uvicorn src.barnabeenet.main:app --host 0.0.0.0 --port 8000

# 6. (Optional) GPU Worker on Man-of-war
cd workers
source .venv-gpu/bin/activate
python -m uvicorn gpu_stt_worker:app --host 0.0.0.0 --port 8001
```

### Configure via Dashboard

1. Open http://192.168.86.51:8000/
2. Go to Config → Providers
3. Add OpenRouter API key
4. Test connection
5. Go to Config → Activities
6. Click "Auto-Select" for free models

### Verify Working

```bash
# Health check
curl http://192.168.86.51:8000/health

# Simple chat
curl "http://192.168.86.51:8000/api/v1/chat?text=what+time+is+it"

# Full pipeline
curl -X POST "http://192.168.86.51:8000/api/v1/voice/process" \
  -H "Content-Type: application/json" \
  -d '{"text": "turn on the kitchen light"}'
```

---

## Complete File Inventory

### Core Application Files

```
src/barnabeenet/
├── __init__.py
├── config.py                      # Settings (Pydantic)
├── main.py                        # FastAPI app entry
├── agents/
│   ├── __init__.py
│   ├── action.py                  # Device control
│   ├── base.py                    # Base agent class
│   ├── echo.py                    # Debug echo agent
│   ├── instant.py                 # Quick responses
│   ├── interaction.py             # LLM conversations
│   ├── manager.py                 # Agent manager
│   ├── memory.py                  # Memory operations
│   ├── meta.py                    # Intent classification
│   ├── orchestrator.py            # Pipeline coordinator
│   ├── profile.py                 # Family profiles
│   ├── self_improvement.py        # Claude Code
│   └── parsing/
│       └── compound_parser.py     # "X and Y" commands
├── api/routes/
│   ├── __init__.py
│   ├── chat.py
│   ├── config.py
│   ├── dashboard.py
│   ├── e2e.py
│   ├── health.py
│   ├── homeassistant.py
│   ├── logic.py
│   ├── memory.py
│   ├── profiles.py
│   ├── self_improve.py
│   └── voice.py
├── core/
│   ├── __init__.py
│   ├── decision_registry.py
│   └── logic_registry.py
├── models/
│   ├── __init__.py
│   ├── ha_commands.py
│   ├── pipeline_trace.py
│   ├── profiles.py
│   ├── provider_config.py
│   ├── schemas.py
│   └── stt_modes.py
├── prompts/
│   ├── action_agent.txt
│   ├── instant_agent.txt
│   ├── interaction_agent.txt
│   ├── memory_agent.txt
│   └── meta_agent.txt
├── services/
│   ├── __init__.py
│   ├── activity_log.py
│   ├── ai_correction.py
│   ├── dashboard_service.py
│   ├── device_capabilities.py
│   ├── e2e_tester.py
│   ├── entity_queries.py
│   ├── logic_diagnostics.py
│   ├── logic_health.py
│   ├── message_bus.py
│   ├── metrics.py
│   ├── metrics_store.py
│   ├── pipeline_signals.py
│   ├── profiles.py
│   ├── secrets.py
│   ├── timers.py
│   ├── voice_pipeline.py
│   ├── homeassistant/
│   │   ├── __init__.py
│   │   ├── client.py
│   │   ├── entities.py
│   │   ├── mock_ha.py
│   │   ├── resolver.py
│   │   └── topology.py
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── cache.py
│   │   ├── openrouter.py
│   │   └── signals.py
│   ├── memory/
│   │   ├── __init__.py
│   │   └── storage.py
│   ├── stt/
│   │   ├── __init__.py
│   │   ├── azure_stt.py
│   │   ├── distil_whisper.py
│   │   └── router.py
│   └── tts/
│       ├── __init__.py
│       └── kokoro_tts.py
└── static/
    ├── index.html
    ├── app.js
    └── styles.css
```

### Configuration Files

```
config/
├── llm.yaml                       # LLM model config
├── llm-free.yaml                  # Free tier config
├── llm-paid.yaml                  # Paid tier config
├── patterns.yaml                  # Intent patterns
├── routing.yaml                   # Routing rules
└── overrides.yaml                 # Behavior overrides
```

### Test Files

```
tests/
├── __init__.py
├── test_action_agent.py
├── test_config.py
├── test_dashboard.py
├── test_dashboard_contract.py
├── test_distil_whisper.py
├── test_e2e.py
├── test_health.py
├── test_homeassistant.py
├── test_homeassistant_api.py
├── test_instant_agent.py
├── test_intent_coverage.py
├── test_interaction_agent.py
├── test_kokoro_tts.py
├── test_logic_diagnostics.py
├── test_logic_health.py
├── test_memory_agent.py
├── test_memory_storage.py
├── test_meta_agent.py
├── test_metrics.py
├── test_openrouter.py
├── test_orchestrator.py
├── test_pronunciation.py
├── test_providers.py
├── test_self_improvement.py
├── test_stt_modes.py
├── test_stt_router.py
├── test_voice_pipeline_orchestrator.py
└── test_websocket.py
```

### Documentation

```
docs/
├── architecture.md                # As-built architecture
├── INTEGRATION.md                 # API integration guide
├── VIEWASSIST_INTEGRATION.md      # ViewAssist setup
├── INTENT_CLASSIFICATION_ISSUES.md
├── IMPLEMENTATION_STATUS.md
├── QUICK_REFERENCE.md
├── TIMER_SETUP.md
├── VM_DEPLOYMENT_STATUS.md
├── BarnabeeNet_Technical_Architecture.md
├── BarnabeeNet_Features_UseCases.md
├── BarnabeeNet_Family_Profile_System.md
├── BarnabeeNet_MetaAgent_Specification.md
├── BarnabeeNet_Pipeline_Management_Dashboard.md
├── BarnabeeNet_Prompt_Engineering.md
├── BarnabeeNet_Operations_Runbook.md
├── Self_Improvement_Agent_Review.md
└── future/
    └── MOBILE_STT_CLIENT.md
```

### Scripts

```
scripts/
├── clear_all_data.sh
├── clear_redis_data.py
├── debug-logs.sh
├── deploy-vm.sh
├── ollama-tunnel.sh
├── pre-commit.sh
├── restart.sh
├── start-gpu-worker.sh
├── stop-gpu-worker.sh
└── validate.sh
```

### HA Integration

```
ha-integration/
└── custom_components/
    └── barnabeenet/
        ├── __init__.py
        ├── config_flow.py
        ├── const.py
        ├── conversation.py
        └── manifest.json
```

---

## Final Notes

This document captures BarnabeeNet v1.0 as of January 23, 2026. The system is functional and running in production at http://192.168.86.51:8000 with:

- Full voice pipeline (STT → Agents → TTS)
- Multi-agent architecture (Meta, Instant, Action, Interaction, Memory, Profile)
- Home Assistant integration (2291 entities, device control, state streaming)
- Dashboard with full observability
- Logic browser with AI correction
- Self-improvement agent (Claude Code integration)
- ~690 tests, ~51K lines of Python

**Key Takeaway for v2.0:** Start simpler. The core value is voice → AI → action with low latency. Everything else is secondary. Build that first, make it rock solid, then add features incrementally.

---

*Generated from BarnabeeNet v1.0 codebase and documentation.*
