# Documentation Patch: Phase 1 Research Updates

**Date:** January 17, 2026  
**Purpose:** Surgical updates to align documentation with Phase 1 research decisions

This patch documents all changes needed based on:
1. STT/TTS technology research (Kokoro, Distil-Whisper, Parakeet TDT)
2. GPU worker architecture (Man-of-war integration)
3. SkyrimNet deep research insights

---

## Patch 1: BarnabeeNet_Technical_Architecture.md

### 1.1 Technology Stack Table (find "Technology Stack" section)

**FIND:**
```markdown
| **STT** | Faster-Whisper | 0.10+ | Speech recognition |
| **TTS** | Piper | 1.2+ | Voice synthesis |
```

**REPLACE WITH:**
```markdown
| **STT (CPU)** | Distil-Whisper | 1.0+ | Speech recognition (Beelink fallback) |
| **STT (GPU)** | Parakeet TDT 0.6B v2 | 1.22+ | Speech recognition (Man-of-war primary) |
| **TTS** | Kokoro | 0.3+ | Voice synthesis (replaced Piper - faster, better quality) |
```

### 1.2 Add GPU Worker Section (after "Design Principles" section)

**ADD NEW SECTION:**
```markdown
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
```

### 1.3 Update TTS Implementation Code Block

**FIND the section starting with:**
```python
# voice/tts.py
"""Text-to-Speech using Piper."""
```

**REPLACE the entire code block with:**
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

## Patch 2: BarnabeeNet_README_v3.2.md (or latest version)

### 2.1 Update Voice Pipeline Section

**FIND:**
```markdown
### Text-to-Speech

**Primary:** Piper (local, fast, good quality)

```yaml
tts:
  engine: piper
  voice: en_US-lessac-medium  # Natural, good prosody
  sample_rate: 22050
```

**REPLACE WITH:**
```markdown
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
```

### 2.2 Update Implementation Roadmap Phase 1

**FIND:**
```markdown
### Phase 1: Infrastructure Foundation (Weeks 1-4)

- [X] HA custom integration skeleton
- [X] SQLite schema + migrations
- [X] Redis configuration
- [ ] Basic STT pipeline (Faster-Whisper)
- [ ] Basic TTS pipeline (Piper)
```

**REPLACE WITH:**
```markdown
### Phase 1: Infrastructure Foundation (Weeks 1-4)

- [X] HA custom integration skeleton
- [X] SQLite schema + migrations
- [X] Redis configuration
- [ ] Basic STT pipeline (Distil-Whisper CPU + Parakeet GPU)
- [ ] Basic TTS pipeline (Kokoro)
- [ ] GPU worker on Man-of-war (WSL2 + CUDA)
- [ ] Health check routing system
```

---

## Patch 3: docs/architecture.md

### 3.1 Update Quick Reference Table

**FIND:**
```markdown
| STT | Faster-Whisper | Container |
| TTS | Piper | Container |
```

**REPLACE WITH:**
```markdown
| STT (CPU) | Distil-Whisper | BarnabeeNet Core |
| STT (GPU) | Parakeet TDT 0.6B v2 | Man-of-war Worker |
| TTS | Kokoro | BarnabeeNet Core |
```

---

## Patch 4: barnabeenet-project-log-updated.md

### 4.1 Update Phase 1 TODO

**FIND:**
```markdown
## Phase 1: Core Services
**Status:** 🔄 Ready to Start

### TODO
- [ ] Add Faster-Whisper container (STT)
- [ ] Add Piper container (TTS)
```

**REPLACE WITH:**
```markdown
## Phase 1: Core Services
**Status:** 🔄 In Progress

### TODO
- [ ] Add Distil-Whisper STT (CPU fallback)
- [ ] Add Parakeet TDT STT (GPU primary on Man-of-war)
- [ ] Add Kokoro TTS
- [ ] Setup GPU worker on Man-of-war (WSL2 + CUDA)
- [ ] Implement health check routing
```

### 4.2 Add New Decision to Decisions Table

**ADD ROW to "Decisions Made" table:**
```markdown
| 2026-01-17 | Kokoro over Piper for TTS | Research shows Kokoro is faster (<0.3s) and better quality |
| 2026-01-17 | Dual-path STT (Parakeet + Distil-Whisper) | GPU primary for speed, CPU fallback for reliability |
| 2026-01-17 | Man-of-war as GPU worker | RTX 4070 Ti provides 10x faster STT than CPU |
| 2026-01-17 | WSL2 for GPU worker | No dual-boot needed, can game while worker runs |
```

---

## Patch 5: BarnabeeNet_Implementation_Guide.md

### 5.1 Update Voice Pipeline Section Header

**FIND:**
```markdown
### 2.3 Text-to-Speech Implementation

#### voice/tts.py

```python
"""Text-to-Speech using Piper."""
```

**REPLACE WITH:**
```markdown
### 2.3 Text-to-Speech Implementation

#### voice/tts.py

```python
"""Text-to-Speech using Kokoro.

Kokoro-82M was selected over Piper based on 2025 benchmarks:
- Speed: <0.3s processing (faster than Piper)
- Quality: Comparable to larger models
- License: Apache 2.0 (commercial-friendly)
- Size: 82M parameters (runs efficiently on CPU)
"""
```

---

## Patch 6: Add SkyrimNet Insights to Theory Document

### 6.1 BarnabeeNet_Theory_Research.md - Add Section

**ADD after "Game AI Inspiration" section:**

```markdown
### SkyrimNet Deep Dive: Applicable Patterns

Based on detailed analysis of SkyrimNet's architecture (see `SkyrimNet_Deep_Research_For_BarnabeeNet.md`), these patterns directly apply to BarnabeeNet:

#### 1. Multi-Tier Model Strategy
SkyrimNet uses different models for different cognitive tasks:

| Task | SkyrimNet Model | BarnabeeNet Equivalent |
|------|-----------------|------------------------|
| Quick classification | DeepSeek (fast) | Local classifier / Haiku |
| Dialogue generation | Claude Sonnet | Claude Sonnet via OpenRouter |
| Complex reasoning | Claude Opus | Claude Opus for planning |
| Memory operations | MiniLM embeddings | MiniLM-L6-v2 |

#### 2. First-Person Memory Perspective
SkyrimNet stores NPC memories from the NPC's perspective, not third-person:

```
# Bad (third-person):
"The player asked Lydia about her past."

# Good (first-person, SkyrimNet style):
"My Thane asked about my childhood in Whiterun. I shared memories of training with the guards."
```

BarnabeeNet should store memories from Barnabee's perspective about family members.

#### 3. Context Decorators
SkyrimNet injects live state into prompts via "decorators":

```python
# SkyrimNet pattern
@decorator("current_time")
@decorator("nearby_npcs")  
@decorator("recent_events")
def build_prompt(base_prompt):
    # Decorators automatically inject context
    pass
```

BarnabeeNet equivalent:
```python
@decorator("home_state")      # Current device states
@decorator("family_presence") # Who's home
@decorator("time_context")    # Morning routine vs evening
@decorator("recent_commands") # What was just asked
```

#### 4. Hot-Reload Configuration
SkyrimNet reloads prompts and config without restart. BarnabeeNet should support:
- Prompt template changes
- Model routing rules
- Voice settings
- Privacy zone definitions

#### 5. Comprehensive Observability
SkyrimNet's dashboard shows exactly what the AI is "thinking":
- Full prompt sent to each model
- Token counts and costs
- Latency breakdown
- Memory retrievals

BarnabeeNet needs equivalent visibility for debugging and optimization.
```

---

## How to Apply These Patches in Cursor

For each patch:

1. **Open the target file** in Cursor
2. **Use Ctrl+F** to find the "FIND" text
3. **Select the text** to replace
4. **Delete and paste** the "REPLACE WITH" content
5. **Save the file** (Ctrl+S)

Or use Cursor's AI:
1. Select the section to update
2. Press **Ctrl+K**
3. Say: "Replace this with: [paste the REPLACE WITH content]"

---

## Verification Checklist

After applying all patches, verify:

- [ ] `BarnabeeNet_Technical_Architecture.md` mentions Kokoro and Parakeet
- [ ] `BarnabeeNet_README_v3.x.md` has updated STT/TTS sections
- [ ] `docs/architecture.md` Quick Reference is updated
- [ ] `barnabeenet-project-log-updated.md` Phase 1 TODO reflects new stack
- [ ] Implementation Guide references Kokoro
- [ ] Theory doc includes SkyrimNet patterns

---

## Git Commit Message

```
docs: Update voice pipeline tech stack based on Phase 1 research

- Replace Piper with Kokoro-82M for TTS (faster, better quality)
- Add dual-path STT: Parakeet TDT (GPU) + Distil-Whisper (CPU)
- Document Man-of-war GPU worker architecture
- Add SkyrimNet architectural patterns to theory doc
- Update implementation roadmap for Phase 1
```
