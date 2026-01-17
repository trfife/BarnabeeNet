# BarnabeeNet Implementation Guide

**Version:** 1.0  
**Last Updated:** January 16, 2026  
**Author:** Thom Fife  
**Document Type:** Technical Implementation Guide

---

## Table of Contents

1. [Prerequisites and Environment Setup](#1-prerequisites-and-environment-setup)
2. [Phase 1: Infrastructure Foundation](#2-phase-1-infrastructure-foundation)
3. [Phase 2: Speaker Recognition & Personalization](#3-phase-2-speaker-recognition--personalization)
4. [Phase 3: Memory & Intelligence](#4-phase-3-memory--intelligence)
5. [Phase 4: Proactive & Self-Improving Intelligence](#5-phase-4-proactive--self-improving-intelligence)
6. [Phase 5: Polish & Optimization](#6-phase-5-polish--optimization)
7. [Testing Strategy](#7-testing-strategy)
8. [Deployment Procedures](#8-deployment-procedures)
9. [Troubleshooting Guide](#9-troubleshooting-guide)
10. [Configuration Reference](#10-configuration-reference)

---

## 1. Prerequisites and Environment Setup

### 1.1 Hardware Preparation

#### Beelink EQi12 Production Server

Before beginning implementation, verify the following hardware specifications:

```bash
# Verify CPU capabilities
lscpu | grep -E "(Model name|CPU\(s\)|Thread|Core)"

# Expected output:
# Model name: 12th Gen Intel(R) Core(TM) i3-1220P
# CPU(s): 12
# Thread(s) per core: 2
# Core(s) per socket: 10

# Verify RAM (must be 24GB for model loading)
free -h
# Expected: Mem: 24Gi

# Verify NVMe storage
lsblk -d -o NAME,SIZE,MODEL
nvme list
```

#### Network Configuration

```bash
# Configure dual LAN interfaces
# Edit /etc/network/interfaces (Proxmox)

auto vmbr0
iface vmbr0 inet static
    address 192.168.1.10/24
    gateway 192.168.1.1
    bridge-ports enp1s0
    bridge-stp off
    bridge-fd 0

auto vmbr1
iface vmbr1 inet static
    address 10.0.0.1/24
    bridge-ports enp2s0
    bridge-stp off
    bridge-fd 0
    # IoT VLAN for smart devices
```

### 1.2 Proxmox VE Installation and Configuration

#### Base Proxmox Installation

1. **Download Proxmox VE 8.x ISO** from https://www.proxmox.com/en/downloads
2. **Flash to USB** using Balena Etcher or Rufus
3. **Boot and install** using the text-based installer for Intel 12th Gen compatibility

```bash
# Post-installation - access Proxmox shell
# Update repositories (remove enterprise repo if no subscription)
mv /etc/apt/sources.list.d/pve-enterprise.list /etc/apt/sources.list.d/pve-enterprise.list.bak

# Add no-subscription repository
echo "deb http://download.proxmox.com/debian/pve bookworm pve-no-subscription" > /etc/apt/sources.list.d/pve-no-subscription.list

# Update and upgrade
apt update && apt dist-upgrade -y

# Install useful packages
apt install -y vim htop iotop intel-microcode
```

#### Create Home Assistant OS VM

Use the community script (successor to tteck's scripts):

```bash
# Run from Proxmox shell - NOT over SSH
bash -c "$(wget -qLO - https://github.com/community-scripts/ProxmoxVE/raw/main/vm/haos-vm.sh)"

# Select advanced settings when prompted:
# - Machine Type: Q35 (modern, better UEFI support)
# - Disk Cache: Write Through (data safety over speed)
# - CPU Cores: 4 (minimum recommended)
# - RAM: 4096 MB (4GB minimum, 8GB recommended)
# - Storage: local-lvm or your preferred storage pool
```

**Recommended VM Resource Allocation:**

| VM/Container | CPU Cores | RAM | Storage | Purpose |
|--------------|-----------|-----|---------|---------|
| Home Assistant OS | 4 | 8 GB | 64 GB | Core automation |
| Redis (LXC) | 1 | 512 MB | 4 GB | Short-term memory |
| Voice Services (LXC) | 4 | 8 GB | 32 GB | STT/TTS processing |
| Development (VM) | 4 | 8 GB | 64 GB | Testing environment |

#### Redis LXC Container Setup

```bash
# Create Redis LXC using community script
bash -c "$(wget -qLO - https://github.com/community-scripts/ProxmoxVE/raw/main/ct/redis.sh)"

# Post-creation Redis configuration
# Edit /etc/redis/redis.conf in the container:

bind 0.0.0.0
protected-mode no
maxmemory 256mb
maxmemory-policy allkeys-lru

# Session TTL configuration for BarnabeeNet
# Working memory: 10 minutes = 600 seconds
timeout 0
tcp-keepalive 300
```

### 1.3 Development Environment Setup

#### Local Development (Gaming PC)

```bash
# Create Python virtual environment
python3 -m venv ~/barnabeenet-dev
source ~/barnabeenet-dev/bin/activate

# Install core dependencies
pip install --upgrade pip setuptools wheel

# BarnabeeNet core requirements
pip install \
    homeassistant \
    faster-whisper \
    speechbrain \
    redis \
    aioredis \
    sentence-transformers \
    piper-tts \
    httpx \
    aiofiles \
    voluptuous \
    python-dotenv

# ML/AI requirements
pip install \
    torch \
    torchaudio \
    transformers \
    openai \
    anthropic \
    google-generativeai

# Testing requirements
pip install \
    pytest \
    pytest-asyncio \
    pytest-cov \
    pytest-homeassistant-custom-component \
    deepeval \
    langfuse
```

#### VS Code Configuration

Create `.vscode/settings.json` in your project:

```json
{
    "python.defaultInterpreterPath": "~/barnabeenet-dev/bin/python",
    "python.analysis.typeCheckingMode": "basic",
    "python.analysis.autoImportCompletions": true,
    "editor.formatOnSave": true,
    "python.formatting.provider": "black",
    "python.linting.enabled": true,
    "python.linting.pylintEnabled": true,
    "files.associations": {
        "*.yaml": "yaml"
    },
    "[python]": {
        "editor.rulers": [88, 120]
    }
}
```

Create `.vscode/launch.json` for debugging:

```json
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Home Assistant (Custom Component)",
            "type": "python",
            "request": "launch",
            "module": "homeassistant",
            "args": [
                "-c", "${workspaceFolder}/config",
                "--debug"
            ],
            "env": {
                "PYTHONPATH": "${workspaceFolder}"
            },
            "justMyCode": false
        },
        {
            "name": "Pytest - Current File",
            "type": "python",
            "request": "launch",
            "module": "pytest",
            "args": ["${file}", "-v", "-s"],
            "console": "integratedTerminal"
        }
    ]
}
```

### 1.4 Directory Structure

```
barnabeenet/
├── custom_components/
│   └── barnabeenet/
│       ├── __init__.py              # Integration setup
│       ├── manifest.json            # HA component metadata
│       ├── config_flow.py           # UI configuration
│       ├── const.py                 # Constants
│       ├── coordinator.py           # Data update coordinator
│       │
│       ├── agents/                  # Multi-agent system
│       │   ├── __init__.py
│       │   ├── base.py              # Base agent class
│       │   ├── meta_agent.py        # Router/classifier
│       │   ├── instant_agent.py     # Pattern-matched responses
│       │   ├── action_agent.py      # Device control
│       │   ├── interaction_agent.py # Complex conversations
│       │   ├── memory_agent.py      # Memory operations
│       │   ├── proactive_agent.py   # Background monitoring
│       │   └── evolver_agent.py     # Self-improvement
│       │
│       ├── voice/                   # Voice processing
│       │   ├── __init__.py
│       │   ├── stt.py               # Speech-to-text wrapper
│       │   ├── tts.py               # Text-to-speech wrapper
│       │   ├── speaker_id.py        # Speaker recognition
│       │   └── wake_word.py         # Wake word detection
│       │
│       ├── memory/                  # Memory system
│       │   ├── __init__.py
│       │   ├── working.py           # Redis short-term
│       │   ├── episodic.py          # SQLite conversations
│       │   ├── semantic.py          # Extracted facts
│       │   └── consolidation.py     # Batch processing
│       │
│       ├── llm/                     # LLM integration
│       │   ├── __init__.py
│       │   ├── router.py            # OpenRouter integration
│       │   ├── local.py             # Local model inference
│       │   └── prompts/             # Prompt templates
│       │       ├── meta_agent.txt
│       │       ├── action_agent.txt
│       │       └── interaction_agent.txt
│       │
│       ├── services/                # HA service definitions
│       │   ├── __init__.py
│       │   └── services.yaml
│       │
│       └── frontend/                # Dashboard panel
│           ├── panel.js
│           └── styles.css
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py                  # pytest fixtures
│   ├── test_meta_agent.py
│   ├── test_stt.py
│   ├── test_speaker_id.py
│   └── test_memory.py
│
├── config/                          # Test HA config
│   ├── configuration.yaml
│   └── secrets.yaml
│
├── scripts/
│   ├── install_models.sh
│   ├── enroll_speaker.py
│   └── benchmark_latency.py
│
├── pyproject.toml
├── requirements.txt
└── README.md
```

---

## 2. Phase 1: Infrastructure Foundation

### 2.1 Home Assistant Custom Integration Skeleton

#### manifest.json

```json
{
    "domain": "barnabeenet",
    "name": "BarnabeeNet Voice Assistant",
    "version": "3.0.0",
    "documentation": "https://github.com/thomfife/barnabeenet",
    "issue_tracker": "https://github.com/thomfife/barnabeenet/issues",
    "dependencies": ["conversation", "intent"],
    "codeowners": ["@thomfife"],
    "requirements": [
        "faster-whisper>=1.0.0",
        "speechbrain>=1.0.0",
        "redis>=5.0.0",
        "aioredis>=2.0.0",
        "sentence-transformers>=2.2.0",
        "piper-tts>=1.2.0",
        "httpx>=0.24.0"
    ],
    "iot_class": "local_push",
    "config_flow": true
}
```

#### const.py

```python
"""Constants for BarnabeeNet integration."""
from typing import Final

DOMAIN: Final = "barnabeenet"

# Configuration keys
CONF_REDIS_HOST: Final = "redis_host"
CONF_REDIS_PORT: Final = "redis_port"
CONF_STT_MODEL: Final = "stt_model"
CONF_TTS_VOICE: Final = "tts_voice"
CONF_OPENROUTER_API_KEY: Final = "openrouter_api_key"
CONF_GAMING_PC_HOST: Final = "gaming_pc_host"

# Default values
DEFAULT_REDIS_HOST: Final = "localhost"
DEFAULT_REDIS_PORT: Final = 6379
DEFAULT_STT_MODEL: Final = "distil-whisper/distil-small.en"
DEFAULT_TTS_VOICE: Final = "en_US-lessac-medium"

# Latency targets (milliseconds)
LATENCY_INSTANT: Final = 5
LATENCY_ACTION: Final = 100
LATENCY_QUERY: Final = 500
LATENCY_CONVERSATION: Final = 3000

# Memory TTLs (seconds)
WORKING_MEMORY_TTL: Final = 600  # 10 minutes
SESSION_TTL: Final = 1800  # 30 minutes

# Classification categories
CLASS_INSTANT: Final = "instant"
CLASS_ACTION: Final = "action"
CLASS_QUERY: Final = "query"
CLASS_CONVERSATION: Final = "conversation"
CLASS_MEMORY: Final = "memory"
CLASS_EMERGENCY: Final = "emergency"
CLASS_PROACTIVE: Final = "proactive"
CLASS_EVOLVE: Final = "evolve"
CLASS_GESTURE: Final = "gesture"

# Agent identifiers
AGENT_META: Final = "meta"
AGENT_INSTANT: Final = "instant"
AGENT_ACTION: Final = "action"
AGENT_INTERACTION: Final = "interaction"
AGENT_MEMORY: Final = "memory"
AGENT_PROACTIVE: Final = "proactive"
AGENT_EVOLVER: Final = "evolver"
```

#### __init__.py (Integration Setup)

```python
"""BarnabeeNet - Privacy-First Multi-Agent Voice Assistant."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    DOMAIN,
    CONF_REDIS_HOST,
    CONF_REDIS_PORT,
    DEFAULT_REDIS_HOST,
    DEFAULT_REDIS_PORT,
)
from .coordinator import BarnabeeNetCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_REDIS_HOST, default=DEFAULT_REDIS_HOST): cv.string,
                vol.Optional(CONF_REDIS_PORT, default=DEFAULT_REDIS_PORT): cv.port,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up BarnabeeNet from YAML configuration."""
    if DOMAIN not in config:
        return True

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["yaml_config"] = config[DOMAIN]

    _LOGGER.info("BarnabeeNet YAML configuration loaded")
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up BarnabeeNet from a config entry."""
    _LOGGER.info("Setting up BarnabeeNet integration")

    coordinator = BarnabeeNetCoordinator(hass, entry)

    try:
        await coordinator.async_initialize()
    except Exception as err:
        _LOGGER.error("Failed to initialize BarnabeeNet: %s", err)
        return False

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Forward setup to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register services
    await _async_register_services(hass, coordinator)

    _LOGGER.info("BarnabeeNet integration setup complete")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    coordinator: BarnabeeNetCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Shutdown coordinator
    await coordinator.async_shutdown()

    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def _async_register_services(
    hass: HomeAssistant, coordinator: BarnabeeNetCoordinator
) -> None:
    """Register BarnabeeNet services."""

    async def process_voice(call) -> dict[str, Any]:
        """Process a voice command through BarnabeeNet."""
        audio_data = call.data.get("audio_data")
        speaker_hint = call.data.get("speaker_hint")

        result = await coordinator.process_voice_command(
            audio_data=audio_data,
            speaker_hint=speaker_hint,
        )
        return result

    async def enroll_speaker(call) -> dict[str, Any]:
        """Enroll a new speaker for recognition."""
        name = call.data.get("name")
        audio_samples = call.data.get("audio_samples")

        result = await coordinator.enroll_speaker(
            name=name,
            audio_samples=audio_samples,
        )
        return result

    async def query_memory(call) -> dict[str, Any]:
        """Search BarnabeeNet's memory."""
        query = call.data.get("query")
        speaker_id = call.data.get("speaker_id")

        result = await coordinator.query_memory(
            query=query,
            speaker_id=speaker_id,
        )
        return result

    hass.services.async_register(DOMAIN, "process_voice", process_voice)
    hass.services.async_register(DOMAIN, "enroll_speaker", enroll_speaker)
    hass.services.async_register(DOMAIN, "query_memory", query_memory)

    _LOGGER.info("BarnabeeNet services registered")
```

#### coordinator.py

```python
"""Data coordinator for BarnabeeNet."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

import aioredis
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    DOMAIN,
    CONF_REDIS_HOST,
    CONF_REDIS_PORT,
    DEFAULT_REDIS_HOST,
    DEFAULT_REDIS_PORT,
    WORKING_MEMORY_TTL,
)
from .agents.meta_agent import MetaAgent
from .agents.instant_agent import InstantAgent
from .agents.action_agent import ActionAgent
from .agents.interaction_agent import InteractionAgent
from .voice.stt import SpeechToText
from .voice.tts import TextToSpeech
from .voice.speaker_id import SpeakerIdentification
from .memory.working import WorkingMemory
from .memory.episodic import EpisodicMemory

_LOGGER = logging.getLogger(__name__)


class BarnabeeNetCoordinator(DataUpdateCoordinator):
    """Coordinate BarnabeeNet operations."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=None,  # Event-driven, not polling
        )
        self.entry = entry
        self.config = entry.data

        # Components (initialized in async_initialize)
        self.redis: aioredis.Redis | None = None
        self.stt: SpeechToText | None = None
        self.tts: TextToSpeech | None = None
        self.speaker_id: SpeakerIdentification | None = None
        self.working_memory: WorkingMemory | None = None
        self.episodic_memory: EpisodicMemory | None = None

        # Agents
        self.meta_agent: MetaAgent | None = None
        self.instant_agent: InstantAgent | None = None
        self.action_agent: ActionAgent | None = None
        self.interaction_agent: InteractionAgent | None = None

        # Metrics
        self.metrics = {
            "total_requests": 0,
            "latency_sum_ms": 0,
            "cloud_calls": 0,
            "local_calls": 0,
            "errors": 0,
        }

    async def async_initialize(self) -> None:
        """Initialize all BarnabeeNet components."""
        _LOGGER.info("Initializing BarnabeeNet components...")

        # Initialize Redis connection
        redis_host = self.config.get(CONF_REDIS_HOST, DEFAULT_REDIS_HOST)
        redis_port = self.config.get(CONF_REDIS_PORT, DEFAULT_REDIS_PORT)

        self.redis = await aioredis.from_url(
            f"redis://{redis_host}:{redis_port}",
            encoding="utf-8",
            decode_responses=True,
        )

        # Verify Redis connection
        await self.redis.ping()
        _LOGGER.info("Redis connection established")

        # Initialize memory systems
        self.working_memory = WorkingMemory(
            redis=self.redis,
            ttl=WORKING_MEMORY_TTL,
        )
        self.episodic_memory = EpisodicMemory(
            hass=self.hass,
            db_path=self.hass.config.path("barnabeenet.db"),
        )
        await self.episodic_memory.async_initialize()

        # Initialize voice components
        self.stt = SpeechToText(
            model_name=self.config.get("stt_model", "distil-whisper/distil-small.en"),
            device="cpu",
            compute_type="int8",
        )
        await self.stt.async_initialize()

        self.tts = TextToSpeech(
            voice=self.config.get("tts_voice", "en_US-lessac-medium"),
        )
        await self.tts.async_initialize()

        self.speaker_id = SpeakerIdentification()
        await self.speaker_id.async_initialize()

        # Initialize agents
        self.meta_agent = MetaAgent(coordinator=self)
        self.instant_agent = InstantAgent(coordinator=self)
        self.action_agent = ActionAgent(coordinator=self, hass=self.hass)
        self.interaction_agent = InteractionAgent(
            coordinator=self,
            openrouter_key=self.config.get("openrouter_api_key"),
        )

        _LOGGER.info("BarnabeeNet initialization complete")

    async def async_shutdown(self) -> None:
        """Shutdown all BarnabeeNet components."""
        _LOGGER.info("Shutting down BarnabeeNet...")

        if self.redis:
            await self.redis.close()

        if self.episodic_memory:
            await self.episodic_memory.async_close()

        _LOGGER.info("BarnabeeNet shutdown complete")

    async def process_voice_command(
        self,
        audio_data: bytes,
        speaker_hint: str | None = None,
    ) -> dict[str, Any]:
        """Process a voice command through the full pipeline."""
        start_time = datetime.now()
        session_id = f"session_{start_time.timestamp()}"

        try:
            # Step 1: Speech-to-Text
            transcription = await self.stt.transcribe(audio_data)
            _LOGGER.debug("Transcription: %s", transcription)

            # Step 2: Speaker Identification
            speaker_id, confidence = await self.speaker_id.identify(
                audio_data,
                hint=speaker_hint,
            )
            _LOGGER.debug("Speaker: %s (confidence: %.2f)", speaker_id, confidence)

            # Step 3: Load working memory context
            context = await self.working_memory.get_context(
                session_id=session_id,
                speaker_id=speaker_id,
            )

            # Step 4: Meta Agent routing
            classification = await self.meta_agent.classify(
                text=transcription,
                speaker_id=speaker_id,
                context=context,
            )
            _LOGGER.debug("Classification: %s", classification)

            # Step 5: Route to appropriate agent
            response = await self._route_to_agent(
                classification=classification,
                text=transcription,
                speaker_id=speaker_id,
                context=context,
            )

            # Step 6: Update working memory
            await self.working_memory.add_exchange(
                session_id=session_id,
                speaker_id=speaker_id,
                user_input=transcription,
                assistant_response=response["text"],
            )

            # Step 7: Generate TTS audio
            audio_response = await self.tts.synthesize(response["text"])

            # Calculate metrics
            end_time = datetime.now()
            latency_ms = (end_time - start_time).total_seconds() * 1000
            self.metrics["total_requests"] += 1
            self.metrics["latency_sum_ms"] += latency_ms

            return {
                "success": True,
                "transcription": transcription,
                "speaker_id": speaker_id,
                "speaker_confidence": confidence,
                "classification": classification,
                "response_text": response["text"],
                "response_audio": audio_response,
                "latency_ms": latency_ms,
                "agent_used": classification["agent"],
            }

        except Exception as err:
            self.metrics["errors"] += 1
            _LOGGER.error("Error processing voice command: %s", err)
            return {
                "success": False,
                "error": str(err),
            }

    async def _route_to_agent(
        self,
        classification: dict[str, Any],
        text: str,
        speaker_id: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Route request to the appropriate agent."""
        agent_type = classification["agent"]

        if agent_type == "instant":
            return await self.instant_agent.handle(text)
        elif agent_type == "action":
            return await self.action_agent.handle(
                text=text,
                speaker_id=speaker_id,
            )
        elif agent_type in ("query", "conversation"):
            return await self.interaction_agent.handle(
                text=text,
                speaker_id=speaker_id,
                context=context,
                classification=classification,
            )
        else:
            # Default fallback
            return await self.interaction_agent.handle(
                text=text,
                speaker_id=speaker_id,
                context=context,
                classification=classification,
            )

    async def enroll_speaker(
        self,
        name: str,
        audio_samples: list[bytes],
    ) -> dict[str, Any]:
        """Enroll a new speaker for recognition."""
        return await self.speaker_id.enroll(
            name=name,
            audio_samples=audio_samples,
        )

    async def query_memory(
        self,
        query: str,
        speaker_id: str | None = None,
    ) -> dict[str, Any]:
        """Search episodic memory."""
        return await self.episodic_memory.search(
            query=query,
            speaker_id=speaker_id,
        )

    def get_metrics(self) -> dict[str, Any]:
        """Get current performance metrics."""
        avg_latency = 0
        if self.metrics["total_requests"] > 0:
            avg_latency = (
                self.metrics["latency_sum_ms"] / self.metrics["total_requests"]
            )

        return {
            **self.metrics,
            "average_latency_ms": avg_latency,
        }
```

### 2.2 Speech-to-Text Implementation

#### voice/stt.py

```python
"""Speech-to-Text using Faster-Whisper."""
from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import numpy as np

_LOGGER = logging.getLogger(__name__)

# Thread pool for CPU-bound transcription
_executor = ThreadPoolExecutor(max_workers=2)


class SpeechToText:
    """Faster-Whisper STT wrapper optimized for low latency."""

    def __init__(
        self,
        model_name: str = "distil-whisper/distil-small.en",
        device: str = "cpu",
        compute_type: str = "int8",
        beam_size: int = 1,
    ) -> None:
        """Initialize STT with specified model."""
        self.model_name = model_name
        self.device = device
        self.compute_type = compute_type
        self.beam_size = beam_size
        self.model = None

    async def async_initialize(self) -> None:
        """Load the Whisper model asynchronously."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(_executor, self._load_model)
        _LOGGER.info(
            "Faster-Whisper model loaded: %s (device=%s, compute=%s)",
            self.model_name,
            self.device,
            self.compute_type,
        )

    def _load_model(self) -> None:
        """Load the model (runs in thread pool)."""
        from faster_whisper import WhisperModel

        self.model = WhisperModel(
            self.model_name,
            device=self.device,
            compute_type=self.compute_type,
        )

    async def transcribe(
        self,
        audio_data: bytes,
        language: str = "en",
    ) -> str:
        """Transcribe audio to text."""
        if self.model is None:
            raise RuntimeError("STT model not initialized")

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            _executor,
            self._transcribe_sync,
            audio_data,
            language,
        )
        return result

    def _transcribe_sync(
        self,
        audio_data: bytes,
        language: str,
    ) -> str:
        """Synchronous transcription (runs in thread pool)."""
        import io
        import soundfile as sf

        # Convert bytes to numpy array
        audio_io = io.BytesIO(audio_data)
        audio_np, sample_rate = sf.read(audio_io)

        # Ensure mono audio
        if len(audio_np.shape) > 1:
            audio_np = audio_np.mean(axis=1)

        # Resample to 16kHz if needed
        if sample_rate != 16000:
            import librosa
            audio_np = librosa.resample(
                audio_np,
                orig_sr=sample_rate,
                target_sr=16000,
            )

        # Convert to float32
        audio_np = audio_np.astype(np.float32)

        # Transcribe with optimized settings
        segments, info = self.model.transcribe(
            audio_np,
            language=language,
            beam_size=self.beam_size,
            vad_filter=True,
            vad_parameters=dict(
                min_silence_duration_ms=500,
                speech_pad_ms=200,
            ),
        )

        # Concatenate all segments
        text = " ".join(segment.text for segment in segments)
        return text.strip()

    async def transcribe_streaming(
        self,
        audio_stream,
        language: str = "en",
    ):
        """Stream transcription for real-time processing."""
        # Implementation for streaming STT
        # Uses chunked processing with VAD
        buffer = []
        async for chunk in audio_stream:
            buffer.append(chunk)

            # Process when we have enough audio (~1 second)
            if len(buffer) >= 16000:  # 1 second at 16kHz
                audio_data = np.concatenate(buffer)
                text = await self.transcribe(audio_data.tobytes(), language)
                if text:
                    yield text
                buffer = buffer[-4000:]  # Keep 250ms overlap


class StreamingSTT:
    """Real-time streaming STT with local agreement policy.

    Based on WhisperStreaming/SimulStreaming architecture for
    ultra-low latency transcription.
    """

    def __init__(
        self,
        model_name: str = "distil-whisper/distil-small.en",
        chunk_size_ms: int = 500,
        min_chunk_size_ms: int = 200,
    ) -> None:
        self.model_name = model_name
        self.chunk_size_ms = chunk_size_ms
        self.min_chunk_size_ms = min_chunk_size_ms
        self.buffer = []
        self.confirmed_text = ""

    async def process_chunk(self, audio_chunk: np.ndarray) -> dict[str, Any]:
        """Process an audio chunk and return partial/final transcription."""
        self.buffer.append(audio_chunk)
        total_audio = np.concatenate(self.buffer)

        # Only process if we have minimum audio
        total_duration_ms = (len(total_audio) / 16000) * 1000
        if total_duration_ms < self.min_chunk_size_ms:
            return {"type": "partial", "text": ""}

        # Transcribe current buffer
        # Use local agreement policy: only confirm text that appears
        # consistently across multiple transcriptions
        current_text = await self._transcribe(total_audio)

        # Find confirmed portion using local agreement
        confirmed, partial = self._local_agreement(current_text)

        if confirmed:
            self.confirmed_text += " " + confirmed
            # Trim buffer to keep only unconfirmed audio
            self._trim_buffer()

        return {
            "type": "final" if confirmed else "partial",
            "confirmed": self.confirmed_text.strip(),
            "partial": partial,
        }

    def _local_agreement(self, current_text: str) -> tuple[str, str]:
        """Apply local agreement policy for streaming."""
        # This is a simplified version - real implementation
        # would track multiple transcriptions and find consensus
        words = current_text.split()
        if len(words) >= 3:
            # Confirm all but last 2 words
            confirmed = " ".join(words[:-2])
            partial = " ".join(words[-2:])
            return confirmed, partial
        return "", current_text

    def _trim_buffer(self) -> None:
        """Trim buffer to remove confirmed audio."""
        # Keep ~500ms of audio for context overlap
        keep_samples = int(0.5 * 16000)
        total_samples = sum(len(chunk) for chunk in self.buffer)
        if total_samples > keep_samples:
            # Flatten, trim, and re-buffer
            all_audio = np.concatenate(self.buffer)
            self.buffer = [all_audio[-keep_samples:]]

    async def _transcribe(self, audio: np.ndarray) -> str:
        """Internal transcription method."""
        # Placeholder - would use faster-whisper
        pass

    def reset(self) -> None:
        """Reset the streaming state."""
        self.buffer = []
        self.confirmed_text = ""
```

### 2.3 Text-to-Speech Implementation

#### voice/tts.py

```python
"""Text-to-Speech using Piper."""
from __future__ import annotations

import asyncio
import logging
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

_LOGGER = logging.getLogger(__name__)
_executor = ThreadPoolExecutor(max_workers=2)


class TextToSpeech:
    """Piper TTS wrapper for fast local synthesis."""

    def __init__(
        self,
        voice: str = "en_US-lessac-medium",
        voices_dir: str | None = None,
        sample_rate: int = 22050,
    ) -> None:
        """Initialize TTS with specified voice."""
        self.voice = voice
        self.voices_dir = voices_dir or Path.home() / ".local/share/piper/voices"
        self.sample_rate = sample_rate
        self.piper_path: str | None = None

    async def async_initialize(self) -> None:
        """Verify Piper installation and voice availability."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(_executor, self._verify_setup)
        _LOGGER.info("Piper TTS initialized with voice: %s", self.voice)

    def _verify_setup(self) -> None:
        """Verify Piper is available."""
        # Check for piper binary
        result = subprocess.run(
            ["which", "piper"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            # Try pip-installed piper
            result = subprocess.run(
                ["python", "-m", "piper", "--help"],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                raise RuntimeError("Piper TTS not found")
            self.piper_path = "python -m piper"
        else:
            self.piper_path = result.stdout.strip()

        # Verify voice model exists
        voice_path = Path(self.voices_dir) / f"{self.voice}.onnx"
        if not voice_path.exists():
            _LOGGER.warning(
                "Voice model not found at %s, will download on first use",
                voice_path,
            )

    async def synthesize(
        self,
        text: str,
        output_format: str = "wav",
    ) -> bytes:
        """Synthesize text to audio."""
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            _executor,
            self._synthesize_sync,
            text,
            output_format,
        )
        return result

    def _synthesize_sync(
        self,
        text: str,
        output_format: str,
    ) -> bytes:
        """Synchronous TTS synthesis."""
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=f".{output_format}") as tmp:
            # Build piper command
            cmd = [
                "piper",
                "--model", str(Path(self.voices_dir) / f"{self.voice}.onnx"),
                "--output_file", tmp.name,
            ]

            # Run piper with text input
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            stdout, stderr = process.communicate(input=text.encode())

            if process.returncode != 0:
                _LOGGER.error("Piper TTS error: %s", stderr.decode())
                raise RuntimeError(f"TTS synthesis failed: {stderr.decode()}")

            # Read generated audio
            with open(tmp.name, "rb") as f:
                return f.read()

    async def synthesize_streaming(
        self,
        text: str,
    ):
        """Stream TTS audio for lower perceived latency."""
        # Split text into sentences for streaming
        sentences = self._split_sentences(text)

        for sentence in sentences:
            audio = await self.synthesize(sentence)
            yield audio

    def _split_sentences(self, text: str) -> list[str]:
        """Split text into sentences for streaming."""
        import re

        # Simple sentence splitting
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [s for s in sentences if s.strip()]


class AdaptiveTTS:
    """TTS with adaptive prosody based on context."""

    def __init__(self, base_tts: TextToSpeech) -> None:
        self.tts = base_tts
        self.prosody_settings = {
            "calm": {"rate": 0.9, "pitch": -2},
            "urgent": {"rate": 1.2, "pitch": 2},
            "friendly": {"rate": 1.0, "pitch": 0},
            "informative": {"rate": 1.1, "pitch": 0},
        }

    async def synthesize_adaptive(
        self,
        text: str,
        mood: str = "friendly",
        speaker_state: dict[str, Any] | None = None,
    ) -> bytes:
        """Synthesize with adaptive prosody based on context."""
        # Adjust prosody based on detected user state
        if speaker_state and speaker_state.get("stressed"):
            mood = "calm"

        settings = self.prosody_settings.get(mood, self.prosody_settings["friendly"])

        # Apply prosody via SSML or voice settings
        # Piper doesn't natively support SSML, so we use voice selection
        # For full prosody control, consider using a voice with variations

        return await self.tts.synthesize(text)
```

### 2.4 Meta Agent Implementation

#### agents/base.py

```python
"""Base agent class for BarnabeeNet."""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..coordinator import BarnabeeNetCoordinator

_LOGGER = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Base class for all BarnabeeNet agents."""

    def __init__(
        self,
        coordinator: BarnabeeNetCoordinator,
        name: str,
    ) -> None:
        """Initialize the agent."""
        self.coordinator = coordinator
        self.name = name
        self.metrics = {
            "calls": 0,
            "errors": 0,
            "total_latency_ms": 0,
        }

    @abstractmethod
    async def handle(self, **kwargs) -> dict[str, Any]:
        """Handle a request."""
        pass

    async def _track_metrics(self, start_time: datetime) -> None:
        """Track agent metrics."""
        end_time = datetime.now()
        latency_ms = (end_time - start_time).total_seconds() * 1000
        self.metrics["calls"] += 1
        self.metrics["total_latency_ms"] += latency_ms

    def get_average_latency(self) -> float:
        """Get average latency in milliseconds."""
        if self.metrics["calls"] == 0:
            return 0
        return self.metrics["total_latency_ms"] / self.metrics["calls"]
```

#### agents/meta_agent.py

```python
"""Meta Agent - Request Router and Classifier."""
from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import TYPE_CHECKING, Any

from .base import BaseAgent
from ..const import (
    CLASS_INSTANT,
    CLASS_ACTION,
    CLASS_QUERY,
    CLASS_CONVERSATION,
    CLASS_EMERGENCY,
    CLASS_GESTURE,
    AGENT_INSTANT,
    AGENT_ACTION,
    AGENT_INTERACTION,
)

if TYPE_CHECKING:
    from ..coordinator import BarnabeeNetCoordinator

_LOGGER = logging.getLogger(__name__)


class MetaAgent(BaseAgent):
    """Router that classifies requests and routes to specialized agents.

    Implements a two-phase routing strategy:
    1. Fast rule-based pattern matching (< 5ms)
    2. LLM fallback for ambiguous cases (< 100ms)
    """

    # Pattern definitions for fast routing
    INSTANT_PATTERNS = {
        "time": [
            r"what('s| is) the time",
            r"what time is it",
            r"current time",
            r"^time$",
        ],
        "date": [
            r"what('s| is) the date",
            r"what day is it",
            r"today's date",
            r"^date$",
        ],
        "greeting": [
            r"^(hello|hey|hi|good morning|good afternoon|good evening)",
            r"^hey barnabee",
        ],
        "status": [
            r"how are you",
            r"you okay",
            r"are you there",
        ],
    }

    ACTION_PATTERNS = {
        "light_control": [
            r"turn (on|off) (the )?(\w+ )?lights?",
            r"(dim|brighten) (the )?(\w+ )?lights?",
            r"set (the )?(\w+ )?lights? to (\d+)",
        ],
        "climate_control": [
            r"set (the )?(temperature|thermostat) to (\d+)",
            r"turn (on|off) (the )?(ac|air conditioning|heat|heating)",
            r"make it (warmer|cooler|hotter|colder)",
        ],
        "device_control": [
            r"turn (on|off) (the )?(\w+)",
            r"(open|close) (the )?(\w+)",
            r"(lock|unlock) (the )?(\w+)",
        ],
        "scene_control": [
            r"activate (the )?(\w+) (scene|mode)",
            r"(start|begin) (\w+) mode",
            r"set (the )?mood to (\w+)",
        ],
    }

    QUERY_PATTERNS = {
        "weather": [
            r"what('s| is) the weather",
            r"is it (going to )?(rain|snow|cold|hot)",
            r"weather (forecast|today|tomorrow)",
        ],
        "information": [
            r"what('s| is) (the|my) (\w+)",
            r"tell me about",
            r"how (do|does|can)",
            r"why (is|are|do|does)",
        ],
    }

    EMERGENCY_PATTERNS = [
        r"(call|dial) 911",
        r"emergency",
        r"help.*fire",
        r"intruder",
        r"break.?in",
    ]

    GESTURE_PATTERNS = {
        "crown_twist_yes": "confirm_yes",
        "crown_twist_no": "confirm_no",
        "button_click": "confirm",
        "motion_shake": "dismiss",
        "double_tap": "quick_action",
    }

    def __init__(self, coordinator: BarnabeeNetCoordinator) -> None:
        """Initialize Meta Agent."""
        super().__init__(coordinator, "meta_agent")

        # Compile regex patterns for performance
        self._compiled_instant = self._compile_patterns(self.INSTANT_PATTERNS)
        self._compiled_action = self._compile_patterns(self.ACTION_PATTERNS)
        self._compiled_query = self._compile_patterns(self.QUERY_PATTERNS)
        self._compiled_emergency = [
            re.compile(p, re.IGNORECASE) for p in self.EMERGENCY_PATTERNS
        ]

    def _compile_patterns(
        self, patterns: dict[str, list[str]]
    ) -> dict[str, list[re.Pattern]]:
        """Compile regex patterns for fast matching."""
        compiled = {}
        for category, pattern_list in patterns.items():
            compiled[category] = [
                re.compile(p, re.IGNORECASE) for p in pattern_list
            ]
        return compiled

    async def classify(
        self,
        text: str,
        speaker_id: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Classify a request and determine routing.

        Returns:
            dict with:
                - classification: str (instant, action, query, etc.)
                - agent: str (which agent to route to)
                - confidence: float (0.0 to 1.0)
                - metadata: dict (extracted entities, etc.)
        """
        start_time = datetime.now()
        text_lower = text.lower().strip()

        # Phase 1: Rule-based classification
        result = self._rule_based_classify(text_lower)

        if result["confidence"] >= 0.7:
            await self._track_metrics(start_time)
            return result

        # Phase 2: LLM fallback for ambiguous cases
        result = await self._llm_classify(text, speaker_id, context)
        await self._track_metrics(start_time)

        return result

    def _rule_based_classify(self, text: str) -> dict[str, Any]:
        """Fast rule-based classification."""
        # Check emergency first (highest priority)
        for pattern in self._compiled_emergency:
            if pattern.search(text):
                return {
                    "classification": CLASS_EMERGENCY,
                    "agent": AGENT_ACTION,  # Emergency routes to action for 911
                    "confidence": 0.95,
                    "metadata": {"emergency_type": "detected"},
                }

        # Check instant response patterns
        for category, patterns in self._compiled_instant.items():
            for pattern in patterns:
                if pattern.search(text):
                    return {
                        "classification": CLASS_INSTANT,
                        "agent": AGENT_INSTANT,
                        "confidence": 0.9,
                        "metadata": {"category": category},
                    }

        # Check action patterns
        for category, patterns in self._compiled_action.items():
            for pattern in patterns:
                match = pattern.search(text)
                if match:
                    return {
                        "classification": CLASS_ACTION,
                        "agent": AGENT_ACTION,
                        "confidence": 0.85,
                        "metadata": {
                            "category": category,
                            "match_groups": match.groups(),
                        },
                    }

        # Check query patterns
        for category, patterns in self._compiled_query.items():
            for pattern in patterns:
                if pattern.search(text):
                    return {
                        "classification": CLASS_QUERY,
                        "agent": AGENT_INTERACTION,
                        "confidence": 0.75,
                        "metadata": {"category": category},
                    }

        # Default: needs LLM classification
        return {
            "classification": CLASS_CONVERSATION,
            "agent": AGENT_INTERACTION,
            "confidence": 0.5,
            "metadata": {"needs_llm": True},
        }

    async def _llm_classify(
        self,
        text: str,
        speaker_id: str | None,
        context: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """LLM-based classification for ambiguous requests."""
        # Build classification prompt
        prompt = self._build_classification_prompt(text, speaker_id, context)

        try:
            # Use fast/cheap model for classification
            # Via OpenRouter or local Phi-3.5
            response = await self._call_classifier_llm(prompt)

            # Parse structured response
            return self._parse_classification_response(response)

        except Exception as err:
            _LOGGER.warning("LLM classification failed: %s", err)
            # Fallback to conversation agent
            return {
                "classification": CLASS_CONVERSATION,
                "agent": AGENT_INTERACTION,
                "confidence": 0.4,
                "metadata": {"fallback": True, "error": str(err)},
            }

    def _build_classification_prompt(
        self,
        text: str,
        speaker_id: str | None,
        context: dict[str, Any] | None,
    ) -> str:
        """Build the classification prompt."""
        return f"""Classify the following voice command into one of these categories:
- instant: Simple queries with fixed responses (time, date, greetings)
- action: Device control, automation, home commands
- query: Information requests (weather, calendar, facts)
- conversation: Complex questions, multi-turn dialogue
- memory: Requests requiring personal history retrieval
- emergency: Safety-critical situations

Speaker: {speaker_id or 'unknown'}
Context: {context.get('last_topic', 'none') if context else 'none'}

Command: "{text}"

Respond with JSON:
{{"classification": "<category>", "confidence": <0.0-1.0>, "entities": {{}}}}"""

    async def _call_classifier_llm(self, prompt: str) -> str:
        """Call the classification LLM."""
        # This would integrate with OpenRouter or local model
        # Placeholder - implement with actual LLM call
        return '{"classification": "conversation", "confidence": 0.6, "entities": {}}'

    def _parse_classification_response(self, response: str) -> dict[str, Any]:
        """Parse the LLM classification response."""
        import json

        try:
            data = json.loads(response)
            classification = data.get("classification", CLASS_CONVERSATION)

            # Map classification to agent
            agent_map = {
                CLASS_INSTANT: AGENT_INSTANT,
                CLASS_ACTION: AGENT_ACTION,
                CLASS_QUERY: AGENT_INTERACTION,
                CLASS_CONVERSATION: AGENT_INTERACTION,
            }

            return {
                "classification": classification,
                "agent": agent_map.get(classification, AGENT_INTERACTION),
                "confidence": data.get("confidence", 0.5),
                "metadata": data.get("entities", {}),
            }

        except json.JSONDecodeError:
            return {
                "classification": CLASS_CONVERSATION,
                "agent": AGENT_INTERACTION,
                "confidence": 0.4,
                "metadata": {"parse_error": True},
            }

    def classify_gesture(self, gesture_type: str) -> dict[str, Any]:
        """Classify a gesture input from wearable."""
        action = self.GESTURE_PATTERNS.get(gesture_type)

        if action:
            return {
                "classification": CLASS_GESTURE,
                "agent": AGENT_ACTION,
                "confidence": 1.0,
                "metadata": {
                    "gesture": gesture_type,
                    "action": action,
                },
            }

        return {
            "classification": CLASS_GESTURE,
            "agent": AGENT_ACTION,
            "confidence": 0.5,
            "metadata": {
                "gesture": gesture_type,
                "action": "unknown",
            },
        }

    async def handle(self, **kwargs) -> dict[str, Any]:
        """Handle classification request."""
        text = kwargs.get("text", "")
        speaker_id = kwargs.get("speaker_id")
        context = kwargs.get("context")

        return await self.classify(text, speaker_id, context)
```

### 2.5 Instant Response Agent

#### agents/instant_agent.py

```python
"""Instant Response Agent - Zero-latency pattern-matched responses."""
from __future__ import annotations

import logging
import random
from datetime import datetime
from typing import TYPE_CHECKING, Any

from .base import BaseAgent

if TYPE_CHECKING:
    from ..coordinator import BarnabeeNetCoordinator

_LOGGER = logging.getLogger(__name__)


class InstantAgent(BaseAgent):
    """Agent for instant, pattern-matched responses with no LLM latency."""

    # Response templates
    TIME_RESPONSES = [
        "It's {time}.",
        "The time is {time}.",
        "Right now it's {time}.",
    ]

    DATE_RESPONSES = [
        "Today is {date}.",
        "It's {date}.",
        "The date is {date}.",
    ]

    GREETING_RESPONSES = {
        "morning": [
            "Good morning{name}! How can I help you today?",
            "Morning{name}! What can I do for you?",
        ],
        "afternoon": [
            "Good afternoon{name}! How can I help?",
            "Hello{name}! What do you need?",
        ],
        "evening": [
            "Good evening{name}! What can I do for you?",
            "Evening{name}! How can I help?",
        ],
        "default": [
            "Hello{name}! How can I help you?",
            "Hey{name}! What do you need?",
        ],
    }

    STATUS_RESPONSES = [
        "I'm doing great, thanks for asking!",
        "All systems are running smoothly.",
        "I'm here and ready to help!",
        "Doing well! How about you?",
    ]

    MATH_OPERATORS = {
        "+": lambda a, b: a + b,
        "-": lambda a, b: a - b,
        "*": lambda a, b: a * b,
        "/": lambda a, b: a / b if b != 0 else "undefined",
    }

    def __init__(self, coordinator: BarnabeeNetCoordinator) -> None:
        """Initialize Instant Agent."""
        super().__init__(coordinator, "instant_agent")

    async def handle(
        self,
        text: str,
        category: str | None = None,
        speaker_id: str | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """Handle an instant response request."""
        start_time = datetime.now()
        text_lower = text.lower().strip()

        # Determine response based on category or content
        if category == "time" or self._is_time_query(text_lower):
            response = self._handle_time()
        elif category == "date" or self._is_date_query(text_lower):
            response = self._handle_date()
        elif category == "greeting" or self._is_greeting(text_lower):
            response = self._handle_greeting(speaker_id)
        elif category == "status" or self._is_status_query(text_lower):
            response = self._handle_status()
        elif math_result := self._try_math(text_lower):
            response = math_result
        else:
            # Fallback
            response = "I'm not sure how to respond to that."

        await self._track_metrics(start_time)

        return {
            "text": response,
            "agent": self.name,
            "latency_ms": (datetime.now() - start_time).total_seconds() * 1000,
        }

    def _is_time_query(self, text: str) -> bool:
        """Check if query is about time."""
        time_keywords = ["time", "what time", "clock"]
        return any(kw in text for kw in time_keywords)

    def _is_date_query(self, text: str) -> bool:
        """Check if query is about date."""
        date_keywords = ["date", "what day", "today"]
        return any(kw in text for kw in date_keywords)

    def _is_greeting(self, text: str) -> bool:
        """Check if text is a greeting."""
        greetings = ["hello", "hey", "hi", "good morning", "good afternoon", "good evening"]
        return any(text.startswith(g) for g in greetings)

    def _is_status_query(self, text: str) -> bool:
        """Check if asking about status."""
        status_keywords = ["how are you", "you okay", "are you there"]
        return any(kw in text for kw in status_keywords)

    def _handle_time(self) -> str:
        """Generate time response."""
        now = datetime.now()
        time_str = now.strftime("%I:%M %p")
        template = random.choice(self.TIME_RESPONSES)
        return template.format(time=time_str)

    def _handle_date(self) -> str:
        """Generate date response."""
        now = datetime.now()
        date_str = now.strftime("%A, %B %d, %Y")
        template = random.choice(self.DATE_RESPONSES)
        return template.format(date=date_str)

    def _handle_greeting(self, speaker_id: str | None) -> str:
        """Generate contextual greeting."""
        now = datetime.now()
        hour = now.hour

        # Determine time of day
        if 5 <= hour < 12:
            time_key = "morning"
        elif 12 <= hour < 17:
            time_key = "afternoon"
        elif 17 <= hour < 22:
            time_key = "evening"
        else:
            time_key = "default"

        template = random.choice(self.GREETING_RESPONSES[time_key])

        # Personalize if speaker known
        name_str = ""
        if speaker_id and speaker_id != "guest":
            name_str = f", {speaker_id.title()}"

        return template.format(name=name_str)

    def _handle_status(self) -> str:
        """Generate status response."""
        return random.choice(self.STATUS_RESPONSES)

    def _try_math(self, text: str) -> str | None:
        """Try to evaluate simple math expressions."""
        import re

        # Pattern: "what is X op Y"
        pattern = r"what is (\d+(?:\.\d+)?)\s*([+\-*/])\s*(\d+(?:\.\d+)?)"
        match = re.search(pattern, text)

        if match:
            a = float(match.group(1))
            op = match.group(2)
            b = float(match.group(3))

            if op in self.MATH_OPERATORS:
                result = self.MATH_OPERATORS[op](a, b)
                if isinstance(result, float):
                    # Format nicely
                    if result == int(result):
                        result = int(result)
                    else:
                        result = round(result, 2)
                return f"That's {result}."

        return None
```

### 2.6 SQLite Database Schema

#### memory/schema.sql

```sql
-- BarnabeeNet SQLite Schema
-- Version: 3.0.0

-- Enable foreign keys
PRAGMA foreign_keys = ON;

-- Conversations table (episodic memory)
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    speaker_id TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,

    -- Content
    user_input TEXT NOT NULL,
    assistant_response TEXT,

    -- Classification
    intent TEXT,
    classification TEXT,
    agent_used TEXT,
    confidence REAL,

    -- Processing metadata
    processing_time_ms INTEGER,
    cloud_used BOOLEAN DEFAULT FALSE,
    model_used TEXT,

    -- Vector embedding (384-dim float32, stored as blob)
    embedding BLOB,

    -- Flags
    important BOOLEAN DEFAULT FALSE,
    archived BOOLEAN DEFAULT FALSE,

    -- Indexes for common queries
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_conversations_session ON conversations(session_id);
CREATE INDEX IF NOT EXISTS idx_conversations_speaker ON conversations(speaker_id);
CREATE INDEX IF NOT EXISTS idx_conversations_timestamp ON conversations(timestamp);
CREATE INDEX IF NOT EXISTS idx_conversations_intent ON conversations(intent);

-- Semantic facts table (extracted knowledge)
CREATE TABLE IF NOT EXISTS semantic_facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject TEXT NOT NULL,          -- "thom", "living_room", "family"
    predicate TEXT NOT NULL,        -- "prefers", "located_in", "consists_of"
    object TEXT NOT NULL,           -- "warm lighting", "first floor", "4 adults"
    confidence REAL DEFAULT 1.0,
    source_conversation_id INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_confirmed DATETIME,
    expires_at DATETIME,            -- For time-sensitive facts

    FOREIGN KEY (source_conversation_id) REFERENCES conversations(id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_semantic_spo
    ON semantic_facts(subject, predicate, object);
CREATE INDEX IF NOT EXISTS idx_semantic_subject ON semantic_facts(subject);

-- User preferences table
CREATE TABLE IF NOT EXISTS user_preferences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    category TEXT NOT NULL,         -- "lighting", "temperature", "music", etc.
    preference_key TEXT NOT NULL,
    preference_value TEXT NOT NULL,
    context TEXT,                   -- "morning", "evening", "working", etc.
    confidence REAL DEFAULT 1.0,
    source_conversation_id INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(user_id, category, preference_key, context),
    FOREIGN KEY (source_conversation_id) REFERENCES conversations(id)
);

CREATE INDEX IF NOT EXISTS idx_preferences_user ON user_preferences(user_id);
CREATE INDEX IF NOT EXISTS idx_preferences_category ON user_preferences(user_id, category);

-- Speaker profiles table
CREATE TABLE IF NOT EXISTS speaker_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    embedding BLOB NOT NULL,        -- Speaker voice embedding
    permission_level TEXT DEFAULT 'standard',  -- 'admin', 'standard', 'child', 'guest'
    enrolled_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_seen DATETIME,
    enrollment_samples INTEGER DEFAULT 0,
    confidence_threshold REAL DEFAULT 0.75
);

CREATE INDEX IF NOT EXISTS idx_speakers_user ON speaker_profiles(user_id);

-- Event log for pattern detection
CREATE TABLE IF NOT EXISTS event_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    event_type TEXT NOT NULL,       -- "device_change", "command", "automation"
    entity_id TEXT,
    old_state TEXT,
    new_state TEXT,
    triggered_by TEXT,              -- "user", "automation", "schedule", "barnabee"
    user_id TEXT,
    context TEXT                    -- JSON blob for additional context
);

CREATE INDEX IF NOT EXISTS idx_events_type_time ON event_log(event_type, timestamp);
CREATE INDEX IF NOT EXISTS idx_events_entity ON event_log(entity_id);

-- Automation suggestions (learned patterns)
CREATE TABLE IF NOT EXISTS automation_suggestions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern_description TEXT NOT NULL,
    suggested_automation TEXT NOT NULL,  -- JSON automation config
    confidence REAL DEFAULT 0.0,
    occurrences INTEGER DEFAULT 0,
    status TEXT DEFAULT 'pending',  -- 'pending', 'accepted', 'rejected'
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    reviewed_at DATETIME
);

-- Audit log for debugging and transparency
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    session_id TEXT,
    speaker_id TEXT,
    speaker_confidence REAL,

    -- Request
    audio_hash TEXT,                -- SHA256 of audio (not audio itself)
    transcription TEXT,
    detected_intent TEXT,

    -- Routing
    meta_agent_decision TEXT,       -- JSON of classification
    agent_invoked TEXT,

    -- Processing
    processing_time_ms INTEGER,
    cloud_api_used BOOLEAN,
    cloud_api_name TEXT,
    tokens_used INTEGER,
    estimated_cost REAL,

    -- Response
    response_text TEXT,
    action_executed TEXT,           -- JSON of HA service call

    -- Privacy
    privacy_zone TEXT,
    pii_detected BOOLEAN DEFAULT FALSE,

    -- Multi-modal
    input_modality TEXT,            -- "voice", "gesture", "touch"
    gesture_type TEXT
);

CREATE INDEX IF NOT EXISTS idx_audit_session ON audit_log(session_id);
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_speaker ON audit_log(speaker_id);

-- System configuration (for Evolver Agent)
CREATE TABLE IF NOT EXISTS system_config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_by TEXT
);

-- Model benchmarks (for Evolver Agent)
CREATE TABLE IF NOT EXISTS model_benchmarks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_name TEXT NOT NULL,
    benchmark_type TEXT NOT NULL,   -- "latency", "accuracy", "cost"
    score REAL NOT NULL,
    parameters TEXT,                -- JSON of test parameters
    run_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_benchmarks_model ON model_benchmarks(model_name);

-- Triggers for updated_at
CREATE TRIGGER IF NOT EXISTS update_conversations_timestamp
    AFTER UPDATE ON conversations
BEGIN
    UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS update_preferences_timestamp
    AFTER UPDATE ON user_preferences
BEGIN
    UPDATE user_preferences SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;
```

### 2.7 Configuration System

#### config/barnabeenet.yaml (Example Configuration)

```yaml
# BarnabeeNet Configuration
# Place in Home Assistant config directory

barnabeenet:
  # Redis configuration
  redis:
    host: "192.168.1.10"
    port: 6379
    db: 0

  # Speech-to-Text configuration
  stt:
    model: "distil-whisper/distil-small.en"
    device: "cpu"
    compute_type: "int8"
    beam_size: 1
    language: "en"

  # Text-to-Speech configuration
  tts:
    engine: "piper"
    voice: "en_US-lessac-medium"
    sample_rate: 22050

  # Speaker recognition
  speaker_recognition:
    model: "speechbrain/spkrec-ecapa-voxceleb"
    confidence_threshold: 0.75
    fallback_to_guest: true

  # Agent configuration
  agents:
    meta:
      rule_based_first: true
      llm_fallback_threshold: 0.7
      fallback_model: "gemini-flash"

    action:
      confirmation_required:
        - "lock"
        - "unlock"
        - "garage"
      timeout_seconds: 30

    interaction:
      primary_model: "claude-3-haiku"
      fallback_model: "phi-3.5"
      max_tokens: 500
      temperature: 0.7

  # LLM providers (via OpenRouter)
  llm:
    openrouter:
      api_key: !secret openrouter_api_key
      default_model: "anthropic/claude-3-haiku"
      fallback_models:
        - "google/gemini-flash-1.5"
        - "microsoft/phi-3.5-mini"

    local:
      enabled: true
      host: "192.168.1.20"  # Gaming PC
      port: 8080
      models:
        - "phi-3.5"
        - "llama-3.1-8b"

  # Privacy configuration
  privacy:
    zones:
      children_rooms:
        rooms:
          - "bedroom.penelope"
          - "bedroom.xander"
          - "bedroom.zachary"
          - "bedroom.viola"
        constraints:
          audio_capture: false
          memory_retention: false
          proactive_notifications: false

      bathrooms:
        rooms:
          - "bathroom.master"
          - "bathroom.kids"
        constraints:
          audio_capture: false
          presence_only: true
          memory_retention: false

  # Cost controls
  cost_controls:
    daily_limit_usd: 1.00
    warning_threshold: 0.80
    degradation_levels:
      green:
        threshold: 0.50
        restrictions: []
      yellow:
        threshold: 0.80
        restrictions:
          - "interaction_agent:local_only"
      red:
        threshold: 1.00
        restrictions:
          - "interaction_agent:disabled"
          - "action_only:true"

  # Latency targets (milliseconds)
  latency_targets:
    instant: 5
    action: 100
    query: 500
    conversation: 3000

  # Memory settings
  memory:
    working_memory_ttl: 600  # 10 minutes
    session_ttl: 1800  # 30 minutes
    episodic_retention_days: 30
    consolidation_schedule: "0 3 * * *"  # 3 AM daily
```

---

## 3. Phase 2: Speaker Recognition & Personalization

### 3.1 ECAPA-TDNN Speaker Recognition

#### voice/speaker_id.py

```python
"""Speaker Identification using ECAPA-TDNN."""
from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import numpy as np

_LOGGER = logging.getLogger(__name__)
_executor = ThreadPoolExecutor(max_workers=2)


class SpeakerIdentification:
    """Speaker identification and verification using SpeechBrain ECAPA-TDNN.

    This model achieves 0.86% EER on VoxCeleb, making it suitable for
    household speaker identification with proper enrollment.
    """

    def __init__(
        self,
        model_source: str = "speechbrain/spkrec-ecapa-voxceleb",
        device: str = "cpu",
        confidence_threshold: float = 0.75,
    ) -> None:
        """Initialize speaker identification."""
        self.model_source = model_source
        self.device = device
        self.confidence_threshold = confidence_threshold
        self.verifier = None
        self.embeddings: dict[str, np.ndarray] = {}

    async def async_initialize(self) -> None:
        """Load the ECAPA-TDNN model."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(_executor, self._load_model)
        _LOGGER.info("ECAPA-TDNN speaker recognition model loaded")

    def _load_model(self) -> None:
        """Load the SpeechBrain model (runs in thread pool)."""
        from speechbrain.inference import SpeakerRecognition

        self.verifier = SpeakerRecognition.from_hparams(
            source=self.model_source,
            savedir="~/.cache/speechbrain/spkrec-ecapa-voxceleb",
            run_opts={"device": self.device},
        )

    async def identify(
        self,
        audio_data: bytes,
        hint: str | None = None,
    ) -> tuple[str, float]:
        """Identify the speaker from audio.

        Args:
            audio_data: Raw audio bytes
            hint: Optional speaker hint from location/device context

        Returns:
            Tuple of (speaker_id, confidence)
        """
        if not self.embeddings:
            return ("guest", 0.0)

        loop = asyncio.get_event_loop()
        speaker_id, confidence = await loop.run_in_executor(
            _executor,
            self._identify_sync,
            audio_data,
            hint,
        )

        return speaker_id, confidence

    def _identify_sync(
        self,
        audio_data: bytes,
        hint: str | None,
    ) -> tuple[str, float]:
        """Synchronous speaker identification."""
        import io
        import soundfile as sf
        import torch

        # Convert audio bytes to tensor
        audio_io = io.BytesIO(audio_data)
        audio_np, sample_rate = sf.read(audio_io)

        # Ensure mono
        if len(audio_np.shape) > 1:
            audio_np = audio_np.mean(axis=1)

        # Resample to 16kHz if needed
        if sample_rate != 16000:
            import librosa
            audio_np = librosa.resample(audio_np, orig_sr=sample_rate, target_sr=16000)

        # Get embedding for query audio
        audio_tensor = torch.tensor(audio_np).unsqueeze(0).float()
        query_embedding = self.verifier.encode_batch(audio_tensor)
        query_embedding = query_embedding.squeeze().cpu().numpy()

        # Compare against enrolled speakers
        best_match = "guest"
        best_score = 0.0

        for speaker_id, enrolled_embedding in self.embeddings.items():
            # Cosine similarity
            score = self._cosine_similarity(query_embedding, enrolled_embedding)

            # Apply hint boost if available
            if hint and hint.lower() == speaker_id.lower():
                score *= 1.1  # 10% boost for context hints

            if score > best_score:
                best_score = score
                best_match = speaker_id

        # Apply threshold
        if best_score < self.confidence_threshold:
            return ("guest", best_score)

        return (best_match, best_score)

    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Calculate cosine similarity between two embeddings."""
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

    async def enroll(
        self,
        name: str,
        audio_samples: list[bytes],
    ) -> dict[str, Any]:
        """Enroll a new speaker with multiple audio samples.

        Args:
            name: Speaker name/identifier
            audio_samples: List of audio samples (5+ recommended)

        Returns:
            Enrollment result with success status
        """
        if len(audio_samples) < 3:
            return {
                "success": False,
                "error": "Need at least 3 audio samples for enrollment",
            }

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            _executor,
            self._enroll_sync,
            name,
            audio_samples,
        )

        return result

    def _enroll_sync(
        self,
        name: str,
        audio_samples: list[bytes],
    ) -> dict[str, Any]:
        """Synchronous speaker enrollment."""
        import io
        import soundfile as sf
        import torch

        embeddings = []

        for i, audio_data in enumerate(audio_samples):
            try:
                audio_io = io.BytesIO(audio_data)
                audio_np, sample_rate = sf.read(audio_io)

                # Preprocess
                if len(audio_np.shape) > 1:
                    audio_np = audio_np.mean(axis=1)

                if sample_rate != 16000:
                    import librosa
                    audio_np = librosa.resample(
                        audio_np, orig_sr=sample_rate, target_sr=16000
                    )

                # Get embedding
                audio_tensor = torch.tensor(audio_np).unsqueeze(0).float()
                embedding = self.verifier.encode_batch(audio_tensor)
                embeddings.append(embedding.squeeze().cpu().numpy())

            except Exception as err:
                _LOGGER.warning("Failed to process sample %d: %s", i, err)

        if len(embeddings) < 3:
            return {
                "success": False,
                "error": f"Only {len(embeddings)} valid samples processed",
            }

        # Average embeddings for final enrollment
        averaged_embedding = np.mean(embeddings, axis=0)

        # Normalize
        averaged_embedding = averaged_embedding / np.linalg.norm(averaged_embedding)

        # Store
        speaker_id = name.lower().replace(" ", "_")
        self.embeddings[speaker_id] = averaged_embedding

        _LOGGER.info(
            "Enrolled speaker '%s' with %d samples",
            speaker_id,
            len(embeddings),
        )

        return {
            "success": True,
            "speaker_id": speaker_id,
            "samples_used": len(embeddings),
            "embedding_dimension": len(averaged_embedding),
        }

    async def load_enrollments(self, db_path: Path) -> None:
        """Load speaker enrollments from database."""
        import sqlite3

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT user_id, embedding FROM speaker_profiles WHERE embedding IS NOT NULL"
        )

        for user_id, embedding_blob in cursor.fetchall():
            embedding = np.frombuffer(embedding_blob, dtype=np.float32)
            self.embeddings[user_id] = embedding
            _LOGGER.debug("Loaded enrollment for %s", user_id)

        conn.close()
        _LOGGER.info("Loaded %d speaker enrollments", len(self.embeddings))

    async def save_enrollment(
        self,
        db_path: Path,
        speaker_id: str,
        display_name: str,
        permission_level: str = "standard",
    ) -> None:
        """Save speaker enrollment to database."""
        import sqlite3

        if speaker_id not in self.embeddings:
            raise ValueError(f"No enrollment found for {speaker_id}")

        embedding = self.embeddings[speaker_id]
        embedding_blob = embedding.tobytes()

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT OR REPLACE INTO speaker_profiles
            (user_id, display_name, embedding, permission_level, enrollment_samples)
            VALUES (?, ?, ?, ?, ?)
            """,
            (speaker_id, display_name, embedding_blob, permission_level, 5),
        )

        conn.commit()
        conn.close()

        _LOGGER.info("Saved enrollment for %s to database", speaker_id)
```

### 3.2 Permission System

```python
"""Permission system for family-aware access control."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

_LOGGER = logging.getLogger(__name__)


class PermissionLevel(Enum):
    """User permission levels."""
    ADMIN = "admin"       # Full access, can modify system
    STANDARD = "standard" # Normal adult access
    CHILD = "child"       # Limited access, safety restricted
    GUEST = "guest"       # Minimal access, no personal data


@dataclass
class Permission:
    """Permission definition."""
    name: str
    description: str
    min_level: PermissionLevel
    requires_confirmation: bool = False
    allowed_zones: list[str] | None = None


class PermissionManager:
    """Manage permissions for BarnabeeNet actions."""

    # Define all permissions
    PERMISSIONS = {
        # Device control
        "control_lights": Permission(
            name="control_lights",
            description="Turn lights on/off",
            min_level=PermissionLevel.CHILD,
        ),
        "control_climate": Permission(
            name="control_climate",
            description="Adjust thermostat",
            min_level=PermissionLevel.STANDARD,
        ),
        "control_locks": Permission(
            name="control_locks",
            description="Lock/unlock doors",
            min_level=PermissionLevel.ADMIN,
            requires_confirmation=True,
        ),
        "control_garage": Permission(
            name="control_garage",
            description="Open/close garage",
            min_level=PermissionLevel.ADMIN,
            requires_confirmation=True,
        ),
        "control_security": Permission(
            name="control_security",
            description="Arm/disarm security",
            min_level=PermissionLevel.ADMIN,
            requires_confirmation=True,
        ),

        # Information access
        "access_calendar": Permission(
            name="access_calendar",
            description="View calendar events",
            min_level=PermissionLevel.STANDARD,
        ),
        "access_personal_memory": Permission(
            name="access_personal_memory",
            description="Access personal conversation history",
            min_level=PermissionLevel.STANDARD,
        ),
        "access_family_memory": Permission(
            name="access_family_memory",
            description="Access family-wide information",
            min_level=PermissionLevel.ADMIN,
        ),

        # System administration
        "modify_automations": Permission(
            name="modify_automations",
            description="Create/edit automations",
            min_level=PermissionLevel.ADMIN,
        ),
        "enroll_speakers": Permission(
            name="enroll_speakers",
            description="Add new family members",
            min_level=PermissionLevel.ADMIN,
        ),
        "modify_settings": Permission(
            name="modify_settings",
            description="Change system settings",
            min_level=PermissionLevel.ADMIN,
        ),
    }

    # Permission level hierarchy
    LEVEL_HIERARCHY = {
        PermissionLevel.GUEST: 0,
        PermissionLevel.CHILD: 1,
        PermissionLevel.STANDARD: 2,
        PermissionLevel.ADMIN: 3,
    }

    def __init__(self, user_profiles: dict[str, dict[str, Any]]) -> None:
        """Initialize permission manager."""
        self.user_profiles = user_profiles

    def check_permission(
        self,
        speaker_id: str,
        action: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Check if a speaker has permission for an action.

        Returns:
            dict with:
                - allowed: bool
                - requires_confirmation: bool
                - reason: str (if denied)
        """
        # Get user's permission level
        user_level = self._get_user_level(speaker_id)

        # Get required permission
        permission = self.PERMISSIONS.get(action)
        if not permission:
            _LOGGER.warning("Unknown permission requested: %s", action)
            return {
                "allowed": False,
                "requires_confirmation": False,
                "reason": f"Unknown action: {action}",
            }

        # Check level hierarchy
        user_rank = self.LEVEL_HIERARCHY[user_level]
        required_rank = self.LEVEL_HIERARCHY[permission.min_level]

        if user_rank < required_rank:
            return {
                "allowed": False,
                "requires_confirmation": False,
                "reason": f"Insufficient permissions. {action} requires {permission.min_level.value} level.",
            }

        # Check zone restrictions
        if permission.allowed_zones and context:
            current_zone = context.get("zone")
            if current_zone and current_zone not in permission.allowed_zones:
                return {
                    "allowed": False,
                    "requires_confirmation": False,
                    "reason": f"Action not allowed in zone: {current_zone}",
                }

        return {
            "allowed": True,
            "requires_confirmation": permission.requires_confirmation,
            "reason": None,
        }

    def _get_user_level(self, speaker_id: str) -> PermissionLevel:
        """Get the permission level for a user."""
        if speaker_id == "guest" or speaker_id not in self.user_profiles:
            return PermissionLevel.GUEST

        profile = self.user_profiles.get(speaker_id, {})
        level_str = profile.get("permission_level", "standard")

        try:
            return PermissionLevel(level_str)
        except ValueError:
            return PermissionLevel.STANDARD

    def get_allowed_actions(self, speaker_id: str) -> list[str]:
        """Get list of actions allowed for a user."""
        user_level = self._get_user_level(speaker_id)
        user_rank = self.LEVEL_HIERARCHY[user_level]

        allowed = []
        for name, permission in self.PERMISSIONS.items():
            required_rank = self.LEVEL_HIERARCHY[permission.min_level]
            if user_rank >= required_rank:
                allowed.append(name)

        return allowed
```

---

## 4. Phase 3: Memory & Intelligence

### 4.1 Working Memory (Redis)

#### memory/working.py

```python
"""Working Memory using Redis for short-term context."""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

import aioredis

_LOGGER = logging.getLogger(__name__)


class WorkingMemory:
    """Redis-backed working memory for conversation context.

    Stores:
    - Current session context
    - Recent exchanges (last 10 minutes)
    - Extracted entities
    - Conversation intent/topic
    """

    def __init__(
        self,
        redis: aioredis.Redis,
        ttl: int = 600,  # 10 minutes
        max_exchanges: int = 10,
    ) -> None:
        """Initialize working memory."""
        self.redis = redis
        self.ttl = ttl
        self.max_exchanges = max_exchanges

    def _session_key(self, session_id: str, suffix: str) -> str:
        """Generate Redis key for session data."""
        return f"barnabeenet:session:{session_id}:{suffix}"

    def _user_key(self, speaker_id: str, suffix: str) -> str:
        """Generate Redis key for user data."""
        return f"barnabeenet:user:{speaker_id}:{suffix}"

    async def get_context(
        self,
        session_id: str,
        speaker_id: str | None = None,
    ) -> dict[str, Any]:
        """Get the current context for a session."""
        context = {}

        # Get session context
        session_data = await self.redis.get(
            self._session_key(session_id, "context")
        )
        if session_data:
            context["session"] = json.loads(session_data)

        # Get recent exchanges
        exchanges = await self.redis.lrange(
            self._session_key(session_id, "exchanges"),
            0,
            self.max_exchanges - 1,
        )
        context["exchanges"] = [json.loads(e) for e in exchanges]

        # Get user-specific context if speaker identified
        if speaker_id and speaker_id != "guest":
            user_context = await self.redis.get(
                self._user_key(speaker_id, "context")
            )
            if user_context:
                context["user"] = json.loads(user_context)

            # Get user's recent topic
            topic = await self.redis.get(
                self._user_key(speaker_id, "current_topic")
            )
            if topic:
                context["last_topic"] = topic

        return context

    async def add_exchange(
        self,
        session_id: str,
        speaker_id: str,
        user_input: str,
        assistant_response: str,
        entities: dict[str, Any] | None = None,
    ) -> None:
        """Add an exchange to working memory."""
        exchange = {
            "timestamp": datetime.now().isoformat(),
            "speaker_id": speaker_id,
            "user_input": user_input,
            "assistant_response": assistant_response,
            "entities": entities or {},
        }

        # Add to session exchanges (LPUSH for most recent first)
        key = self._session_key(session_id, "exchanges")
        await self.redis.lpush(key, json.dumps(exchange))

        # Trim to max exchanges
        await self.redis.ltrim(key, 0, self.max_exchanges - 1)

        # Set TTL
        await self.redis.expire(key, self.ttl)

        # Update user context
        if speaker_id and speaker_id != "guest":
            await self._update_user_context(speaker_id, exchange)

    async def _update_user_context(
        self,
        speaker_id: str,
        exchange: dict[str, Any],
    ) -> None:
        """Update user-specific context from exchange."""
        # Extract and store topic
        topic = self._extract_topic(exchange["user_input"])
        if topic:
            await self.redis.setex(
                self._user_key(speaker_id, "current_topic"),
                self.ttl,
                topic,
            )

        # Update user context with entities
        if exchange.get("entities"):
            user_context_key = self._user_key(speaker_id, "context")
            existing = await self.redis.get(user_context_key)
            context = json.loads(existing) if existing else {}

            # Merge entities
            context.update(exchange["entities"])

            await self.redis.setex(
                user_context_key,
                self.ttl,
                json.dumps(context),
            )

    def _extract_topic(self, text: str) -> str | None:
        """Extract the main topic from text."""
        # Simple extraction - in production, use NLP
        text_lower = text.lower()

        topic_keywords = {
            "weather": ["weather", "temperature", "rain", "forecast"],
            "lights": ["lights", "lighting", "lamp", "bright", "dim"],
            "music": ["music", "song", "play", "spotify"],
            "calendar": ["calendar", "schedule", "appointment", "meeting"],
            "temperature": ["thermostat", "ac", "heat", "cold", "warm"],
        }

        for topic, keywords in topic_keywords.items():
            if any(kw in text_lower for kw in keywords):
                return topic

        return None

    async def set_session_intent(
        self,
        session_id: str,
        intent: str,
    ) -> None:
        """Set the current session intent."""
        context = {"intent": intent, "set_at": datetime.now().isoformat()}

        await self.redis.setex(
            self._session_key(session_id, "context"),
            self.ttl,
            json.dumps(context),
        )

    async def clear_session(self, session_id: str) -> None:
        """Clear all data for a session."""
        pattern = self._session_key(session_id, "*")
        keys = await self.redis.keys(pattern)

        if keys:
            await self.redis.delete(*keys)

    async def get_recent_exchanges_for_prompt(
        self,
        session_id: str,
        max_tokens: int = 500,
    ) -> str:
        """Get formatted recent exchanges for LLM prompt context."""
        exchanges = await self.redis.lrange(
            self._session_key(session_id, "exchanges"),
            0,
            5,  # Last 5 exchanges max
        )

        if not exchanges:
            return ""

        # Format for prompt
        lines = ["Recent conversation:"]
        for e in reversed(exchanges):  # Chronological order
            exchange = json.loads(e)
            lines.append(f"User: {exchange['user_input']}")
            lines.append(f"Assistant: {exchange['assistant_response']}")

        return "\n".join(lines)
```

### 4.2 Episodic Memory (SQLite)

#### memory/episodic.py

```python
"""Episodic Memory using SQLite for long-term conversation storage."""
from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any

import aiosqlite
import numpy as np

_LOGGER = logging.getLogger(__name__)
_executor = ThreadPoolExecutor(max_workers=2)


class EpisodicMemory:
    """SQLite-backed episodic memory with vector search.

    Stores conversation history with embeddings for semantic retrieval.
    """

    def __init__(
        self,
        hass,
        db_path: str | Path,
        embedding_model: str = "all-MiniLM-L6-v2",
    ) -> None:
        """Initialize episodic memory."""
        self.hass = hass
        self.db_path = Path(db_path)
        self.embedding_model = embedding_model
        self.encoder = None
        self.db: aiosqlite.Connection | None = None

    async def async_initialize(self) -> None:
        """Initialize database and embedding model."""
        # Load embedding model
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(_executor, self._load_encoder)

        # Initialize database
        self.db = await aiosqlite.connect(self.db_path)

        # Create schema
        await self._create_schema()

        _LOGGER.info("Episodic memory initialized: %s", self.db_path)

    def _load_encoder(self) -> None:
        """Load sentence transformer model."""
        from sentence_transformers import SentenceTransformer

        self.encoder = SentenceTransformer(self.embedding_model)
        _LOGGER.info("Loaded embedding model: %s", self.embedding_model)

    async def _create_schema(self) -> None:
        """Create database schema if not exists."""
        schema_path = Path(__file__).parent / "schema.sql"

        if schema_path.exists():
            with open(schema_path) as f:
                schema = f.read()
            await self.db.executescript(schema)
            await self.db.commit()

    async def async_close(self) -> None:
        """Close database connection."""
        if self.db:
            await self.db.close()

    async def store_conversation(
        self,
        session_id: str,
        speaker_id: str,
        user_input: str,
        assistant_response: str,
        intent: str | None = None,
        classification: str | None = None,
        agent_used: str | None = None,
        processing_time_ms: int | None = None,
        cloud_used: bool = False,
    ) -> int:
        """Store a conversation exchange."""
        # Generate embedding
        loop = asyncio.get_event_loop()
        embedding = await loop.run_in_executor(
            _executor,
            self._generate_embedding,
            user_input + " " + assistant_response,
        )

        # Insert into database
        cursor = await self.db.execute(
            """
            INSERT INTO conversations (
                session_id, speaker_id, user_input, assistant_response,
                intent, classification, agent_used, processing_time_ms,
                cloud_used, embedding
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                speaker_id,
                user_input,
                assistant_response,
                intent,
                classification,
                agent_used,
                processing_time_ms,
                cloud_used,
                embedding.tobytes(),
            ),
        )

        await self.db.commit()
        return cursor.lastrowid

    def _generate_embedding(self, text: str) -> np.ndarray:
        """Generate embedding for text."""
        embedding = self.encoder.encode(text)
        return embedding.astype(np.float32)

    async def search(
        self,
        query: str,
        speaker_id: str | None = None,
        limit: int = 5,
        days_back: int = 30,
    ) -> list[dict[str, Any]]:
        """Search episodic memory using semantic similarity.

        Args:
            query: Search query text
            speaker_id: Optional filter by speaker
            limit: Maximum results to return
            days_back: How far back to search

        Returns:
            List of relevant conversation records
        """
        # Generate query embedding
        loop = asyncio.get_event_loop()
        query_embedding = await loop.run_in_executor(
            _executor,
            self._generate_embedding,
            query,
        )

        # Build query with filters
        sql = """
            SELECT
                id, session_id, speaker_id, user_input, assistant_response,
                intent, timestamp, embedding
            FROM conversations
            WHERE timestamp > datetime('now', ?)
        """
        params = [f"-{days_back} days"]

        if speaker_id:
            sql += " AND speaker_id = ?"
            params.append(speaker_id)

        sql += " ORDER BY timestamp DESC LIMIT 100"  # Get recent for reranking

        cursor = await self.db.execute(sql, params)
        rows = await cursor.fetchall()

        # Rerank by semantic similarity
        results = []
        for row in rows:
            embedding = np.frombuffer(row[7], dtype=np.float32)
            similarity = self._cosine_similarity(query_embedding, embedding)

            results.append({
                "id": row[0],
                "session_id": row[1],
                "speaker_id": row[2],
                "user_input": row[3],
                "assistant_response": row[4],
                "intent": row[5],
                "timestamp": row[6],
                "similarity": similarity,
            })

        # Sort by similarity and return top results
        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:limit]

    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Calculate cosine similarity."""
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

    async def get_user_history(
        self,
        speaker_id: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Get recent conversation history for a user."""
        cursor = await self.db.execute(
            """
            SELECT
                id, session_id, user_input, assistant_response,
                intent, timestamp
            FROM conversations
            WHERE speaker_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (speaker_id, limit),
        )

        rows = await cursor.fetchall()
        return [
            {
                "id": row[0],
                "session_id": row[1],
                "user_input": row[2],
                "assistant_response": row[3],
                "intent": row[4],
                "timestamp": row[5],
            }
            for row in rows
        ]

    async def mark_important(self, conversation_id: int) -> None:
        """Mark a conversation as important (won't be auto-archived)."""
        await self.db.execute(
            "UPDATE conversations SET important = TRUE WHERE id = ?",
            (conversation_id,),
        )
        await self.db.commit()

    async def cleanup_old_records(self, days: int = 30) -> int:
        """Remove old, non-important conversations."""
        cursor = await self.db.execute(
            """
            DELETE FROM conversations
            WHERE timestamp < datetime('now', ?)
            AND important = FALSE
            """,
            (f"-{days} days",),
        )
        await self.db.commit()
        return cursor.rowcount
```

---

## 5. Phase 4: Proactive & Self-Improving Intelligence

*[Section continues with Proactive Agent, Evolver Agent, and Wearable integration implementation...]*

---

## 6. Phase 5: Polish & Optimization

*[Section covers latency optimization, cost optimization, error handling, and monitoring...]*

---

## 7. Testing Strategy

### 7.1 Test Structure

```
tests/
├── conftest.py                  # Shared fixtures
├── unit/
│   ├── test_meta_agent.py       # Classification tests
│   ├── test_instant_agent.py    # Response pattern tests
│   ├── test_action_agent.py     # Action parsing tests
│   └── test_memory.py           # Memory operations tests
├── integration/
│   ├── test_stt_pipeline.py     # STT integration
│   ├── test_speaker_id.py       # Speaker recognition
│   └── test_full_pipeline.py    # End-to-end voice tests
└── evaluation/
    ├── test_latency.py          # Latency benchmarks
    ├── test_accuracy.py         # Response accuracy
    └── test_agents.py           # Agent behavior evaluation
```

### 7.2 Test Fixtures (conftest.py)

```python
"""Pytest fixtures for BarnabeeNet tests."""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock

from custom_components.barnabeenet.coordinator import BarnabeeNetCoordinator
from custom_components.barnabeenet.agents.meta_agent import MetaAgent
from custom_components.barnabeenet.agents.instant_agent import InstantAgent


@pytest.fixture
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_hass():
    """Create mock Home Assistant instance."""
    hass = MagicMock()
    hass.config.path = MagicMock(return_value="/tmp/test_barnabeenet.db")
    return hass


@pytest.fixture
def mock_redis():
    """Create mock Redis client."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.setex = AsyncMock()
    redis.lpush = AsyncMock()
    redis.lrange = AsyncMock(return_value=[])
    redis.ltrim = AsyncMock()
    redis.expire = AsyncMock()
    redis.ping = AsyncMock()
    return redis


@pytest.fixture
def mock_coordinator(mock_hass, mock_redis):
    """Create mock BarnabeeNet coordinator."""
    coordinator = MagicMock(spec=BarnabeeNetCoordinator)
    coordinator.hass = mock_hass
    coordinator.redis = mock_redis
    return coordinator


@pytest.fixture
def meta_agent(mock_coordinator):
    """Create MetaAgent instance for testing."""
    return MetaAgent(mock_coordinator)


@pytest.fixture
def instant_agent(mock_coordinator):
    """Create InstantAgent instance for testing."""
    return InstantAgent(mock_coordinator)


# Test data fixtures
@pytest.fixture
def sample_audio():
    """Generate sample audio data for testing."""
    import numpy as np
    import io
    import soundfile as sf

    # Generate 1 second of silence at 16kHz
    audio = np.zeros(16000, dtype=np.float32)
    buffer = io.BytesIO()
    sf.write(buffer, audio, 16000, format="WAV")
    return buffer.getvalue()


@pytest.fixture
def sample_transcriptions():
    """Sample transcriptions for testing classification."""
    return {
        "instant": [
            "What time is it?",
            "What's the date today?",
            "Hello Barnabee",
            "How are you?",
        ],
        "action": [
            "Turn on the living room lights",
            "Set the temperature to 72 degrees",
            "Lock the front door",
            "Turn off all the lights",
        ],
        "query": [
            "What's the weather like today?",
            "When is my next meeting?",
            "What's on my calendar?",
        ],
        "conversation": [
            "Tell me a story about a robot",
            "What do you think about artificial intelligence?",
            "Help me plan a birthday party",
        ],
    }
```

### 7.3 Unit Tests

```python
"""Unit tests for Meta Agent classification."""
import pytest
from custom_components.barnabeenet.const import (
    CLASS_INSTANT,
    CLASS_ACTION,
    CLASS_QUERY,
    CLASS_CONVERSATION,
)


class TestMetaAgentClassification:
    """Test Meta Agent rule-based classification."""

    @pytest.mark.asyncio
    async def test_classify_time_query(self, meta_agent):
        """Test classification of time queries."""
        queries = [
            "What time is it?",
            "What's the time?",
            "Current time",
            "time",
        ]

        for query in queries:
            result = await meta_agent.classify(query)
            assert result["classification"] == CLASS_INSTANT
            assert result["confidence"] >= 0.7
            assert result["metadata"]["category"] == "time"

    @pytest.mark.asyncio
    async def test_classify_light_control(self, meta_agent):
        """Test classification of light control commands."""
        queries = [
            "Turn on the lights",
            "Turn off the living room lights",
            "Dim the bedroom lights",
            "Set the kitchen lights to 50%",
        ]

        for query in queries:
            result = await meta_agent.classify(query)
            assert result["classification"] == CLASS_ACTION
            assert result["confidence"] >= 0.7
            assert result["metadata"]["category"] == "light_control"

    @pytest.mark.asyncio
    async def test_classify_weather_query(self, meta_agent):
        """Test classification of weather queries."""
        queries = [
            "What's the weather?",
            "Is it going to rain today?",
            "Weather forecast",
        ]

        for query in queries:
            result = await meta_agent.classify(query)
            assert result["classification"] == CLASS_QUERY
            assert result["confidence"] >= 0.7

    @pytest.mark.asyncio
    async def test_classify_ambiguous_query(self, meta_agent):
        """Test that ambiguous queries have lower confidence."""
        query = "Can you help me with something?"
        result = await meta_agent.classify(query)

        # Ambiguous queries should go to conversation with lower confidence
        assert result["classification"] == CLASS_CONVERSATION
        assert result["confidence"] < 0.7

    @pytest.mark.asyncio
    async def test_classify_gesture(self, meta_agent):
        """Test gesture classification."""
        gestures = {
            "crown_twist_yes": "confirm_yes",
            "button_click": "confirm",
            "motion_shake": "dismiss",
        }

        for gesture, expected_action in gestures.items():
            result = meta_agent.classify_gesture(gesture)
            assert result["metadata"]["action"] == expected_action
            assert result["confidence"] == 1.0


class TestInstantAgent:
    """Test Instant Agent responses."""

    @pytest.mark.asyncio
    async def test_time_response(self, instant_agent):
        """Test time response generation."""
        result = await instant_agent.handle(
            text="What time is it?",
            category="time",
        )

        assert "time" in result["text"].lower() or ":" in result["text"]
        assert result["latency_ms"] < 50  # Should be very fast

    @pytest.mark.asyncio
    async def test_greeting_response_with_name(self, instant_agent):
        """Test personalized greeting."""
        result = await instant_agent.handle(
            text="Hello",
            category="greeting",
            speaker_id="thom",
        )

        assert "thom" in result["text"].lower()

    @pytest.mark.asyncio
    async def test_math_evaluation(self, instant_agent):
        """Test simple math evaluation."""
        test_cases = [
            ("What is 2 + 2?", "4"),
            ("What is 10 - 3?", "7"),
            ("What is 6 * 7?", "42"),
            ("What is 15 / 3?", "5"),
        ]

        for query, expected in test_cases:
            result = await instant_agent.handle(text=query)
            assert expected in result["text"]
```

### 7.4 LLM Agent Evaluation

```python
"""Evaluation tests for LLM-based agents."""
import pytest
from deepeval import assert_test
from deepeval.metrics import (
    AnswerRelevancyMetric,
    FaithfulnessMetric,
)
from deepeval.test_case import LLMTestCase


class TestInteractionAgentEvaluation:
    """Evaluate Interaction Agent responses using LLM-as-judge."""

    @pytest.fixture
    def relevancy_metric(self):
        """Answer relevancy metric."""
        return AnswerRelevancyMetric(threshold=0.7)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("query,expected_topic", [
        ("What's the weather like today?", "weather"),
        ("Tell me about the solar system", "astronomy"),
        ("How do I make pasta?", "cooking"),
    ])
    async def test_response_relevancy(
        self,
        interaction_agent,
        relevancy_metric,
        query,
        expected_topic,
    ):
        """Test that responses are relevant to the query."""
        result = await interaction_agent.handle(
            text=query,
            speaker_id="test_user",
            context={},
            classification={"classification": "query"},
        )

        test_case = LLMTestCase(
            input=query,
            actual_output=result["text"],
        )

        assert_test(test_case, [relevancy_metric])


class TestLatencyBenchmarks:
    """Benchmark latency against targets."""

    LATENCY_TARGETS = {
        "instant": 5,
        "action": 100,
        "query": 500,
        "conversation": 3000,
    }

    @pytest.mark.asyncio
    async def test_instant_latency(self, instant_agent, sample_transcriptions):
        """Verify instant agent meets latency target."""
        import time

        for query in sample_transcriptions["instant"][:3]:
            start = time.perf_counter()
            await instant_agent.handle(text=query)
            latency_ms = (time.perf_counter() - start) * 1000

            assert latency_ms < self.LATENCY_TARGETS["instant"] * 2  # 2x margin
```

---

## 8. Deployment Procedures

### 8.1 Pre-Deployment Checklist

```markdown
## BarnabeeNet Deployment Checklist

### Infrastructure
- [ ] Proxmox VE 8.x installed and updated
- [ ] Home Assistant OS VM created (4+ cores, 8GB RAM)
- [ ] Redis LXC container running
- [ ] Network VLANs configured
- [ ] Backup strategy in place

### BarnabeeNet Integration
- [ ] Custom component copied to `/config/custom_components/barnabeenet/`
- [ ] Configuration added to `configuration.yaml`
- [ ] Secrets configured in `secrets.yaml`
- [ ] Database initialized (schema applied)

### Voice Pipeline
- [ ] Faster-Whisper model downloaded
- [ ] Piper voice model downloaded
- [ ] ECAPA-TDNN model downloaded
- [ ] Audio devices configured

### Testing
- [ ] Unit tests passing
- [ ] Integration tests passing
- [ ] Latency benchmarks within targets
- [ ] Speaker enrollment tested

### Security
- [ ] API keys secured in secrets
- [ ] Privacy zones configured
- [ ] Permission levels assigned
- [ ] Audit logging enabled
```

### 8.2 Installation Script

```bash
#!/bin/bash
# BarnabeeNet Installation Script
# Run on Home Assistant OS or container

set -e

BARNABEENET_VERSION="3.0.0"
INSTALL_DIR="/config/custom_components/barnabeenet"
MODELS_DIR="/config/models"

echo "Installing BarnabeeNet v${BARNABEENET_VERSION}..."

# Create directories
mkdir -p "$INSTALL_DIR"
mkdir -p "$MODELS_DIR/whisper"
mkdir -p "$MODELS_DIR/piper"
mkdir -p "$MODELS_DIR/speechbrain"

# Download component (from release or git)
if [ -n "$GITHUB_TOKEN" ]; then
    # Download from private release
    curl -sL -H "Authorization: token $GITHUB_TOKEN" \
        "https://github.com/thomfife/barnabeenet/releases/download/v${BARNABEENET_VERSION}/barnabeenet.zip" \
        -o /tmp/barnabeenet.zip
else
    # Public release
    curl -sL \
        "https://github.com/thomfife/barnabeenet/releases/download/v${BARNABEENET_VERSION}/barnabeenet.zip" \
        -o /tmp/barnabeenet.zip
fi

unzip -o /tmp/barnabeenet.zip -d "$INSTALL_DIR"
rm /tmp/barnabeenet.zip

# Download models
echo "Downloading Faster-Whisper model..."
python3 -c "
from faster_whisper import WhisperModel
model = WhisperModel('distil-whisper/distil-small.en', device='cpu')
print('Whisper model downloaded')
"

echo "Downloading Piper voice..."
curl -sL \
    "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx" \
    -o "$MODELS_DIR/piper/en_US-lessac-medium.onnx"

echo "Downloading speaker recognition model..."
python3 -c "
from speechbrain.inference import SpeakerRecognition
verifier = SpeakerRecognition.from_hparams(
    source='speechbrain/spkrec-ecapa-voxceleb',
    savedir='$MODELS_DIR/speechbrain'
)
print('Speaker recognition model downloaded')
"

# Initialize database
echo "Initializing database..."
python3 "$INSTALL_DIR/scripts/init_db.py" --db-path /config/barnabeenet.db

echo "BarnabeeNet installation complete!"
echo "Add the following to your configuration.yaml:"
echo ""
echo "barnabeenet:"
echo "  redis:"
echo "    host: YOUR_REDIS_HOST"
echo "    port: 6379"
```

---

## 9. Troubleshooting Guide

### 9.1 Common Issues

| Issue | Symptoms | Solution |
|-------|----------|----------|
| STT Timeout | Transcription takes >5s | Check CPU usage, reduce model size |
| Speaker Not Recognized | Always returns "guest" | Re-enroll with more/varied samples |
| Redis Connection Failed | "Connection refused" errors | Verify Redis container running, check network |
| High Latency | Response >3s for actions | Enable local LLM, check network to cloud |
| Memory Full | OOM errors | Increase VM RAM, reduce model sizes |

### 9.2 Diagnostic Commands

```bash
# Check BarnabeeNet logs
ha core logs | grep barnabeenet

# Test Redis connectivity
redis-cli -h 192.168.1.10 ping

# Check model loading
python3 -c "from faster_whisper import WhisperModel; m = WhisperModel('distil-whisper/distil-small.en'); print('OK')"

# Verify speaker embeddings
python3 -c "
import sqlite3
conn = sqlite3.connect('/config/barnabeenet.db')
print(conn.execute('SELECT user_id FROM speaker_profiles').fetchall())
"

# Latency benchmark
python3 /config/custom_components/barnabeenet/scripts/benchmark_latency.py
```

---

## 10. Configuration Reference

### 10.1 Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `BARNABEENET_REDIS_HOST` | Redis server hostname | `localhost` |
| `BARNABEENET_REDIS_PORT` | Redis server port | `6379` |
| `BARNABEENET_LOG_LEVEL` | Logging level | `INFO` |
| `OPENROUTER_API_KEY` | OpenRouter API key | *required* |
| `BARNABEENET_LOCAL_LLM_HOST` | Gaming PC IP for local LLM | *optional* |

### 10.2 YAML Configuration Options

See Section 2.7 for complete configuration reference.

---

## Document History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-01-16 | Initial implementation guide |
