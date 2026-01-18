# BarnabeeNet Dashboard & Signal Architecture Specification

**Document Version:** 1.0  
**Date:** January 17, 2026  
**Based On:** SkyrimNet Beta 10 Architecture Analysis  
**Purpose:** Comprehensive specification for BarnabeeNet's observability layer, dashboard controls, and signal logging system

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Dashboard Architecture Philosophy](#2-dashboard-architecture-philosophy)
3. [Main Dashboard Overview](#3-main-dashboard-overview)
4. [Signal Logging Architecture](#4-signal-logging-architecture)
5. [Conversation & Request Inspector](#5-conversation--request-inspector)
6. [Memory System Dashboard](#6-memory-system-dashboard)
7. [Configuration Management Interface](#7-configuration-management-interface)
8. [Event System Controls](#8-event-system-controls)
9. [Agent Management Dashboard](#9-agent-management-dashboard)
10. [Family Profile Management](#10-family-profile-management)
11. [Trigger & Automation Builder](#11-trigger--automation-builder)
12. [Cost & Performance Monitoring](#12-cost--performance-monitoring)
13. [Trace Explorer](#13-trace-explorer)
14. [System Administration](#14-system-administration)
15. [Mobile Dashboard Considerations](#15-mobile-dashboard-considerations)
16. [Implementation Roadmap](#16-implementation-roadmap)

---

## 1. Executive Summary

### 1.1 What This Document Defines

This specification translates SkyrimNet's proven dashboard and observability architecture into BarnabeeNet's smart home context. The dashboard serves as the **complete control surface** for the AI assistant, providing:

- **Full Visibility** — See exactly what Barnabee is "thinking" at any moment
- **Comprehensive Control** — Adjust every parameter without code changes
- **Real-Time Monitoring** — Live streams of all system activity
- **Signal Logging** — Complete audit trail of every interaction
- **Ease of Use** — Intuitive interfaces designed for non-technical family members

### 1.2 Key Design Principles (Learned from SkyrimNet)

| Principle | SkyrimNet Implementation | BarnabeeNet Translation |
|-----------|-------------------------|------------------------|
| **Every signal logged** | Full prompt/response capture for all LLM calls | Complete conversation context with all injected state |
| **Hot-reload everything** | YAML changes take effect immediately | Configuration changes apply without restart |
| **See the AI's reasoning** | Request inspector shows full context | Conversation inspector shows why Barnabee responded that way |
| **Granular control** | Per-NPC model overrides | Per-room, per-user, per-time-of-day overrides |
| **Ease of iteration** | Web UI for all settings | Mobile-friendly dashboard with guided wizards |

### 1.3 Dashboard Access Tiers

| Tier | Users | Capabilities |
|------|-------|--------------|
| **Admin** | Thom, Elizabeth | Full access to all controls, configuration, logs |
| **Family** | Older children | View conversations, adjust personal preferences |
| **Guest** | Visitors | View-only status, no configuration access |
| **Child** | Younger children | No dashboard access (privacy protection) |

---

## 2. Dashboard Architecture Philosophy

### 2.1 "Alive" Feeling Through Observability

SkyrimNet's key insight: **the "alive" feeling comes from the orchestration of multiple systems, and debugging requires seeing all of them simultaneously**. BarnabeeNet's dashboard must expose:

1. **What Barnabee heard** — Transcribed speech with speaker identification
2. **What Barnabee knew** — Context injected into the prompt (home state, memories, profiles)
3. **What Barnabee decided** — Agent routing decisions and reasoning
4. **What Barnabee did** — Actions taken (device control, responses, memory storage)
5. **What Barnabee learned** — New memories and pattern updates

### 2.2 Real-Time Streaming Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    BarnabeeNet Core Engine                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │  Voice   │  │  Agent   │  │  Memory  │  │  Action  │        │
│  │ Pipeline │  │  Router  │  │  System  │  │ Executor │        │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘        │
│       │             │             │             │               │
│       └─────────────┴─────────────┴─────────────┘               │
│                           │                                      │
│                    ┌──────▼──────┐                              │
│                    │ Event Bus   │                              │
│                    │ (Redis      │                              │
│                    │  Streams)   │                              │
│                    └──────┬──────┘                              │
└───────────────────────────┼─────────────────────────────────────┘
                            │
              ┌─────────────┼─────────────┐
              │             │             │
        ┌─────▼─────┐ ┌─────▼─────┐ ┌─────▼─────┐
        │ WebSocket │ │   REST    │ │  Grafana  │
        │  Server   │ │    API    │ │  Metrics  │
        └─────┬─────┘ └─────┬─────┘ └─────┬─────┘
              │             │             │
              └─────────────┼─────────────┘
                            │
                    ┌───────▼───────┐
                    │   Dashboard   │
                    │   (Web UI)    │
                    └───────────────┘
```

### 2.3 Technology Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| **Primary Dashboard** | Grafana + Custom Panels | Industry-standard, extensible, mobile-ready |
| **Real-Time Updates** | WebSocket (Socket.IO) | Low-latency streaming |
| **REST API** | FastAPI | Async Python, automatic OpenAPI docs |
| **Metrics Storage** | Prometheus + InfluxDB | Time-series for performance, InfluxDB for logs |
| **Configuration UI** | Custom React Components | Complex nested YAML editing |

---

## 3. Main Dashboard Overview

### 3.1 Home Overview Panel

The landing page provides at-a-glance system status:

```
┌─────────────────────────────────────────────────────────────────────────┐
│  🏠 BarnabeeNet Home Dashboard                      [Admin: Thom] ⚙️    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐         │
│  │ 🟢 System OK    │  │ 👥 4 Home       │  │ 💬 12 Today     │         │
│  │ Uptime: 14d 3h  │  │ Thom, Elizabeth │  │ Last: 2m ago   │         │
│  │ Version: 1.2.3  │  │ Penelope, Xander│  │ Cost: $0.23    │         │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘         │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ Recent Activity Stream                                    [Live] │   │
│  ├─────────────────────────────────────────────────────────────────┤   │
│  │ 10:23 AM │ 🎤 Thom (Office): "What's the weather today?"        │   │
│  │ 10:23 AM │ 🤖 Barnabee: "It's 72°F and sunny, perfect for..."   │   │
│  │ 10:21 AM │ 🏠 Motion detected in Kitchen                        │   │
│  │ 10:15 AM │ 💡 Living room lights set to 80%                     │   │
│  │ 10:12 AM │ 🚪 Front door unlocked (Elizabeth arrived)           │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌──────────────────────┐  ┌──────────────────────────────────────┐   │
│  │ Ambient Conditions   │  │ Active Devices                       │   │
│  │                      │  │                                      │   │
│  │ 🌡️ Inside: 71°F     │  │ 💡 Lights: 8 on / 24 total          │   │
│  │ 💧 Humidity: 45%     │  │ 🔌 Switches: 3 on / 12 total        │   │
│  │ ☀️ Outside: 72°F     │  │ 🌡️ Climate: 2 active                │   │
│  │ 🌤️ Sunny            │  │ 🔒 Locks: All secured               │   │
│  └──────────────────────┘  └──────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ Quick Actions                                                    │   │
│  │                                                                  │   │
│  │  [🌙 Good Night]  [🎬 Movie Mode]  [👋 Away Mode]  [🔇 Quiet]   │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Home Overview Controls

| Control | Function | Access Level |
|---------|----------|--------------|
| **System Status** | View uptime, version, error count | All |
| **Occupancy Display** | Who's home based on presence detection | Family+ |
| **Activity Stream** | Real-time event feed with filtering | Family+ |
| **Quick Actions** | One-tap scene activation | Family+ |
| **Ambient Display** | Current environmental conditions | All |
| **Device Summary** | Aggregate device states | Family+ |

### 3.3 Navigation Structure

```
📊 Dashboard (Home)
├── 💬 Conversations
│   ├── Live Feed
│   ├── History Search
│   └── Request Inspector
├── 🧠 Memory
│   ├── Memory Browser
│   ├── Semantic Search
│   └── Analytics
├── 👥 Family
│   ├── Profiles
│   ├── Preferences
│   └── Speaker Enrollment
├── ⚡ Automation
│   ├── Triggers
│   ├── Actions
│   └── Schedules
├── ⚙️ Configuration
│   ├── Agents
│   ├── LLM Settings
│   ├── Voice Settings
│   └── Privacy Zones
├── 📈 Analytics
│   ├── Cost Tracking
│   ├── Performance
│   └── Usage Patterns
└── 🔧 System
    ├── Logs
    ├── Trace Explorer
    └── Backups
```

---

## 4. Signal Logging Architecture

### 4.1 Signal Types Captured

BarnabeeNet logs **every signal** entering and leaving the system:

#### 4.1.1 Input Signals

| Signal Type | Source | Data Captured | Retention |
|-------------|--------|---------------|-----------|
| **Voice Input** | Microphones/Satellites | Raw audio (optional), transcription, speaker ID, confidence, room | 30 days |
| **Text Input** | Dashboard, App | Raw text, source device, user ID | 30 days |
| **Home Assistant Events** | HA Event Bus | Entity, old_state, new_state, timestamp, attributes | 7 days (ephemeral), 90 days (significant) |
| **Presence Changes** | Person entities | Who, arrived/left, timestamp, device used | 90 days |
| **Calendar Events** | Google/iCloud sync | Event details, attendees, reminders | Until event + 7 days |
| **Gesture Input** | Wearables | Gesture type, context_id, confidence | 24 hours |

#### 4.1.2 Processing Signals

| Signal Type | Source | Data Captured | Retention |
|-------------|--------|---------------|-----------|
| **Agent Routing** | Meta Agent | Input classification, selected agent, confidence, reasoning | 30 days |
| **Memory Retrieval** | Memory Agent | Query, results, similarity scores, retrieval time | 30 days |
| **Context Assembly** | Prompt Builder | All injected context blocks, token counts | 30 days |
| **LLM Request** | All Agents | Full prompt, model config, request timestamp | 30 days |
| **LLM Response** | All Agents | Full response, tokens used, latency, cost | 30 days |

#### 4.1.3 Output Signals

| Signal Type | Destination | Data Captured | Retention |
|-------------|-------------|---------------|-----------|
| **Speech Output** | TTS → Speakers | Text, voice used, audio duration, target room | 30 days |
| **Device Actions** | Home Assistant | Service call, entity, data, result, latency | 90 days |
| **Memory Storage** | Memory DB | Memory content, type, importance, embedding | Permanent (with decay) |
| **Notifications** | Mobile/Dashboard | Content, priority, target users, delivery status | 30 days |

### 4.2 Signal Schema Definition

Every signal follows a consistent schema:

```python
@dataclass
class Signal:
    """Base signal schema for all BarnabeeNet events."""
    
    # Identity
    signal_id: str              # UUID
    signal_type: str            # Category (input/processing/output)
    signal_subtype: str         # Specific type (voice_input, llm_request, etc.)
    
    # Timing
    timestamp: datetime         # When signal was created
    duration_ms: Optional[int]  # Processing duration if applicable
    
    # Context
    conversation_id: str        # Links related signals
    trace_id: str               # For distributed tracing
    parent_signal_id: Optional[str]  # Causal chain
    
    # Location
    room: Optional[str]         # Physical location
    device: Optional[str]       # Source/target device
    
    # People
    speaker_id: Optional[str]   # Who initiated
    target_users: List[str]     # Who it's for
    
    # Content
    payload: dict               # Signal-specific data
    
    # Metadata
    importance: float           # 0.0-1.0 for retention decisions
    tags: List[str]             # Searchable labels
    
    # Privacy
    privacy_level: str          # public/family/private/sensitive
    redacted: bool              # Whether PII was removed
```

### 4.3 Conversation Context Logging

For every conversation turn, log the **complete context**:

```json
{
  "conversation_id": "conv_abc123",
  "turn_number": 3,
  "timestamp": "2026-01-17T10:23:45Z",
  
  "input": {
    "type": "voice",
    "transcription": "What's the weather today?",
    "speaker_id": "thom",
    "speaker_confidence": 0.94,
    "room": "office",
    "audio_duration_ms": 1823
  },
  
  "routing": {
    "agent_selected": "instant_agent",
    "confidence": 0.89,
    "reasoning": "Simple factual query matching weather pattern",
    "alternative_agents": [
      {"agent": "interaction_agent", "score": 0.45}
    ]
  },
  
  "context_injected": {
    "home_state": {
      "weather": {"temp": 72, "condition": "sunny", "humidity": 45},
      "occupancy": ["thom", "elizabeth", "penelope", "xander"],
      "time_context": "late_morning_weekday"
    },
    "speaker_profile": {
      "name": "Thom",
      "preferences": {"temperature_unit": "fahrenheit"},
      "recent_topics": ["work project", "weekend plans"]
    },
    "retrieved_memories": [],
    "conversation_history": [
      {"role": "user", "content": "Good morning Barnabee"},
      {"role": "assistant", "content": "Good morning, Thom!"}
    ]
  },
  
  "llm_call": {
    "model": "deepseek/deepseek-v3",
    "temperature": 0.5,
    "max_tokens": 200,
    "full_prompt": "[Complete prompt text...]",
    "input_tokens": 847,
    "output_tokens": 42,
    "latency_ms": 312,
    "cost_usd": 0.00012
  },
  
  "response": {
    "text": "It's 72°F and sunny outside, Thom—perfect weather for that lunch meeting you have today.",
    "actions_taken": [],
    "tts_duration_ms": 2100,
    "target_room": "office"
  },
  
  "memory_operations": {
    "stored": [],
    "retrieved": [],
    "updated": []
  }
}
```

### 4.4 Short-Lived Event System

For high-frequency signals that shouldn't persist (adapted from SkyrimNet):

```python
class ShortLivedEvent:
    """Ephemeral events with automatic expiration."""
    
    event_id: str           # Unique key (overwrites on collision)
    event_type: str         # Category
    description: str        # Human-readable
    data: dict              # Payload
    ttl_ms: int             # Time-to-live in milliseconds
    source_room: str        # Origin
    created_at: datetime
    expires_at: datetime
    
# Example: Motion detection (high frequency, short relevance)
event = ShortLivedEvent(
    event_id="motion_kitchen",  # Key ensures only latest is kept
    event_type="motion_detected",
    description="Motion detected in Kitchen",
    data={"sensor": "binary_sensor.kitchen_motion", "occupancy_count": 2},
    ttl_ms=30000,  # 30 seconds
    source_room="kitchen"
)
```

**Event ID Strategy:** Using room-specific IDs (e.g., `motion_kitchen`) ensures only the most recent event per location is kept, preventing context explosion.

---

## 5. Conversation & Request Inspector

### 5.1 Live Conversation Feed

```
┌─────────────────────────────────────────────────────────────────────────┐
│  💬 Live Conversations                              [Filter ▼] [Pause] │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─ 10:23:45 AM ─────────────────────────────────────────────────────┐ │
│  │ 🎤 Thom (Office) → Barnabee                                       │ │
│  │ "What's the weather today?"                                       │ │
│  │                                                                    │ │
│  │ Agent: instant_agent (89% confidence)                             │ │
│  │ Model: deepseek/deepseek-v3 │ 847→42 tokens │ 312ms │ $0.00012   │ │
│  │                                                          [Inspect]│ │
│  └───────────────────────────────────────────────────────────────────┘ │
│  ┌─ 10:23:46 AM ─────────────────────────────────────────────────────┐ │
│  │ 🤖 Barnabee → Thom (Office)                                       │ │
│  │ "It's 72°F and sunny outside, Thom—perfect weather for that       │ │
│  │  lunch meeting you have today."                                   │ │
│  │                                                                    │ │
│  │ TTS: piper │ 2.1s audio │ No actions taken                        │ │
│  └───────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│  ┌─ 10:21:12 AM ─────────────────────────────────────────────────────┐ │
│  │ 🏠 System Event                                                    │ │
│  │ Motion detected in Kitchen (Elizabeth, Penelope)                  │ │
│  │                                                                    │ │
│  │ Triggered: No proactive response (routine activity)               │ │
│  └───────────────────────────────────────────────────────────────────┘ │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 5.2 Request Inspector (Deep Dive)

When clicking [Inspect] on any conversation turn:

```
┌─────────────────────────────────────────────────────────────────────────┐
│  🔍 Request Inspector                                          [Close] │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─ Request Metadata ───────────────────────────────────────────────┐  │
│  │ Request ID: req_7f3a2b1c                                         │  │
│  │ Conversation: conv_abc123 (Turn 3)                               │  │
│  │ Trace ID: trace_9d8e7f6a (Click to view full trace)              │  │
│  │ Timestamp: 2026-01-17T10:23:45.123Z                              │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  ┌─ Input ──────────────────────────────────────────────────────────┐  │
│  │ Type: Voice                                                      │  │
│  │ Transcription: "What's the weather today?"                       │  │
│  │ Speaker: Thom (94% confidence)                                   │  │
│  │ Room: Office                                                     │  │
│  │ Audio Duration: 1.82s                                            │  │
│  │                                                     [Play Audio] │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  ┌─ Agent Routing ──────────────────────────────────────────────────┐  │
│  │ Selected: instant_agent                                          │  │
│  │ Confidence: 89%                                                  │  │
│  │ Reasoning: "Simple factual query matching weather pattern"       │  │
│  │                                                                  │  │
│  │ Alternatives Considered:                                         │  │
│  │   • interaction_agent: 45% (would use for complex weather Q)     │  │
│  │   • action_agent: 12% (no device control implied)                │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  ┌─ Context Injected ───────────────────────────────────────────────┐  │
│  │ [▼ Home State] (234 tokens)                                      │  │
│  │     Weather: 72°F, sunny, 45% humidity                           │  │
│  │     Occupancy: Thom, Elizabeth, Penelope, Xander                 │  │
│  │     Time: Late morning, weekday                                  │  │
│  │     Active Devices: 8 lights, office climate at 70°F             │  │
│  │                                                                  │  │
│  │ [▼ Speaker Profile] (156 tokens)                                 │  │
│  │     Name: Thom                                                   │  │
│  │     Preferences: Fahrenheit, concise responses                   │  │
│  │     Today's Calendar: Lunch meeting at 12:30 PM                  │  │
│  │                                                                  │  │
│  │ [▼ Retrieved Memories] (0 tokens)                                │  │
│  │     No relevant memories retrieved                               │  │
│  │                                                                  │  │
│  │ [▼ Conversation History] (89 tokens)                             │  │
│  │     Turn 1: "Good morning Barnabee" → "Good morning, Thom!"      │  │
│  │     Turn 2: [Previous exchange...]                               │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  ┌─ Full Prompt ────────────────────────────────────────────────────┐  │
│  │ [Expand to view complete 847-token prompt]                       │  │
│  │                                                                  │  │
│  │ You are Barnabee, a warm and helpful AI assistant for the Fife  │  │
│  │ family. You are currently speaking with Thom in his office...    │  │
│  │                                                                  │  │
│  │ Current conditions:                                              │  │
│  │ - Weather: 72°F and sunny                                        │  │
│  │ - Time: 10:23 AM on Friday, January 17                           │  │
│  │ ...                                                              │  │
│  │                                                     [Copy Full]  │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  ┌─ LLM Response ───────────────────────────────────────────────────┐  │
│  │ Model: deepseek/deepseek-v3                                      │  │
│  │ Temperature: 0.5 │ Max Tokens: 200                               │  │
│  │                                                                  │  │
│  │ Response:                                                        │  │
│  │ "It's 72°F and sunny outside, Thom—perfect weather for that     │  │
│  │  lunch meeting you have today."                                  │  │
│  │                                                                  │  │
│  │ Tokens: 847 input → 42 output                                    │  │
│  │ Latency: 312ms                                                   │  │
│  │ Cost: $0.00012                                                   │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  ┌─ Actions & Output ───────────────────────────────────────────────┐  │
│  │ Device Actions: None                                             │  │
│  │ Memory Operations: None                                          │  │
│  │                                                                  │  │
│  │ TTS Output:                                                      │  │
│  │   Engine: Piper │ Voice: barnabee_warm                           │  │
│  │   Duration: 2.1s │ Target: Office speakers                       │  │
│  │                                                     [Play Audio] │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 5.3 Conversation Inspector Controls

| Control | Function | Ease of Use Feature |
|---------|----------|---------------------|
| **Expand/Collapse Sections** | Show/hide context blocks | Reduces cognitive load |
| **Copy Full Prompt** | One-click copy for debugging | Easy sharing with developers |
| **Play Audio** | Listen to original input or TTS output | Verify transcription accuracy |
| **View Trace** | Link to full request waterfall | Deep debugging when needed |
| **Token Counts** | Per-section token usage | Identify context bloat |
| **Retry with Changes** | Re-run with modified parameters | Rapid experimentation |

### 5.4 Conversation Search

```
┌─────────────────────────────────────────────────────────────────────────┐
│  🔎 Search Conversations                                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─ Search ─────────────────────────────────────────────────────────┐  │
│  │ [                                                              🔍] │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  ┌─ Filters ────────────────────────────────────────────────────────┐  │
│  │                                                                  │  │
│  │ Date Range: [Last 7 days ▼]    Speaker: [All ▼]                 │  │
│  │                                                                  │  │
│  │ Room: [All ▼]    Agent: [All ▼]    Has Actions: [Any ▼]         │  │
│  │                                                                  │  │
│  │ Cost Range: [$0.00] to [$1.00]    Latency: [0ms] to [5000ms]    │  │
│  │                                                                  │  │
│  │ [✓] Include system events    [ ] Only errors                     │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  Results: 847 conversations matching filters                            │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Memory System Dashboard

### 6.1 Memory Browser

```
┌─────────────────────────────────────────────────────────────────────────┐
│  🧠 Memory Browser                                      [+ New Memory]  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─ Semantic Search ────────────────────────────────────────────────┐  │
│  │ [Search memories...                                            🔍] │  │
│  │                                                                  │  │
│  │ Family Member: [All ▼]   Type: [All ▼]   Min Importance: [0.3]  │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  ┌─ Results (23 memories) ──────────────────────────────────────────┐  │
│  │                                                                  │  │
│  │ ┌────────────────────────────────────────────────────────────┐  │  │
│  │ │ 📝 About: Thom │ Type: ROUTINE │ Importance: 0.82          │  │  │
│  │ │                                                            │  │  │
│  │ │ "Every weekday morning around 7, Thom heads to his office. │  │  │
│  │ │  I've learned he focuses best when it's a bit cool—68°F    │  │  │
│  │ │  feels right for him."                                     │  │  │
│  │ │                                                            │  │  │
│  │ │ Created: Jan 10, 2026 │ Last accessed: Today               │  │  │
│  │ │ Similarity: 0.89                       [Edit] [Archive]    │  │  │
│  │ └────────────────────────────────────────────────────────────┘  │  │
│  │                                                                  │  │
│  │ ┌────────────────────────────────────────────────────────────┐  │  │
│  │ │ 📝 About: Elizabeth │ Type: PREFERENCE │ Importance: 0.75  │  │  │
│  │ │                                                            │  │  │
│  │ │ "Elizabeth was cooking this evening and asked for some     │  │  │
│  │ │  jazz. There's something about the way music fills the     │  │  │
│  │ │  kitchen when she's there—she seems lighter, more at ease."│  │  │
│  │ │                                                            │  │  │
│  │ │ Created: Jan 15, 2026 │ Last accessed: Yesterday           │  │  │
│  │ │ Similarity: 0.76                       [Edit] [Archive]    │  │  │
│  │ └────────────────────────────────────────────────────────────┘  │  │
│  │                                                                  │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 6.2 Memory Analytics Panel

```
┌─────────────────────────────────────────────────────────────────────────┐
│  📊 Memory Analytics                                                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─ Overview ───────────────────────────────────────────────────────┐  │
│  │                                                                  │  │
│  │ Total Memories: 1,247    Active: 1,089    Archived: 158         │  │
│  │                                                                  │  │
│  │ By Family Member:              By Type:                         │  │
│  │   Thom: 312 (25%)               ROUTINE: 423 (34%)              │  │
│  │   Elizabeth: 287 (23%)          PREFERENCE: 298 (24%)           │  │
│  │   Penelope: 198 (16%)           EXPERIENCE: 267 (21%)           │  │
│  │   Xander: 176 (14%)             RELATIONSHIP: 156 (13%)         │  │
│  │   Household: 274 (22%)          KNOWLEDGE: 103 (8%)             │  │
│  │                                                                  │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  ┌─ Importance Distribution ────────────────────────────────────────┐  │
│  │                                                                  │  │
│  │  0.9-1.0  ████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  89      │  │
│  │  0.8-0.9  ██████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  156     │  │
│  │  0.7-0.8  ████████████████████░░░░░░░░░░░░░░░░░░░░░░░░  234     │  │
│  │  0.6-0.7  ██████████████████████████░░░░░░░░░░░░░░░░░░  312     │  │
│  │  0.5-0.6  ████████████████████████████████░░░░░░░░░░░░  298     │  │
│  │  < 0.5   ████████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  158     │  │
│  │                                                                  │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  ┌─ Recent Memory Activity ─────────────────────────────────────────┐  │
│  │                                                                  │  │
│  │ Today:        +12 created, 45 accessed, 3 decayed               │  │
│  │ This Week:    +67 created, 312 accessed, 18 archived            │  │
│  │ This Month:   +234 created, 1,089 accessed, 89 archived         │  │
│  │                                                                  │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 6.3 Memory System Controls

| Control | Function | Ease of Use Feature |
|---------|----------|---------------------|
| **Semantic Search** | Natural language memory lookup | Just type what you're looking for |
| **Filter by Person** | Show memories about specific family member | Quick dropdown selection |
| **Filter by Type** | ROUTINE, PREFERENCE, EXPERIENCE, etc. | Understand memory categories |
| **Importance Slider** | Filter by memory significance | Hide low-value memories |
| **Edit Memory** | Modify memory content | Correct mistakes |
| **Archive Memory** | Remove from active retrieval | Clean up without deleting |
| **Create Memory** | Manually add a memory | Seed important information |
| **Bulk Operations** | Select multiple for archive/delete | Efficient cleanup |

---

## 7. Configuration Management Interface

### 7.1 Design Philosophy: Guided Complexity

The configuration UI follows a **progressive disclosure** pattern:

1. **Easy Settings** — Common adjustments with friendly names and descriptions
2. **Advanced Settings** — Full configuration access for power users
3. **Raw YAML** — Direct file editing for developers

### 7.2 Easy Settings Panel

```
┌─────────────────────────────────────────────────────────────────────────┐
│  ⚙️ Easy Settings                                                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─ Personality ────────────────────────────────────────────────────┐  │
│  │                                                                  │  │
│  │ Response Style                                                   │  │
│  │ ├─────────●───────────────────────────────────────────────────┤  │  │
│  │ Concise                                              Detailed   │  │
│  │                                                                  │  │
│  │ Warmth Level                                                     │  │
│  │ ├───────────────────●─────────────────────────────────────────┤  │  │
│  │ Professional                                          Friendly  │  │
│  │                                                                  │  │
│  │ Proactivity                                                      │  │
│  │ ├─────────────────────────●───────────────────────────────────┤  │  │
│  │ Only when asked                              Suggest frequently  │  │
│  │                                                                  │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  ┌─ Voice Settings ─────────────────────────────────────────────────┐  │
│  │                                                                  │  │
│  │ Wake Word: [Hey Barnabee ▼]    Voice: [Warm & Friendly ▼]       │  │
│  │                                                                  │  │
│  │ Speaking Speed                                                   │  │
│  │ ├───────────────────●─────────────────────────────────────────┤  │  │
│  │ Slower                                                  Faster   │  │
│  │                                                                  │  │
│  │ [✓] Confirm before device actions                               │  │
│  │ [✓] Announce who you're talking to                              │  │
│  │ [ ] Use spatial audio (requires setup)                          │  │
│  │                                                                  │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  ┌─ Privacy ────────────────────────────────────────────────────────┐  │
│  │                                                                  │  │
│  │ [✓] Children's rooms are private zones                          │  │
│  │ [✓] Bathrooms are private zones                                 │  │
│  │ [✓] Don't remember sensitive health discussions                 │  │
│  │ [ ] Allow camera integration                                    │  │
│  │                                                                  │  │
│  │ Data Retention: [30 days ▼]                                     │  │
│  │                                                                  │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  ┌─ Cost Controls ──────────────────────────────────────────────────┐  │
│  │                                                                  │  │
│  │ Daily Budget: [$1.00        ]    Current: $0.23 (23%)           │  │
│  │                                                                  │  │
│  │ When budget is low:                                             │  │
│  │ [●] Use cheaper models    [ ] Limit responses    [ ] Notify me  │  │
│  │                                                                  │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│                                              [Reset to Defaults] [Save] │
└─────────────────────────────────────────────────────────────────────────┘
```

### 7.3 Advanced Configuration Manager

```
┌─────────────────────────────────────────────────────────────────────────┐
│  🔧 Advanced Configuration                              [Search: ____] │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─ Config Files ────┐  ┌─ Editor ──────────────────────────────────┐  │
│  │                   │  │                                           │  │
│  │ 📄 barnabee.yaml  │  │ # barnabee.yaml                          │  │
│  │ 📄 llm.yaml      ←│  │                                           │  │
│  │ 📄 memory.yaml    │  │ agents:                                   │  │
│  │ 📄 voice.yaml     │  │   meta:                                   │  │
│  │ 📄 privacy.yaml   │  │     model: "deepseek/deepseek-v3"        │  │
│  │ 📄 triggers.yaml  │  │     temperature: 0.5                      │  │
│  │ 📄 actions.yaml   │  │     max_tokens: 200                       │  │
│  │                   │  │                                           │  │
│  │ ─────────────────│  │   instant:                                │  │
│  │ 📁 overrides/     │  │     patterns:                             │  │
│  │   📄 office.yaml  │  │       - pattern: "what time"              │  │
│  │   📄 thom.yaml    │  │         response: "time_query"            │  │
│  │                   │  │       - pattern: "weather"                │  │
│  │                   │  │         response: "weather_query"         │  │
│  │                   │  │                                           │  │
│  │                   │  │   interaction:                            │  │
│  │                   │  │     model: "anthropic/claude-3.5-sonnet" │  │
│  │                   │  │     temperature: 0.7                      │  │
│  │                   │  │     max_tokens: 2000                      │  │
│  │                   │  │                                           │  │
│  └───────────────────┘  │                            [Validate] [Save] │
│                         └───────────────────────────────────────────┘  │
│                                                                         │
│  ┌─ Validation ─────────────────────────────────────────────────────┐  │
│  │ ✅ YAML syntax valid                                             │  │
│  │ ✅ Schema validation passed                                      │  │
│  │ ✅ Model names verified against OpenRouter                       │  │
│  │ ⚠️ Warning: temperature 0.7 may produce varied responses        │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 7.4 Per-Room / Per-User Overrides

**Key SkyrimNet Pattern:** Override any configuration value at different scopes.

```
┌─────────────────────────────────────────────────────────────────────────┐
│  🏠 Configuration Overrides                                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Override Scope: [Room: Office ▼]                                       │
│                                                                         │
│  ┌─ Active Overrides for Office ────────────────────────────────────┐  │
│  │                                                                  │  │
│  │  Setting                      │ Base Value  │ Override Value    │  │
│  │  ─────────────────────────────┼─────────────┼─────────────────  │  │
│  │  agents.interaction.model     │ claude-3.5  │ claude-3.5-sonnet │  │
│  │  voice.tts.speed              │ 1.0         │ 1.1               │  │
│  │  proactive.enabled            │ true        │ false             │  │
│  │                                                                  │  │
│  │  Reason: Thom prefers faster speech and no interruptions while  │  │
│  │  working in the office.                                         │  │
│  │                                                                  │  │
│  │                                   [+ Add Override] [Clear All]  │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  ┌─ Override Priority ──────────────────────────────────────────────┐  │
│  │                                                                  │  │
│  │  1. User-specific (e.g., thom.yaml)           Highest priority  │  │
│  │  2. Room-specific (e.g., office.yaml)                ↑          │  │
│  │  3. Time-based (e.g., night_mode.yaml)               │          │  │
│  │  4. Base configuration                        Lowest priority   │  │
│  │                                                                  │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 7.5 Configuration Controls Summary

| Control | Function | Ease of Use Feature |
|---------|----------|---------------------|
| **Easy Settings** | Slider-based common adjustments | No technical knowledge needed |
| **Descriptions** | Every setting has help text | Hover for explanation |
| **Validation** | Real-time syntax and schema checks | Prevents breaking changes |
| **Hot Reload** | Changes apply immediately | No restart required |
| **Search** | Find settings across all files | Type what you're looking for |
| **Overrides** | Scope settings by room/user/time | Contextual customization |
| **Diff View** | See changes before saving | Prevent accidents |
| **Backup/Restore** | Automatic config backups | Easy recovery |

---

## 8. Event System Controls

### 8.1 Event Manager Dashboard

```
┌─────────────────────────────────────────────────────────────────────────┐
│  ⚡ Event Manager                                                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─ Live Event Stream ──────────────────────────────────────────────┐  │
│  │                                                         [Pause]  │  │
│  │                                                                  │  │
│  │ 10:25:12 │ state_changed │ light.living_room │ on → off         │  │
│  │ 10:25:10 │ motion_detected │ kitchen │ Elizabeth detected        │  │
│  │ 10:25:03 │ temperature_changed │ climate.office │ 70°F → 71°F   │  │
│  │ 10:24:58 │ voice_input │ office │ Thom: "Turn off living room"  │  │
│  │ 10:24:45 │ presence_changed │ home │ +Elizabeth                  │  │
│  │                                                                  │  │
│  │                                              [Filter ▼] [Export] │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  ┌─ Event Types ────────────────────────────────────────────────────┐  │
│  │                                                                  │  │
│  │ Type                    │ Count (24h) │ Enabled │ TTL    │ Log  │  │
│  │ ────────────────────────┼─────────────┼─────────┼────────┼───── │  │
│  │ state_changed           │ 2,847       │ [✓]     │ 60s    │ [✓]  │  │
│  │ motion_detected         │ 1,234       │ [✓]     │ 30s    │ [ ]  │  │
│  │ presence_changed        │ 12          │ [✓]     │ ∞      │ [✓]  │  │
│  │ voice_input             │ 47          │ [✓]     │ ∞      │ [✓]  │  │
│  │ calendar_reminder       │ 8           │ [✓]     │ 5m     │ [✓]  │  │
│  │ temperature_changed     │ 567         │ [✓]     │ 60s    │ [ ]  │  │
│  │                                                                  │  │
│  │                                           [+ Register New Type]  │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  ┌─ Short-Lived Event Queue ────────────────────────────────────────┐  │
│  │                                                                  │  │
│  │ Event ID              │ Type           │ TTL Remaining │ Room   │  │
│  │ ──────────────────────┼────────────────┼───────────────┼─────── │  │
│  │ motion_kitchen        │ motion         │ 18s           │ Kitchen│  │
│  │ motion_living_room    │ motion         │ 3s            │ Living │  │
│  │ temp_change_office    │ temperature    │ 45s           │ Office │  │
│  │                                                                  │  │
│  │ Queue Size: 3 / 100 max                                         │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 8.2 Custom Event Schema Registration

```
┌─────────────────────────────────────────────────────────────────────────┐
│  📋 Register Event Schema                                       [Close] │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Event Type ID: [appliance_cycle_complete          ]                    │
│  Display Name:  [Appliance Cycle Complete          ]                    │
│  Description:   [Washer/dryer/dishwasher finished  ]                    │
│                                                                         │
│  ┌─ Fields ─────────────────────────────────────────────────────────┐  │
│  │                                                                  │  │
│  │ Name          │ Type    │ Required │ Description                │  │
│  │ ──────────────┼─────────┼──────────┼─────────────────────────── │  │
│  │ appliance     │ string  │ [✓]      │ Which appliance finished   │  │
│  │ cycle_type    │ string  │ [ ]      │ Wash, dry, rinse, etc.     │  │
│  │ duration_min  │ number  │ [ ]      │ How long the cycle took    │  │
│  │                                                    [+ Add Field] │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  ┌─ Format Templates ───────────────────────────────────────────────┐  │
│  │                                                                  │  │
│  │ recent_events: [The {{appliance}} finished its {{cycle_type}} ] │  │
│  │                                                                  │  │
│  │ compact:       [{{appliance}}: done                           ] │  │
│  │                                                                  │  │
│  │ verbose:       [{{appliance}} completed {{cycle_type}} cycle  ] │  │
│  │                [in {{duration_min}} minutes                   ] │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  Ephemeral: [✓] Auto-expire    TTL: [300000   ] ms (5 minutes)         │
│                                                                         │
│                                              [Preview] [Register]       │
└─────────────────────────────────────────────────────────────────────────┘
```

### 8.3 Event System Controls Summary

| Control | Function | Ease of Use Feature |
|---------|----------|---------------------|
| **Live Stream** | Real-time event feed | See what's happening now |
| **Pause/Resume** | Stop scrolling for inspection | Catch fast events |
| **Filter by Type** | Show only specific events | Reduce noise |
| **Enable/Disable** | Turn event types on/off | Control what triggers Barnabee |
| **TTL Configuration** | How long events stay relevant | Tune context window |
| **Log Toggle** | Whether to persist events | Control storage usage |
| **Schema Registration** | Define new event types | Extensibility |
| **Format Templates** | Customize how events display | Consistent formatting |

---

## 9. Agent Management Dashboard

### 9.1 Agent Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│  🤖 Agent Management                                                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─ Agent Status ───────────────────────────────────────────────────┐  │
│  │                                                                  │  │
│  │ Agent           │ Status │ Model              │ Calls/hr │ Cost │  │
│  │ ────────────────┼────────┼────────────────────┼──────────┼───── │  │
│  │ 🧭 Meta         │ 🟢 On  │ deepseek-v3        │ 47       │ $0.01│  │
│  │ ⚡ Instant      │ 🟢 On  │ (pattern match)    │ 23       │ $0.00│  │
│  │ 🎬 Action       │ 🟢 On  │ deepseek-v3        │ 12       │ $0.02│  │
│  │ 💬 Interaction  │ 🟢 On  │ claude-3.5-sonnet  │ 8        │ $0.15│  │
│  │ 🧠 Memory       │ 🟢 On  │ gpt-4o-mini        │ 3        │ $0.01│  │
│  │ 👁️ Proactive    │ 🟡 Idle│ deepseek-v3        │ 2        │ $0.00│  │
│  │                                                                  │  │
│  │                                        [Configure All Agents]   │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  ┌─ Agent Performance (Last Hour) ──────────────────────────────────┐  │
│  │                                                                  │  │
│  │  Meta Agent     ████████████████████░░░░░░░░░░░░░░░░  47 calls   │  │
│  │  Instant Agent  ███████████░░░░░░░░░░░░░░░░░░░░░░░░░  23 calls   │  │
│  │  Action Agent   ██████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  12 calls   │  │
│  │  Interaction    ████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   8 calls   │  │
│  │  Memory Agent   ██░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   3 calls   │  │
│  │  Proactive      █░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   2 calls   │  │
│  │                                                                  │  │
│  │  Avg Latency: Meta 89ms │ Action 312ms │ Interaction 1.2s       │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 9.2 Individual Agent Configuration

```
┌─────────────────────────────────────────────────────────────────────────┐
│  ⚙️ Configure: Interaction Agent                               [Close] │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─ Model Settings ─────────────────────────────────────────────────┐  │
│  │                                                                  │  │
│  │ Model: [anthropic/claude-3.5-sonnet              ▼]             │  │
│  │                                                                  │  │
│  │ Temperature                                                      │  │
│  │ ├───────────────────────────●─────────────────────────────────┤  │  │
│  │ 0.0 (Precise)                                    1.5 (Creative) │  │
│  │ Current: 0.7                                                    │  │
│  │                                                                  │  │
│  │ Max Tokens: [2000        ]                                      │  │
│  │                                                                  │  │
│  │ [Advanced: Top-P, Frequency Penalty, Top-K...]                  │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  ┌─ Routing Rules ──────────────────────────────────────────────────┐  │
│  │                                                                  │  │
│  │ This agent handles:                                             │  │
│  │ [✓] Complex multi-turn conversations                            │  │
│  │ [✓] Advice and recommendations                                  │  │
│  │ [✓] Creative requests (stories, jokes)                          │  │
│  │ [✓] Emotional support conversations                             │  │
│  │ [ ] Device control (handled by Action Agent)                    │  │
│  │ [ ] Quick factual queries (handled by Instant Agent)            │  │
│  │                                                                  │  │
│  │ Minimum confidence to route here: [0.6     ]                    │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  ┌─ Context Settings ───────────────────────────────────────────────┐  │
│  │                                                                  │  │
│  │ Include in context:                                             │  │
│  │ [✓] Speaker profile (public block)                              │  │
│  │ [✓] Home state summary                                          │  │
│  │ [✓] Retrieved memories (max: [5   ])                            │  │
│  │ [✓] Conversation history (max turns: [10  ])                    │  │
│  │ [✓] Calendar context                                            │  │
│  │ [ ] Full device states (verbose)                                │  │
│  │                                                                  │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│                                      [Test with Sample] [Save]         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 9.3 Agent Controls Summary

| Control | Function | Ease of Use Feature |
|---------|----------|---------------------|
| **Status Overview** | See all agents at once | Quick health check |
| **Enable/Disable** | Turn agents on/off | Troubleshoot by isolation |
| **Model Selection** | Choose LLM per agent | Dropdown with cost estimates |
| **Temperature Slider** | Adjust creativity | Visual scale with descriptions |
| **Routing Rules** | What queries go to this agent | Checkboxes with examples |
| **Context Settings** | What information to include | Balance cost vs context |
| **Test with Sample** | Try a query against this agent | Validate before saving |
| **Performance Metrics** | Calls, latency, cost per agent | Identify bottlenecks |

---

## 10. Family Profile Management

### 10.1 Family Profiles Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│  👥 Family Profiles                                                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │
│  │    👨       │  │    👩       │  │    👧       │  │    👦       │   │
│  │   Thom      │  │  Elizabeth  │  │  Penelope   │  │   Xander    │   │
│  │   Admin     │  │   Admin     │  │   Family    │  │   Family    │   │
│  │ [Enrolled]  │  │ [Enrolled]  │  │ [Enrolled]  │  │ [Enrolled]  │   │
│  │             │  │             │  │             │  │             │   │
│  │ [Edit]      │  │ [Edit]      │  │ [Edit]      │  │ [Edit]      │   │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘   │
│                                                                         │
│  ┌─────────────┐  ┌─────────────┐                                      │
│  │    👶       │  │    👶       │       [+ Add Family Member]          │
│  │   Zachary   │  │   Viola     │       [+ Add Guest Profile]          │
│  │   Child     │  │   Child     │                                      │
│  │ [Protected] │  │ [Protected] │                                      │
│  │             │  │             │                                      │
│  │ [Edit]      │  │ [Edit]      │                                      │
│  └─────────────┘  └─────────────┘                                      │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 10.2 Individual Profile Editor

```
┌─────────────────────────────────────────────────────────────────────────┐
│  👨 Edit Profile: Thom                                          [Close] │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─ Basic Information ──────────────────────────────────────────────┐  │
│  │                                                                  │  │
│  │ Display Name: [Thom                    ]                        │  │
│  │ Role: [Admin ▼]    Pronouns: [he/him ▼]                         │  │
│  │                                                                  │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  ┌─ Voice Enrollment ───────────────────────────────────────────────┐  │
│  │                                                                  │  │
│  │ Status: ✅ Enrolled (12 samples)                                │  │
│  │ Recognition Accuracy: 94%                                       │  │
│  │                                                                  │  │
│  │ [Re-enroll Voice] [Test Recognition]                            │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  ┌─ Public Profile (Visible to Barnabee) ───────────────────────────┐  │
│  │                                                                  │  │
│  │ Thom is the father of the household and a tech professional.    │  │
│  │ He works from his home office most days and values focus time.  │  │
│  │ He prefers concise responses and appreciates when Barnabee      │  │
│  │ anticipates his needs, especially around his work schedule.     │  │
│  │                                                                  │  │
│  │ Preferences:                                                    │  │
│  │ • Temperature: Prefers cooler (68°F) when working               │  │
│  │ • Music: Jazz, lo-fi, ambient electronica                       │  │
│  │ • Communication: Direct, minimal small talk                     │  │
│  │                                                                  │  │
│  │                                           [Edit] [AI Suggest]   │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  ┌─ Private Notes (Admin Only) ─────────────────────────────────────┐  │
│  │                                                                  │  │
│  │ [Notes visible only to admins, not included in prompts]         │  │
│  │                                                                  │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  ┌─ Preferences ────────────────────────────────────────────────────┐  │
│  │                                                                  │  │
│  │ Response Style: [Concise ▼]    Temperature Unit: [Fahrenheit ▼] │  │
│  │                                                                  │  │
│  │ [✓] Include calendar context in responses                       │  │
│  │ [✓] Announce identity when speaking to me                       │  │
│  │ [ ] Enable proactive suggestions                                │  │
│  │                                                                  │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│                                              [Delete Profile] [Save]   │
└─────────────────────────────────────────────────────────────────────────┘
```

### 10.3 Profile Controls Summary

| Control | Function | Ease of Use Feature |
|---------|----------|---------------------|
| **Voice Enrollment** | Train speaker recognition | Guided wizard with sample phrases |
| **Recognition Test** | Verify enrollment quality | Immediate feedback |
| **Public Profile** | What Barnabee knows about them | Plain English, editable |
| **AI Suggest** | Let Barnabee draft profile updates | Based on conversation history |
| **Preferences** | Personal settings | Dropdown menus for common choices |
| **Role Assignment** | Admin/Family/Guest/Child | Controls dashboard access |
| **Privacy Protection** | Child profiles | No data retention, restricted features |

---

## 11. Trigger & Automation Builder

### 11.1 Trigger Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│  ⚡ Triggers & Automations                              [+ New Trigger] │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─ Active Triggers ────────────────────────────────────────────────┐  │
│  │                                                                  │  │
│  │ Name                    │ Events           │ Last Fired │ Status │  │
│  │ ────────────────────────┼──────────────────┼────────────┼─────── │  │
│  │ 🌙 Bedtime Reminder     │ time: 20:15      │ Yesterday  │ 🟢 On  │  │
│  │ 🚪 Welcome Home         │ presence_changed │ 2 hrs ago  │ 🟢 On  │  │
│  │ 🧺 Laundry Done         │ state_changed    │ 3 days ago │ 🟢 On  │  │
│  │ ☀️ Good Morning         │ time + motion    │ Today 7:03 │ 🟢 On  │  │
│  │ 🔒 Lock Check           │ time: 22:00      │ Yesterday  │ 🟡 Test│  │
│  │                                                                  │  │
│  │                                              [Import] [Export]   │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 11.2 Visual Trigger Builder

```
┌─────────────────────────────────────────────────────────────────────────┐
│  🔧 Edit Trigger: Bedtime Reminder                              [Close] │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Name: [Bedtime Reminder                                     ]          │
│  Description: [Remind kids it's almost bedtime on school nights]        │
│                                                                         │
│  ┌─ WHEN (Trigger Events) ──────────────────────────────────────────┐  │
│  │                                                                  │  │
│  │  ┌──────────────────────────────────────────────────────────┐   │  │
│  │  │ 🕐 Time Trigger                                          │   │  │
│  │  │    Time: [20:15    ]                                     │   │  │
│  │  │    Days: [✓]M [✓]T [✓]W [✓]Th [ ]F [ ]Sa [✓]Su          │   │  │
│  │  └──────────────────────────────────────────────────────────┘   │  │
│  │                                                                  │  │
│  │  AND                                               [+ Add Event] │  │
│  │                                                                  │  │
│  │  ┌──────────────────────────────────────────────────────────┐   │  │
│  │  │ 👁️ State Condition                                       │   │  │
│  │  │    Entity: [sensor.kids_room_motion ▼]                   │   │  │
│  │  │    State: [on ▼]                                         │   │  │
│  │  └──────────────────────────────────────────────────────────┘   │  │
│  │                                                                  │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  ┌─ IF (Conditions) ────────────────────────────────────────────────┐  │
│  │                                                                  │  │
│  │  ┌──────────────────────────────────────────────────────────┐   │  │
│  │  │ 📅 Template Condition                                    │   │  │
│  │  │    {{ is_school_night() }}                               │   │  │
│  │  └──────────────────────────────────────────────────────────┘   │  │
│  │                                                                  │  │
│  │  ┌──────────────────────────────────────────────────────────┐   │  │
│  │  │ 🔁 Cooldown Condition                                    │   │  │
│  │  │    {{ not already_reminded_today('bedtime') }}           │   │  │
│  │  └──────────────────────────────────────────────────────────┘   │  │
│  │                                                   [+ Add Condition] │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  ┌─ THEN (Actions) ─────────────────────────────────────────────────┐  │
│  │                                                                  │  │
│  │  ┌──────────────────────────────────────────────────────────┐   │  │
│  │  │ 💬 Proactive Suggestion                                  │   │  │
│  │  │    Message: "It's getting close to bedtime for the       │   │  │
│  │  │              little ones."                               │   │  │
│  │  │    Target Room: [Kids Room ▼]                            │   │  │
│  │  │    Priority: [Normal ▼]                                  │   │  │
│  │  └──────────────────────────────────────────────────────────┘   │  │
│  │                                                    [+ Add Action] │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  Cooldown: [3600     ] seconds (1 hour)                                │
│  Status: [✓] Enabled                                                   │
│                                                                         │
│                              [Test Trigger] [Delete] [Save]            │
└─────────────────────────────────────────────────────────────────────────┘
```

### 11.3 Trigger System Controls

| Control | Function | Ease of Use Feature |
|---------|----------|---------------------|
| **Visual Builder** | Drag-and-drop trigger creation | No YAML knowledge required |
| **Event Type Dropdown** | Select from all available events | Shows event descriptions |
| **Condition Templates** | Pre-built common conditions | `is_school_night()`, `is_home()`, etc. |
| **Action Templates** | Pre-built common actions | Speak, notify, device control |
| **Test Trigger** | Fire trigger manually | Verify behavior before enabling |
| **Cooldown Setting** | Prevent repeated firing | Simple duration input |
| **Import/Export** | Share triggers as YAML | Community sharing |
| **Trigger History** | When did this last fire? | Debugging |

---

## 12. Cost & Performance Monitoring

### 12.1 Cost Dashboard

```
┌─────────────────────────────────────────────────────────────────────────┐
│  💰 Cost Tracking                                                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─ Today's Usage ──────────────────────────────────────────────────┐  │
│  │                                                                  │  │
│  │  Daily Budget: $1.00                                            │  │
│  │  ├──────────────────────●────────────────────────────────────┤  │  │
│  │  $0.00                 $0.23                              $1.00  │  │
│  │                        (23%)                                    │  │
│  │                                                                  │  │
│  │  Status: 🟢 Under budget                                        │  │
│  │                                                                  │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  ┌─ Cost Breakdown ─────────────────────────────────────────────────┐  │
│  │                                                                  │  │
│  │  Agent              │ Calls │ Tokens (in/out)  │ Cost           │  │
│  │  ───────────────────┼───────┼──────────────────┼─────────────── │  │
│  │  Interaction        │ 8     │ 12,847 / 1,234   │ $0.15 (65%)    │  │
│  │  Action             │ 12    │ 4,234 / 456      │ $0.04 (17%)    │  │
│  │  Memory             │ 3     │ 2,123 / 312      │ $0.02 (9%)     │  │
│  │  Meta               │ 47    │ 8,234 / 423      │ $0.01 (4%)     │  │
│  │  Proactive          │ 2     │ 1,234 / 89       │ $0.01 (4%)     │  │
│  │  ───────────────────┼───────┼──────────────────┼─────────────── │  │
│  │  TOTAL              │ 72    │ 28,672 / 2,514   │ $0.23          │  │
│  │                                                                  │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  ┌─ 7-Day Trend ────────────────────────────────────────────────────┐  │
│  │                                                                  │  │
│  │  $1.00 ┤                                                        │  │
│  │        │                     ╭─╮                                │  │
│  │  $0.50 ┤    ╭─╮   ╭─╮  ╭─╮ │ │ ╭─╮                             │  │
│  │        │╭─╮│ │╭─╮│ │╭─╮│ │ │ │ │ │                             │  │
│  │  $0.00 ┼─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴────                         │  │
│  │         Mon Tue Wed Thu Fri Sat Sun                             │  │
│  │                                                                  │  │
│  │  Avg: $0.31/day    Total: $2.17/week    Projected: $9.30/month  │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 12.2 Performance Dashboard

```
┌─────────────────────────────────────────────────────────────────────────┐
│  📈 Performance Metrics                                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─ Response Latency (Last Hour) ───────────────────────────────────┐  │
│  │                                                                  │  │
│  │  Agent           │ P50     │ P90     │ P99     │ Target         │  │
│  │  ─────────────────┼─────────┼─────────┼─────────┼─────────────── │  │
│  │  Instant         │ 5ms     │ 8ms     │ 15ms    │ < 10ms   ✅    │  │
│  │  Meta            │ 89ms    │ 145ms   │ 234ms   │ < 200ms  ✅    │  │
│  │  Action          │ 312ms   │ 456ms   │ 678ms   │ < 500ms  ⚠️    │  │
│  │  Interaction     │ 1,234ms │ 1,890ms │ 2,456ms │ < 3000ms ✅    │  │
│  │                                                                  │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  ┌─ End-to-End Latency Distribution ────────────────────────────────┐  │
│  │                                                                  │  │
│  │  < 500ms   ████████████████████████████░░░░░░░░░░░░░░░  62%     │  │
│  │  500-1000  ██████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  24%     │  │
│  │  1000-2000 ██████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  10%     │  │
│  │  2000-3000 ██░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   3%     │  │
│  │  > 3000ms  █░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   1%     │  │
│  │                                                                  │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  ┌─ Error Rate ─────────────────────────────────────────────────────┐  │
│  │                                                                  │  │
│  │  Total Requests: 847     Errors: 3     Error Rate: 0.35%        │  │
│  │                                                                  │  │
│  │  Recent Errors:                                                 │  │
│  │  • 10:15 AM │ LLM timeout │ Interaction Agent │ [View]          │  │
│  │  • 09:45 AM │ STT failure │ Voice Pipeline │ [View]             │  │
│  │  • 08:23 AM │ HA unavailable │ Action Agent │ [View]            │  │
│  │                                                                  │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 13. Trace Explorer

### 13.1 Waterfall Visualization

```
┌─────────────────────────────────────────────────────────────────────────┐
│  🔬 Trace Explorer                                              [Close] │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Trace ID: trace_9d8e7f6a                                              │
│  Request: "What should I wear today?" (Thom, Office)                   │
│  Total Duration: 1,847ms                                               │
│                                                                         │
│  ┌─ Waterfall View ─────────────────────────────────────────────────┐  │
│  │                                                                  │  │
│  │  0ms                                              1847ms         │  │
│  │  │                                                    │         │  │
│  │  ├─ STT Processing ─────────┤                        │  312ms   │  │
│  │  │                          │                        │         │  │
│  │  │                          ├─ Speaker ID ───┤       │  89ms    │  │
│  │  │                          │                │       │         │  │
│  │  │                          │                ├─ Meta Agent ─┤   │  156ms
│  │  │                          │                │              │   │  │
│  │  │                          │                │    ├─ Memory Retrieval │ 234ms
│  │  │                          │                │    │                │  │
│  │  │                          │                │    │    ├─ Context Build │ 45ms
│  │  │                          │                │    │    │              │  │
│  │  │                          │                │    │    │    ├─ LLM Call ─────────┤ 823ms
│  │  │                          │                │    │    │    │                    │
│  │  │                          │                │    │    │    │                    ├─ TTS │ 188ms
│  │  │                          │                │    │    │    │                    │    │
│  │  ────────────────────────────────────────────────────────────────   │
│  │                                                                  │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  ┌─ Phase Details ──────────────────────────────────────────────────┐  │
│  │                                                                  │  │
│  │  Phase              │ Duration │ % of Total │ Details           │  │
│  │  ───────────────────┼──────────┼────────────┼────────────────── │  │
│  │  STT Processing     │ 312ms    │ 17%        │ Whisper base.en   │  │
│  │  Speaker ID         │ 89ms     │ 5%         │ Thom (94% conf)   │  │
│  │  Meta Agent         │ 156ms    │ 8%         │ → Interaction     │  │
│  │  Memory Retrieval   │ 234ms    │ 13%        │ 5 memories found  │  │
│  │  Context Build      │ 45ms     │ 2%         │ 1,234 tokens      │  │
│  │  LLM Call           │ 823ms    │ 45%        │ claude-3.5-sonnet │  │
│  │  TTS Generation     │ 188ms    │ 10%        │ Piper, 2.3s audio │  │
│  │  ───────────────────┼──────────┼────────────┼────────────────── │  │
│  │  TOTAL              │ 1,847ms  │ 100%       │                   │  │
│  │                                                                  │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│                                  [Export Trace] [Compare to Average]   │
└─────────────────────────────────────────────────────────────────────────┘
```

### 13.2 Trace Explorer Controls

| Control | Function | Ease of Use Feature |
|---------|----------|---------------------|
| **Waterfall View** | Visual timing breakdown | See bottlenecks instantly |
| **Phase Details** | Detailed metrics per phase | Understand where time goes |
| **Expand Phase** | Drill into specific phase | See exact parameters |
| **Export Trace** | Download as JSON | Share for debugging |
| **Compare to Average** | Overlay average timing | Spot anomalies |
| **Link to Request** | Jump to full request inspector | Complete context |

---

## 14. System Administration

### 14.1 System Health Panel

```
┌─────────────────────────────────────────────────────────────────────────┐
│  🔧 System Administration                                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─ System Health ──────────────────────────────────────────────────┐  │
│  │                                                                  │  │
│  │  Component          │ Status │ Details                          │  │
│  │  ───────────────────┼────────┼───────────────────────────────── │  │
│  │  Core Engine        │ 🟢 OK  │ Uptime: 14d 3h 27m               │  │
│  │  Home Assistant     │ 🟢 OK  │ 2,847 entities, 0.8s avg latency │  │
│  │  Redis              │ 🟢 OK  │ Memory: 234MB / 1GB              │  │
│  │  SQLite             │ 🟢 OK  │ DB size: 1.2GB, 1.2M memories    │  │
│  │  OpenRouter         │ 🟢 OK  │ 99.9% uptime (30d)               │  │
│  │  Voice Satellites   │ 🟡 Warn│ 3/4 online (Kitchen offline)     │  │
│  │                                                                  │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  ┌─ Quick Actions ──────────────────────────────────────────────────┐  │
│  │                                                                  │  │
│  │  [Restart Core]  [Clear Cache]  [Backup Now]  [View Logs]       │  │
│  │                                                                  │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  ┌─ Log Viewer ─────────────────────────────────────────────────────┐  │
│  │                                                                  │  │
│  │  Log Level: [INFO ▼]    Component: [All ▼]    [Download]        │  │
│  │                                                                  │  │
│  │  10:25:12 INFO  core: Request processed in 1847ms               │  │
│  │  10:25:10 INFO  voice: STT transcription: "What should I..."    │  │
│  │  10:25:03 WARN  satellite: Kitchen satellite heartbeat missed   │  │
│  │  10:24:58 INFO  memory: Retrieved 5 memories (234ms)            │  │
│  │  10:24:45 INFO  presence: Elizabeth detected at front door      │  │
│  │                                                                  │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  ┌─ Backup Management ──────────────────────────────────────────────┐  │
│  │                                                                  │  │
│  │  Last Backup: Today 3:00 AM (automatic)                         │  │
│  │  Backup Size: 1.4GB                                             │  │
│  │  Retention: 7 daily, 4 weekly, 12 monthly                       │  │
│  │                                                                  │  │
│  │  Available Backups:                                             │  │
│  │  • 2026-01-17 03:00 (1.4GB) [Restore] [Download]               │  │
│  │  • 2026-01-16 03:00 (1.4GB) [Restore] [Download]               │  │
│  │  • 2026-01-15 03:00 (1.3GB) [Restore] [Download]               │  │
│  │                                                                  │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 15. Mobile Dashboard Considerations

### 15.1 Responsive Design Requirements

The dashboard must work seamlessly on:
- **Desktop** (1920x1080+): Full multi-panel layout
- **Tablet** (768-1024px): Collapsible sidebar, stacked panels
- **Mobile** (320-768px): Single-column, hamburger menu

### 15.2 Mobile-First Features

| Feature | Mobile Adaptation |
|---------|-------------------|
| **Quick Actions** | Large touch targets, bottom sheet |
| **Conversation Feed** | Swipe to inspect, pull to refresh |
| **Easy Settings** | Full-width sliders, large toggles |
| **Voice Enrollment** | Guided wizard with audio feedback |
| **Notifications** | Push notifications with action buttons |

### 15.3 Mobile Home Screen Widget

```
┌─────────────────────────┐
│ 🏠 BarnabeeNet          │
│                         │
│ 👥 4 Home │ 💬 3 Today  │
│                         │
│ 🌡️ 71°F  │ ☀️ Sunny    │
│                         │
│ [🌙 Night] [🎬 Movie]   │
└─────────────────────────┘
```

---

## 16. Implementation Roadmap

### Phase 1: Core Dashboard (Weeks 1-3)

- [ ] Basic Grafana setup with Home Assistant integration
- [ ] Real-time activity stream via WebSocket
- [ ] Conversation log with basic search
- [ ] System health monitoring

### Phase 2: Request Inspector (Weeks 4-5)

- [ ] Full context logging for all LLM calls
- [ ] Request detail view with expandable sections
- [ ] Conversation search with filters

### Phase 3: Configuration UI (Weeks 6-7)

- [ ] Easy Settings panel with sliders
- [ ] Advanced YAML editor with validation
- [ ] Override system for rooms/users

### Phase 4: Memory Dashboard (Weeks 8-9)

- [ ] Memory browser with semantic search
- [ ] Memory analytics and visualization
- [ ] Manual memory CRUD operations

### Phase 5: Agent & Trigger Management (Weeks 10-11)

- [ ] Agent status and configuration
- [ ] Visual trigger builder
- [ ] Trigger testing and history

### Phase 6: Advanced Features (Weeks 12-14)

- [ ] Trace Explorer with waterfall visualization
- [ ] Cost tracking and budgets
- [ ] Performance analytics
- [ ] Mobile optimization

### Phase 7: Polish & Documentation (Weeks 15-16)

- [ ] User documentation and tooltips
- [ ] Onboarding wizard
- [ ] Accessibility audit
- [ ] Performance optimization

---

## Appendix A: Signal Schema Reference

### A.1 Input Signals

```python
@dataclass
class VoiceInputSignal(Signal):
    signal_subtype: str = "voice_input"
    payload: VoiceInputPayload

@dataclass
class VoiceInputPayload:
    transcription: str
    confidence: float
    speaker_id: str
    speaker_confidence: float
    audio_duration_ms: int
    audio_url: Optional[str]  # If audio retention enabled
```

### A.2 Processing Signals

```python
@dataclass
class LLMRequestSignal(Signal):
    signal_subtype: str = "llm_request"
    payload: LLMRequestPayload

@dataclass
class LLMRequestPayload:
    agent: str
    model: str
    temperature: float
    max_tokens: int
    prompt_sections: Dict[str, str]
    full_prompt: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    cost_usd: float
    response: str
```

### A.3 Output Signals

```python
@dataclass
class DeviceActionSignal(Signal):
    signal_subtype: str = "device_action"
    payload: DeviceActionPayload

@dataclass
class DeviceActionPayload:
    domain: str
    service: str
    entity_id: str
    service_data: dict
    result: str
    latency_ms: int
```

---

## Appendix B: Dashboard Access Control Matrix

| Feature | Admin | Family | Guest | Child |
|---------|-------|--------|-------|-------|
| View Activity Stream | ✅ | ✅ | ✅ | ❌ |
| View Conversations | ✅ | ✅ | ❌ | ❌ |
| Inspect Requests | ✅ | ❌ | ❌ | ❌ |
| Edit Configuration | ✅ | ❌ | ❌ | ❌ |
| Easy Settings | ✅ | ✅ | ❌ | ❌ |
| View Memories | ✅ | Own only | ❌ | ❌ |
| Edit Profiles | ✅ | Own only | ❌ | ❌ |
| Create Triggers | ✅ | ❌ | ❌ | ❌ |
| View Costs | ✅ | ❌ | ❌ | ❌ |
| System Admin | ✅ | ❌ | ❌ | ❌ |

---

## Document History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-01-17 | Initial specification based on SkyrimNet analysis |

---

*This document defines the observability and control layer for BarnabeeNet. For memory system details, see BarnabeeNet_Memory_System_Enhancements.md. For agent architecture, see BarnabeeNet_Technical_Architecture.md.*
