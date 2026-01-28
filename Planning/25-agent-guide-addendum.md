# Area 25: Agent Implementation Guide - Addendum

**Version:** 1.0  
**Status:** Implementation Ready  
**Purpose:** Additional guidance for AI coding agents including parallelization opportunities, checkpoints, and scaffold usage  

---

## 1. Using the Scaffold

### 1.1 Scaffold Location

The implementation scaffold is located at `/home/thom/projects/Planning/scaffold/`. 

**AGENT ACTION:** At the start of Phase 0, copy the scaffold to the build location:

```bash
# Copy scaffold to build location
cp -r /home/thom/projects/Planning/scaffold/* /opt/barnabee-v2/

# Verify structure
ls -la /opt/barnabee-v2/
```

The scaffold includes:
- `pyproject.toml` - Complete dependencies for ALL areas
- `src/barnabee/config.py` - Centralized configuration
- `src/barnabee/interfaces.py` - Interface contracts between areas
- `.env.example` - All environment variables documented
- `data/golden_dataset_v1.jsonl` - 150+ labeled utterances for testing
- `tests/conftest.py` - Shared test fixtures including mock HA
- `tests/fixtures/ha/mock_entities.json` - Mock Home Assistant for testing
- `.github/workflows/ci.yml` - CI pipeline definition

### 1.2 Key Files to Use

| File | Purpose | When to Use |
|------|---------|-------------|
| `interfaces.py` | Data contracts between areas | Import when building any area |
| `config.py` | All settings in one place | Import at module initialization |
| `mock_entities.json` | Test without real HA | Set `BARNABEE_TEST_USE_MOCK_HA=true` |
| `golden_dataset_v1.jsonl` | Intent classification testing | Phase 2A testing |
| `seed_memories.json` | Memory search testing | Phase 3 testing |

---

## 2. Parallelization Opportunities

### 2.1 Phase Parallelization

Some work can be done in parallel within phases. The agent should take advantage of this when possible.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     PARALLELIZATION OPPORTUNITIES                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  PHASE 1: Infrastructure                                                     │
│  ════════════════════════                                                    │
│                                                                              │
│  Phase 1A: Core Data Layer        Phase 1B: Voice Pipeline                  │
│  ─────────────────────────        ─────────────────────────                 │
│  ┌─────────────────────┐          ┌─────────────────────┐                   │
│  │ SQLite Schema       │          │ Pipecat Setup       │  ← Can start     │
│  │ Migrations          │  ──────▶ │ Transport Layer     │    after schema   │
│  │ Basic Repositories  │          │ (no DB needed yet)  │    is done        │
│  └─────────────────────┘          └─────────────────────┘                   │
│           │                                │                                 │
│           ▼                                ▼                                 │
│  ┌─────────────────────┐          ┌─────────────────────┐                   │
│  │ Redis Session Store │ ◀──┬───▶ │ STT/TTS Services    │  ← Parallel      │
│  │ FTS5 Search         │    │     │ Wake Word           │                   │
│  └─────────────────────┘    │     └─────────────────────┘                   │
│                             │                                                │
│                        Both need Redis running                               │
│                                                                              │
│  PHASE 2: Backbone                                                          │
│  ═════════════════                                                          │
│                                                                              │
│  ┌─────────────────────┐          ┌─────────────────────┐                   │
│  │ Phase 2A:           │          │ Phase 2B:           │                   │
│  │ Intent              │ ◀──────▶ │ Home Assistant      │  ← PARALLEL!     │
│  │ Classification      │          │ Integration         │                   │
│  │                     │          │                     │                   │
│  │ - Pattern matcher   │          │ - WebSocket client  │                   │
│  │ - Embedding         │          │ - Entity cache      │                   │
│  │   classifier        │          │ - Command executor  │                   │
│  │ - LLM fallback      │          │                     │                   │
│  └─────────────────────┘          └─────────────────────┘                   │
│           │                                │                                 │
│           └────────────┬───────────────────┘                                │
│                        │                                                     │
│                        ▼                                                     │
│              ┌─────────────────────┐                                        │
│              │ Integration Tests    │  ← After both complete                │
│              │ "Turn on the lights" │                                        │
│              └─────────────────────┘                                        │
│                                                                              │
│  PHASE 3-4: Data + Core                                                     │
│  ══════════════════════                                                     │
│                                                                              │
│  These are mostly SEQUENTIAL due to tight integration.                       │
│  Memory system needs to work before response generation can use it.          │
│                                                                              │
│  PHASE 5: Extended Features                                                  │
│  ═════════════════════════                                                   │
│                                                                              │
│  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐                   │
│  │ Meeting   │ │ Self-     │ │ Calendar  │ │ Dashboard │  ← PARALLEL!     │
│  │ Scribe    │ │ Improve   │ │ Email     │ │ Build     │                   │
│  │ (Area 07) │ │ (Area 08) │ │ (Area 12) │ │ (Area 09) │                   │
│  └───────────┘ └───────────┘ └───────────┘ └───────────┘                   │
│                                                                              │
│  All depend on Phase 4 completion but not on each other.                     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Within-Phase Parallelization

Even within a single phase, many operations can run in parallel:

```python
# Example: Phase 1A - Run these tests in parallel
pytest tests/unit/test_db.py tests/unit/test_memory_repo.py tests/unit/test_session.py -n auto

# Example: Phase 2 - Start both services
docker compose up -d redis  # First (required by both)
# Then in parallel:
#   Terminal 1: Work on intent classification
#   Terminal 2: Work on HA integration
```

### 2.3 Agent Parallel Tool Calls

When the agent needs to gather information, it should batch tool calls:

```
GOOD: Read 3 files in parallel
┌─────────────────────────────────────┐
│ Read: 01-core-data-layer.md         │
│ Read: 02-voice-pipeline.md          │  ← All in one message
│ Read: interfaces.py                 │
└─────────────────────────────────────┘

BAD: Read files sequentially
┌─────────────────────────────────────┐
│ Read: 01-core-data-layer.md         │  ← Message 1
└─────────────────────────────────────┘
┌─────────────────────────────────────┐
│ Read: 02-voice-pipeline.md          │  ← Message 2 (wasted time)
└─────────────────────────────────────┘
```

---

## 3. Checkpoints (Updated)

### 3.1 Model Download Checkpoint (NEW)

**IMPORTANT:** Model download happens at MILESTONE 1 CHECKPOINT, not during preflight.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     MILESTONE 1 CHECKPOINT                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  BEFORE human testing of voice pipeline:                                     │
│                                                                              │
│  □ Run model download script                                                │
│    └── /opt/barnabee-v2/scripts/download_models.sh                         │
│    └── This downloads ~6GB of models, takes 15-30 minutes                   │
│                                                                              │
│  □ Verify models downloaded                                                 │
│    └── ls -la /opt/barnabee-v2/models/                                     │
│    └── Should see: parakeet, kokoro, openwakeword, silero_vad              │
│                                                                              │
│  □ Run model warmup                                                         │
│    └── First inference is slow, warmup avoids this during testing          │
│                                                                              │
│  THEN: Stop for human voice pipeline testing                                 │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Updated Checkpoint Summary

| Checkpoint | When | What Happens |
|------------|------|--------------|
| **Pre-flight** | Before Phase 0 | Environment verification, permissions, network |
| **Milestone 1** | End of Phase 1B | Model download, voice pipeline testing |
| **Milestone 2** | End of Phase 2B | HA integration testing ("turn on the lights") |
| **Milestone 3** | End of Phase 4 | Full E2E testing (voice + memory + persona) |
| **Milestone 4** | End of Phase 5 | Production readiness review |

### 3.3 Credential Checkpoints

Stop and request credentials at these specific points:

| Credential | Phase | Stop Message |
|------------|-------|--------------|
| HA Token | Phase 2B start | "🔑 Need HA long-lived access token. Add to Dashboard Settings or .env: `BARNABEE_HA_TOKEN=...`" |
| Azure OpenAI | Phase 2A start | "🔑 Need Azure OpenAI credentials. Add to Dashboard Settings or .env: `BARNABEE_LLM_AZURE_*`" |
| Daily.co API | Phase 1B (if using) | "🔑 Need Daily.co API key for WebRTC. Add `BARNABEE_VOICE_DAILY_API_KEY=...` or skip for local-only" |
| Google OAuth | Phase 5 (Calendar) | "🔑 Need Google OAuth credentials for calendar/email integration" |

---

## 4. Testing with Mock Home Assistant

### 4.1 Why Mock HA

Testing with real Home Assistant means:
- Lights turning on/off during tests
- Locks cycling (security concern)
- Thermostats changing temperature
- False wake word triggers affecting family

The mock HA client allows full testing without any real-world effects.

### 4.2 Enabling Mock HA

```bash
# In .env or environment
BARNABEE_TEST_USE_MOCK_HA=true
BARNABEE_TEST_MOCK_HA_ENTITIES_PATH=/opt/barnabee-v2/tests/fixtures/ha/mock_entities.json
```

### 4.3 Mock HA Features

The mock client (`tests/conftest.py :: mock_ha_client`) provides:

- **State queries** - Returns fixture data instead of real states
- **Service calls** - Logs calls and simulates state changes
- **Alias resolution** - "living room lights" → "light.living_room"
- **Call logging** - Assert that correct services were called

```python
# Example test using mock HA
async def test_turn_on_lights(mock_ha_client, make_classification_result):
    classification = make_classification_result(
        intent="light_control",
        utterance="turn on the living room lights",
    )
    
    # Execute command
    result = await command_executor.execute(classification, mock_ha_client)
    
    # Verify correct service was called
    assert len(mock_ha_client.call_log) == 1
    assert mock_ha_client.call_log[0]["service"] == "turn_on"
    assert mock_ha_client.call_log[0]["kwargs"]["entity_id"] == "light.living_room"
    
    # Verify state changed (in mock)
    state = await mock_ha_client.get_state("light.living_room")
    assert state["state"] == "on"
```

### 4.4 Adding Test Entities

To add new mock entities, edit `tests/fixtures/ha/mock_entities.json`:

```json
{
  "entities": {
    "light.new_room": {
      "entity_id": "light.new_room",
      "state": "off",
      "attributes": {
        "friendly_name": "New Room Lights",
        "supported_features": 63
      },
      "domain": "light",
      "area": "New Room"
    }
  },
  "entity_aliases": {
    "new room lights": "light.new_room"
  }
}
```

---

## 5. Dashboard-Managed Configuration

### 5.1 Runtime Configuration

In production, environment variables are managed through the Dashboard Admin UI, NOT by editing `.env` files.

The Dashboard provides:
- **Settings page** - Edit all configuration values
- **Secrets management** - Secure storage for API keys
- **Hot reload** - Some settings apply without restart
- **Validation** - Prevents invalid configurations
- **Audit log** - Track who changed what

### 5.2 Configuration Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     CONFIGURATION MANAGEMENT                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Development:                                                                │
│  ────────────                                                                │
│  .env file → config.py → application                                        │
│                                                                              │
│  Production:                                                                 │
│  ───────────                                                                 │
│  Dashboard UI → Database → config.py → application                          │
│       │                                                                      │
│       └── Admin → Settings → [Edit Value] → Save                            │
│                                    │                                         │
│                                    ▼                                         │
│                         ┌─────────────────┐                                 │
│                         │ encrypted_tokens │  (for secrets)                 │
│                         │ config_values    │  (for settings)                │
│                         └─────────────────┘                                 │
│                                    │                                         │
│                                    ▼                                         │
│                         Application hot-reloads                              │
│                         (for supported settings)                             │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.3 Dashboard Settings Page (Area 09)

When building the Dashboard (Area 09), include a Settings page with:

```typescript
// dashboard/src/pages/Admin/Settings.tsx

interface SettingsSection {
  title: string;
  settings: Setting[];
}

const settingsSections: SettingsSection[] = [
  {
    title: "Home Assistant",
    settings: [
      { key: "BARNABEE_HA_URL", label: "HA URL", type: "url" },
      { key: "BARNABEE_HA_TOKEN", label: "Access Token", type: "secret" },
    ]
  },
  {
    title: "LLM Providers",
    settings: [
      { key: "BARNABEE_LLM_AZURE_ENDPOINT", label: "Azure Endpoint", type: "url" },
      { key: "BARNABEE_LLM_AZURE_API_KEY", label: "Azure API Key", type: "secret" },
      { key: "BARNABEE_LLM_AZURE_DEPLOYMENT", label: "Deployment Name", type: "text" },
    ]
  },
  // ... etc
];
```

---

## 6. Health Check Dashboard Integration

### 6.1 Health Check Contract

All services expose `/health` returning the `ServiceHealth` interface:

```python
# From interfaces.py
@dataclass
class ServiceHealth:
    status: str                      # healthy, degraded, unhealthy
    version: str
    uptime_seconds: float
    checks: dict[str, ComponentHealth]
    cpu_percent: Optional[float]
    memory_percent: Optional[float]
    gpu_memory_percent: Optional[float]
    active_sessions: Optional[int]
    requests_per_minute: Optional[float]
```

### 6.2 Dashboard Health Display

The Dashboard should display health status for all services:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  SYSTEM HEALTH                                          Last updated: 10:05  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │ API Server  │  │ GPU Services│  │    Redis    │  │  Pipecat    │        │
│  │             │  │             │  │             │  │             │        │
│  │   ✅ OK     │  │   ✅ OK     │  │   ✅ OK     │  │   ⚠️ WARN   │        │
│  │             │  │             │  │             │  │             │        │
│  │ v2.0.0      │  │ v2.0.0      │  │ v7.2.4      │  │ v2.0.0      │        │
│  │ 45% CPU     │  │ 62% GPU mem │  │ 128MB used  │  │ 2 sessions  │        │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘        │
│                                                                              │
│  Component Details:                                                          │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │ API Server                                                             │  │
│  │   ├── database: ✅ healthy (5ms)                                      │  │
│  │   ├── redis: ✅ healthy (2ms)                                         │  │
│  │   ├── ha_connection: ✅ healthy                                       │  │
│  │   └── llm_providers: ✅ healthy (azure: ok, ollama: ok)              │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │ GPU Services                                                           │  │
│  │   ├── stt_model: ✅ healthy (loaded, 45ms avg)                        │  │
│  │   ├── tts_model: ✅ healthy (loaded, 120ms avg)                       │  │
│  │   ├── embedding_model: ✅ healthy (loaded)                            │  │
│  │   └── gpu_memory: ✅ healthy (62% used, 10GB/16GB)                    │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │ Pipecat (Voice Pipeline)                                               │  │
│  │   ├── wake_word: ⚠️ degraded (high false positive rate: 0.8/hr)      │  │
│  │   ├── transport: ✅ healthy (2 active connections)                    │  │
│  │   └── audio_processing: ✅ healthy                                    │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 6.3 Health Endpoint Implementation

Each service implements `/health`:

```python
# src/barnabee/api/health.py

from fastapi import APIRouter
from barnabee.interfaces import ServiceHealth, ComponentHealth

router = APIRouter()

@router.get("/health", response_model=ServiceHealth)
async def health_check(
    db = Depends(get_db),
    redis = Depends(get_redis),
    ha_client = Depends(get_ha_client),
) -> ServiceHealth:
    """
    Health check endpoint.
    Returns detailed health status for Dashboard display.
    """
    checks = {}
    overall_status = "healthy"
    
    # Check database
    try:
        start = time.perf_counter()
        await db.execute("SELECT 1")
        latency = (time.perf_counter() - start) * 1000
        checks["database"] = ComponentHealth(
            status="healthy",
            latency_ms=int(latency),
        )
    except Exception as e:
        checks["database"] = ComponentHealth(
            status="unhealthy",
            message=str(e),
        )
        overall_status = "unhealthy"
    
    # Check Redis
    try:
        start = time.perf_counter()
        await redis.ping()
        latency = (time.perf_counter() - start) * 1000
        checks["redis"] = ComponentHealth(
            status="healthy",
            latency_ms=int(latency),
        )
    except Exception as e:
        checks["redis"] = ComponentHealth(
            status="unhealthy",
            message=str(e),
        )
        overall_status = "degraded" if overall_status == "healthy" else overall_status
    
    # Check HA connection
    # ... etc
    
    return ServiceHealth(
        status=overall_status,
        version=__version__,
        uptime_seconds=get_uptime(),
        checks=checks,
        cpu_percent=psutil.cpu_percent(),
        memory_percent=psutil.virtual_memory().percent,
        active_sessions=session_manager.active_count,
        requests_per_minute=metrics.get_rpm(),
    )
```

---

## 7. Summary

This addendum provides:

1. **Scaffold usage instructions** - How to use the pre-built scaffold
2. **Parallelization guidance** - What can be built in parallel
3. **Updated checkpoints** - Including model download at Milestone 1
4. **Mock HA testing** - Test without affecting real devices
5. **Dashboard configuration** - How settings are managed in production
6. **Health check integration** - How health displays on the Dashboard

The agent should read this document alongside `24-agent-implementation-guide.md` for complete guidance.

---

**End of Area 25: Agent Implementation Guide Addendum**
