# BarnabeeNet Technical Architecture

**Document Version:** 1.0  
**Last Updated:** January 17, 2026  
**Author:** Thom Fife  
**Status:** 📋 Planning / Reference  
**Purpose:** Comprehensive technical specification for BarnabeeNet implementation

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [System Components](#system-components)
3. [Home Assistant Integration](#home-assistant-integration)
4. [Multi-Agent System Design](#multi-agent-system-design)
5. [Message Bus Architecture](#message-bus-architecture)
6. [Voice Processing Pipeline](#voice-processing-pipeline)
7. [Speaker Recognition System](#speaker-recognition-system)
8. [Memory System Architecture](#memory-system-architecture)
9. [Database Schema](#database-schema)
10. [API Specifications](#api-specifications)
11. [LLM Orchestration](#llm-orchestration)
12. [Multi-Modal Input Processing](#multi-modal-input-processing)
13. [Security Architecture](#security-architecture)
14. [Performance Optimization](#performance-optimization)
15. [Deployment Architecture](#deployment-architecture)
16. [Monitoring & Observability](#monitoring--observability)

---

## Architecture Overview

### High-Level System Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           BARNABEENET ARCHITECTURE                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                     INPUT LAYER (Multi-Modal)                        │    │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐       │    │
│  │  │ Voice   │ │   AR    │ │ Touch   │ │Wearable │ │ Alexa/  │       │    │
│  │  │(Whisper)│ │(Glasses)│ │(Tablet) │ │(Amazfit)│ │ ThinkS  │       │    │
│  │  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘       │    │
│  └───────┼──────────┼──────────┼──────────┼──────────┼────────────────┘    │
│          │          │          │          │          │                      │
│          └──────────┴──────────┴──────────┴──────────┘                      │
│                              │                                               │
│  ┌───────────────────────────▼───────────────────────────────────────────┐  │
│  │                      PROCESSING LAYER                                  │  │
│  │  ┌─────────────────────────────────────────────────────────────────┐  │  │
│  │  │                    MESSAGE BUS (Redis Streams)                   │  │  │
│  │  └──────────────────────────┬──────────────────────────────────────┘  │  │
│  │                             │                                          │  │
│  │  ┌──────────────────────────▼──────────────────────────────────────┐  │  │
│  │  │                      META AGENT (Router)                         │  │  │
│  │  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │  │  │
│  │  │  │Pattern Match│  │ LLM Fallback│  │   Policy Engine Check   │  │  │  │
│  │  │  └─────────────┘  └─────────────┘  └─────────────────────────┘  │  │  │
│  │  └──────────────────────────┬──────────────────────────────────────┘  │  │
│  │                             │                                          │  │
│  │         ┌───────────────────┼───────────────────┐                     │  │
│  │         │                   │                   │                     │  │
│  │  ┌──────▼──────┐     ┌──────▼──────┐     ┌──────▼──────┐             │  │
│  │  │   INSTANT   │     │   ACTION    │     │ INTERACTION │             │  │
│  │  │    AGENT    │     │    AGENT    │     │    AGENT    │             │  │
│  │  │   (<5ms)    │     │  (<100ms)   │     │   (<3s)     │             │  │
│  │  └─────────────┘     └──────┬──────┘     └──────┬──────┘             │  │
│  │                             │                   │                     │  │
│  │  ┌─────────────┐     ┌──────▼──────┐     ┌──────▼──────┐             │  │
│  │  │  PROACTIVE  │     │   MEMORY    │     │   EVOLVER   │             │  │
│  │  │    AGENT    │     │    AGENT    │     │    AGENT    │             │  │
│  │  │ (Background)│     │  (<50ms)    │     │ (Scheduled) │             │  │
│  │  └─────────────┘     └─────────────┘     └─────────────┘             │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │                        DATA LAYER                                      │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │  │
│  │  │   SQLite    │  │    Redis    │  │   Speaker   │  │   Vector    │   │  │
│  │  │ (Persistent)│  │  (Ephemeral)│  │  Embeddings │  │  (sqlite-vec)│   │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘   │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │                       OUTPUT LAYER                                     │  │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐         │  │
│  │  │   TTS   │ │   AR    │ │ Home    │ │ Watch   │ │Dashboard│         │  │
│  │  │(Kokoro) │ │ Overlay │ │Assistant│ │ Haptic  │ │  Panel  │         │  │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘         │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Technology Stack

| Layer | Technology | Version | Purpose |
|-------|------------|---------|---------|
| **Runtime** | Python | 3.13+ | Core application |
| **Framework** | Home Assistant | 2025.12+ | Automation backbone |
| **Async** | asyncio | stdlib | Non-blocking I/O |
| **Message Bus** | Redis Streams | 7.0+ | Inter-agent communication |
| **Database** | SQLite | 3.45+ | Persistent storage |
| **Vector Search** | sqlite-vec | 0.1+ | Semantic memory |
| **STT (CPU)** | Distil-Whisper | 1.0+ | Speech recognition (Beelink fallback) |
| **STT (GPU)** | Parakeet TDT 0.6B v2 | 1.22+ | Speech recognition (Man-of-war primary) |
| **TTS** | Kokoro | 0.3+ | Voice synthesis (replaced Piper - faster, better quality) |
| **Speaker ID** | SpeechBrain | 1.0+ | ECAPA-TDNN embeddings |
| **Embeddings** | sentence-transformers | 2.2+ | Text embeddings |
| **LLM Routing** | OpenRouter | 1.0+ | Multi-model orchestration |
| **Caching** | Redis | 7.0+ | Working memory |

### Design Principles

1. **Async-First**: All I/O operations use `async/await`
2. **Event-Driven**: Agents communicate via message bus, not direct calls
3. **Fail-Safe**: Graceful degradation when services unavailable
4. **Observable**: All operations traced and logged

### GPU Worker Architecture

BarnabeeNet employs a two-tier compute architecture for voice processing:

```
┌─────────────────────────────────────────────────────────────────────┐
│                     STT ROUTING (Zero-Latency Decision)             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   Background Health Check (every 3s):                               │
│   → Ping Man-of-war GPU worker                                      │
│   → Update cached availability state                                │
│                                                                     │
│   Request Path (instant):                                           │
│   → Read cached state (no waiting)                                  │
│   → Route to available backend                                      │
│                                                                     │
│   ┌─────────────────────┐         ┌─────────────────────┐          │
│   │  Man-of-war (GPU)   │         │   Beelink (CPU)     │          │
│   │  Parakeet TDT       │         │   Distil-Whisper    │          │
│   │  ~20-40ms total     │         │   ~150-300ms        │          │
│   │  PRIMARY            │         │   FALLBACK          │          │
│   └─────────────────────┘         └─────────────────────┘          │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

| Tier | Hardware | STT Model | Latency | Availability |
|------|----------|-----------|---------|--------------|
| Primary | Man-of-war (RTX 4070 Ti) | Parakeet TDT 0.6B v2 | ~20-40ms | When awake |
| Fallback | Beelink VM (CPU) | Distil-Whisper small.en | ~150-300ms | Always |

The health check runs out-of-band, so routing decisions add zero latency to the request path.
5. **Testable**: Dependency injection for all external services

---

## System Components

### Component Hierarchy

```
barnabeenet/
├── __init__.py                 # Integration entry point
├── manifest.json               # HA component metadata
├── config_flow.py              # UI configuration wizard
├── const.py                    # Constants and configuration
├── coordinator.py              # Data update coordinator
│
├── core/                       # Core infrastructure
│   ├── __init__.py
│   ├── bus.py                  # Message bus implementation
│   ├── policy.py               # Policy engine
│   ├── context.py              # Request context management
│   └── exceptions.py           # Custom exceptions
│
├── agents/                     # Multi-agent system
│   ├── __init__.py
│   ├── base.py                 # Base agent class
│   ├── meta_agent.py           # Router/classifier
│   ├── instant_agent.py        # Pattern-matched responses
│   ├── action_agent.py         # Device control
│   ├── interaction_agent.py    # Complex conversations
│   ├── memory_agent.py         # Memory operations
│   ├── proactive_agent.py      # Background monitoring
│   └── evolver_agent.py        # Self-improvement
│
├── voice/                      # Voice processing
│   ├── __init__.py
│   ├── stt.py                  # Speech-to-text
│   ├── tts.py                  # Text-to-speech
│   ├── speaker_id.py           # Speaker recognition
│   ├── wake_word.py            # Wake word detection
│   └── vad.py                  # Voice activity detection
│
├── multimodal/                 # Multi-modal inputs
│   ├── __init__.py
│   ├── ar_glasses.py           # Even Realities SDK
│   ├── wearable.py             # Amazfit integration
│   ├── bluetooth.py            # Headset audio
│   └── dashboard.py            # ThinkSmart Views
│
├── memory/                     # Memory system
│   ├── __init__.py
│   ├── working.py              # Redis short-term
│   ├── episodic.py             # Conversation history
│   ├── semantic.py             # Extracted facts
│   ├── procedural.py           # Learned routines
│   ├── embeddings.py           # Vector operations
│   └── consolidation.py        # Batch processing
│
├── llm/                        # LLM orchestration
│   ├── __init__.py
│   ├── router.py               # Model selection
│   ├── openrouter.py           # OpenRouter client
│   ├── local.py                # Local model inference
│   └── prompts.py              # Prompt templates
│
├── services/                   # HA service definitions
│   ├── __init__.py
│   └── services.yaml           # Service schemas
│
├── models/                     # Data models
│   ├── __init__.py
│   ├── request.py              # Request/Response models
│   ├── memory.py               # Memory models
│   ├── user.py                 # User/Speaker models
│   └── events.py               # Event models
│
└── frontend/                   # Dashboard UI
    ├── panel.js                # Main panel
    ├── styles.css              # Styling
    └── components/             # UI components
```

### Component Dependencies

```
┌─────────────────────────────────────────────────────────────────┐
│                    DEPENDENCY GRAPH                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│                      ┌─────────────┐                            │
│                      │   config    │                            │
│                      └──────┬──────┘                            │
│                             │                                    │
│              ┌──────────────┼──────────────┐                    │
│              │              │              │                    │
│       ┌──────▼──────┐ ┌─────▼─────┐ ┌─────▼─────┐              │
│       │    core     │ │  models   │ │   const   │              │
│       └──────┬──────┘ └─────┬─────┘ └───────────┘              │
│              │              │                                    │
│       ┌──────┴──────────────┴──────────────┐                    │
│       │                                     │                    │
│  ┌────▼────┐  ┌────────┐  ┌────────┐  ┌────▼────┐              │
│  │  voice  │  │ memory │  │  llm   │  │ agents  │              │
│  └────┬────┘  └────┬───┘  └────┬───┘  └────┬────┘              │
│       │            │           │           │                    │
│       └────────────┴───────────┴───────────┘                    │
│                         │                                        │
│                  ┌──────▼──────┐                                │
│                  │ coordinator │                                │
│                  └──────┬──────┘                                │
│                         │                                        │
│                  ┌──────▼──────┐                                │
│                  │  __init__   │                                │
│                  └─────────────┘                                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Home Assistant Integration

### Manifest Configuration

```json
{
  "domain": "barnabeenet",
  "name": "BarnabeeNet Voice Assistant",
  "version": "3.0.0",
  "documentation": "https://github.com/thomfife/barnabeenet",
  "issue_tracker": "https://github.com/thomfife/barnabeenet/issues",
  "dependencies": ["conversation", "intent", "media_player"],
  "after_dependencies": ["zha", "zwave_js", "mqtt"],
  "codeowners": ["@thomfife"],
  "requirements": [
    "faster-whisper>=1.0.0",
    "speechbrain>=1.0.0",
    "redis>=5.0.0",
    "sentence-transformers>=2.2.0",
    "kokoro>=0.3.0",
    "openai>=1.0.0",
    "anthropic>=0.20.0",
    "aiohttp>=3.9.0"
  ],
  "iot_class": "local_push",
  "config_flow": true,
  "quality_scale": "silver"
}
```

### Integration Entry Point

```python
# __init__.py
"""BarnabeeNet Voice Assistant Integration."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .coordinator import BarnabeeNetCoordinator

if TYPE_CHECKING:
    from .core.bus import MessageBus

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SELECT,
    Platform.SWITCH,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the BarnabeeNet component."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up BarnabeeNet from a config entry."""
    
    # Initialize coordinator
    coordinator = BarnabeeNetCoordinator(hass, entry)
    await coordinator.async_initialize()
    
    # Store coordinator reference
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
    }
    
    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    # Register services
    await coordinator.async_register_services()
    
    # Start background tasks
    await coordinator.async_start_background_tasks()
    
    _LOGGER.info("BarnabeeNet initialized successfully")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    
    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        # Clean up coordinator
        coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
        await coordinator.async_shutdown()
        hass.data[DOMAIN].pop(entry.entry_id)
    
    return unload_ok
```

### Data Coordinator

```python
# coordinator.py
"""BarnabeeNet Data Coordinator."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, SCAN_INTERVAL
from .core.bus import MessageBus
from .core.policy import PolicyEngine
from .agents import AgentOrchestrator
from .voice import VoicePipeline
from .memory import MemoryManager

if TYPE_CHECKING:
    pass

_LOGGER = logging.getLogger(__name__)


class BarnabeeNetCoordinator(DataUpdateCoordinator):
    """Coordinate BarnabeeNet data and operations."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=SCAN_INTERVAL),
        )
        self.entry = entry
        self.config = entry.data
        
        # Core components (initialized in async_initialize)
        self.bus: MessageBus | None = None
        self.policy: PolicyEngine | None = None
        self.agents: AgentOrchestrator | None = None
        self.voice: VoicePipeline | None = None
        self.memory: MemoryManager | None = None
        
        # Background tasks
        self._background_tasks: set[asyncio.Task] = set()

    async def async_initialize(self) -> None:
        """Initialize all components."""
        _LOGGER.info("Initializing BarnabeeNet components...")
        
        # Initialize message bus first (other components depend on it)
        self.bus = MessageBus(self.hass, self.config)
        await self.bus.async_connect()
        
        # Initialize policy engine
        self.policy = PolicyEngine(self.hass, self.config)
        await self.policy.async_load_policies()
        
        # Initialize memory manager
        self.memory = MemoryManager(self.hass, self.config, self.bus)
        await self.memory.async_initialize()
        
        # Initialize voice pipeline
        self.voice = VoicePipeline(self.hass, self.config, self.bus)
        await self.voice.async_initialize()
        
        # Initialize agent orchestrator (depends on all above)
        self.agents = AgentOrchestrator(
            hass=self.hass,
            config=self.config,
            bus=self.bus,
            policy=self.policy,
            memory=self.memory,
            voice=self.voice,
        )
        await self.agents.async_initialize()
        
        _LOGGER.info("BarnabeeNet initialization complete")

    async def async_register_services(self) -> None:
        """Register Home Assistant services."""
        
        async def handle_process_voice(call: ServiceCall) -> dict:
            """Handle voice processing service call."""
            audio_data = call.data.get("audio_data")
            speaker_hint = call.data.get("speaker_hint")
            device_id = call.data.get("device_id")
            
            result = await self.voice.async_process(
                audio_data=audio_data,
                speaker_hint=speaker_hint,
                device_id=device_id,
            )
            return result
        
        async def handle_enroll_speaker(call: ServiceCall) -> dict:
            """Handle speaker enrollment service call."""
            name = call.data.get("name")
            audio_samples = call.data.get("audio_samples")
            permissions = call.data.get("permissions", [])
            
            result = await self.voice.speaker_id.async_enroll(
                name=name,
                audio_samples=audio_samples,
                permissions=permissions,
            )
            return result
        
        async def handle_query_memory(call: ServiceCall) -> dict:
            """Handle memory query service call."""
            query = call.data.get("query")
            speaker_id = call.data.get("speaker_id")
            memory_type = call.data.get("memory_type", "all")
            limit = call.data.get("limit", 10)
            
            results = await self.memory.async_search(
                query=query,
                speaker_id=speaker_id,
                memory_type=memory_type,
                limit=limit,
            )
            return {"results": results}
        
        async def handle_process_text(call: ServiceCall) -> dict:
            """Handle text processing (non-voice) service call."""
            text = call.data.get("text")
            speaker_id = call.data.get("speaker_id", "unknown")
            device_id = call.data.get("device_id")
            
            result = await self.agents.async_process_request(
                text=text,
                speaker_id=speaker_id,
                device_id=device_id,
            )
            return result
        
        # Register services
        self.hass.services.async_register(
            DOMAIN, "process_voice", handle_process_voice
        )
        self.hass.services.async_register(
            DOMAIN, "enroll_speaker", handle_enroll_speaker
        )
        self.hass.services.async_register(
            DOMAIN, "query_memory", handle_query_memory
        )
        self.hass.services.async_register(
            DOMAIN, "process_text", handle_process_text
        )

    async def async_start_background_tasks(self) -> None:
        """Start background processing tasks."""
        
        # Proactive agent monitoring
        task = asyncio.create_task(self.agents.proactive.async_run_monitor())
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        
        # Memory consolidation (runs nightly)
        task = asyncio.create_task(self.memory.async_run_consolidation_scheduler())
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        
        # Message bus consumer
        task = asyncio.create_task(self.bus.async_consume_events())
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

    async def async_shutdown(self) -> None:
        """Shutdown all components gracefully."""
        _LOGGER.info("Shutting down BarnabeeNet...")
        
        # Cancel background tasks
        for task in self._background_tasks:
            task.cancel()
        
        # Wait for tasks to complete
        if self._background_tasks:
            await asyncio.gather(*self._background_tasks, return_exceptions=True)
        
        # Shutdown components in reverse order
        if self.agents:
            await self.agents.async_shutdown()
        if self.voice:
            await self.voice.async_shutdown()
        if self.memory:
            await self.memory.async_shutdown()
        if self.bus:
            await self.bus.async_disconnect()
        
        _LOGGER.info("BarnabeeNet shutdown complete")

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data for coordinator update."""
        return {
            "stats": await self._get_stats(),
            "recent_conversations": await self._get_recent_conversations(),
            "active_sessions": await self._get_active_sessions(),
        }

    async def _get_stats(self) -> dict:
        """Get system statistics."""
        return {
            "total_commands_today": await self.memory.async_get_command_count_today(),
            "avg_latency_action": await self.memory.async_get_avg_latency("action"),
            "avg_latency_query": await self.memory.async_get_avg_latency("query"),
            "cloud_calls_today": await self.memory.async_get_cloud_call_count_today(),
            "estimated_cost_today": await self.memory.async_get_estimated_cost_today(),
        }

    async def _get_recent_conversations(self) -> list[dict]:
        """Get recent conversation summaries."""
        return await self.memory.async_get_recent_conversations(limit=10)

    async def _get_active_sessions(self) -> list[dict]:
        """Get active conversation sessions."""
        return await self.memory.working.async_get_active_sessions()
```

---

## Multi-Agent System Design

### Base Agent Class

```python
# agents/base.py
"""Base Agent implementation."""
from __future__ import annotations

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable
from enum import Enum

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from ..core.bus import MessageBus
    from ..core.policy import PolicyEngine
    from ..memory import MemoryManager

_LOGGER = logging.getLogger(__name__)


class AgentType(Enum):
    """Agent type enumeration."""
    META = "meta"
    INSTANT = "instant"
    ACTION = "action"
    INTERACTION = "interaction"
    MEMORY = "memory"
    PROACTIVE = "proactive"
    EVOLVER = "evolver"


class IntentCategory(Enum):
    """Intent classification categories."""
    INSTANT = "instant"          # No LLM needed
    ACTION = "action"            # Device control
    QUERY = "query"              # Information retrieval
    CONVERSATION = "conversation" # Multi-turn dialogue
    MEMORY = "memory"            # Personal context
    EMERGENCY = "emergency"      # Safety-critical
    PROACTIVE = "proactive"      # Background notification
    GESTURE = "gesture"          # Wearable input
    UNKNOWN = "unknown"          # Requires classification


@dataclass
class AgentRequest:
    """Request to an agent."""
    request_id: str
    text: str
    speaker_id: str
    speaker_confidence: float
    device_id: str | None
    privacy_zone: str
    timestamp: float
    session_id: str
    context: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)


@dataclass
class AgentResponse:
    """Response from an agent."""
    request_id: str
    text: str
    actions: list[dict] = field(default_factory=list)
    tts_audio: bytes | None = None
    ar_overlay: dict | None = None
    watch_notification: dict | None = None
    confidence: float = 1.0
    agent_type: AgentType | None = None
    processing_time_ms: int = 0
    cloud_used: bool = False
    metadata: dict = field(default_factory=dict)


class BaseAgent(ABC):
    """Base class for all agents."""

    agent_type: AgentType
    latency_target_ms: int = 1000

    def __init__(
        self,
        hass: HomeAssistant,
        config: dict,
        bus: MessageBus,
        policy: PolicyEngine,
        memory: MemoryManager,
    ) -> None:
        """Initialize base agent."""
        self.hass = hass
        self.config = config
        self.bus = bus
        self.policy = policy
        self.memory = memory
        self._initialized = False
        self._logger = logging.getLogger(f"{__name__}.{self.agent_type.value}")

    async def async_initialize(self) -> None:
        """Initialize the agent."""
        self._logger.info(f"Initializing {self.agent_type.value} agent")
        await self._async_setup()
        self._initialized = True
        self._logger.info(f"{self.agent_type.value} agent initialized")

    @abstractmethod
    async def _async_setup(self) -> None:
        """Agent-specific setup (override in subclass)."""
        pass

    @abstractmethod
    async def async_process(self, request: AgentRequest) -> AgentResponse:
        """Process a request (override in subclass)."""
        pass

    async def async_handle_request(self, request: AgentRequest) -> AgentResponse:
        """Handle a request with timing and error handling."""
        start_time = time.perf_counter()
        
        try:
            # Check policy
            policy_result = await self.policy.async_check(request, self.agent_type)
            if not policy_result.allowed:
                return AgentResponse(
                    request_id=request.request_id,
                    text=policy_result.denial_message or "Sorry, I can't do that.",
                    confidence=1.0,
                    agent_type=self.agent_type,
                )
            
            # Process request
            response = await self.async_process(request)
            
            # Calculate processing time
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            response.processing_time_ms = elapsed_ms
            response.agent_type = self.agent_type
            
            # Log if over latency target
            if elapsed_ms > self.latency_target_ms:
                self._logger.warning(
                    f"{self.agent_type.value} exceeded latency target: "
                    f"{elapsed_ms}ms > {self.latency_target_ms}ms"
                )
            
            # Emit metrics event
            await self.bus.async_emit("agent.processed", {
                "agent_type": self.agent_type.value,
                "request_id": request.request_id,
                "processing_time_ms": elapsed_ms,
                "cloud_used": response.cloud_used,
            })
            
            return response
            
        except Exception as e:
            self._logger.error(f"Error processing request: {e}", exc_info=True)
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            
            return AgentResponse(
                request_id=request.request_id,
                text="Sorry, I encountered an error processing that request.",
                confidence=0.0,
                agent_type=self.agent_type,
                processing_time_ms=elapsed_ms,
                metadata={"error": str(e)},
            )

    async def async_shutdown(self) -> None:
        """Shutdown the agent."""
        self._logger.info(f"Shutting down {self.agent_type.value} agent")
        await self._async_cleanup()
        self._initialized = False

    async def _async_cleanup(self) -> None:
        """Agent-specific cleanup (override in subclass if needed)."""
        pass
```

### Agent Orchestrator

```python
# agents/__init__.py
"""Agent Orchestrator - coordinates all agents."""
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from .base import AgentRequest, AgentResponse, AgentType, IntentCategory
from .meta_agent import MetaAgent
from .instant_agent import InstantAgent
from .action_agent import ActionAgent
from .interaction_agent import InteractionAgent
from .memory_agent import MemoryAgent
from .proactive_agent import ProactiveAgent
from .evolver_agent import EvolverAgent

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from ..core.bus import MessageBus
    from ..core.policy import PolicyEngine
    from ..memory import MemoryManager
    from ..voice import VoicePipeline

_LOGGER = logging.getLogger(__name__)


class AgentOrchestrator:
    """Orchestrate multi-agent processing."""

    def __init__(
        self,
        hass: HomeAssistant,
        config: dict,
        bus: MessageBus,
        policy: PolicyEngine,
        memory: MemoryManager,
        voice: VoicePipeline,
    ) -> None:
        """Initialize orchestrator."""
        self.hass = hass
        self.config = config
        self.bus = bus
        self.policy = policy
        self.memory = memory
        self.voice = voice
        
        # Initialize agents
        agent_kwargs = {
            "hass": hass,
            "config": config,
            "bus": bus,
            "policy": policy,
            "memory": memory,
        }
        
        self.meta = MetaAgent(**agent_kwargs)
        self.instant = InstantAgent(**agent_kwargs)
        self.action = ActionAgent(**agent_kwargs, voice=voice)
        self.interaction = InteractionAgent(**agent_kwargs, voice=voice)
        self.memory_agent = MemoryAgent(**agent_kwargs)
        self.proactive = ProactiveAgent(**agent_kwargs, voice=voice)
        self.evolver = EvolverAgent(**agent_kwargs)
        
        # Agent routing map
        self._agent_map = {
            IntentCategory.INSTANT: self.instant,
            IntentCategory.ACTION: self.action,
            IntentCategory.QUERY: self.interaction,
            IntentCategory.CONVERSATION: self.interaction,
            IntentCategory.MEMORY: self.memory_agent,
            IntentCategory.GESTURE: self.action,
        }

    async def async_initialize(self) -> None:
        """Initialize all agents."""
        _LOGGER.info("Initializing agent orchestrator...")
        
        # Initialize in parallel
        await asyncio.gather(
            self.meta.async_initialize(),
            self.instant.async_initialize(),
            self.action.async_initialize(),
            self.interaction.async_initialize(),
            self.memory_agent.async_initialize(),
            self.proactive.async_initialize(),
            self.evolver.async_initialize(),
        )
        
        _LOGGER.info("Agent orchestrator initialized")

    async def async_process_request(
        self,
        text: str,
        speaker_id: str,
        device_id: str | None = None,
        session_id: str | None = None,
        context: dict | None = None,
    ) -> dict:
        """Process a text request through the agent pipeline."""
        import uuid
        import time
        
        # Create request object
        request = AgentRequest(
            request_id=str(uuid.uuid4()),
            text=text,
            speaker_id=speaker_id,
            speaker_confidence=1.0,  # Text input, no speaker verification
            device_id=device_id,
            privacy_zone=await self._get_privacy_zone(device_id),
            timestamp=time.time(),
            session_id=session_id or str(uuid.uuid4()),
            context=context or {},
        )
        
        # Load conversation context from working memory
        request.context["history"] = await self.memory.working.async_get_context(
            session_id=request.session_id,
            speaker_id=speaker_id,
        )
        
        # Route through meta agent
        classification = await self.meta.async_classify(request)
        
        # Get appropriate agent
        agent = self._agent_map.get(classification.intent, self.interaction)
        
        # Process request
        response = await agent.async_handle_request(request)
        
        # Store in memory
        await self.memory.async_store_conversation(request, response)
        
        # Generate TTS if needed
        if response.text and not response.tts_audio:
            response.tts_audio = await self.voice.tts.async_synthesize(response.text)
        
        return {
            "request_id": response.request_id,
            "text": response.text,
            "audio": response.tts_audio,
            "actions": response.actions,
            "ar_overlay": response.ar_overlay,
            "watch_notification": response.watch_notification,
            "agent_type": response.agent_type.value if response.agent_type else None,
            "processing_time_ms": response.processing_time_ms,
            "cloud_used": response.cloud_used,
        }

    async def _get_privacy_zone(self, device_id: str | None) -> str:
        """Determine privacy zone from device location."""
        if not device_id:
            return "unknown"
        
        # Look up device area in Home Assistant
        device_registry = self.hass.helpers.device_registry.async_get(self.hass)
        area_registry = self.hass.helpers.area_registry.async_get(self.hass)
        
        device = device_registry.async_get(device_id)
        if device and device.area_id:
            area = area_registry.async_get_area(device.area_id)
            if area:
                # Map area to privacy zone
                return self._map_area_to_zone(area.name)
        
        return "common_area"

    def _map_area_to_zone(self, area_name: str) -> str:
        """Map area name to privacy zone."""
        zone_mapping = self.config.get("privacy_zones", {})
        
        for zone, areas in zone_mapping.items():
            if area_name.lower() in [a.lower() for a in areas]:
                return zone
        
        return "common_area"

    async def async_shutdown(self) -> None:
        """Shutdown all agents."""
        _LOGGER.info("Shutting down agent orchestrator...")
        
        await asyncio.gather(
            self.meta.async_shutdown(),
            self.instant.async_shutdown(),
            self.action.async_shutdown(),
            self.interaction.async_shutdown(),
            self.memory_agent.async_shutdown(),
            self.proactive.async_shutdown(),
            self.evolver.async_shutdown(),
        )
        
        _LOGGER.info("Agent orchestrator shutdown complete")
```

### Meta Agent (Router)

```python
# agents/meta_agent.py
"""Meta Agent - Request classification and routing."""
from __future__ import annotations

import re
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .base import BaseAgent, AgentType, IntentCategory, AgentRequest, AgentResponse

if TYPE_CHECKING:
    pass

_LOGGER = logging.getLogger(__name__)


@dataclass
class ClassificationResult:
    """Result of intent classification."""
    intent: IntentCategory
    confidence: float
    sub_category: str | None = None
    entities: dict | None = None


class MetaAgent(BaseAgent):
    """Meta agent for request classification and routing."""

    agent_type = AgentType.META
    latency_target_ms = 20

    # Pattern matching rules (Phase 1: rule-based)
    INSTANT_PATTERNS = [
        (r"^(what('s| is) the )?(current )?time(\?)?$", "time"),
        (r"^(what('s| is) )?(today'?s? )?date(\?)?$", "date"),
        (r"^(hello|hey|hi)( barnabee)?(\?)?$", "greeting"),
        (r"^good (morning|afternoon|evening|night)$", "greeting"),
        (r"^(what('s| is) )?(\d+)\s*[\+\-\*\/]\s*(\d+)(\?)?$", "math"),
        (r"^(how are you|you okay)(\?)?$", "status"),
        (r"^thank(s| you).*$", "thanks"),
    ]

    ACTION_PATTERNS = [
        (r"^(turn|switch) (on|off) .*$", "switch"),
        (r"^(set|change) .* to .*$", "set"),
        (r"^(dim|brighten) .*$", "light"),
        (r"^(lock|unlock) .*$", "lock"),
        (r"^(open|close) .*$", "cover"),
        (r"^(play|pause|stop|skip) .*$", "media"),
        (r"^activate .*$", "scene"),
        (r"^(start|stop) .* mode$", "mode"),
    ]

    QUERY_PATTERNS = [
        (r"^(what('s| is) the )?(temperature|weather|humidity) .*$", "sensor"),
        (r"^(is|are) .* (on|off|open|closed|locked|unlocked)(\?)?$", "state"),
        (r"^(what|how much|how many) .*$", "query"),
        (r"^(when|where) .*$", "query"),
    ]

    MEMORY_PATTERNS = [
        (r"^remember (that )?.*$", "store"),
        (r"^(do you remember|what do you know about) .*$", "recall"),
        (r"^forget .*$", "forget"),
        (r"^(when|what) did (i|we) .*$", "recall"),
    ]

    GESTURE_PATTERNS = [
        (r"^crown_twist_(yes|no|up|down)$", "choice"),
        (r"^button_click_(confirm|cancel)$", "confirm"),
        (r"^motion_shake$", "dismiss"),
        (r"^double_tap$", "quick_action"),
    ]

    async def _async_setup(self) -> None:
        """Setup meta agent."""
        # Compile patterns for efficiency
        self._instant_patterns = [
            (re.compile(p, re.IGNORECASE), c) for p, c in self.INSTANT_PATTERNS
        ]
        self._action_patterns = [
            (re.compile(p, re.IGNORECASE), c) for p, c in self.ACTION_PATTERNS
        ]
        self._query_patterns = [
            (re.compile(p, re.IGNORECASE), c) for p, c in self.QUERY_PATTERNS
        ]
        self._memory_patterns = [
            (re.compile(p, re.IGNORECASE), c) for p, c in self.MEMORY_PATTERNS
        ]
        self._gesture_patterns = [
            (re.compile(p, re.IGNORECASE), c) for p, c in self.GESTURE_PATTERNS
        ]

    async def async_process(self, request: AgentRequest) -> AgentResponse:
        """Process is not used for meta agent - use async_classify instead."""
        raise NotImplementedError("Use async_classify for MetaAgent")

    async def async_classify(self, request: AgentRequest) -> ClassificationResult:
        """Classify the intent of a request."""
        text = request.text.strip()
        
        # Phase 1: Pattern matching (fast path)
        result = self._pattern_match(text)
        if result.confidence >= 0.9:
            self._logger.debug(
                f"Pattern match: {result.intent.value} "
                f"(conf={result.confidence}, sub={result.sub_category})"
            )
            return result
        
        # Phase 2: Heuristic classification
        result = self._heuristic_classify(text, request.context)
        if result.confidence >= 0.7:
            self._logger.debug(
                f"Heuristic match: {result.intent.value} "
                f"(conf={result.confidence})"
            )
            return result
        
        # Phase 3: LLM fallback (only for ambiguous cases)
        result = await self._llm_classify(text, request.context)
        self._logger.debug(
            f"LLM classification: {result.intent.value} "
            f"(conf={result.confidence})"
        )
        return result

    def _pattern_match(self, text: str) -> ClassificationResult:
        """Pattern-based classification."""
        
        # Check instant patterns
        for pattern, sub_category in self._instant_patterns:
            if pattern.match(text):
                return ClassificationResult(
                    intent=IntentCategory.INSTANT,
                    confidence=0.95,
                    sub_category=sub_category,
                )
        
        # Check gesture patterns
        for pattern, sub_category in self._gesture_patterns:
            if pattern.match(text):
                return ClassificationResult(
                    intent=IntentCategory.GESTURE,
                    confidence=0.95,
                    sub_category=sub_category,
                )
        
        # Check action patterns
        for pattern, sub_category in self._action_patterns:
            if pattern.match(text):
                return ClassificationResult(
                    intent=IntentCategory.ACTION,
                    confidence=0.90,
                    sub_category=sub_category,
                )
        
        # Check memory patterns
        for pattern, sub_category in self._memory_patterns:
            if pattern.match(text):
                return ClassificationResult(
                    intent=IntentCategory.MEMORY,
                    confidence=0.90,
                    sub_category=sub_category,
                )
        
        # Check query patterns
        for pattern, sub_category in self._query_patterns:
            if pattern.match(text):
                return ClassificationResult(
                    intent=IntentCategory.QUERY,
                    confidence=0.85,
                    sub_category=sub_category,
                )
        
        # No pattern match
        return ClassificationResult(
            intent=IntentCategory.UNKNOWN,
            confidence=0.0,
        )

    def _heuristic_classify(
        self, text: str, context: dict
    ) -> ClassificationResult:
        """Heuristic-based classification."""
        text_lower = text.lower()
        
        # Check for conversation continuation
        if context.get("history") and len(context["history"]) > 0:
            # Likely a follow-up
            return ClassificationResult(
                intent=IntentCategory.CONVERSATION,
                confidence=0.75,
            )
        
        # Check for question markers
        if text.endswith("?") or text_lower.startswith(
            ("what", "where", "when", "who", "how", "why", "is", "are", "can", "could")
        ):
            return ClassificationResult(
                intent=IntentCategory.QUERY,
                confidence=0.70,
            )
        
        # Check for imperative verbs (commands)
        command_verbs = [
            "turn", "set", "change", "make", "adjust", "open", "close",
            "start", "stop", "play", "pause", "lock", "unlock", "activate"
        ]
        first_word = text_lower.split()[0] if text_lower.split() else ""
        if first_word in command_verbs:
            return ClassificationResult(
                intent=IntentCategory.ACTION,
                confidence=0.70,
            )
        
        # Default to conversation
        return ClassificationResult(
            intent=IntentCategory.CONVERSATION,
            confidence=0.50,
        )

    async def _llm_classify(
        self, text: str, context: dict
    ) -> ClassificationResult:
        """LLM-based classification (fallback)."""
        from ..llm import LLMRouter
        
        prompt = f"""Classify the following user request into one of these categories:
- instant: Simple factual queries (time, date, greetings, math)
- action: Device control commands (lights, locks, thermostats, media)
- query: Information requests about home state or general knowledge
- conversation: Multi-turn dialogue, complex reasoning, creative requests
- memory: Requests to remember or recall personal information

User request: "{text}"

Context: {context.get('history', [])[-3:] if context.get('history') else 'No previous context'}

Respond with only the category name and confidence (0.0-1.0), separated by comma.
Example: action, 0.85"""

        try:
            llm = LLMRouter(self.hass, self.config)
            response = await llm.async_complete(
                prompt=prompt,
                model="fast",  # Use fast model for classification
                max_tokens=20,
            )
            
            # Parse response
            parts = response.strip().split(",")
            category = parts[0].strip().lower()
            confidence = float(parts[1].strip()) if len(parts) > 1 else 0.7
            
            # Map to IntentCategory
            category_map = {
                "instant": IntentCategory.INSTANT,
                "action": IntentCategory.ACTION,
                "query": IntentCategory.QUERY,
                "conversation": IntentCategory.CONVERSATION,
                "memory": IntentCategory.MEMORY,
            }
            
            intent = category_map.get(category, IntentCategory.CONVERSATION)
            
            return ClassificationResult(
                intent=intent,
                confidence=confidence,
            )
            
        except Exception as e:
            self._logger.warning(f"LLM classification failed: {e}")
            return ClassificationResult(
                intent=IntentCategory.CONVERSATION,
                confidence=0.50,
            )
```

### Action Agent

```python
# agents/action_agent.py
"""Action Agent - Device control and automation."""
from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.core import ServiceCall
from homeassistant.helpers import entity_registry

from .base import BaseAgent, AgentType, AgentRequest, AgentResponse

if TYPE_CHECKING:
    from ..voice import VoicePipeline

_LOGGER = logging.getLogger(__name__)


class ActionAgent(BaseAgent):
    """Agent for device control and home automation."""

    agent_type = AgentType.ACTION
    latency_target_ms = 100

    def __init__(self, *args, voice: VoicePipeline, **kwargs) -> None:
        """Initialize action agent."""
        super().__init__(*args, **kwargs)
        self.voice = voice
        self._entity_cache: dict[str, Any] = {}

    async def _async_setup(self) -> None:
        """Setup action agent."""
        # Build entity cache for faster lookups
        await self._refresh_entity_cache()
        
        # Subscribe to entity registry updates
        self.hass.bus.async_listen(
            "entity_registry_updated",
            self._handle_entity_update,
        )

    async def _refresh_entity_cache(self) -> None:
        """Refresh the entity lookup cache."""
        registry = entity_registry.async_get(self.hass)
        
        self._entity_cache = {}
        for entry in registry.entities.values():
            # Index by various names for flexible matching
            name_lower = entry.name.lower() if entry.name else ""
            entity_id = entry.entity_id.lower()
            
            # Store entity info
            entity_info = {
                "entity_id": entry.entity_id,
                "domain": entry.domain,
                "name": entry.name,
                "area_id": entry.area_id,
            }
            
            self._entity_cache[entity_id] = entity_info
            if name_lower:
                self._entity_cache[name_lower] = entity_info

    async def _handle_entity_update(self, event) -> None:
        """Handle entity registry updates."""
        await self._refresh_entity_cache()

    async def async_process(self, request: AgentRequest) -> AgentResponse:
        """Process an action request."""
        
        # Parse the action from natural language
        action_spec = await self._parse_action(request.text, request.context)
        
        if not action_spec:
            return AgentResponse(
                request_id=request.request_id,
                text="I'm not sure what you'd like me to do. Could you be more specific?",
                confidence=0.3,
            )
        
        # Validate action is allowed
        validation = await self._validate_action(action_spec, request)
        if not validation["allowed"]:
            return AgentResponse(
                request_id=request.request_id,
                text=validation["message"],
                confidence=0.9,
            )
        
        # Execute the action
        result = await self._execute_action(action_spec)
        
        # Generate confirmation
        confirmation = self._generate_confirmation(action_spec, result)
        
        return AgentResponse(
            request_id=request.request_id,
            text=confirmation,
            actions=[action_spec],
            confidence=0.9,
            cloud_used=action_spec.get("_cloud_used", False),
        )

    async def _parse_action(
        self, text: str, context: dict
    ) -> dict | None:
        """Parse natural language into action specification."""
        text_lower = text.lower()
        
        # Try rule-based parsing first
        action = self._rule_based_parse(text_lower)
        if action:
            return action
        
        # Fall back to LLM parsing
        return await self._llm_parse_action(text, context)

    def _rule_based_parse(self, text: str) -> dict | None:
        """Rule-based action parsing."""
        import re
        
        # Pattern: turn on/off [entity]
        match = re.match(r"turn (on|off) (?:the )?(.+)", text)
        if match:
            state = match.group(1)
            entity_name = match.group(2).strip()
            entity = self._resolve_entity(entity_name)
            
            if entity:
                service = "turn_on" if state == "on" else "turn_off"
                return {
                    "action": "call_service",
                    "domain": entity["domain"],
                    "service": service,
                    "target": {"entity_id": entity["entity_id"]},
                    "data": {},
                }
        
        # Pattern: set [entity] to [value]
        match = re.match(r"set (?:the )?(.+) to (.+)", text)
        if match:
            entity_name = match.group(1).strip()
            value = match.group(2).strip()
            entity = self._resolve_entity(entity_name)
            
            if entity:
                # Determine service based on domain and value
                service_spec = self._determine_set_service(entity, value)
                if service_spec:
                    return service_spec
        
        # Pattern: dim/brighten [entity] to [percent]
        match = re.match(r"(dim|brighten) (?:the )?(.+?)(?: to (\d+)%?)?$", text)
        if match:
            action = match.group(1)
            entity_name = match.group(2).strip()
            percent = match.group(3)
            entity = self._resolve_entity(entity_name)
            
            if entity and entity["domain"] == "light":
                brightness = int(percent) if percent else (30 if action == "dim" else 100)
                return {
                    "action": "call_service",
                    "domain": "light",
                    "service": "turn_on",
                    "target": {"entity_id": entity["entity_id"]},
                    "data": {"brightness_pct": brightness},
                }
        
        # Pattern: lock/unlock [entity]
        match = re.match(r"(lock|unlock) (?:the )?(.+)", text)
        if match:
            action = match.group(1)
            entity_name = match.group(2).strip()
            entity = self._resolve_entity(entity_name)
            
            if entity and entity["domain"] == "lock":
                return {
                    "action": "call_service",
                    "domain": "lock",
                    "service": action,
                    "target": {"entity_id": entity["entity_id"]},
                    "data": {},
                }
        
        return None

    def _resolve_entity(self, name: str) -> dict | None:
        """Resolve entity name to entity info."""
        name_lower = name.lower()
        
        # Direct lookup
        if name_lower in self._entity_cache:
            return self._entity_cache[name_lower]
        
        # Fuzzy matching
        for cached_name, entity_info in self._entity_cache.items():
            if name_lower in cached_name or cached_name in name_lower:
                return entity_info
        
        # Try with common suffixes removed
        suffixes = [" light", " lights", " lamp", " switch", " door", " lock"]
        for suffix in suffixes:
            test_name = name_lower.replace(suffix, "").strip()
            if test_name in self._entity_cache:
                return self._entity_cache[test_name]
        
        return None

    def _determine_set_service(
        self, entity: dict, value: str
    ) -> dict | None:
        """Determine the appropriate service for a 'set' command."""
        domain = entity["domain"]
        
        if domain == "light":
            # Parse brightness or color
            if "%" in value or value.isdigit():
                brightness = int(value.replace("%", ""))
                return {
                    "action": "call_service",
                    "domain": "light",
                    "service": "turn_on",
                    "target": {"entity_id": entity["entity_id"]},
                    "data": {"brightness_pct": brightness},
                }
        
        elif domain == "climate":
            # Parse temperature
            temp_match = re.search(r"(\d+)", value)
            if temp_match:
                temperature = int(temp_match.group(1))
                return {
                    "action": "call_service",
                    "domain": "climate",
                    "service": "set_temperature",
                    "target": {"entity_id": entity["entity_id"]},
                    "data": {"temperature": temperature},
                }
        
        elif domain == "cover":
            # Parse position
            if "%" in value or value.isdigit():
                position = int(value.replace("%", ""))
                return {
                    "action": "call_service",
                    "domain": "cover",
                    "service": "set_cover_position",
                    "target": {"entity_id": entity["entity_id"]},
                    "data": {"position": position},
                }
        
        return None

    async def _llm_parse_action(
        self, text: str, context: dict
    ) -> dict | None:
        """Use LLM to parse complex action requests."""
        from ..llm import LLMRouter
        
        # Get available entities for context
        available_entities = list(self._entity_cache.keys())[:50]  # Limit for token efficiency
        
        prompt = f"""Parse the following home automation command into a structured action.

Available entities (sample): {available_entities}

User command: "{text}"

Respond with a JSON object containing:
- action: "call_service"
- domain: the entity domain (light, switch, climate, etc.)
- service: the service to call (turn_on, turn_off, set_temperature, etc.)
- target: {{ "entity_id": "domain.entity_name" }}
- data: {{ any additional parameters }}
- confirmation: a brief confirmation message

If the command cannot be parsed, respond with: {{"error": "reason"}}

JSON response:"""

        try:
            llm = LLMRouter(self.hass, self.config)
            response = await llm.async_complete(
                prompt=prompt,
                model="action",  # Use action-optimized model
                max_tokens=200,
            )
            
            # Parse JSON response
            action_spec = json.loads(response.strip())
            
            if "error" in action_spec:
                self._logger.warning(f"LLM could not parse action: {action_spec['error']}")
                return None
            
            action_spec["_cloud_used"] = True
            return action_spec
            
        except Exception as e:
            self._logger.error(f"LLM action parsing failed: {e}")
            return None

    async def _validate_action(
        self, action_spec: dict, request: AgentRequest
    ) -> dict:
        """Validate that the action is allowed."""
        
        # Check speaker permissions
        target = action_spec.get("target", {})
        entity_id = target.get("entity_id")
        
        if entity_id:
            # Get entity domain
            domain = entity_id.split(".")[0]
            
            # Check domain-level permissions
            user_permissions = await self.policy.async_get_user_permissions(
                request.speaker_id
            )
            
            if domain not in user_permissions.get("allowed_domains", []):
                if "all_devices" not in user_permissions.get("permissions", []):
                    return {
                        "allowed": False,
                        "message": f"Sorry, you don't have permission to control {domain} devices.",
                    }
            
            # Check for security-sensitive actions
            if domain in ["lock", "alarm_control_panel", "cover"]:
                if "security_controls" not in user_permissions.get("permissions", []):
                    # Require confirmation
                    return {
                        "allowed": False,
                        "message": "Security actions require additional confirmation.",
                        "requires_confirmation": True,
                    }
        
        return {"allowed": True}

    async def _execute_action(self, action_spec: dict) -> dict:
        """Execute the action in Home Assistant."""
        try:
            domain = action_spec["domain"]
            service = action_spec["service"]
            target = action_spec.get("target", {})
            data = action_spec.get("data", {})
            
            # Combine target and data for service call
            service_data = {**data}
            if "entity_id" in target:
                service_data["entity_id"] = target["entity_id"]
            
            # Call the service
            await self.hass.services.async_call(
                domain=domain,
                service=service,
                service_data=service_data,
                blocking=True,
            )
            
            return {"success": True}
            
        except Exception as e:
            self._logger.error(f"Action execution failed: {e}")
            return {"success": False, "error": str(e)}

    def _generate_confirmation(
        self, action_spec: dict, result: dict
    ) -> str:
        """Generate a confirmation message."""
        if not result.get("success"):
            error = result.get("error", "Unknown error")
            return f"Sorry, I couldn't complete that action: {error}"
        
        # Use LLM-generated confirmation if available
        if "confirmation" in action_spec:
            return action_spec["confirmation"]
        
        # Generate based on action
        domain = action_spec["domain"]
        service = action_spec["service"]
        target = action_spec.get("target", {})
        entity_id = target.get("entity_id", "")
        
        # Simple entity name extraction
        entity_name = entity_id.split(".")[-1].replace("_", " ").title()
        
        confirmations = {
            ("light", "turn_on"): f"Turning on {entity_name}",
            ("light", "turn_off"): f"Turning off {entity_name}",
            ("switch", "turn_on"): f"{entity_name} is now on",
            ("switch", "turn_off"): f"{entity_name} is now off",
            ("lock", "lock"): f"Locking {entity_name}",
            ("lock", "unlock"): f"Unlocking {entity_name}",
            ("climate", "set_temperature"): f"Setting temperature",
            ("cover", "open_cover"): f"Opening {entity_name}",
            ("cover", "close_cover"): f"Closing {entity_name}",
        }
        
        return confirmations.get((domain, service), "Done")
```

---

## Message Bus Architecture

### Redis Streams Implementation

```python
# core/bus.py
"""Message Bus using Redis Streams."""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import TYPE_CHECKING, Any, Callable, Coroutine

import redis.asyncio as redis

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


@dataclass
class BusEvent:
    """Event on the message bus."""
    event_id: str
    event_type: str
    timestamp: float
    source: str
    data: dict
    correlation_id: str | None = None


class MessageBus:
    """Message bus for inter-agent communication using Redis Streams."""

    STREAM_NAME = "barnabeenet:events"
    CONSUMER_GROUP = "barnabeenet:agents"
    MAX_STREAM_LENGTH = 10000  # Trim stream to this length

    def __init__(self, hass: HomeAssistant, config: dict) -> None:
        """Initialize message bus."""
        self.hass = hass
        self.config = config
        self._redis: redis.Redis | None = None
        self._subscribers: dict[str, list[Callable]] = {}
        self._consumer_task: asyncio.Task | None = None
        self._running = False

    async def async_connect(self) -> None:
        """Connect to Redis."""
        redis_url = self.config.get("redis_url", "redis://localhost:6379")
        
        self._redis = redis.from_url(
            redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
        
        # Test connection
        await self._redis.ping()
        _LOGGER.info(f"Connected to Redis at {redis_url}")
        
        # Create consumer group if not exists
        try:
            await self._redis.xgroup_create(
                self.STREAM_NAME,
                self.CONSUMER_GROUP,
                mkstream=True,
            )
        except redis.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise

    async def async_disconnect(self) -> None:
        """Disconnect from Redis."""
        self._running = False
        
        if self._consumer_task:
            self._consumer_task.cancel()
            try:
                await self._consumer_task
            except asyncio.CancelledError:
                pass
        
        if self._redis:
            await self._redis.close()
            self._redis = None

    async def async_emit(
        self,
        event_type: str,
        data: dict,
        correlation_id: str | None = None,
    ) -> str:
        """Emit an event to the bus."""
        event = BusEvent(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            timestamp=datetime.now().timestamp(),
            source=f"barnabeenet:{self.hass.data.get('instance_id', 'default')}",
            data=data,
            correlation_id=correlation_id,
        )
        
        # Serialize event
        event_data = {
            "event_id": event.event_id,
            "event_type": event.event_type,
            "timestamp": str(event.timestamp),
            "source": event.source,
            "data": json.dumps(data),
            "correlation_id": event.correlation_id or "",
        }
        
        # Add to stream
        await self._redis.xadd(
            self.STREAM_NAME,
            event_data,
            maxlen=self.MAX_STREAM_LENGTH,
        )
        
        _LOGGER.debug(f"Emitted event: {event_type} (id={event.event_id})")
        return event.event_id

    def subscribe(
        self,
        event_type: str,
        callback: Callable[[BusEvent], Coroutine],
    ) -> Callable:
        """Subscribe to events of a specific type."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        
        self._subscribers[event_type].append(callback)
        
        # Return unsubscribe function
        def unsubscribe():
            self._subscribers[event_type].remove(callback)
        
        return unsubscribe

    async def async_consume_events(self) -> None:
        """Consume events from the stream."""
        self._running = True
        consumer_name = f"consumer:{uuid.uuid4().hex[:8]}"
        
        _LOGGER.info(f"Starting event consumer: {consumer_name}")
        
        while self._running:
            try:
                # Read from stream
                messages = await self._redis.xreadgroup(
                    groupname=self.CONSUMER_GROUP,
                    consumername=consumer_name,
                    streams={self.STREAM_NAME: ">"},
                    count=10,
                    block=1000,  # 1 second timeout
                )
                
                for stream_name, stream_messages in messages:
                    for message_id, message_data in stream_messages:
                        await self._process_message(message_id, message_data)
                        
                        # Acknowledge message
                        await self._redis.xack(
                            self.STREAM_NAME,
                            self.CONSUMER_GROUP,
                            message_id,
                        )
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                _LOGGER.error(f"Error consuming events: {e}")
                await asyncio.sleep(1)

    async def _process_message(
        self,
        message_id: str,
        message_data: dict,
    ) -> None:
        """Process a message from the stream."""
        try:
            # Deserialize event
            event = BusEvent(
                event_id=message_data["event_id"],
                event_type=message_data["event_type"],
                timestamp=float(message_data["timestamp"]),
                source=message_data["source"],
                data=json.loads(message_data["data"]),
                correlation_id=message_data.get("correlation_id") or None,
            )
            
            # Get subscribers
            callbacks = self._subscribers.get(event.event_type, [])
            
            # Also notify wildcard subscribers
            callbacks.extend(self._subscribers.get("*", []))
            
            # Invoke callbacks
            for callback in callbacks:
                try:
                    await callback(event)
                except Exception as e:
                    _LOGGER.error(
                        f"Error in event callback for {event.event_type}: {e}"
                    )
                    
        except Exception as e:
            _LOGGER.error(f"Error processing message {message_id}: {e}")

    async def async_request_response(
        self,
        event_type: str,
        data: dict,
        timeout: float = 5.0,
    ) -> dict | None:
        """Send a request and wait for a response."""
        correlation_id = str(uuid.uuid4())
        response_event = asyncio.Event()
        response_data: dict | None = None
        
        # Set up response handler
        async def handle_response(event: BusEvent):
            nonlocal response_data
            if event.correlation_id == correlation_id:
                response_data = event.data
                response_event.set()
        
        # Subscribe to response
        unsubscribe = self.subscribe(f"{event_type}.response", handle_response)
        
        try:
            # Emit request
            await self.async_emit(
                f"{event_type}.request",
                data,
                correlation_id=correlation_id,
            )
            
            # Wait for response
            await asyncio.wait_for(response_event.wait(), timeout=timeout)
            return response_data
            
        except asyncio.TimeoutError:
            _LOGGER.warning(f"Request timeout for {event_type}")
            return None
        finally:
            unsubscribe()
```

### Event Schema

```python
# models/events.py
"""Event models for message bus."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class VoiceInputEvent:
    """Voice input received event."""
    event_type: Literal["voice.input"] = "voice.input"
    request_id: str = ""
    audio_data: bytes = b""
    device_id: str = ""
    timestamp: float = 0.0


@dataclass
class TranscriptionEvent:
    """Transcription complete event."""
    event_type: Literal["voice.transcription"] = "voice.transcription"
    request_id: str = ""
    text: str = ""
    speaker_id: str = ""
    speaker_confidence: float = 0.0
    language: str = "en"


@dataclass
class IntentClassifiedEvent:
    """Intent classification event."""
    event_type: Literal["agent.intent_classified"] = "agent.intent_classified"
    request_id: str = ""
    intent: str = ""
    confidence: float = 0.0
    target_agent: str = ""


@dataclass
class AgentProcessedEvent:
    """Agent processing complete event."""
    event_type: Literal["agent.processed"] = "agent.processed"
    request_id: str = ""
    agent_type: str = ""
    response_text: str = ""
    actions: list[dict] = field(default_factory=list)
    processing_time_ms: int = 0
    cloud_used: bool = False


@dataclass
class ActionExecutedEvent:
    """Action execution event."""
    event_type: Literal["action.executed"] = "action.executed"
    request_id: str = ""
    domain: str = ""
    service: str = ""
    entity_id: str = ""
    success: bool = True
    error: str | None = None


@dataclass
class ProactiveNotificationEvent:
    """Proactive notification event."""
    event_type: Literal["proactive.notification"] = "proactive.notification"
    notification_id: str = ""
    category: str = ""
    urgency: str = "low"
    message: str = ""
    actions: list[dict] = field(default_factory=list)
    target_users: list[str] = field(default_factory=list)
```

---

## Voice Processing Pipeline

### Speech-to-Text Implementation

```python
# voice/stt.py
"""Speech-to-Text using Faster-Whisper."""
from __future__ import annotations

import asyncio
import logging
import io
from typing import TYPE_CHECKING

import numpy as np
from faster_whisper import WhisperModel

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class SpeechToText:
    """Speech-to-text using Faster-Whisper."""

    def __init__(self, hass: HomeAssistant, config: dict) -> None:
        """Initialize STT."""
        self.hass = hass
        self.config = config
        self._model: WhisperModel | None = None
        self._model_lock = asyncio.Lock()

    async def async_initialize(self) -> None:
        """Initialize the Whisper model."""
        model_size = self.config.get("stt_model", "distil-whisper/distil-small.en")
        device = self.config.get("stt_device", "cpu")
        compute_type = self.config.get("stt_compute_type", "int8")
        
        _LOGGER.info(f"Loading Whisper model: {model_size}")
        
        # Load model in executor to avoid blocking
        self._model = await self.hass.async_add_executor_job(
            self._load_model, model_size, device, compute_type
        )
        
        _LOGGER.info("Whisper model loaded")

    def _load_model(
        self,
        model_size: str,
        device: str,
        compute_type: str,
    ) -> WhisperModel:
        """Load Whisper model (blocking)."""
        return WhisperModel(
            model_size,
            device=device,
            compute_type=compute_type,
        )

    async def async_transcribe(
        self,
        audio_data: bytes,
        language: str = "en",
    ) -> dict:
        """Transcribe audio data to text."""
        if not self._model:
            raise RuntimeError("STT model not initialized")
        
        async with self._model_lock:
            # Convert bytes to numpy array
            audio_array = await self.hass.async_add_executor_job(
                self._bytes_to_audio, audio_data
            )
            
            # Transcribe
            segments, info = await self.hass.async_add_executor_job(
                self._transcribe_audio, audio_array, language
            )
            
            # Combine segments
            text = " ".join(segment.text.strip() for segment in segments)
            
            return {
                "text": text,
                "language": info.language,
                "language_probability": info.language_probability,
                "duration": info.duration,
            }

    def _bytes_to_audio(self, audio_data: bytes) -> np.ndarray:
        """Convert audio bytes to numpy array."""
        import soundfile as sf
        
        # Read audio from bytes
        audio, sample_rate = sf.read(io.BytesIO(audio_data))
        
        # Convert to mono if stereo
        if len(audio.shape) > 1:
            audio = audio.mean(axis=1)
        
        # Resample to 16kHz if needed
        if sample_rate != 16000:
            import librosa
            audio = librosa.resample(audio, orig_sr=sample_rate, target_sr=16000)
        
        return audio.astype(np.float32)

    def _transcribe_audio(
        self,
        audio: np.ndarray,
        language: str,
    ) -> tuple:
        """Transcribe audio (blocking)."""
        segments, info = self._model.transcribe(
            audio,
            language=language if language != "auto" else None,
            beam_size=1,  # Faster inference
            vad_filter=True,  # Filter out non-speech
            vad_parameters=dict(
                min_silence_duration_ms=500,
                threshold=0.5,
            ),
        )
        
        return list(segments), info

    async def async_shutdown(self) -> None:
        """Shutdown STT."""
        self._model = None
```

### Text-to-Speech Implementation

```python
# voice/tts.py
"""Text-to-Speech using Kokoro."""
from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)
_executor = ThreadPoolExecutor(max_workers=2)


class TextToSpeech:
    """Kokoro TTS wrapper - fast, high-quality local synthesis."""

    def __init__(self, hass: HomeAssistant, config: dict) -> None:
        """Initialize TTS."""
        self.hass = hass
        self.config = config
        self._voice = config.get("tts_voice", "af_bella")
        self._speed = config.get("tts_speed", 1.0)
        self._sample_rate = 24000  # Kokoro native rate
        self._pipeline = None
        self._cache: dict[str, bytes] = {}
        self._cache_max_size = 100

    async def async_initialize(self) -> None:
        """Initialize Kokoro TTS pipeline."""
        from kokoro import KPipeline
        
        self._pipeline = await self.hass.async_add_executor_job(
            KPipeline,
            self._voice,
        )
        _LOGGER.info(f"Kokoro TTS initialized with voice: {self._voice}")

    async def async_synthesize(
        self,
        text: str,
        voice: str | None = None,
    ) -> bytes:
        """Synthesize text to speech audio."""
        voice = voice or self._voice
        
        # Check cache
        cache_key = f"{voice}:{text}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # Synthesize
        audio_data = await self.hass.async_add_executor_job(
            self._synthesize, text, voice
        )
        
        # Cache result
        if len(self._cache) >= self._cache_max_size:
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
        self._cache[cache_key] = audio_data
        
        return audio_data

    def _synthesize(self, text: str, voice: str) -> bytes:
        """Synthesize audio (blocking)."""
        import soundfile as sf
        import io
        
        # Generate audio with Kokoro
        audio = self._pipeline(text, voice=voice, speed=self._speed)
        
        # Convert to WAV bytes
        buffer = io.BytesIO()
        sf.write(buffer, audio, self._sample_rate, format='WAV')
        return buffer.getvalue()

    async def async_shutdown(self) -> None:
        """Shutdown TTS."""
        self._cache.clear()
        self._pipeline = None
```

---

## Speaker Recognition System

### ECAPA-TDNN Implementation

```python
# voice/speaker_id.py
"""Speaker Recognition using ECAPA-TDNN."""
from __future__ import annotations

import asyncio
import logging
import numpy as np
from pathlib import Path
from typing import TYPE_CHECKING
from dataclasses import dataclass

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


@dataclass
class SpeakerProfile:
    """Speaker profile with embedding."""
    speaker_id: str
    name: str
    embedding: np.ndarray
    permissions: list[str]
    enrolled_at: float
    last_verified: float | None = None


class SpeakerRecognition:
    """Speaker recognition using ECAPA-TDNN embeddings."""

    SIMILARITY_THRESHOLD = 0.75  # Minimum cosine similarity for positive ID
    EMBEDDING_DIM = 192

    def __init__(self, hass: HomeAssistant, config: dict) -> None:
        """Initialize speaker recognition."""
        self.hass = hass
        self.config = config
        self._model = None
        self._profiles: dict[str, SpeakerProfile] = {}
        self._model_lock = asyncio.Lock()
        self._profiles_path = Path(config.get("data_dir", ".")) / "speaker_profiles.npz"

    async def async_initialize(self) -> None:
        """Initialize speaker recognition model."""
        _LOGGER.info("Loading ECAPA-TDNN speaker recognition model...")
        
        # Load model in executor
        self._model = await self.hass.async_add_executor_job(self._load_model)
        
        # Load existing profiles
        await self._load_profiles()
        
        _LOGGER.info(
            f"Speaker recognition initialized with {len(self._profiles)} profiles"
        )

    def _load_model(self):
        """Load SpeechBrain ECAPA-TDNN model (blocking)."""
        from speechbrain.inference import SpeakerRecognition
        
        return SpeakerRecognition.from_hparams(
            source="speechbrain/spkrec-ecapa-voxceleb",
            savedir="models/speechbrain",
        )

    async def _load_profiles(self) -> None:
        """Load speaker profiles from disk."""
        if not self._profiles_path.exists():
            return
        
        try:
            data = await self.hass.async_add_executor_job(
                np.load, str(self._profiles_path), allow_pickle=True
            )
            
            for speaker_id in data.files:
                profile_data = data[speaker_id].item()
                self._profiles[speaker_id] = SpeakerProfile(**profile_data)
                
        except Exception as e:
            _LOGGER.error(f"Error loading speaker profiles: {e}")

    async def _save_profiles(self) -> None:
        """Save speaker profiles to disk."""
        try:
            profile_data = {
                speaker_id: {
                    "speaker_id": profile.speaker_id,
                    "name": profile.name,
                    "embedding": profile.embedding,
                    "permissions": profile.permissions,
                    "enrolled_at": profile.enrolled_at,
                    "last_verified": profile.last_verified,
                }
                for speaker_id, profile in self._profiles.items()
            }
            
            await self.hass.async_add_executor_job(
                np.savez, str(self._profiles_path), **profile_data
            )
            
        except Exception as e:
            _LOGGER.error(f"Error saving speaker profiles: {e}")

    async def async_identify(
        self,
        audio_data: bytes,
    ) -> tuple[str, float]:
        """Identify speaker from audio.
        
        Returns:
            Tuple of (speaker_id, confidence).
            speaker_id is "guest" if no match found.
        """
        if not self._model:
            return "guest", 0.0
        
        async with self._model_lock:
            # Extract embedding
            embedding = await self._extract_embedding(audio_data)
            
            if embedding is None:
                return "guest", 0.0
            
            # Compare against all profiles
            best_match = "guest"
            best_score = 0.0
            
            for speaker_id, profile in self._profiles.items():
                score = self._cosine_similarity(embedding, profile.embedding)
                
                if score > best_score:
                    best_score = score
                    best_match = speaker_id
            
            # Check threshold
            if best_score < self.SIMILARITY_THRESHOLD:
                _LOGGER.debug(
                    f"No speaker match (best={best_score:.2f} < {self.SIMILARITY_THRESHOLD})"
                )
                return "guest", best_score
            
            _LOGGER.debug(f"Speaker identified: {best_match} (score={best_score:.2f})")
            return best_match, best_score

    async def _extract_embedding(self, audio_data: bytes) -> np.ndarray | None:
        """Extract speaker embedding from audio."""
        try:
            # Convert bytes to waveform
            audio_array = await self.hass.async_add_executor_job(
                self._bytes_to_waveform, audio_data
            )
            
            # Extract embedding
            embedding = await self.hass.async_add_executor_job(
                self._model.encode_batch, audio_array
            )
            
            return embedding.squeeze().numpy()
            
        except Exception as e:
            _LOGGER.error(f"Error extracting speaker embedding: {e}")
            return None

    def _bytes_to_waveform(self, audio_data: bytes) -> "torch.Tensor":
        """Convert audio bytes to waveform tensor."""
        import torch
        import torchaudio
        import io
        
        waveform, sample_rate = torchaudio.load(io.BytesIO(audio_data))
        
        # Resample to 16kHz if needed
        if sample_rate != 16000:
            resampler = torchaudio.transforms.Resample(sample_rate, 16000)
            waveform = resampler(waveform)
        
        return waveform

    def _cosine_similarity(
        self,
        embedding1: np.ndarray,
        embedding2: np.ndarray,
    ) -> float:
        """Calculate cosine similarity between embeddings."""
        norm1 = np.linalg.norm(embedding1)
        norm2 = np.linalg.norm(embedding2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return float(np.dot(embedding1, embedding2) / (norm1 * norm2))

    async def async_enroll(
        self,
        name: str,
        audio_samples: list[bytes],
        permissions: list[str] | None = None,
    ) -> dict:
        """Enroll a new speaker.
        
        Args:
            name: Display name for the speaker
            audio_samples: List of audio samples (minimum 3 recommended)
            permissions: List of permission strings
            
        Returns:
            Enrollment result dict
        """
        import time
        import uuid
        
        if len(audio_samples) < 3:
            return {
                "success": False,
                "error": "At least 3 audio samples required for enrollment",
            }
        
        # Extract embeddings from all samples
        embeddings = []
        for sample in audio_samples:
            embedding = await self._extract_embedding(sample)
            if embedding is not None:
                embeddings.append(embedding)
        
        if len(embeddings) < 3:
            return {
                "success": False,
                "error": "Could not extract sufficient embeddings from samples",
            }
        
        # Average embeddings
        average_embedding = np.mean(embeddings, axis=0)
        
        # Normalize
        average_embedding = average_embedding / np.linalg.norm(average_embedding)
        
        # Create profile
        speaker_id = f"speaker_{uuid.uuid4().hex[:8]}"
        profile = SpeakerProfile(
            speaker_id=speaker_id,
            name=name,
            embedding=average_embedding,
            permissions=permissions or [],
            enrolled_at=time.time(),
        )
        
        # Store profile
        self._profiles[speaker_id] = profile
        await self._save_profiles()
        
        _LOGGER.info(f"Enrolled speaker: {name} (id={speaker_id})")
        
        return {
            "success": True,
            "speaker_id": speaker_id,
            "name": name,
        }

    async def async_update_permissions(
        self,
        speaker_id: str,
        permissions: list[str],
    ) -> bool:
        """Update speaker permissions."""
        if speaker_id not in self._profiles:
            return False
        
        self._profiles[speaker_id].permissions = permissions
        await self._save_profiles()
        return True

    async def async_remove_speaker(self, speaker_id: str) -> bool:
        """Remove a speaker profile."""
        if speaker_id not in self._profiles:
            return False
        
        del self._profiles[speaker_id]
        await self._save_profiles()
        
        _LOGGER.info(f"Removed speaker: {speaker_id}")
        return True

    def get_speaker_permissions(self, speaker_id: str) -> list[str]:
        """Get permissions for a speaker."""
        profile = self._profiles.get(speaker_id)
        if profile:
            return profile.permissions
        return []

    async def async_shutdown(self) -> None:
        """Shutdown speaker recognition."""
        await self._save_profiles()
        self._model = None
```

---

## Memory System Architecture

### Memory Manager

```python
# memory/__init__.py
"""Memory System - Working, Episodic, Semantic, Procedural."""
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from .working import WorkingMemory
from .episodic import EpisodicMemory
from .semantic import SemanticMemory
from .procedural import ProceduralMemory
from .embeddings import EmbeddingService
from .consolidation import MemoryConsolidator

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from ..core.bus import MessageBus
    from ..models.request import AgentRequest, AgentResponse

_LOGGER = logging.getLogger(__name__)


class MemoryManager:
    """Unified memory management."""

    def __init__(
        self,
        hass: HomeAssistant,
        config: dict,
        bus: MessageBus,
    ) -> None:
        """Initialize memory manager."""
        self.hass = hass
        self.config = config
        self.bus = bus
        
        # Initialize memory subsystems
        self.embeddings = EmbeddingService(hass, config)
        self.working = WorkingMemory(hass, config)
        self.episodic = EpisodicMemory(hass, config, self.embeddings)
        self.semantic = SemanticMemory(hass, config)
        self.procedural = ProceduralMemory(hass, config)
        self.consolidator = MemoryConsolidator(
            hass, config, self.episodic, self.semantic, self.procedural
        )

    async def async_initialize(self) -> None:
        """Initialize all memory subsystems."""
        _LOGGER.info("Initializing memory systems...")
        
        await asyncio.gather(
            self.embeddings.async_initialize(),
            self.working.async_initialize(),
            self.episodic.async_initialize(),
            self.semantic.async_initialize(),
            self.procedural.async_initialize(),
        )
        
        _LOGGER.info("Memory systems initialized")

    async def async_store_conversation(
        self,
        request: "AgentRequest",
        response: "AgentResponse",
    ) -> None:
        """Store a conversation exchange."""
        # Store in working memory (short-term)
        await self.working.async_store(
            session_id=request.session_id,
            speaker_id=request.speaker_id,
            user_input=request.text,
            assistant_response=response.text,
        )
        
        # Store in episodic memory (long-term)
        await self.episodic.async_store(
            request=request,
            response=response,
        )

    async def async_search(
        self,
        query: str,
        speaker_id: str | None = None,
        memory_type: str = "all",
        limit: int = 10,
    ) -> list[dict]:
        """Search across memory types."""
        results = []
        
        if memory_type in ("all", "episodic"):
            episodic_results = await self.episodic.async_search(
                query=query,
                speaker_id=speaker_id,
                limit=limit,
            )
            results.extend(episodic_results)
        
        if memory_type in ("all", "semantic"):
            semantic_results = await self.semantic.async_search(
                subject=speaker_id,
                query=query,
                limit=limit,
            )
            results.extend(semantic_results)
        
        return results

    async def async_get_context_for_speaker(
        self,
        speaker_id: str,
        limit: int = 5,
    ) -> dict:
        """Get relevant context for a speaker."""
        return {
            "recent_conversations": await self.episodic.async_get_recent(
                speaker_id=speaker_id, limit=limit
            ),
            "facts": await self.semantic.async_get_facts(
                subject=speaker_id, limit=limit
            ),
            "preferences": await self.semantic.async_get_preferences(
                user_id=speaker_id
            ),
        }

    async def async_run_consolidation_scheduler(self) -> None:
        """Run memory consolidation on schedule."""
        import datetime
        
        while True:
            try:
                # Run at 3 AM daily
                now = datetime.datetime.now()
                target = now.replace(hour=3, minute=0, second=0, microsecond=0)
                if now >= target:
                    target += datetime.timedelta(days=1)
                
                wait_seconds = (target - now).total_seconds()
                _LOGGER.info(
                    f"Memory consolidation scheduled in {wait_seconds/3600:.1f} hours"
                )
                
                await asyncio.sleep(wait_seconds)
                
                # Run consolidation
                await self.consolidator.async_run()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                _LOGGER.error(f"Memory consolidation error: {e}")
                await asyncio.sleep(3600)  # Wait an hour and retry

    # Stats methods
    async def async_get_command_count_today(self) -> int:
        """Get command count for today."""
        return await self.episodic.async_get_count_today()

    async def async_get_avg_latency(self, agent_type: str) -> float:
        """Get average latency for agent type."""
        return await self.episodic.async_get_avg_latency(agent_type)

    async def async_get_cloud_call_count_today(self) -> int:
        """Get cloud call count for today."""
        return await self.episodic.async_get_cloud_count_today()

    async def async_get_estimated_cost_today(self) -> float:
        """Get estimated cost for today."""
        return await self.episodic.async_get_cost_today()

    async def async_get_recent_conversations(self, limit: int = 10) -> list[dict]:
        """Get recent conversations."""
        return await self.episodic.async_get_recent(limit=limit)

    async def async_shutdown(self) -> None:
        """Shutdown memory systems."""
        await asyncio.gather(
            self.working.async_shutdown(),
            self.episodic.async_shutdown(),
            self.semantic.async_shutdown(),
            self.procedural.async_shutdown(),
        )
```

### Working Memory (Redis)

```python
# memory/working.py
"""Working Memory using Redis."""
from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

import redis.asyncio as redis

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class WorkingMemory:
    """Short-term working memory using Redis."""

    SESSION_TTL = 600  # 10 minutes
    KEY_PREFIX = "barnabeenet:working"

    def __init__(self, hass: HomeAssistant, config: dict) -> None:
        """Initialize working memory."""
        self.hass = hass
        self.config = config
        self._redis: redis.Redis | None = None

    async def async_initialize(self) -> None:
        """Initialize Redis connection."""
        redis_url = self.config.get("redis_url", "redis://localhost:6379")
        self._redis = redis.from_url(redis_url)
        await self._redis.ping()

    async def async_store(
        self,
        session_id: str,
        speaker_id: str,
        user_input: str,
        assistant_response: str,
    ) -> None:
        """Store a conversation turn in working memory."""
        key = f"{self.KEY_PREFIX}:session:{session_id}"
        
        turn = {
            "speaker_id": speaker_id,
            "user": user_input,
            "assistant": assistant_response,
            "timestamp": self._get_timestamp(),
        }
        
        # Add to list
        await self._redis.rpush(key, json.dumps(turn))
        
        # Trim to last 10 turns
        await self._redis.ltrim(key, -10, -1)
        
        # Set expiration
        await self._redis.expire(key, self.SESSION_TTL)

    async def async_get_context(
        self,
        session_id: str,
        speaker_id: str | None = None,
    ) -> list[dict]:
        """Get conversation context for a session."""
        key = f"{self.KEY_PREFIX}:session:{session_id}"
        
        turns = await self._redis.lrange(key, 0, -1)
        
        context = []
        for turn_json in turns:
            turn = json.loads(turn_json)
            if speaker_id is None or turn["speaker_id"] == speaker_id:
                context.append({
                    "role": "user",
                    "content": turn["user"],
                })
                context.append({
                    "role": "assistant",
                    "content": turn["assistant"],
                })
        
        return context

    async def async_get_active_sessions(self) -> list[dict]:
        """Get all active sessions."""
        pattern = f"{self.KEY_PREFIX}:session:*"
        sessions = []
        
        async for key in self._redis.scan_iter(pattern):
            session_id = key.split(":")[-1]
            turns = await self._redis.lrange(key, 0, -1)
            
            if turns:
                last_turn = json.loads(turns[-1])
                sessions.append({
                    "session_id": session_id,
                    "speaker_id": last_turn["speaker_id"],
                    "turn_count": len(turns),
                    "last_activity": last_turn["timestamp"],
                })
        
        return sessions

    async def async_store_entity(
        self,
        session_id: str,
        entity_type: str,
        entity_value: str,
    ) -> None:
        """Store an extracted entity."""
        key = f"{self.KEY_PREFIX}:entities:{session_id}"
        await self._redis.hset(key, entity_type, entity_value)
        await self._redis.expire(key, self.SESSION_TTL)

    async def async_get_entities(self, session_id: str) -> dict:
        """Get extracted entities for a session."""
        key = f"{self.KEY_PREFIX}:entities:{session_id}"
        return await self._redis.hgetall(key)

    async def async_clear_session(self, session_id: str) -> None:
        """Clear a session's working memory."""
        pattern = f"{self.KEY_PREFIX}:*:{session_id}"
        async for key in self._redis.scan_iter(pattern):
            await self._redis.delete(key)

    def _get_timestamp(self) -> float:
        """Get current timestamp."""
        import time
        return time.time()

    async def async_shutdown(self) -> None:
        """Shutdown working memory."""
        if self._redis:
            await self._redis.close()
```

---

## Database Schema

### SQLite Schema Definition

```sql
-- schema.sql
-- BarnabeeNet Database Schema

-- Enable foreign keys
PRAGMA foreign_keys = ON;

-- ============================================
-- CONVERSATIONS (Episodic Memory)
-- ============================================

CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    speaker_id TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    -- Content
    user_input TEXT NOT NULL,
    assistant_response TEXT,
    
    -- Classification
    intent TEXT,
    sub_intent TEXT,
    agent_used TEXT,
    
    -- Performance
    processing_time_ms INTEGER,
    cloud_used BOOLEAN DEFAULT FALSE,
    cloud_model TEXT,
    cloud_cost REAL DEFAULT 0.0,
    
    -- Context
    device_id TEXT,
    privacy_zone TEXT,
    
    -- Importance flag for retention
    important BOOLEAN DEFAULT FALSE,
    
    -- Embedding for semantic search (stored as BLOB)
    embedding BLOB,
    
    -- Indexes
    UNIQUE(session_id, timestamp)
);

CREATE INDEX IF NOT EXISTS idx_conversations_speaker 
    ON conversations(speaker_id);
CREATE INDEX IF NOT EXISTS idx_conversations_timestamp 
    ON conversations(timestamp);
CREATE INDEX IF NOT EXISTS idx_conversations_session 
    ON conversations(session_id);
CREATE INDEX IF NOT EXISTS idx_conversations_intent 
    ON conversations(intent);

-- ============================================
-- SEMANTIC FACTS
-- ============================================

CREATE TABLE IF NOT EXISTS semantic_facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject TEXT NOT NULL,
    predicate TEXT NOT NULL,
    object TEXT NOT NULL,
    
    -- Metadata
    confidence REAL DEFAULT 1.0,
    source_type TEXT DEFAULT 'conversation',
    source_conversation_id INTEGER,
    
    -- Timestamps
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_confirmed DATETIME,
    last_contradicted DATETIME,
    
    -- Decay tracking
    confirmation_count INTEGER DEFAULT 1,
    
    FOREIGN KEY (source_conversation_id) 
        REFERENCES conversations(id) ON DELETE SET NULL,
    UNIQUE(subject, predicate, object)
);

CREATE INDEX IF NOT EXISTS idx_semantic_subject 
    ON semantic_facts(subject);
CREATE INDEX IF NOT EXISTS idx_semantic_predicate 
    ON semantic_facts(predicate);

-- ============================================
-- USER PREFERENCES
-- ============================================

CREATE TABLE IF NOT EXISTS user_preferences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    category TEXT NOT NULL,
    preference_key TEXT NOT NULL,
    preference_value TEXT NOT NULL,
    
    -- Context for conditional preferences
    context TEXT,
    
    -- Confidence and tracking
    confidence REAL DEFAULT 1.0,
    learned_from_conversation_id INTEGER,
    
    -- Timestamps
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (learned_from_conversation_id) 
        REFERENCES conversations(id) ON DELETE SET NULL,
    UNIQUE(user_id, category, preference_key, context)
);

CREATE INDEX IF NOT EXISTS idx_preferences_user 
    ON user_preferences(user_id);
CREATE INDEX IF NOT EXISTS idx_preferences_category 
    ON user_preferences(category);

-- ============================================
-- EVENT LOG (for pattern detection)
-- ============================================

CREATE TABLE IF NOT EXISTS event_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    event_type TEXT NOT NULL,
    entity_id TEXT,
    old_state TEXT,
    new_state TEXT,
    triggered_by TEXT,
    user_id TEXT
);

CREATE INDEX IF NOT EXISTS idx_events_type_time 
    ON event_log(event_type, timestamp);
CREATE INDEX IF NOT EXISTS idx_events_entity 
    ON event_log(entity_id);

-- ============================================
-- LEARNED AUTOMATIONS (Procedural Memory)
-- ============================================

CREATE TABLE IF NOT EXISTS learned_automations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    
    -- Pattern definition
    trigger_pattern TEXT NOT NULL,
    action_sequence TEXT NOT NULL,
    
    -- Confidence and usage
    confidence REAL DEFAULT 0.0,
    usage_count INTEGER DEFAULT 0,
    last_used DATETIME,
    
    -- Status
    status TEXT DEFAULT 'suggested',
    approved_by TEXT,
    approved_at DATETIME,
    
    -- Timestamps
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- AUDIT LOG
-- ============================================

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    session_id TEXT,
    request_id TEXT,
    speaker_id TEXT,
    speaker_confidence REAL,
    
    -- Request details
    audio_hash TEXT,
    transcription TEXT,
    detected_intent TEXT,
    
    -- Routing
    meta_agent_decision TEXT,
    agent_invoked TEXT,
    
    -- Performance
    processing_time_ms INTEGER,
    cloud_api_used BOOLEAN,
    cloud_api_name TEXT,
    
    -- Response
    response_text TEXT,
    action_executed TEXT,
    
    -- Privacy
    privacy_zone TEXT,
    pii_detected BOOLEAN DEFAULT FALSE,
    
    -- Multi-modal
    input_modality TEXT DEFAULT 'voice',
    gesture_type TEXT
);

CREATE INDEX IF NOT EXISTS idx_audit_timestamp 
    ON audit_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_speaker 
    ON audit_log(speaker_id);
CREATE INDEX IF NOT EXISTS idx_audit_session 
    ON audit_log(session_id);

-- ============================================
-- SPEAKER PROFILES (backup to file storage)
-- ============================================

CREATE TABLE IF NOT EXISTS speaker_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    speaker_id TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    
    -- Permissions
    permissions TEXT,  -- JSON array
    
    -- Metadata
    enrolled_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_verified DATETIME,
    verification_count INTEGER DEFAULT 0,
    
    -- Status
    active BOOLEAN DEFAULT TRUE
);

-- ============================================
-- VECTOR SEARCH TABLE (sqlite-vec)
-- ============================================

-- This is created by sqlite-vec extension
-- CREATE VIRTUAL TABLE vec_conversations USING vec0(
--     conversation_id INTEGER PRIMARY KEY,
--     embedding float[384]
-- );
```

### Database Manager

```python
# memory/database.py
"""Database management for BarnabeeNet."""
from __future__ import annotations

import asyncio
import logging
import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING, Any

import aiosqlite

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class DatabaseManager:
    """Manage SQLite database connections and operations."""

    def __init__(self, hass: HomeAssistant, config: dict) -> None:
        """Initialize database manager."""
        self.hass = hass
        self.config = config
        self._db_path = Path(config.get("data_dir", ".")) / "barnabeenet.db"
        self._connection: aiosqlite.Connection | None = None

    async def async_initialize(self) -> None:
        """Initialize database connection and schema."""
        _LOGGER.info(f"Initializing database at {self._db_path}")
        
        # Ensure directory exists
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Connect
        self._connection = await aiosqlite.connect(str(self._db_path))
        
        # Enable WAL mode for better concurrency
        await self._connection.execute("PRAGMA journal_mode=WAL")
        await self._connection.execute("PRAGMA foreign_keys=ON")
        
        # Initialize schema
        await self._initialize_schema()
        
        # Initialize vector extension
        await self._initialize_vector_search()
        
        _LOGGER.info("Database initialized")

    async def _initialize_schema(self) -> None:
        """Initialize database schema."""
        schema_path = Path(__file__).parent / "schema.sql"
        
        if schema_path.exists():
            schema = schema_path.read_text()
            await self._connection.executescript(schema)
            await self._connection.commit()

    async def _initialize_vector_search(self) -> None:
        """Initialize sqlite-vec extension."""
        try:
            # Load extension
            await self._connection.enable_load_extension(True)
            
            # Try to load sqlite-vec
            vec_path = self.config.get("sqlite_vec_path", "vec0")
            await self._connection.load_extension(vec_path)
            
            # Create vector table if not exists
            await self._connection.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS vec_conversations 
                USING vec0(
                    conversation_id INTEGER PRIMARY KEY,
                    embedding float[384]
                )
            """)
            await self._connection.commit()
            
            _LOGGER.info("sqlite-vec extension loaded")
            
        except Exception as e:
            _LOGGER.warning(f"Could not load sqlite-vec: {e}")

    async def async_execute(
        self,
        query: str,
        parameters: tuple = (),
    ) -> aiosqlite.Cursor:
        """Execute a query."""
        return await self._connection.execute(query, parameters)

    async def async_executemany(
        self,
        query: str,
        parameters: list[tuple],
    ) -> aiosqlite.Cursor:
        """Execute a query with multiple parameter sets."""
        return await self._connection.executemany(query, parameters)

    async def async_fetch_one(
        self,
        query: str,
        parameters: tuple = (),
    ) -> dict | None:
        """Fetch a single row as dict."""
        cursor = await self._connection.execute(query, parameters)
        row = await cursor.fetchone()
        
        if row is None:
            return None
        
        columns = [description[0] for description in cursor.description]
        return dict(zip(columns, row))

    async def async_fetch_all(
        self,
        query: str,
        parameters: tuple = (),
    ) -> list[dict]:
        """Fetch all rows as list of dicts."""
        cursor = await self._connection.execute(query, parameters)
        rows = await cursor.fetchall()
        
        columns = [description[0] for description in cursor.description]
        return [dict(zip(columns, row)) for row in rows]

    async def async_commit(self) -> None:
        """Commit transaction."""
        await self._connection.commit()

    async def async_shutdown(self) -> None:
        """Shutdown database connection."""
        if self._connection:
            await self._connection.close()
```

---

## API Specifications

### Internal REST API

```yaml
# api_spec.yaml
openapi: 3.0.0
info:
  title: BarnabeeNet Internal API
  version: 3.0.0
  description: Internal API for BarnabeeNet voice assistant

servers:
  - url: /api/barnabeenet
    description: Home Assistant internal endpoint

paths:
  /process:
    post:
      summary: Process voice or text input
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties:
                text:
                  type: string
                  description: Text input (alternative to audio)
                audio_data:
                  type: string
                  format: base64
                  description: Base64-encoded audio
                speaker_hint:
                  type: string
                  description: Optional speaker ID hint
                device_id:
                  type: string
                  description: Source device ID
                session_id:
                  type: string
                  description: Conversation session ID
      responses:
        '200':
          description: Successful response
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ProcessResponse'

  /enroll:
    post:
      summary: Enroll a new speaker
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required:
                - name
                - audio_samples
              properties:
                name:
                  type: string
                audio_samples:
                  type: array
                  items:
                    type: string
                    format: base64
                permissions:
                  type: array
                  items:
                    type: string
      responses:
        '200':
          description: Enrollment result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/EnrollmentResponse'

  /memory/search:
    get:
      summary: Search memory
      parameters:
        - name: q
          in: query
          required: true
          schema:
            type: string
        - name: speaker_id
          in: query
          schema:
            type: string
        - name: memory_type
          in: query
          schema:
            type: string
            enum: [all, episodic, semantic]
        - name: limit
          in: query
          schema:
            type: integer
            default: 10
      responses:
        '200':
          description: Search results
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/MemorySearchResponse'

  /stats:
    get:
      summary: Get system statistics
      responses:
        '200':
          description: System statistics
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/StatsResponse'

  /stream:
    get:
      summary: WebSocket for real-time updates
      description: WebSocket endpoint for dashboard updates

components:
  schemas:
    ProcessResponse:
      type: object
      properties:
        request_id:
          type: string
        text:
          type: string
        audio_url:
          type: string
        actions:
          type: array
          items:
            type: object
        agent_type:
          type: string
        processing_time_ms:
          type: integer
        cloud_used:
          type: boolean

    EnrollmentResponse:
      type: object
      properties:
        success:
          type: boolean
        speaker_id:
          type: string
        name:
          type: string
        error:
          type: string

    MemorySearchResponse:
      type: object
      properties:
        results:
          type: array
          items:
            type: object
            properties:
              type:
                type: string
              content:
                type: object
              score:
                type: number

    StatsResponse:
      type: object
      properties:
        total_commands_today:
          type: integer
        avg_latency_action:
          type: number
        avg_latency_query:
          type: number
        cloud_calls_today:
          type: integer
        estimated_cost_today:
          type: number
```

---

## LLM Orchestration

### OpenRouter Integration

```python
# llm/router.py
"""LLM Router for multi-model orchestration."""
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, AsyncIterator

import aiohttp

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class LLMRouter:
    """Route LLM requests to appropriate models."""

    # Model tiers
    MODEL_TIERS = {
        "fast": [
            "google/gemini-2.0-flash-001",
            "anthropic/claude-3-haiku",
            "openai/gpt-4o-mini",
        ],
        "action": [
            "openai/gpt-4.1-nano",
            "google/gemini-2.0-flash-001",
        ],
        "conversation": [
            "anthropic/claude-sonnet-4",
            "openai/gpt-4o",
        ],
        "complex": [
            "anthropic/claude-sonnet-4",
            "openai/o1-preview",
        ],
    }

    # Cost per million tokens (approximate)
    MODEL_COSTS = {
        "google/gemini-2.0-flash-001": {"input": 0.075, "output": 0.30},
        "anthropic/claude-3-haiku": {"input": 0.25, "output": 1.25},
        "anthropic/claude-sonnet-4": {"input": 3.00, "output": 15.00},
        "openai/gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "openai/gpt-4o": {"input": 2.50, "output": 10.00},
        "openai/gpt-4.1-nano": {"input": 0.10, "output": 0.40},
    }

    def __init__(self, hass: HomeAssistant, config: dict) -> None:
        """Initialize LLM router."""
        self.hass = hass
        self.config = config
        self._api_key = config.get("openrouter_api_key")
        self._base_url = "https://openrouter.ai/api/v1"
        self._session: aiohttp.ClientSession | None = None

    async def async_initialize(self) -> None:
        """Initialize HTTP session."""
        self._session = aiohttp.ClientSession(
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            }
        )

    async def async_complete(
        self,
        prompt: str,
        model: str = "fast",
        system_prompt: str | None = None,
        max_tokens: int = 500,
        temperature: float = 0.7,
    ) -> str:
        """Get a completion from the LLM."""
        # Select model from tier
        model_id = self._select_model(model)
        
        # Build messages
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        # Make request
        async with self._session.post(
            f"{self._base_url}/chat/completions",
            json={
                "model": model_id,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            },
        ) as response:
            if response.status != 200:
                error = await response.text()
                raise RuntimeError(f"LLM request failed: {error}")
            
            data = await response.json()
            return data["choices"][0]["message"]["content"]

    async def async_complete_streaming(
        self,
        prompt: str,
        model: str = "conversation",
        system_prompt: str | None = None,
        max_tokens: int = 1000,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        """Get a streaming completion from the LLM."""
        model_id = self._select_model(model)
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        async with self._session.post(
            f"{self._base_url}/chat/completions",
            json={
                "model": model_id,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "stream": True,
            },
        ) as response:
            async for line in response.content:
                line = line.decode().strip()
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    
                    import json
                    chunk = json.loads(data)
                    content = chunk["choices"][0]["delta"].get("content", "")
                    if content:
                        yield content

    def _select_model(self, tier: str) -> str:
        """Select best available model for tier."""
        models = self.MODEL_TIERS.get(tier, self.MODEL_TIERS["fast"])
        
        # Check cost limits
        if self._is_over_budget():
            # Fall back to cheapest model
            return models[-1]
        
        return models[0]

    def _is_over_budget(self) -> bool:
        """Check if daily budget is exceeded."""
        # Implement budget tracking
        return False

    def estimate_cost(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """Estimate cost for a request."""
        model_id = self._select_model(model)
        costs = self.MODEL_COSTS.get(model_id, {"input": 0, "output": 0})
        
        input_cost = (input_tokens / 1_000_000) * costs["input"]
        output_cost = (output_tokens / 1_000_000) * costs["output"]
        
        return input_cost + output_cost

    async def async_shutdown(self) -> None:
        """Shutdown HTTP session."""
        if self._session:
            await self._session.close()
```

---

## Security Architecture

### Policy Engine

```python
# core/policy.py
"""Policy Engine for access control."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from ..agents.base import AgentRequest, AgentType

_LOGGER = logging.getLogger(__name__)


@dataclass
class PolicyResult:
    """Result of a policy check."""
    allowed: bool
    denial_message: str | None = None
    requires_confirmation: bool = False
    confirmation_prompt: str | None = None


class PolicyEngine:
    """Central policy engine for all access control."""

    # Default permission sets
    PERMISSION_SETS = {
        "admin": {
            "permissions": ["all_devices", "security_controls", "configuration"],
            "allowed_domains": ["*"],
        },
        "adult": {
            "permissions": ["device_control", "memory_access"],
            "allowed_domains": [
                "light", "switch", "climate", "media_player",
                "cover", "fan", "scene",
            ],
        },
        "teen": {
            "permissions": ["limited_control"],
            "allowed_domains": ["light", "media_player", "scene"],
            "restrictions": ["no_locks", "no_thermostat_override"],
        },
        "child": {
            "permissions": ["entertainment_only"],
            "allowed_domains": ["media_player"],
            "restrictions": ["no_device_control"],
        },
        "guest": {
            "permissions": ["basic_access"],
            "allowed_domains": ["light"],
            "restrictions": ["no_memory", "no_security"],
        },
    }

    # Privacy zones
    PRIVACY_ZONES = {
        "children_rooms": {
            "audio_capture": False,
            "memory_retention": False,
            "proactive_notifications": False,
        },
        "bathrooms": {
            "audio_capture": False,
            "memory_retention": False,
            "presence_only": True,
        },
        "common_areas": {
            "audio_capture": True,
            "memory_retention": True,
            "proactive_notifications": True,
        },
    }

    # High-risk actions requiring confirmation
    CONFIRMATION_REQUIRED = [
        ("lock", "unlock"),
        ("alarm_control_panel", "*"),
        ("cover", "open_cover"),  # Garage doors
    ]

    def __init__(self, hass: HomeAssistant, config: dict) -> None:
        """Initialize policy engine."""
        self.hass = hass
        self.config = config
        self._user_permissions: dict[str, dict] = {}

    async def async_load_policies(self) -> None:
        """Load policies from configuration."""
        # Load user-specific permissions from config
        user_config = self.config.get("user_permissions", {})
        
        for user_id, user_perms in user_config.items():
            base_set = user_perms.get("permission_set", "adult")
            base_perms = self.PERMISSION_SETS.get(base_set, {}).copy()
            
            # Apply overrides
            if "additional_permissions" in user_perms:
                base_perms.setdefault("permissions", [])
                base_perms["permissions"].extend(user_perms["additional_permissions"])
            
            if "restrictions" in user_perms:
                base_perms.setdefault("restrictions", [])
                base_perms["restrictions"].extend(user_perms["restrictions"])
            
            self._user_permissions[user_id] = base_perms

    async def async_check(
        self,
        request: "AgentRequest",
        agent_type: "AgentType",
    ) -> PolicyResult:
        """Check if a request is allowed."""
        
        # Check privacy zone restrictions
        zone_result = self._check_privacy_zone(request)
        if not zone_result.allowed:
            return zone_result
        
        # Check user permissions
        user_result = await self._check_user_permissions(request)
        if not user_result.allowed:
            return user_result
        
        # Check for high-risk actions
        if agent_type.value == "action":
            confirm_result = self._check_confirmation_required(request)
            if confirm_result.requires_confirmation:
                return confirm_result
        
        return PolicyResult(allowed=True)

    def _check_privacy_zone(self, request: "AgentRequest") -> PolicyResult:
        """Check privacy zone restrictions."""
        zone = request.privacy_zone
        zone_config = self.PRIVACY_ZONES.get(zone, self.PRIVACY_ZONES["common_areas"])
        
        # Check audio capture permission
        if not zone_config.get("audio_capture", True):
            return PolicyResult(
                allowed=False,
                denial_message="Voice commands are not available in this area.",
            )
        
        return PolicyResult(allowed=True)

    async def _check_user_permissions(
        self,
        request: "AgentRequest",
    ) -> PolicyResult:
        """Check user-specific permissions."""
        user_perms = await self.async_get_user_permissions(request.speaker_id)
        
        # Check for "all" permission
        if "all_devices" in user_perms.get("permissions", []):
            return PolicyResult(allowed=True)
        
        # Check for restrictions
        restrictions = user_perms.get("restrictions", [])
        
        if "no_device_control" in restrictions:
            return PolicyResult(
                allowed=False,
                denial_message="You don't have permission to control devices.",
            )
        
        return PolicyResult(allowed=True)

    def _check_confirmation_required(
        self,
        request: "AgentRequest",
    ) -> PolicyResult:
        """Check if action requires confirmation."""
        # Parse action from request text
        text_lower = request.text.lower()
        
        for domain, service in self.CONFIRMATION_REQUIRED:
            if domain in text_lower:
                if service == "*" or service in text_lower:
                    return PolicyResult(
                        allowed=True,
                        requires_confirmation=True,
                        confirmation_prompt=f"Are you sure you want to {request.text}?",
                    )
        
        return PolicyResult(allowed=True)

    async def async_get_user_permissions(self, speaker_id: str) -> dict:
        """Get permissions for a user."""
        if speaker_id in self._user_permissions:
            return self._user_permissions[speaker_id]
        
        # Return guest permissions for unknown users
        return self.PERMISSION_SETS["guest"]
```

---

## Deployment Architecture

### Docker Compose Configuration

```yaml
# docker-compose.yml
version: '3.8'

services:
  homeassistant:
    container_name: homeassistant
    image: ghcr.io/home-assistant/home-assistant:stable
    volumes:
      - ./homeassistant:/config
      - ./custom_components/barnabeenet:/config/custom_components/barnabeenet
      - /etc/localtime:/etc/localtime:ro
    restart: unless-stopped
    network_mode: host
    depends_on:
      - redis

  redis:
    container_name: barnabeenet-redis
    image: redis:7-alpine
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    ports:
      - "6379:6379"
    restart: unless-stopped

  # Optional: Ollama for local LLM inference
  ollama:
    container_name: barnabeenet-ollama
    image: ollama/ollama:latest
    volumes:
      - ollama_data:/root/.ollama
    ports:
      - "11434:11434"
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    restart: unless-stopped

volumes:
  redis_data:
  ollama_data:
```

### Proxmox VM Configuration

```yaml
# proxmox_config.yaml
# BarnabeeNet VM Configuration for Proxmox

vm:
  id: 100
  name: barnabeenet
  
  hardware:
    cores: 8
    memory: 16384  # 16GB
    balloon: 0     # Disable ballooning for predictable performance
    
  disks:
    - type: scsi
      size: 100G
      storage: local-lvm
      ssd: true
      
  network:
    - bridge: vmbr0
      model: virtio
      tag: 10  # IoT VLAN
      
  passthrough:
    # USB passthrough for Zigbee/Z-Wave coordinators
    usb:
      - vendorid: "10c4"
        productid: "ea60"
        
startup:
  order: 1
  up: 120
  down: 60
```

---

## Monitoring & Observability

### Metrics Collection

```python
# monitoring/metrics.py
"""Metrics collection for observability."""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


@dataclass
class MetricsSummary:
    """Summary of collected metrics."""
    request_count: int = 0
    error_count: int = 0
    avg_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    cloud_request_count: int = 0
    estimated_cost: float = 0.0
    
    # By agent
    agent_metrics: dict = field(default_factory=dict)
    
    # By speaker
    speaker_metrics: dict = field(default_factory=dict)


class MetricsCollector:
    """Collect and aggregate metrics."""

    def __init__(self, hass: HomeAssistant, config: dict) -> None:
        """Initialize metrics collector."""
        self.hass = hass
        self.config = config
        self._latencies: list[float] = []
        self._request_count = 0
        self._error_count = 0
        self._cloud_count = 0
        self._cost = 0.0
        self._agent_latencies: dict[str, list[float]] = {}
        self._speaker_counts: dict[str, int] = {}
        self._lock = asyncio.Lock()

    async def record_request(
        self,
        agent_type: str,
        speaker_id: str,
        latency_ms: float,
        cloud_used: bool,
        cost: float = 0.0,
        success: bool = True,
    ) -> None:
        """Record a request metric."""
        async with self._lock:
            self._request_count += 1
            self._latencies.append(latency_ms)
            
            if not success:
                self._error_count += 1
            
            if cloud_used:
                self._cloud_count += 1
                self._cost += cost
            
            # By agent
            if agent_type not in self._agent_latencies:
                self._agent_latencies[agent_type] = []
            self._agent_latencies[agent_type].append(latency_ms)
            
            # By speaker
            self._speaker_counts[speaker_id] = self._speaker_counts.get(speaker_id, 0) + 1
            
            # Trim old data (keep last hour)
            max_samples = 3600
            if len(self._latencies) > max_samples:
                self._latencies = self._latencies[-max_samples:]
            for agent in self._agent_latencies:
                if len(self._agent_latencies[agent]) > max_samples:
                    self._agent_latencies[agent] = self._agent_latencies[agent][-max_samples:]

    async def get_summary(self) -> MetricsSummary:
        """Get metrics summary."""
        async with self._lock:
            summary = MetricsSummary(
                request_count=self._request_count,
                error_count=self._error_count,
                cloud_request_count=self._cloud_count,
                estimated_cost=self._cost,
            )
            
            # Calculate latency percentiles
            if self._latencies:
                sorted_latencies = sorted(self._latencies)
                summary.avg_latency_ms = sum(sorted_latencies) / len(sorted_latencies)
                summary.p95_latency_ms = sorted_latencies[int(len(sorted_latencies) * 0.95)]
                summary.p99_latency_ms = sorted_latencies[int(len(sorted_latencies) * 0.99)]
            
            # Agent metrics
            for agent, latencies in self._agent_latencies.items():
                if latencies:
                    summary.agent_metrics[agent] = {
                        "count": len(latencies),
                        "avg_ms": sum(latencies) / len(latencies),
                    }
            
            # Speaker metrics
            summary.speaker_metrics = self._speaker_counts.copy()
            
            return summary

    async def reset_daily(self) -> None:
        """Reset daily counters."""
        async with self._lock:
            self._request_count = 0
            self._error_count = 0
            self._cloud_count = 0
            self._cost = 0.0
            self._speaker_counts = {}
```

### Tracing

```python
# monitoring/tracing.py
"""Distributed tracing for request tracking."""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


@dataclass
class Span:
    """A single span in a trace."""
    trace_id: str
    span_id: str
    parent_span_id: str | None
    operation: str
    start_time: float
    end_time: float | None = None
    tags: dict = field(default_factory=dict)
    logs: list = field(default_factory=list)
    status: str = "ok"


class Tracer:
    """Distributed tracing for request flows."""

    def __init__(self, hass: HomeAssistant, config: dict) -> None:
        """Initialize tracer."""
        self.hass = hass
        self.config = config
        self._traces: dict[str, list[Span]] = {}
        self._current_trace: asyncio.ContextVar[str | None] = asyncio.ContextVar(
            "current_trace", default=None
        )
        self._current_span: asyncio.ContextVar[str | None] = asyncio.ContextVar(
            "current_span", default=None
        )

    def start_trace(self, operation: str) -> str:
        """Start a new trace."""
        trace_id = str(uuid.uuid4())
        self._traces[trace_id] = []
        self._current_trace.set(trace_id)
        
        # Create root span
        self._start_span(operation)
        
        return trace_id

    @asynccontextmanager
    async def span(self, operation: str):
        """Context manager for a span."""
        span_id = self._start_span(operation)
        try:
            yield span_id
        except Exception as e:
            self._set_span_error(span_id, str(e))
            raise
        finally:
            self._end_span(span_id)

    def _start_span(self, operation: str) -> str:
        """Start a new span."""
        trace_id = self._current_trace.get()
        if not trace_id:
            return ""
        
        span_id = str(uuid.uuid4())[:8]
        parent_span_id = self._current_span.get()
        
        span = Span(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
            operation=operation,
            start_time=time.perf_counter(),
        )
        
        self._traces[trace_id].append(span)
        self._current_span.set(span_id)
        
        return span_id

    def _end_span(self, span_id: str) -> None:
        """End a span."""
        trace_id = self._current_trace.get()
        if not trace_id:
            return
        
        for span in self._traces[trace_id]:
            if span.span_id == span_id:
                span.end_time = time.perf_counter()
                break
        
        # Restore parent span
        for span in self._traces[trace_id]:
            if span.span_id == span_id:
                self._current_span.set(span.parent_span_id)
                break

    def _set_span_error(self, span_id: str, error: str) -> None:
        """Mark span as error."""
        trace_id = self._current_trace.get()
        if not trace_id:
            return
        
        for span in self._traces[trace_id]:
            if span.span_id == span_id:
                span.status = "error"
                span.tags["error"] = error
                break

    def add_tag(self, key: str, value: Any) -> None:
        """Add tag to current span."""
        trace_id = self._current_trace.get()
        span_id = self._current_span.get()
        if not trace_id or not span_id:
            return
        
        for span in self._traces[trace_id]:
            if span.span_id == span_id:
                span.tags[key] = value
                break

    def log(self, message: str) -> None:
        """Add log to current span."""
        trace_id = self._current_trace.get()
        span_id = self._current_span.get()
        if not trace_id or not span_id:
            return
        
        for span in self._traces[trace_id]:
            if span.span_id == span_id:
                span.logs.append({
                    "timestamp": time.perf_counter(),
                    "message": message,
                })
                break

    def get_trace(self, trace_id: str) -> list[Span] | None:
        """Get a completed trace."""
        return self._traces.get(trace_id)

    def end_trace(self, trace_id: str) -> list[Span]:
        """End and return a trace."""
        spans = self._traces.pop(trace_id, [])
        self._current_trace.set(None)
        self._current_span.set(None)
        return spans
```

---

## Appendix: Constants and Configuration

```python
# const.py
"""Constants for BarnabeeNet."""

DOMAIN = "barnabeenet"

# Scan intervals
SCAN_INTERVAL = 60  # seconds

# Default configuration
DEFAULT_CONFIG = {
    # Redis
    "redis_url": "redis://localhost:6379",
    
    # STT
    "stt_model": "distil-whisper/distil-small.en",
    "stt_device": "cpu",
    "stt_compute_type": "int8",
    
    # TTS
    "tts_engine": "kokoro",
    "tts_voice": "af_bella",
    "tts_speed": 1.0,
    "tts_sample_rate": 24000,
    
    # Speaker recognition
    "speaker_threshold": 0.75,
    
    # LLM
    "openrouter_api_key": "",
    "daily_cost_limit": 1.00,
    
    # Privacy
    "privacy_zones": {
        "children_rooms": ["bedroom.penelope", "bedroom.xander", "bedroom.zachary", "bedroom.viola"],
        "bathrooms": ["bathroom.master", "bathroom.kids"],
        "common_areas": ["living_room", "kitchen", "office", "garage"],
    },
    
    # Memory
    "memory_retention_days": 30,
    "consolidation_hour": 3,
}

# Event types
EVENT_VOICE_INPUT = f"{DOMAIN}_voice_input"
EVENT_TRANSCRIPTION = f"{DOMAIN}_transcription"
EVENT_RESPONSE = f"{DOMAIN}_response"
EVENT_ACTION = f"{DOMAIN}_action"

# Service names
SERVICE_PROCESS_VOICE = "process_voice"
SERVICE_PROCESS_TEXT = "process_text"
SERVICE_ENROLL_SPEAKER = "enroll_speaker"
SERVICE_QUERY_MEMORY = "query_memory"
```

---

## Document History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-01-16 | Initial technical architecture document |

---

*This document provides the technical foundation for BarnabeeNet implementation. For feature descriptions, see BarnabeeNet_Features_UseCases.md. For hardware details, see BarnabeeNet_Hardware_Specifications.md.*
