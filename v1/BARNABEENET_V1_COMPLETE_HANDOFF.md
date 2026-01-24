# BarnabeeNet v1.0 Complete Project Handoff

**Document Created:** January 24, 2026  
**Purpose:** Complete reference for rebuilding BarnabeeNet v2.0 from lessons learned  
**Project Duration:** January 16 - January 24, 2026 (8 days)

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [What BarnabeeNet Is](#what-barnabeenet-is)
3. [Architecture Overview](#architecture-overview)
4. [Hardware & Infrastructure](#hardware--infrastructure)
5. [Complete Feature List](#complete-feature-list)
6. [Agent System Design](#agent-system-design)
7. [Intent Classification System](#intent-classification-system)
8. [Home Assistant Integration](#home-assistant-integration)
9. [Performance Metrics](#performance-metrics)
10. [What Worked Well](#what-worked-well)
11. [What Didn't Work / Pain Points](#what-didnt-work--pain-points)
12. [Features Not Implemented (Deferred)](#features-not-implemented-deferred)
13. [Recommendations for v2.0](#recommendations-for-v20)
14. [Code Statistics](#code-statistics)
15. [Configuration Reference](#configuration-reference)
16. [API Endpoints Reference](#api-endpoints-reference)
17. [How to Get Back to This Point](#how-to-get-back-to-this-point)

---

## Executive Summary

BarnabeeNet v1.0 is a **privacy-first, multi-agent AI smart home assistant** that achieved:

- **~45ms GPU STT latency** (Parakeet TDT 0.6B v2)
- **~200-500ms TTS latency** (Kokoro)
- **~130ms instant responses** (pattern-matched, no LLM)
- **~1.3-1.5s LLM responses** (with Ollama local or cloud)
- **87.3% intent classification accuracy** (118 test cases)
- **100% memory and emergency classification accuracy**
- **Full Home Assistant integration** (2291 entities, 238 devices, 20 areas)
- **Family profile system** with privacy-aware context injection
- **Self-improvement agent** using Claude Code CLI

### Core Principles Achieved

1. ✅ **Privacy by Architecture** — Audio stays local, only text to LLM
2. ✅ **Latency-Obsessed** — Pattern matching for instant responses
3. ✅ **Family-Aware** — Profiles with communication preferences
4. ✅ **Graceful Degradation** — GPU→CPU→Azure STT fallback chain
5. ✅ **Cost-Conscious** — Activity-based model selection, free tier support
6. ⚠️ **Self-Improving** — Partially implemented (manual approval required)

---

## What BarnabeeNet Is

A voice-activated AI assistant for the Fife family that:

1. **Listens** via Home Assistant integration (phones, tablets, speakers)
2. **Understands** intent via pattern matching + LLM fallback
3. **Acts** by controlling Home Assistant devices
4. **Remembers** family preferences, conversations, and context
5. **Speaks** with a consistent personality (helpful, not theatrical)

### The Barnabee Persona

```
You are Barnabee, the AI assistant for the Fife family household.

Personality:
- Helpful and straightforward
- Patient, especially with children
- No gimmicks, puns, or theatrical personality
- Just a capable, reliable assistant

Communication Style:
- Keep responses brief (1-2 sentences when possible)
- Talk naturally, like a normal person
- Don't use fancy language or act like a butler
- For children, use simpler language
```

---

## Architecture Overview

### High-Level Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                     BARNABEENET PIPELINE                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Audio In ──→ STT Router ──→ MetaAgent ──→ Agent ──→ TTS Out    │
│                   │              │           │                   │
│         ┌────────┴────────┐     │     ┌────┴────┐              │
│         ▼                 ▼     ▼     ▼         ▼              │
│    ┌─────────┐      ┌─────────┐     ┌───────┐ ┌─────────┐      │
│    │Parakeet │      │ Distil  │     │Instant│ │ Action  │      │
│    │  GPU    │      │ Whisper │     │ Agent │ │  Agent  │      │
│    │ ~45ms   │      │ ~2400ms │     │ <5ms  │ │ <100ms  │      │
│    └─────────┘      └─────────┘     └───────┘ └─────────┘      │
│    Man-of-war       Beelink VM                                  │
│                           │     ┌───────────┐ ┌─────────┐      │
│                           │     │Interaction│ │ Memory  │      │
│                           │     │  Agent    │ │  Agent  │      │
│                           │     │  <3s LLM  │ │ <50ms   │      │
│                           │     └───────────┘ └─────────┘      │
│                           │                                     │
│                           ▼                                     │
│                    ┌───────────┐                                │
│                    │  Kokoro   │                                │
│                    │   TTS     │                                │
│                    │ 200-500ms │                                │
│                    └───────────┘                                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Technology Stack

| Layer | Technology | Version | Purpose |
|-------|------------|---------|---------|
| **Runtime** | Python | 3.12+ | Core application |
| **Framework** | FastAPI | 0.109+ | REST API + WebSocket |
| **Message Bus** | Redis Streams | 7.0+ | Inter-agent communication |
| **Vector Search** | Redis + sentence-transformers | - | Semantic memory |
| **STT (GPU)** | Parakeet TDT 0.6B v2 | 1.22+ | Primary speech recognition |
| **STT (CPU)** | Distil-Whisper | 1.0+ | Fallback |
| **STT (Cloud)** | Azure Cognitive Services | - | Mobile/remote |
| **TTS** | Kokoro-82M | 0.3+ | Voice synthesis |
| **LLM** | OpenRouter / Ollama | - | Multi-model orchestration |
| **Platform** | Home Assistant | 2026.1+ | Smart home backbone |

---

## Hardware & Infrastructure

### Production Deployment

| Component | Hardware | IP | Purpose |
|-----------|----------|-----|---------|
| **BarnabeeNet VM** | Beelink EQi12 VM (6 cores, 8GB) | 192.168.86.51 | Main runtime |
| **GPU STT Worker** | Gaming PC RTX 4070 Ti (WSL) | 192.168.86.61:8001 | Fast transcription |
| **Home Assistant** | Proxmox VM | 192.168.86.60:8123 | Smart home platform |
| **Ollama** | Gaming PC WSL (GPU) | localhost:11434 (tunneled) | Local LLM inference |

### Network Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Home Devices  │     │  BarnabeeNet VM │     │   Man-of-war    │
│   (HA Clients)  │────▶│  192.168.86.51  │────▶│   (GPU Worker)  │
│                 │     │  :8000 API      │     │   :8001 STT     │
│                 │     │  :6379 Redis    │     │   :11434 Ollama │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                               │
                               ▼
                        ┌─────────────────┐
                        │ Home Assistant  │
                        │ 192.168.86.60   │
                        │ :8123 API/WS    │
                        └─────────────────┘
```

### Ollama SSH Tunnel (for local LLM)

```bash
# Run on WSL to expose Ollama to VM
#!/bin/bash
while true; do
    ssh -N -R 11434:localhost:11434 thom@192.168.86.51
    sleep 5
done
```

---

## Complete Feature List

### ✅ Implemented

#### Voice Pipeline
- [x] GPU STT (Parakeet TDT 0.6B v2) - 45ms latency
- [x] CPU STT fallback (Distil-Whisper) - 2400ms latency
- [x] Azure STT for mobile/remote
- [x] TTS (Kokoro bm_fable voice) - 200-500ms
- [x] Pronunciation fixes (Viola→Vyola, Xander→Zander)
- [x] STT modes: COMMAND, REALTIME, AMBIENT
- [x] WebSocket streaming `/ws/transcribe`

#### Agent System
- [x] MetaAgent - Intent classification (pattern + LLM fallback)
- [x] InstantAgent - Time, date, math, jokes, facts (no LLM)
- [x] ActionAgent - Device control, compound commands
- [x] InteractionAgent - Complex conversations (LLM)
- [x] MemoryAgent - Store/retrieve/forget operations
- [x] ProfileAgent - Family profile generation/updates
- [x] SelfImprovementAgent - Claude Code CLI integration
- [x] AgentOrchestrator - Full pipeline coordination

#### Home Assistant
- [x] REST + WebSocket API integration
- [x] Entity registry with fuzzy matching
- [x] Smart entity resolution (areas, floors, groups)
- [x] Compound command parser ("X and Y")
- [x] Timer system (alarm, device-duration, delayed)
- [x] Real-time state change streaming
- [x] Custom conversation agent integration
- [x] HA log analysis (LLM-powered)

#### Memory System
- [x] Semantic memory storage (embeddings)
- [x] Episodic memory (conversations)
- [x] Working memory (short-term)
- [x] Vector similarity search
- [x] Memory extraction from conversations
- [x] Diary generation (LLM summaries)

#### Dashboard
- [x] Real-time activity feed
- [x] Chat interface (text + voice)
- [x] Memory management
- [x] HA entity browser
- [x] Configuration (LLM providers, models)
- [x] Logic browser (patterns, routing)
- [x] Self-improvement interface
- [x] Performance graphs (Chart.js)

#### Configuration
- [x] Activity-based LLM model selection
- [x] Free/Paid mode toggle
- [x] 12 LLM provider support
- [x] Encrypted secrets (Fernet)
- [x] Hot-reload for patterns/routing
- [x] YAML-based configuration

#### Observability
- [x] Prometheus metrics
- [x] Grafana dashboards
- [x] Pipeline signal logging
- [x] Request tracing
- [x] Logic diagnostics
- [x] Health monitoring

---

## Agent System Design

### Agent Responsibilities

| Agent | Purpose | Latency Target | LLM Required |
|-------|---------|----------------|--------------|
| **MetaAgent** | Intent classification + routing | <50ms | Pattern first, LLM fallback |
| **InstantAgent** | Quick facts, time, jokes | <5ms | No |
| **ActionAgent** | Device control | <100ms | Pattern first, LLM fallback |
| **InteractionAgent** | Complex conversations | <3s | Yes |
| **MemoryAgent** | Store/retrieve memories | <50ms | For extraction only |
| **ProfileAgent** | Family profile management | <2s | Yes |

### Intent Categories

```python
class IntentCategory(Enum):
    INSTANT = "instant"        # Time, date, jokes, facts
    ACTION = "action"          # Device control
    QUERY = "query"            # Information queries
    CONVERSATION = "conversation"  # Complex dialogue
    MEMORY = "memory"          # Remember/recall
    EMERGENCY = "emergency"    # Safety-critical
    GESTURE = "gesture"        # Physical input
    SELF_IMPROVEMENT = "self_improvement"  # Code fixes
    UNKNOWN = "unknown"
```

### Classification Flow

```
Input Text
    │
    ▼
┌─────────────────┐
│ Pattern Match   │ ← 378 compiled regex patterns
│ (instant check) │   Grouped by: emergency, instant, action, memory, query
└────────┬────────┘
         │
    Match found? ──Yes──▶ Return intent + sub_category + confidence
         │
         No
         │
         ▼
┌─────────────────┐
│   Heuristics    │ ← Keyword-based fallback
│                 │   "turn"/"switch" → action
└────────┬────────┘   "remember"/"what's my" → memory
         │
    High confidence? ──Yes──▶ Return intent
         │
         No
         │
         ▼
┌─────────────────┐
│   LLM Classify  │ ← OpenRouter/Ollama
│   (expensive)   │   Only if patterns fail
└─────────────────┘
```

---

## Intent Classification System

### Current Performance

```
Overall: 103/118 passed (87.3%)

By Intent:
  ✓ Memory:     100% (8/8)
  ✓ Emergency:  100% (10/10)
  ~ Action:      88% (29/33)
  ~ Instant:     84% (56/67)
```

### Pattern Structure

Patterns are defined as tuples: `(regex_pattern, sub_category)`

```python
INSTANT_PATTERNS = [
    # Time queries
    (r"^(what('s| is) (the )?)?(current )?time(\?)?$", "time"),
    (r"^what time is it(\?)?$", "time"),
    (r"^tell me the time(\?)?$", "time"),
    
    # Jokes
    (r"^tell me (a |another )?joke(\?)?$", "joke"),
    (r"^joke( please)?(\?)?$", "joke"),
    
    # Simple facts
    (r"^what colo(u)?r is (the )?(sky|grass|sun)(\?)?$", "simple_fact"),
    (r"^what is the capital of \w+(\?)?$", "simple_fact"),
    
    # ... 232 total instant patterns
]

ACTION_PATTERNS = [
    # Timer patterns (FIRST to avoid conflicts)
    (r"^(set|start) (a )?timer .*$", "timer"),
    (r"^(\d+\s*(?:minutes?|seconds?|hours?))\s+timer$", "timer"),
    
    # Light control
    (r"^(turn|switch) (on|off) .*light.*$", "switch"),
    (r"^(dim|brighten) .*light.*$", "light"),
    
    # ... 89 total action patterns
]
```

### Known Classification Issues

1. **Single-word commands fail**: "lights", "joke" → conversation (no pattern)
2. **Polite prefixes break patterns**: "can you set a timer" → query
3. **Wake word prefix breaks patterns**: "barnabee what time" → conversation
4. **Media vs Timer conflict**: "pause the TV" → timer instead of media

### Recommendations for v2.0

1. **Strip wake words before classification**: Remove "barnabee", "hey barnabee"
2. **Strip polite prefixes**: Remove "can you", "could you", "please"
3. **Add single-word command patterns**: "lights", "timer", "joke"
4. **Separate timer from media patterns**: Check for device context

---

## Home Assistant Integration

### Connection Details

```python
HA_URL = "http://192.168.86.60:8123"
# Token stored encrypted in Redis
```

### Entity Statistics

- **Total Entities:** 2,291
- **Devices:** 238
- **Areas:** 20
- **Automations:** 6
- **Integrations:** 64

### Smart Entity Resolution

```python
# Handles:
# - Fuzzy name matching: "living room light" → light.living_room_light
# - Area targeting: "all lights in kitchen" → area-based service call
# - Floor targeting: "lights downstairs" → all first floor lights
# - Group aliases: "kids rooms" → boys_room + girls_room + playroom
# - Typos: "trun" → "turn", "swtich" → "switch"
```

### Timer System

Three timer types using HA timer helpers:

```python
class TimerType(Enum):
    ALARM = "alarm"           # "wake me up in 30 minutes"
    DEVICE_DURATION = "device_duration"  # "turn on light for 5 minutes"
    DELAYED_ACTION = "delayed_action"    # "turn off light in 10 minutes"
```

Pool: `timer.barnabee_1` through `timer.barnabee_10`

---

## Performance Metrics

### Latency Breakdown (Measured)

| Component | Latency | Notes |
|-----------|---------|-------|
| **STT (GPU)** | 45ms | Parakeet TDT 0.6B v2 |
| **STT (CPU)** | 2,400ms | Distil-Whisper fallback |
| **Pattern Match** | <1ms | 378 patterns |
| **InstantAgent** | ~130ms total | No LLM |
| **ActionAgent** | ~200-500ms | Pattern + HA call |
| **InteractionAgent** | ~1,300-1,500ms | Ollama local |
| **InteractionAgent** | ~2,000-3,000ms | Cloud LLM |
| **TTS** | 200-500ms | Kokoro |
| **Full Pipeline (Instant)** | ~400-600ms | STT + Pattern + TTS |
| **Full Pipeline (LLM)** | ~2,000-3,500ms | STT + LLM + TTS |

### Bottleneck Analysis

```
InteractionAgent breakdown:
├── Memory retrieval:      ~200-300ms (can skip for simple queries)
├── Context loading:       ~100-200ms (profile, HA state)
├── LLM API call:          ~800-1,200ms (Ollama) / ~1,500-2,500ms (cloud)
├── Response processing:   ~50-100ms
└── Total:                 ~1,200-1,800ms
```

### Cost (Free Tier)

Using `meta-llama/llama-3.3-70b-instruct:free` for all activities:
- **Input tokens:** $0.00
- **Output tokens:** $0.00
- **Rate limits:** Lower than paid

---

## What Worked Well

### 1. Multi-Tier STT Architecture
- GPU primary (45ms) with CPU fallback (2.4s) works great
- Zero-latency routing via cached health check
- Azure fallback for mobile provides full coverage

### 2. Pattern-Based Classification
- 87% accuracy with pure regex patterns
- Sub-millisecond classification
- Easy to add new patterns
- Debuggable (can see which pattern matched)

### 3. Activity-Based LLM Config
- Different models per task type
- Easy to optimize cost vs quality
- Free/Paid toggle is very useful

### 4. Compound Command Parser
- "Turn on the lights and play music" works
- Regex-based, no LLM needed
- Handles typos

### 5. Family Profile System
- SkyrimNet-inspired biography pattern
- Privacy-aware context injection
- HA person entity integration for location

### 6. Self-Improvement Agent
- Claude Code CLI integration works
- Two-phase approval (diagnosis → implementation)
- Safety scoring prevents dangerous changes

### 7. Dashboard Design
- Real-time activity feed is invaluable
- Chat interface for testing
- Logic browser for debugging patterns

### 8. Child Safety Monitoring (IMPORTANT - NOT DOCUMENTED ELSEWHERE)

Built-in parental monitoring for children's conversations:

```python
# Monitored family members
CHILD_NAMES = {"penelope", "xander", "zachary", "viola"}

# Concerning patterns that trigger immediate alerts
CONCERNING_PATTERNS = [
    # Self-harm or suicidal ideation
    r"\bwant(?:s?| to)?\s+(?:hurt|kill|harm|cut)\s+(?:myself|me)\b",
    r"\bwish\s+(?:i|I)\s+(?:was|were)\s+dead\b",
    r"\bdon'?t\s+want\s+to\s+(?:live|be alive|be here)\b",
    # Feelings of isolation/depression
    r"\bno\s*one\s+(?:likes|loves|cares about)\s+me\b",
    r"\beveryone\s+hates\s+me\b",
    # Bullying
    r"\b(?:being|getting|got)\s+bullied\b",
    r"\bkids?\s+(?:are|were)\s+(?:mean|cruel)\s+to\s+me\b",
    # Dangerous activities
    r"\btried\s+to\s+(?:run away|sneak out)\b",
    # Abuse indicators
    r"\b(?:someone|they|he|she)\s+touched\s+me\b",
    r"\bscared\s+of\s+(?:going home|being home)\b",
]
```

**When triggered:**
1. Logs to immutable audit trail
2. Sends HA notification to parents' phones (`mobile_app_thomphone`)
3. Response still generated compassionately

**Location:** `src/barnabeenet/agents/orchestrator.py` lines 43-75

### 9. Audit Log System (IMPORTANT - NOT DOCUMENTED ELSEWHERE)

Immutable append-only conversation log for compliance and oversight:

**Location:** `src/barnabeenet/services/audit/log.py`

**Features:**
- Cannot be modified or deleted (compliance requirement)
- "Deleted" entries are soft-deleted but remain searchable
- Indexed by speaker, room, date, content
- Flagged entries for parental alerts
- Separate from memory system (survives "forget this" requests)

```python
@dataclass
class AuditLogEntry:
    entry_id: str
    timestamp: datetime
    conversation_id: str
    speaker: str | None
    room: str
    user_text: str
    assistant_response: str
    intent: str
    agent: str
    triggered_alert: bool
    alert_reason: str | None
    was_deleted: bool  # Soft delete only
```

**Redis keys:** `barnabeenet:audit:log:*`, `barnabeenet:audit:alerts`

### 10. Conversation Context Manager

Token-aware conversation management for long dialogues:

**Location:** `src/barnabeenet/services/conversation/context_manager.py`

**Features:**
- Token estimation (1 token ≈ 4 characters)
- Auto-summarization at 40,000 tokens (80% of 50k limit)
- Keeps 6 most recent turns in full detail
- Summarizes older turns to maintain context
- Room/device-based conversation tracking

---

## What Didn't Work / Pain Points

### 1. LogicRegistry vs Hardcoded Patterns
**Problem:** YAML patterns override hardcoded patterns, but YAML file is incomplete.
**Impact:** Only 11 patterns loaded instead of 378.
**Fix:** Either keep patterns in code OR maintain YAML completely.

### 2. Pattern Fragility
**Problem:** Patterns are brittle to variations.
**Examples:**
- "what time is it" ✓ but "barnabee what time is it" ✗
- "tell me a joke" ✓ but "joke" ✗
- "set a timer for 5 minutes" ✓ but "can you set a timer" ✗

**Root Cause:** Regex anchors (`^...$`) require exact match.

### 3. Memory Retrieval Overhead
**Problem:** Every query does memory retrieval (~200-300ms).
**Impact:** Simple factual questions ("why is the sky blue") don't need memory.
**Fix:** Added `_is_simple_factual_query()` to skip memory for general knowledge.

### 4. LLM Latency
**Problem:** Even fast LLMs (Ollama local) add 800-1200ms.
**Impact:** "Sub-second responses" impossible for LLM queries.
**Mitigation:** Maximize instant patterns, minimize LLM fallback.

### 5. HA Token Management
**Problem:** Token encryption with Fernet requires master key.
**Impact:** If master key lost, all secrets unreadable.
**Workaround:** Hardcoded fallback token (not ideal).

### 6. WebSocket Reconnection
**Problem:** HA WebSocket sometimes drops, needs reconnect.
**Impact:** State changes not received.
**Fix:** Added `ensure_connected()` with auto-reconnect.

### 7. Dashboard Complexity
**Problem:** Single-page app with 3000+ lines of JavaScript.
**Impact:** Hard to maintain, no component structure.
**Recommendation:** Use a framework (Vue, React, Svelte).

### 8. Test Discovery
**Problem:** pytest-testmon sometimes misses changed tests.
**Impact:** Have to run `--no-testmon` periodically.

---

## Features Not Implemented (Deferred)

### High Priority for v2.0

| Feature | Description | Why Deferred |
|---------|-------------|--------------|
| **Speaker ID (ECAPA-TDNN)** | Voice-based speaker recognition | Complexity, HA user is sufficient |
| **Proactive Agent** | Time-based notifications, suggestions | Spec only |
| **Mobile Client** | Android app with BT audio capture | Time |

### Medium Priority

| Feature | Description | Why Deferred |
|---------|-------------|--------------|
| **Evolver Agent** | Autonomous self-improvement | Safety concerns |
| **ViewAssist Integration** | Tablet displays | APIs ready, needs testing |
| **Streaming LLM Responses** | Word-by-word output | HA doesn't support push |
| **SQLite Persistence** | Replace Redis for memories | Redis working fine |

### Low Priority / Future

| Feature | Description |
|---------|-------------|
| AR Glasses (Even Realities G1) | Overlay interface |
| Wearable (Amazfit) | Watch commands |
| ThinkSmart View | Conference room display |
| Voice Cloning (XTTS-v2) | Custom TTS voice |
| Wake Word Detection | On-device "Hey Barnabee" |

---

## Override System (Implemented but Underutilized)

**Location:** `config/overrides.yaml` (318 lines)

The override system is **fully implemented** with hot-reload support, but most rules are disabled by default. v2.0 should leverage this more.

### Structure

```yaml
version: "1.0"

# User-specific overrides
user_overrides:
  kids_restricted:
    name: "Kids Restricted Mode"
    enabled: false  # Can enable via dashboard
    users: ["penelope", "xander", "viola"]
    rules:
      - action: "block"
        domain: "lock"
        message: "Ask a parent to help with locks."
      - action: "restrict_area"
        domain: "light"
        allowed_areas: ["boys_room", "girls_room", "playroom"]
        message: "You can only control lights in your room."

# Room-specific overrides
room_overrides:
  bedroom_quiet:
    name: "Bedroom Quiet Mode"
    enabled: true  # ACTIVE
    rooms: ["master_bedroom", "boys_room", "girls_room"]
    time_range:
      start: "21:00"
      end: "07:00"
    rules:
      - action: "modify_response"
        setting: "tts_volume"
        value: 0.5  # 50% volume at night

# Time-based overrides
time_overrides:
  weekend_relaxed:
    name: "Weekend Relaxed Mode"
    days: ["saturday", "sunday"]
    rules:
      - action: "modify"
        setting: "confirmation_threshold"
        value: 0.6  # Less cautious on weekends

# Global overrides
global_overrides:
  away_mode:
    name: "Away Mode"
    description: "When nobody home"
    enabled: false
    trigger:
      state: "not_home"
      entity: "group.family"
```

### Implemented Actions

| Action | Description |
|--------|-------------|
| `block` | Prevent action with message |
| `restrict_area` | Limit to specific rooms |
| `allow_only` | Whitelist domains/areas |
| `modify_response` | Change TTS settings |
| `modify` | Change any setting |
| `redirect` | Send elsewhere |

### V2 Recommendation

- Enable more defaults
- Add dashboard UI for rule toggling
- Consider machine learning to suggest rules based on usage patterns

---

## Recommendations for v2.0

### Architecture Changes

1. **Separate Intent Classification Service**
   - Dedicated microservice for pattern matching
   - gRPC for low latency
   - Cache recent classifications

2. **Use a Real Frontend Framework**
   - Vue.js or Svelte for dashboard
   - Component-based architecture
   - TypeScript for type safety

3. **Implement Streaming Responses**
   - WebSocket push for partial responses
   - "Thinking..." indicator while LLM runs
   - Progressive enhancement

4. **Simplify Agent Structure**
   ```
   v2.0 Agents:
   ├── RouterAgent (replaces MetaAgent)
   │   └── Pure classification, no LLM
   ├── QuickAgent (replaces InstantAgent)
   │   └── All pattern-matched responses
   ├── DeviceAgent (replaces ActionAgent)
   │   └── HA integration only
   ├── ChatAgent (replaces InteractionAgent)
   │   └── LLM conversations only
   └── MemoryAgent
       └── Storage + retrieval only
   ```

5. **Dedicated Timer Service**
   - Separate from ActionAgent
   - Native HA timer integration
   - Notification callbacks

### Pattern System Improvements

1. **Pre-processing Layer**
   ```python
   def preprocess(text: str) -> str:
       # Strip wake words
       text = re.sub(r"^(hey |hi )?(barnabee|barney)\s*[,.]?\s*", "", text, flags=re.I)
       # Strip polite prefixes
       text = re.sub(r"^(can you |could you |would you |please )\s*", "", text, flags=re.I)
       # Strip trailing punctuation
       text = text.rstrip(".!?,;:")
       return text.strip()
   ```

2. **Fuzzy Pattern Matching**
   - Use Levenshtein distance for typo tolerance
   - Weighted keyword matching as fallback
   - ML-based intent classification as final fallback

3. **Pattern Groups with Priority**
   ```yaml
   patterns:
     emergency:  # Priority 1 - Check first
       priority: 1
       patterns: [...]
     instant:    # Priority 2
       priority: 2
       patterns: [...]
     action:     # Priority 3
       priority: 3
       patterns: [...]
   ```

### Infrastructure Changes

1. **Container-Based Deployment**
   - Docker Compose for all services
   - Easier to rebuild and deploy
   - Better isolation

2. **Ollama as Primary LLM**
   - Local GPU inference
   - No API costs
   - Sub-second for small models

3. **Separate Databases**
   - Redis for cache/pub-sub only
   - SQLite/PostgreSQL for persistent data
   - Vector DB (Chroma/Milvus) for embeddings

---

## Code Statistics

### Lines of Code

| Category | Count |
|----------|-------|
| **Total Python Files** | 100 |
| **Total Lines** | ~27,000 |
| **Test Files** | 28 |
| **Agent Code** | ~12,000 lines |
| **Service Code** | ~8,000 lines |
| **API Routes** | ~4,000 lines |

### Key Files by Size

| File | Lines | Purpose |
|------|-------|---------|
| `agents/instant.py` | 169,839 | InstantAgent (huge pattern list) |
| `agents/orchestrator.py` | 102,025 | Pipeline coordination |
| `agents/self_improvement.py` | 86,431 | Claude Code integration |
| `agents/interaction.py` | 72,934 | LLM conversations |
| `agents/meta.py` | 66,763 | Intent classification |
| `agents/action.py` | 60,905 | Device control |
| `services/entity_queries.py` | 50,587 | HA entity resolution |
| `services/timers.py` | 48,122 | Timer management |

### Dependencies (requirements.txt)

```
fastapi>=0.109.0
uvicorn>=0.27.0
pydantic>=2.0.0
redis>=5.0.0
httpx>=0.26.0
structlog>=24.1.0
sentence-transformers>=2.2.0
numpy>=1.26.0
soundfile>=0.12.0
```

### Dependencies (requirements-gpu.txt)

```
# Additional for GPU worker
torch>=2.1.0
nemo-toolkit>=1.22.0
faster-whisper>=1.0.0
```

---

## Configuration Reference

### Environment Variables

```bash
# Core
BARNABEENET_HOST=0.0.0.0
BARNABEENET_PORT=8000
BARNABEENET_DEBUG=false
BARNABEENET_MASTER_KEY=<fernet-key>

# Redis
REDIS_URL=redis://localhost:6379

# Home Assistant
HA_URL=http://192.168.86.60:8123
HA_TOKEN=<long-lived-token>

# GPU Worker
GPU_WORKER_URL=http://192.168.86.61:8001

# Azure STT (optional)
AZURE_SPEECH_KEY=<key>
AZURE_SPEECH_REGION=eastus

# LLM (OpenRouter)
OPENROUTER_API_KEY=<key>

# Ollama (local)
OLLAMA_URL=http://localhost:11434
```

### config/llm.yaml Structure

```yaml
openrouter:
  site_url: "https://barnabeenet.local"
  site_name: "BarnabeeNet"

agents:
  meta:
    model: "meta-llama/llama-3.3-70b-instruct:free"
    temperature: 0.2
    max_tokens: 200
  instant:
    model: "meta-llama/llama-3.3-70b-instruct:free"
    temperature: 0.3
    max_tokens: 300
  # ... etc

activities:
  meta.classify_intent:
    model: "meta-llama/llama-3.3-70b-instruct:free"
    priority: speed
  interaction.respond:
    model: "meta-llama/llama-3.3-70b-instruct:free"
    priority: quality
  # ... 16+ activities
```

---

## API Endpoints Reference

### Core Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/chat` | GET/POST | Simple chat API |
| `/api/v1/voice/process` | POST | Text-only pipeline |
| `/api/v1/voice/pipeline` | POST | Full voice pipeline |
| `/api/v1/input/text` | POST | Quick text input |
| `/api/v1/input/audio` | POST | Audio file upload |

### Configuration

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/config/providers` | GET | List LLM providers |
| `/api/v1/config/activities` | GET/PUT | Activity configs |
| `/api/v1/config/mode` | GET/POST | Free/Paid toggle |
| `/api/v1/config/models` | GET | Available models |

### Home Assistant

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/homeassistant/status` | GET | Connection status |
| `/api/v1/homeassistant/entities` | GET | Entity list |
| `/api/v1/homeassistant/areas` | GET | Area list |
| `/api/v1/homeassistant/call` | POST | Service call |

### Memory

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/memory` | GET | List memories |
| `/api/v1/memory/search` | POST | Semantic search |
| `/api/v1/memory` | POST | Store memory |
| `/api/v1/memory/{id}` | DELETE | Delete memory |

### Dashboard

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/ws/activity` | WebSocket | Real-time feed |
| `/ws/dashboard` | WebSocket | Dashboard updates |
| `/api/v1/dashboard/stats` | GET | System stats |
| `/api/v1/dashboard/metrics` | GET | Performance metrics |

### Dashboard Contract

**IMPORTANT:** A formal API contract exists to protect dashboard stability.

**Location:** `src/barnabeenet/dashboard_contract.yaml` (165 lines)

The self-improvement agent is **prohibited** from breaking these endpoints. Each page specifies:
- Required endpoints (method, path)
- Required response fields
- Required WebSocket connections

```yaml
# Example from contract
pages:
  dashboard:
    required_endpoints:
      - method: GET
        path: /api/v1/dashboard/status
        response_fields: [status, uptime_seconds, version, components]
      - method: GET
        path: /api/v1/dashboard/stats
        response_fields: [total_requests_24h, total_cost_24h, avg_latency_ms, error_rate_percent]
    required_websocket: /api/v1/ws/activity

  memory:
    required_endpoints:
      - method: GET
        path: /api/v1/memory/stats
        response_fields: [total_memories, by_type, recent_24h, recent_7d, storage_backend]
```

**Test:** `pytest tests/test_dashboard_contract.py` validates compliance.

---

## How to Get Back to This Point

This section provides **complete step-by-step instructions** to rebuild the entire BarnabeeNet infrastructure from scratch on new hardware.

### Infrastructure Overview

| Machine | Purpose | IP | OS |
|---------|---------|----|----|
| **Battlestation** | Proxmox host | 192.168.86.50 | Proxmox VE 8.x |
| **BarnabeeNet VM** | Main server | 192.168.86.51 | NixOS 24.11 |
| **Home Assistant VM** | Smart home | 192.168.86.60 | HAOS |
| **Man-of-war (WSL)** | GPU worker | 192.168.86.61 | Ubuntu 22.04 WSL2 |

---

### PART 1: Proxmox Server Setup (Battlestation)

#### 1.1 Install Proxmox VE

```bash
# Download Proxmox VE 8.x ISO from proxmox.com
# Boot from USB, install to SSD
# Set static IP: 192.168.86.50
# Configure hostname: battlestation
```

#### 1.2 Post-Install Configuration

```bash
# SSH into Proxmox
ssh root@192.168.86.50

# Remove enterprise repo (unless licensed)
rm /etc/apt/sources.list.d/pve-enterprise.list

# Add no-subscription repo
echo "deb http://download.proxmox.com/debian/pve bookworm pve-no-subscription" > /etc/apt/sources.list.d/pve-no-subscription.list

# Update
apt update && apt upgrade -y

# Install useful tools
apt install -y vim htop tmux
```

#### 1.3 Storage Configuration

- Create ZFS pool or LVM for VM storage
- Recommended: 100GB+ for BarnabeeNet VM, 32GB for Home Assistant

---

### PART 2: BarnabeeNet VM (NixOS)

#### 2.1 Create VM in Proxmox

```
VM ID: 101
Name: barnabeenet
CPU: 6 cores (host type)
RAM: 8192 MB
Disk: 100 GB (VirtIO SCSI)
Network: VirtIO (bridge vmbr0)
Boot: UEFI (OVMF)
```

#### 2.2 Install NixOS

```bash
# Download NixOS 24.11 minimal ISO
# Mount to VM and boot

# During install:
# - Set hostname: barnabeenet
# - Create user: thom (wheel group)
# - Enable SSH
# - Set static IP: 192.168.86.51
```

#### 2.3 Configure NixOS

Create `/etc/nixos/configuration.nix`:

```nix
{ config, pkgs, ... }:

{
  imports = [ ./hardware-configuration.nix ];

  # Boot
  boot.loader.systemd-boot.enable = true;
  boot.loader.efi.canTouchEfiVariables = true;

  # Network
  networking.hostName = "barnabeenet";
  networking.interfaces.ens18.ipv4.addresses = [{
    address = "192.168.86.51";
    prefixLength = 24;
  }];
  networking.defaultGateway = "192.168.86.1";
  networking.nameservers = [ "192.168.86.1" "8.8.8.8" ];
  networking.firewall.allowedTCPPorts = [ 22 8000 6379 9090 3000 ];

  # Timezone
  time.timeZone = "America/New_York";

  # User
  users.users.thom = {
    isNormalUser = true;
    extraGroups = [ "wheel" "networkmanager" ];
    openssh.authorizedKeys.keys = [
      # Add your SSH public key here
      "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOP6MkvsXW5bgQmDoSE6uWdckVgzhVFxh4xOuiiEpsBG"
    ];
  };

  # Podman for containers
  virtualisation.podman = {
    enable = true;
    dockerCompat = true;
    defaultNetwork.settings.dns_enabled = true;
  };

  # Packages
  environment.systemPackages = with pkgs; [
    vim git curl wget htop tmux
    podman-compose
    python312 python312Packages.pip python312Packages.virtualenv
    sqlite redis
    jq yq tree ffmpeg
  ];

  # SSH
  services.openssh.enable = true;
  services.openssh.settings.PasswordAuthentication = false;

  # Nix features
  nix.settings.experimental-features = [ "nix-command" "flakes" ];

  system.stateVersion = "24.11";
}
```

Apply configuration:

```bash
sudo nixos-rebuild switch
```

#### 2.4 Clone and Setup BarnabeeNet

```bash
# As user thom
cd ~
git clone git@github.com:trfife/BarnabeeNet.git barnabeenet
cd barnabeenet

# Create virtual environment
python3.12 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

#### 2.5 Create Data Directories

```bash
mkdir -p ~/data/redis ~/data/prometheus ~/data/grafana
```

#### 2.6 Start Infrastructure Services

```bash
cd ~/barnabeenet/infrastructure
podman-compose up -d
```

#### 2.7 Configure Environment

```bash
cd ~/barnabeenet

# Copy example environment
cp .env.example .env

# Generate encryption key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Copy output to .env as BARNABEENET_MASTER_KEY

# Edit .env with your values:
vim .env
```

Required `.env` variables:

```bash
# Required
BARNABEENET_MASTER_KEY=<your-fernet-key>
HA_URL=http://192.168.86.60:8123
HA_TOKEN=<your-ha-long-lived-token>

# Optional (for cloud LLM)
OPENROUTER_API_KEY=<your-openrouter-key>

# GPU Worker
GPU_WORKER_URL=http://192.168.86.61:8001
```

#### 2.8 Create Systemd Service

Create `/etc/nixos/barnabeenet.nix`:

```nix
{ config, pkgs, ... }:

{
  systemd.services.barnabeenet = {
    description = "BarnabeeNet Smart Home Assistant";
    after = [ "network.target" ];
    wantedBy = [ "multi-user.target" ];

    serviceConfig = {
      Type = "simple";
      User = "thom";
      WorkingDirectory = "/home/thom/barnabeenet";
      ExecStart = "/home/thom/barnabeenet/.venv/bin/uvicorn barnabeenet.main:app --host 0.0.0.0 --port 8000";
      Restart = "always";
      RestartSec = 5;
      EnvironmentFile = "/home/thom/barnabeenet/.env";
    };
  };
}
```

Add to `configuration.nix` imports and rebuild:

```bash
sudo nixos-rebuild switch
sudo systemctl start barnabeenet
sudo systemctl status barnabeenet
```

---

### PART 3: Man-of-war WSL2 Setup (GPU Worker)

#### 3.1 Install WSL2 on Windows

```powershell
# In PowerShell as Admin
wsl --install -d Ubuntu-22.04
```

#### 3.2 Configure WSL2 for GPU

Create `%UserProfile%\.wslconfig`:

```ini
[wsl2]
memory=32GB
processors=8
swap=8GB
localhostForwarding=true

[experimental]
autoMemoryReclaim=gradual
```

#### 3.3 Install NVIDIA CUDA in WSL

```bash
# In WSL
# Install NVIDIA CUDA toolkit
wget https://developer.download.nvidia.com/compute/cuda/repos/wsl-ubuntu/x86_64/cuda-keyring_1.1-1_all.deb
sudo dpkg -i cuda-keyring_1.1-1_all.deb
sudo apt update
sudo apt install -y cuda-toolkit-12-3

# Verify GPU access
nvidia-smi
```

#### 3.4 Clone BarnabeeNet

```bash
cd ~
mkdir -p projects
cd projects
git clone git@github.com:trfife/BarnabeeNet.git barnabeenet
cd barnabeenet
```

#### 3.5 Create GPU Virtual Environment

```bash
python3.12 -m venv .venv-gpu
source .venv-gpu/bin/activate

# Install GPU requirements
pip install --upgrade pip
pip install -r requirements-gpu.txt

# Install PyTorch with CUDA
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

#### 3.6 Configure GPU Worker

```bash
# Copy environment
cp .env.example .env

# Edit with GPU-specific settings
vim .env
```

GPU Worker `.env`:

```bash
# GPU Worker mode
WORKER_MODE=gpu
WORKER_HOST=0.0.0.0
WORKER_PORT=8001

# STT Model (Parakeet)
STT_MODEL=nvidia/parakeet-tdt-0.6b-v2
STT_DEVICE=cuda

# TTS Model (Kokoro)
TTS_MODEL=kokoro-v0_19
TTS_DEVICE=cuda
```

#### 3.7 Start GPU Worker

```bash
cd ~/projects/barnabeenet
source .venv-gpu/bin/activate
./scripts/start-gpu-worker.sh

# Or manually:
uvicorn workers.gpu_worker:app --host 0.0.0.0 --port 8001
```

#### 3.8 Configure Windows Firewall

```powershell
# In PowerShell as Admin
New-NetFirewallRule -DisplayName "WSL GPU Worker" -Direction Inbound -LocalPort 8001 -Protocol TCP -Action Allow
```

#### 3.9 Get WSL IP for VM Connection

```bash
# In WSL
ip addr show eth0 | grep inet
# Usually 172.x.x.x - need port forwarding
```

For stable access, set up port forwarding in Windows:

```powershell
# Forward port 8001 from Windows to WSL
netsh interface portproxy add v4tov4 listenport=8001 listenaddress=0.0.0.0 connectport=8001 connectaddress=$(wsl hostname -I)
```

#### 3.10 Install Ollama (Local LLM - RECOMMENDED)

Ollama provides fast local LLM inference on the GPU. Much faster than cloud APIs.

```bash
# In WSL - Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Start Ollama service
sudo systemctl enable ollama
sudo systemctl start ollama

# Pull recommended models
ollama pull llama3.2:3b      # Fast, good for simple queries
ollama pull llama3.2:1b      # Fastest, basic tasks
ollama pull phi3:mini        # Good reasoning, small

# Verify
ollama list
curl http://localhost:11434/api/tags
```

#### 3.11 Configure Ollama for Network Access

```bash
# Configure Ollama to listen on all interfaces
sudo mkdir -p /etc/systemd/system/ollama.service.d
sudo tee /etc/systemd/system/ollama.service.d/override.conf << 'EOF'
[Service]
Environment="OLLAMA_HOST=0.0.0.0"
EOF

sudo systemctl daemon-reload
sudo systemctl restart ollama

# Verify external access
curl http://localhost:11434/api/tags
```

#### 3.12 SSH Tunnel for Ollama (VM Access)

The VM needs to access Ollama on WSL. Set up a persistent SSH tunnel:

```bash
# Create tunnel script
cat > ~/projects/barnabeenet/scripts/ollama-tunnel.sh << 'EOF'
#!/bin/bash
# Persistent SSH tunnel for Ollama access from VM
while true; do
    echo "$(date): Starting SSH tunnel to VM for Ollama..."
    ssh -N -R 11434:localhost:11434 thom@192.168.86.51
    echo "$(date): Tunnel closed, reconnecting in 5s..."
    sleep 5
done
EOF

chmod +x ~/projects/barnabeenet/scripts/ollama-tunnel.sh

# Run in background (use screen or tmux for persistence)
screen -dmS ollama_tunnel ~/projects/barnabeenet/scripts/ollama-tunnel.sh

# Verify from VM
ssh thom@192.168.86.51 'curl -s http://localhost:11434/api/tags'
```

#### 3.13 Add Windows Port Forwarding for Ollama

```powershell
# In PowerShell as Admin
netsh interface portproxy add v4tov4 listenport=11434 listenaddress=0.0.0.0 connectport=11434 connectaddress=$(wsl hostname -I)

# Firewall rule
New-NetFirewallRule -DisplayName "WSL Ollama" -Direction Inbound -LocalPort 11434 -Protocol TCP -Action Allow
```

---

### PART 4: Home Assistant Setup

#### 4.1 Create Home Assistant VM in Proxmox

```
VM ID: 102
Name: homeassistant
CPU: 2 cores
RAM: 4096 MB
Disk: 32 GB (use HAOS qcow2 image)
Network: VirtIO (bridge vmbr0)
```

Download HAOS qcow2 image and import to VM.

#### 4.2 Configure Home Assistant

1. Access at `http://192.168.86.60:8123`
2. Complete initial setup
3. Create Long-Lived Access Token:
   - Profile → Security → Long-Lived Access Tokens → Create Token
   - Save token to BarnabeeNet `.env` as `HA_TOKEN`

#### 4.3 Create Timer Helpers

In Home Assistant, create 10 timer helpers:
- `timer.barnabee_1` through `timer.barnabee_10`

Settings → Devices & Services → Helpers → Create Helper → Timer

#### 4.4 Register BarnabeeNet as Conversation Agent

In Home Assistant `configuration.yaml`:

```yaml
# BarnabeeNet integration
rest_command:
  barnabeenet_process:
    url: "http://192.168.86.51:8000/api/v1/voice/pipeline"
    method: POST
    headers:
      Content-Type: "application/json"
    payload: '{"text": "{{ text }}", "context": {"user_id": "{{ user_id }}", "room": "{{ room }}"}}'
```

---

### PART 5: Verification

#### 5.1 Test VM Server

```bash
# From any machine
curl http://192.168.86.51:8000/health
# Should return: {"status": "healthy", ...}

curl "http://192.168.86.51:8000/api/v1/chat?text=what%20time%20is%20it"
# Should return time response
```

#### 5.2 Test GPU Worker

```bash
# From VM
curl http://192.168.86.61:8001/health
# Should return: {"status": "healthy", "gpu": true, ...}
```

#### 5.3 Test Dashboard

Open browser: `http://192.168.86.51:8000/`

- Dashboard should show activity feed
- Chat should work
- Memory page should show stats

#### 5.4 Run Test Suite

```bash
# On VM
cd ~/barnabeenet
source .venv/bin/activate
pytest -xvs
```

---

### PART 6: SSH Key Setup

For passwordless SSH between machines:

```bash
# On Man-of-war WSL, generate key
ssh-keygen -t ed25519 -C "manofwar-wsl"

# Copy to VM
ssh-copy-id thom@192.168.86.51

# Test
ssh thom@192.168.86.51 'echo "SSH works!"'
```

---

### Quick Reference: IP Addresses

| Service | URL |
|---------|-----|
| BarnabeeNet API | http://192.168.86.51:8000 |
| BarnabeeNet Dashboard | http://192.168.86.51:8000 |
| GPU Worker | http://192.168.86.61:8001 |
| Home Assistant | http://192.168.86.60:8123 |
| Redis | 192.168.86.51:6379 |
| Prometheus | http://192.168.86.51:9090 |
| Grafana | http://192.168.86.51:3000 |
| Proxmox | https://192.168.86.50:8006 |

---

## Key Files to Review for v2.0

1. **Intent Classification**: `src/barnabeenet/agents/meta.py`
2. **Pattern Definitions**: All `*_PATTERNS` lists in meta.py
3. **Agent Orchestration**: `src/barnabeenet/agents/orchestrator.py`
4. **HA Integration**: `src/barnabeenet/services/homeassistant/`
5. **Dashboard**: `src/barnabeenet/static/app.js`
6. **Test Coverage**: `tests/test_intent_coverage.py`
7. **LLM Config**: `config/llm.yaml`

---

## Final Notes

BarnabeeNet v1.0 proved the concept of a privacy-first, multi-agent smart home assistant. The key learnings:

1. **Pattern matching is powerful** — 87% accuracy without any LLM
2. **Latency requires careful design** — Every ms matters for voice
3. **Local LLM is viable** — Ollama on consumer GPU works well
4. **HA integration is complex** — REST, WebSocket, timers, registries
5. **Dashboard is essential** — Can't debug without visibility

For v2.0, focus on:
1. Simpler, more maintainable code
2. Better pattern preprocessing
3. Streaming responses
4. Mobile client
5. Proactive notifications

Good luck with v2.0! 🐝

---

## Additional Reference: Family Members

### The Fife Family

| Name | Role | HA Person Entity | Notes |
|------|------|------------------|-------|
| **Thom** | Primary (Dad) | `person.thom` | Main developer |
| **Elizabeth** | Spouse (Mom) | `person.elizabeth` | - |
| **Penelope** | Child | `person.penelope` | Older daughter |
| **Viola** | Child | `person.viola` | Pronunciation: "Vyola" |
| **Xander** | Child | `person.xander` | Pronunciation: "Zander" |
| **Zachary** | Child | `person.zachary` | Youngest |

### Pets
- **Bagheera** - Cat
- **Shere Khan** - Cat

---

## Additional Reference: All Prompts

### src/barnabeenet/prompts/

| File | Purpose |
|------|---------|
| `meta_agent.txt` | Intent classification prompt |
| `instant_agent.txt` | Quick response generation (fallback) |
| `action_agent.txt` | Device control parsing |
| `interaction_agent.txt` | Barnabee persona for conversations |
| `memory_agent.txt` | Memory generation, extraction, and querying |

### Meta Agent Prompt
```
You are an intent classifier for a smart home assistant.
Classify the user's request into one of these categories:
- instant: Simple queries (time, date, greetings, basic math)
- action: Device control (turn on/off, set temperature, lock doors)
- query: Information requests (weather, sensor states, complex questions)
- conversation: General chat, advice, complex dialogue
- memory: Remember or recall information
- emergency: Safety concerns (fire, medical, security)

Respond with JSON: {"intent": "<category>", "confidence": 0.0-1.0, "sub_category": "optional detail"}
```

### Interaction Agent Prompt
```
You are Barnabee, the AI assistant for the Fife family household.

Personality:
- Helpful and straightforward
- Patient, especially with children
- No gimmicks, puns, or theatrical personality
- Just a capable, reliable assistant

Communication Style:
- Keep responses brief (1-2 sentences when possible)
- Talk naturally, like a normal person
- Don't use fancy language or act like a butler
- For children, use simpler language
```

---

## Additional Reference: All Config Files

### config/

| File | Purpose | Hot-Reload |
|------|---------|------------|
| `llm.yaml` | LLM model configuration per agent/activity | No (restart required) |
| `llm-free.yaml` | Free tier model configuration | No |
| `llm-paid.yaml` | Paid tier model configuration | No |
| `patterns.yaml` | Intent classification regex patterns | Yes |
| `routing.yaml` | Intent → Agent mapping and priorities | Yes |
| `overrides.yaml` | User/room/time behavior overrides | Yes |

### patterns.yaml Structure
```yaml
version: "1.0"
emergency:
  fire:
    pattern: ".*(fire|smoke|burning|flames).*"
    sub_category: "fire"
    confidence: 0.99
    enabled: true
    examples:
      - "there's a fire in the kitchen"
      - "I smell smoke"

instant:
  time_query:
    pattern: "^(what('s| is) (the )?)?(current )?time(\\?)?$"
    sub_category: "time"
    confidence: 0.95
    examples:
      - "what time is it"
```

### routing.yaml Structure
```yaml
version: "1.0"
defaults:
  unknown_intent: "interaction"
  pattern_match_timeout_ms: 50

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
  # ... etc

confidence_thresholds:
  pattern_match: 0.85
  heuristic: 0.70
  llm_fallback: 0.60

memory_retrieval:
  enabled_for: ["conversation", "query", "memory"]
  disabled_for: ["instant", "gesture", "emergency"]
  max_memories: 5
```

---

## Additional Reference: All Scripts

### scripts/

| Script | Purpose | Run On |
|--------|---------|--------|
| `start-gpu-worker.sh` | Start Parakeet STT worker | Man-of-war (WSL) |
| `stop-gpu-worker.sh` | Stop GPU worker | Man-of-war (WSL) |
| `deploy-vm.sh` | Deploy code to VM and restart | Man-of-war (WSL) |
| `restart.sh` | Restart BarnabeeNet service | VM |
| `status.sh` | Check service status | VM |
| `ollama-tunnel.sh` | SSH tunnel for Ollama access | Man-of-war (WSL) |
| `debug-logs.sh` | Query logs by type | VM |
| `switch-llm-config.sh` | Switch between free/paid configs | VM |
| `clear_all_data.sh` | Clear all Redis data | VM |
| `clear_redis_data.py` | Python script to clear Redis | VM |
| `validate.sh` | Pre-commit validation | Any |
| `pre-commit.sh` | Git pre-commit hook | Any |

### Key Script: deploy-vm.sh
```bash
#!/bin/bash
# Deploy to VM and restart
git push
ssh thom@192.168.86.51 'cd ~/barnabeenet && git pull && bash scripts/restart.sh'
```

### Key Script: ollama-tunnel.sh
```bash
#!/bin/bash
# Persistent SSH tunnel for Ollama access from VM
while true; do
    echo "$(date): Starting SSH tunnel to VM for Ollama..."
    ssh -N -R 11434:localhost:11434 thom@192.168.86.51
    echo "$(date): Tunnel closed, reconnecting in 5s..."
    sleep 5
done
```

---

## Additional Reference: Key Documentation

### docs/ (39 files)

**Architecture & Design:**
- `BarnabeeNet_Technical_Architecture.md` - Full technical spec (4000+ lines)
- `architecture.md` - As-built architecture
- `BarnabeeNet_MetaAgent_Specification.md` - Intent classification design
- `BarnabeeNet_Family_Profile_System.md` - Profile agent design (SkyrimNet-inspired)

**Implementation:**
- `IMPLEMENTATION_STATUS.md` - Performance improvements status
- `IMPLEMENTATION_SUMMARY.md` - Feature summary
- `BarnabeeNet_Implementation_Guide.md` - Build guide
- `VM_DEPLOYMENT_STATUS.md` - VM setup status

**Integration:**
- `INTEGRATION.md` - HA integration guide
- `VIEWASSIST_INTEGRATION.md` - ViewAssist setup
- `TIMER_SETUP.md` - Timer helper configuration

**Operations:**
- `BarnabeeNet_Operations_Runbook.md` - Operations guide
- `QUICK_REFERENCE.md` - Quick command reference

**Research & Theory:**
- `SkyrimNet_Deep_Research_For_BarnabeeNet.md` - SkyrimNet patterns analysis
- `BarnabeeNet_Theory_Research.md` - Research notes
- `BarnabeeNet_Prompt_Engineering.md` - Prompt design

**Future:**
- `future/MOBILE_STT_CLIENT.md` - Android client design
- `future/CAPABILITY_ROADMAP.md` - Feature roadmap
- `future/self improvement agent.md` - Self-improvement spec

---

## Additional Reference: Test Suite

### tests/ (28 test files)

| File | Tests | Coverage |
|------|-------|----------|
| `test_meta_agent.py` | Intent classification | MetaAgent |
| `test_instant_agent.py` | Quick responses | InstantAgent |
| `test_action_agent.py` | Device control | ActionAgent |
| `test_interaction_agent.py` | Conversations | InteractionAgent |
| `test_memory_agent.py` | Memory ops | MemoryAgent |
| `test_orchestrator.py` | Pipeline | AgentOrchestrator |
| `test_homeassistant.py` | HA client | HomeAssistantClient |
| `test_homeassistant_api.py` | HA endpoints | HA API routes |
| `test_intent_coverage.py` | **87.3% accuracy** | All intents |
| `test_e2e.py` | End-to-end | Full pipeline |
| `test_stt_router.py` | STT routing | GPU/CPU/Azure |
| `test_kokoro_tts.py` | TTS | Kokoro |
| `test_memory_storage.py` | Memory | Storage |
| `test_providers.py` | LLM providers | OpenRouter etc |
| `test_self_improvement.py` | Self-improve | Claude Code |

### Running Tests
```bash
# Incremental (fast, uses testmon)
pytest

# Full suite
pytest --no-testmon

# Specific test
pytest tests/test_intent_coverage.py -v

# With coverage
pytest --cov=barnabeenet --cov-report=html
```

---

## Additional Reference: NixOS Configuration

### /etc/nixos/configuration.nix (on VM)

```nix
{ config, pkgs, ... }:

{
  imports = [ ./hardware-configuration.nix ./barnabeenet.nix ];

  boot.loader.systemd-boot.enable = true;
  networking.hostName = "barnabeenet";
  time.timeZone = "America/New_York";

  users.users.thom = {
    isNormalUser = true;
    extraGroups = [ "wheel" "networkmanager" ];
    openssh.authorizedKeys.keys = [
      "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOP6MkvsXW5bgQmDoSE6uWdckVgzhVFxh4xOuiiEpsBG"
    ];
  };

  virtualisation.podman = {
    enable = true;
    dockerCompat = true;
    defaultNetwork.settings.dns_enabled = true;
  };

  environment.systemPackages = with pkgs; [
    vim git curl wget htop tmux
    podman-compose
    python312 python312Packages.pip python312Packages.virtualenv
    sqlite redis
    jq yq tree ffmpeg
  ];

  networking.firewall.allowedTCPPorts = [ 22 8000 6379 9090 3000 ];

  nix.settings.experimental-features = [ "nix-command" "flakes" ];
  system.stateVersion = "24.11";
}
```

### /etc/nixos/barnabeenet.nix (systemd service)

```nix
{ config, pkgs, ... }:

{
  systemd.services.barnabeenet = {
    description = "BarnabeeNet Smart Home Assistant";
    after = [ "network.target" "redis.service" ];
    wantedBy = [ "multi-user.target" ];

    serviceConfig = {
      Type = "simple";
      User = "thom";
      WorkingDirectory = "/home/thom/barnabeenet";
      ExecStart = "/home/thom/barnabeenet/.venv/bin/uvicorn barnabeenet.main:app --host 0.0.0.0 --port 8000";
      Restart = "always";
      RestartSec = 5;
      EnvironmentFile = "/home/thom/barnabeenet/.env";
    };
  };
}
```

---

## Additional Reference: Redis Data Structures

### Key Prefixes

| Prefix | Purpose | TTL |
|--------|---------|-----|
| `signal:` | Pipeline signals | 7 days |
| `activity:` | Activity log | 7 days |
| `memory:` | Stored memories | None |
| `embedding:` | Cached embeddings | 7 days |
| `profile:` | Family profiles | None |
| `conversation:` | Conversation context | 30 min |
| `config:` | Runtime config | None |
| `cache:llm:` | LLM response cache | 1-24 hours |

### Redis Streams

| Stream | Purpose |
|--------|---------|
| `signals` | Pipeline signal events |
| `activities` | Activity log events |
| `ha:state_changes` | HA state change events |

---

## Additional Reference: WebSocket Endpoints

| Endpoint | Purpose | Protocol |
|----------|---------|----------|
| `/ws/activity` | Real-time activity feed | JSON messages |
| `/ws/dashboard` | Dashboard updates | JSON messages |
| `/ws/transcribe` | Streaming STT | Binary audio in, JSON out |

### WebSocket Message Types

```typescript
// Activity feed
{ "type": "activity", "data": Activity }
{ "type": "stats_update", "data": Stats }

// Dashboard
{ "type": "metrics", "data": Metrics }
{ "type": "ha_state_change", "data": StateChange }

// Transcribe
{ "type": "config", "streaming": true, "engine": "parakeet" }
{ "type": "partial", "text": "...", "confidence": 0.8 }
{ "type": "final", "text": "...", "confidence": 0.95 }
```

---

*Document generated: January 24, 2026*
*BarnabeeNet v1.0 - 8 days of development*
*~27,000 lines of Python*
*87.3% intent classification accuracy*
*45ms GPU STT latency*
