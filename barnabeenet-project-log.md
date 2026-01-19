# BarnabeeNet Project Log

**Started:** January 16, 2026  
**Goal:** Build a privacy-first, multi-agent AI smart home assistant  

> **Status:** For current “what’s working” and next steps, see **CONTEXT.md**. This log records phases, decisions, and history.

---

## Environment

| Name | Hardware | Role | IP |
|------|----------|------|-----|
| Man-of-war | Gaming PC (i9-14900KF, RTX 4070 Ti, 128GB) | Development + GPU worker (Parakeet STT) | 192.168.86.100 |
| Battlestation | Beelink EQi12 (i5-1220P, 24GB, 500GB) | Proxmox host | 192.168.86.64 |
| BarnabeeNet VM | VM 200 on Battlestation (6 cores, 8GB RAM, 100GB) | BarnabeeNet runtime | 192.168.86.51 |

---

## Phase 0: Foundation Setup
**Status:** ✅ Complete
**Date:** January 16, 2026

### Step 1: Development Environment Setup
**Status:** ✅ Complete
**Date:** January 16, 2026

- [x] Cursor installed on Windows 11
- [x] Anthropic API key created with credits
- [x] WSL2 with Ubuntu-24.04 installed
- [x] git, age, sops installed in WSL
- [x] SSH access to Battlestation verified

---

### Step 2: Repository Initialization
**Status:** ✅ Complete
**Date:** January 16, 2026

- [x] GitHub repository created: https://github.com/trfife/BarnabeeNet
- [x] SSH key configured for GitHub
- [x] Initial structure committed and pushed

---

### Step 3: Create BarnabeeNet VM on Proxmox
**Status:** ✅ Complete
**Date:** January 16, 2026

- [x] Cleaned up unused VMs/containers
- [x] Downloaded NixOS 24.11 ISO to Proxmox
- [x] Created VM 200 (barnabeenet): 6 cores, 8GB RAM, 100GB disk
- [x] Installed NixOS with UEFI boot (systemd-boot)
- [x] SSH access as thom@192.168.86.51 verified
- [x] Nix flakes enabled

---

### Step 4: Base VM Configuration
**Status:** ✅ Complete
**Date:** January 16, 2026

- [x] NixOS configuration updated with Podman + dev tools
- [x] Podman rootless with docker-compat enabled
- [x] SSH key generated for GitHub access from VM
- [x] BarnabeeNet repo cloned to ~/barnabeenet
- [x] Data directories created (~/data/redis, ~/data/models/*)
- [x] Redis 7-alpine container running via podman-compose
- [x] Systemd user service for auto-start on boot
- [x] Verified services survive reboot

#### Installed Packages
- podman, podman-compose
- python312, pip, virtualenv
- sqlite, redis-cli
- age, sops
- jq, yq, tree, ffmpeg

#### Running Services
| Service | Image | Port | Status |
|---------|-------|------|--------|
| Redis | redis:7-alpine | 6379 | Running (auto-start) |

---

## Phase 1: Core Services
**Status:** ✅ Complete

### Step 1: Project Structure + Configuration
**Status:** ✅ Complete
**Date:** January 17, 2026

- [x] Created `pyproject.toml` with modern Python packaging
- [x] Created `requirements.txt` for Beelink CPU dependencies
- [x] Created `requirements-gpu.txt` for Man-of-war GPU dependencies
- [x] Created `.env.example` with all configuration options
- [x] Created project directory structure (`src/barnabeenet/`, `tests/`, `workers/`, `scripts/`)
- [x] Created package `__init__.py` files

### Step 2: Core Application
**Status:** ✅ Complete
**Date:** January 17, 2026

- [x] Created `config.py` - Pydantic Settings with nested config classes
- [x] Created `main.py` - FastAPI app with lifespan management
- [x] Created `models/schemas.py` - All Pydantic request/response models
- [x] Created `api/routes/health.py` - Health check endpoints
- [x] Created `api/routes/voice.py` - STT, TTS, pipeline endpoints
- [x] Implemented background GPU worker health check (zero-latency routing)

### Step 3: STT Services
**Status:** ✅ Complete

- [x] Implement Distil-Whisper CPU service (~2.4s)
- [x] Implement GPU worker client (Parakeet TDT, ~45ms)
- [x] Implement STT router (GPU primary, CPU fallback)
- [x] Azure STT integration (batch + streaming for mobile/remote)
- [x] Tiered STT: COMMAND, REALTIME, AMBIENT modes; PARAKEET, WHISPER, AZURE engines
- [x] WebSocket `/ws/transcribe` for real-time streaming

### Step 4: TTS Service
**Status:** ✅ Complete

- [x] Implement Kokoro TTS service (bm_fable, 232–537ms)
- [x] Pronunciation fixes (Viola→Vyola, Xander→Zander)

### Step 5: GPU Worker (Man-of-war)
**Status:** ✅ Complete

- [x] GPU worker FastAPI app (`workers/gpu_stt_worker.py`)
- [x] Parakeet TDT 0.6B v2 integration
- [x] WSL2 + CUDA on Man-of-war; VM reaches worker via `192.168.86.61:8001`
- [x] Scripts: `start-gpu-worker.sh`, `stop-gpu-worker.sh`; deploy via `deploy-vm.sh`

### Step 6: Deployment Scripts
**Status:** ✅ Complete

- [x] `deploy-vm.sh` – push to VM, restart
- [x] `start-gpu-worker.sh`, `stop-gpu-worker.sh` for Man-of-war
- [x] `restart.sh`, `status.sh` on VM

### Step 7: Tests
**Status:** ✅ Complete

- [x] Unit/integration tests (600+ tests: agents, STT, TTS, config, HA, memory, E2E, etc.)
- [x] E2E framework with mock HA, `ENTITY_STATE` assertions
- [x] E2E API at `/api/v1/e2e/`

---

## Phase 2: Voice Pipeline & Message Bus
**Status:** ✅ Complete

- [x] Message bus (Redis Streams)
- [x] Voice pipeline orchestrator (STT → Agent → TTS)
- [x] Pipeline signal logging, `RequestTrace`, `PipelineLogger`
- [x] Text-only `/api/v1/voice/process` for testing
- [x] Quick input: `POST /input/text`, `POST /input/audio`
- [x] Simple Chat API: `GET/POST /api/v1/chat`

---

## Phase 3: Agent Architecture
**Status:** ✅ Complete

- [x] **MetaAgent** – Intent classification, mood, memory-query generation, pattern + LLM
- [x] **InstantAgent** – Time, date, math, greetings (no LLM)
- [x] **ActionAgent** – HA device control, rule-based + LLM, compound commands, typos
- [x] **InteractionAgent** – Claude/GPT-4 via OpenRouter, Barnabee persona, anti-hallucination
- [x] **MemoryAgent** – Store/retrieve/forget, working memory, extraction, diary generation
- [x] **ProfileAgent** – Family profiles, LLM-generated updates, privacy-aware context
- [x] **AgentOrchestrator** – classify → memory retrieve → route → store; full pipeline
- [x] LLM provider abstraction (12 providers), activity-based model config, encrypted secrets
- [ ] **Proactive Agent** – Deferred (spec only)
- [ ] **Evolver Agent** – Deferred (spec only)

---

## Phase 4: Home Assistant Integration
**Status:** ✅ Complete

- [x] HomeAssistantClient – REST + WebSocket (device/area/entity registries)
- [x] EntityRegistry, fuzzy matching, SmartEntityResolver (areas, floors, groups, typos)
- [x] HATopologyService – floors, areas, natural-language targeting
- [x] Compound commands (“X and Y”), CompoundCommandParser, HATarget models
- [x] Action execution: resolve → HA service call → pipeline logging
- [x] Timer system (TimerManager, HA timer helpers): alarm, device-duration, delayed
- [x] Real-time `state_changed` WebSocket, activity log
- [x] HA custom integration – conversation agent, config flow, speaker/room from HA user/device
- [x] HA log analysis (LLM), “What Barnabee Knows” dashboard view
- [x] Mock HA for E2E testing

---

## Phase 5: Multi-Modal & Advanced Features
**Status:** 🔄 Partially Complete

- [x] Dashboard – Chat (text + voice mic), Memory, HA, Config, Prompts, Logs, Activity
- [x] Azure STT, tiered STT (COMMAND/REALTIME/AMBIENT), `/ws/transcribe`
- [x] Family profiles, ProfileAgent, privacy-aware context
- [x] Observability: Prometheus, Grafana, metrics, traces, waterfall, health checks
- [ ] AR (Even Realities G1) – Deferred
- [ ] Wearable (Amazfit) – Deferred
- [ ] ThinkSmart View – Deferred
- [ ] ViewAssist integration – Next; APIs ready (`/api/v1/chat`, `/api/v1/input/audio`)
- [ ] Mobile client – Placeholder at `docs/future/MOBILE_STT_CLIENT.md`

---

## Phase 6: Hardening & Production
**Status:** 🔄 Partially Complete

- [x] VM deployment (192.168.86.51:8000), NixOS, Redis, Prometheus, Grafana
- [x] 600+ tests, E2E with mock HA, CI-style validation
- [x] Operations Runbook, INTEGRATION.md, CONTEXT.md as live status
- [ ] Full production hardening (rate limits, auth, backups) – Ongoing
- [ ] Speaker ID from voice (ECAPA-TDNN) – Deferred; speaker from HA/request/context only

---

## Deferred / Not Yet Implemented

| Item | Spec / Plan | Current |
|------|-------------|---------|
| **Speaker ID from voice** | ECAPA-TDNN (SpeechBrain) | Speaker from HA user, request, or family profiles only |
| **Memory persistence** | SQLite + sqlite-vec | Redis + in-memory fallback; vector similarity via embeddings in Redis |
| **Proactive Agent** | Polling, safety/convenience/learning | Not implemented |
| **Evolver Agent** | Vibe coding, Azure ML evals | Not implemented |
| **Override system** | `config/overrides/` (user, room, schedule) | Not implemented |
| **Spatial room graph** | YAML graph, path awareness | HATopologyService + HA areas; no full graph |
| **AR, Wearables, ThinkSmart** | Spec | Placeholder / future |

---

## Decisions Made

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-01-16 | Use Cursor as primary IDE | AI-assisted development with Claude integration |
| 2026-01-16 | Use WSL2 for dev tools | Better Linux tooling for infrastructure work |
| 2026-01-16 | Existing Proxmox stays as-is | Only greenfield the BarnabeeNet VM |
| 2026-01-16 | Private GitHub repo | Contains home network details |
| 2026-01-16 | NixOS over Ubuntu | Declarative config is better for AI-driven builds |
| 2026-01-16 | VM ID 200 | Clean numbering, away from existing IDs |
| 2026-01-16 | 8GB RAM, 6 cores | Conservative given Beelink memory constraints |
| 2026-01-16 | UEFI boot with OVMF | Required for systemd-boot |
| 2026-01-16 | Podman rootless over Docker | Security + NixOS compatibility |
| 2026-01-16 | Separate SSH key per machine | Security best practice |
| 2026-01-17 | **Kokoro over Piper for TTS** | Research shows Kokoro is faster (<0.3s) and better quality |
| 2026-01-17 | **Dual-path STT (Parakeet + Distil-Whisper)** | GPU primary for speed, CPU fallback for reliability |
| 2026-01-17 | **Man-of-war as GPU worker** | RTX 4070 Ti provides 10x faster STT than CPU |
| 2026-01-17 | **WSL2 for GPU worker** | No dual-boot needed, can game while worker runs |
| 2026-01-17 | **Zero-latency health check routing** | Background health check, cached state read on request path |
| 2026-01-17 | **Streaming STT, not batch** | Key insight: streaming gives ~100-300ms, batch gives 1-2s |

---

## Research Findings (January 17, 2026)

### TTS Comparison (2025 State of the Art)

| Model | Speed (CPU) | Quality | Voice Clone | License |
|-------|-------------|---------|-------------|---------|
| **Kokoro-82M** | <0.3s ⚡ | Good | No | Apache 2.0 |
| Piper | ~0.1-0.5s | Acceptable | No | MIT |
| XTTS-v2 | Slow (CPU) | Excellent | Yes | Coqui License |

**Decision:** Kokoro for speed, XTTS-v2 deferred to Phase 5 for voice cloning

### STT Comparison (2025 State of the Art)

| Model | WER | Speed (RTFx) | Hardware |
|-------|-----|--------------|----------|
| Parakeet TDT 0.6B v2 | 6.05% | 3386x ⚡ | GPU required |
| Distil-Whisper small.en | ~7% | Fast | CPU OK |
| Faster-Whisper | Varies | Good | CPU OK |

**Decision:** Parakeet on GPU (primary), Distil-Whisper on CPU (fallback)

### Key Insight: Streaming vs Batch STT
- User's existing HA setup achieves millisecond STT because it uses **streaming**
- Batch mode (record → send → process) takes 1-2 seconds
- Streaming mode (process as you speak) completes ~100-300ms after speech ends

---

## Architecture Summary

```
┌─────────────────────────────────────────────────────────────────────┐
│  BARNABEENET VOICE PIPELINE                                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   Audio In ──→ STT Router ──→ Processing ──→ TTS ──→ Audio Out     │
│                    │                                                │
│         ┌─────────┴─────────┐                                      │
│         ▼                   ▼                                       │
│   ┌───────────┐       ┌───────────┐                                │
│   │ Parakeet  │       │ Distil-   │                                │
│   │ (GPU)     │       │ Whisper   │                                │
│   │ PRIMARY   │       │ FALLBACK  │                                │
│   │ ~20-40ms  │       │ ~150-300ms│                                │
│   └───────────┘       └───────────┘                                │
│   Man-of-war          Beelink VM                                   │
│                                                                     │
│   TTS: Kokoro-82M (<300ms) on Beelink                              │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Development Environment Setup

### Cursor IDE
- [x] Installed
- [x] Connected to WSL
- [x] Opened ~/projects/barnabeenet
- [x] Anthropic API key configured (can use Cursor Pro's included access)

### Man-of-war WSL
- [x] Ubuntu 24.04
- [x] Git configured
- [x] SSH keys for GitHub
- [x] Repo cloned to ~/projects/barnabeenet
- [x] Python venv (main `.venv/`); separate `.venv-gpu/` for GPU worker (NeMo, Parakeet)

---

## Documentation Updates
**Status:** ✅ Complete
**Date:** January 17, 2026

- [x] Created `docs/PATCH_Phase1_Updates.md` with surgical doc patches
- [x] Applied patches via Cursor to update:
  - Technology stack (Kokoro, Distil-Whisper, Parakeet)
  - GPU worker architecture
  - Implementation roadmap
  - SkyrimNet patterns

---

## Issues Encountered

| Date | Issue | Resolution |
|------|-------|------------|
| 2026-01-16 | WSL showed "no installed distributions" | Ran `wsl --install -d Ubuntu-24.04` explicitly |
| 2026-01-16 | Git push failed - SSH key not on GitHub | Added SSH key to GitHub settings |
| 2026-01-16 | `qm terminal` - no serial interface | Used Proxmox web console instead |
| 2026-01-16 | Can't paste in Proxmox console | Set root password, SSH in from WSL |
| 2026-01-16 | Mount by label failed | Used mount by device name instead |
| 2026-01-16 | Duplicate /boot entry in hardware-configuration.nix | Manually removed the bind mount entry |
| 2026-01-16 | VM stuck at "Booting from Hard Disk" | VM was using BIOS, not UEFI. Added EFI disk and changed to OVMF |
| 2026-01-16 | SSH key not being accepted | Key was in config but not applied. Ran `nixos-rebuild switch` |
| 2026-01-16 | SSH host key warnings | Expected after reinstalls. Used `ssh-keygen -R` to clear old keys |
| 2026-01-16 | Systemd user service couldn't find podman | Added PATH environment variable to service file |

---

## Proxmox Current State

### VMs
| VMID | Name | Status | Purpose |
|------|------|--------|---------|
| 100 | home-assistant | running | Home Assistant |
| 200 | barnabeenet | running | BarnabeeNet (NixOS) |

### Containers
| VMID | Name | Status | Purpose |
|------|------|--------|---------|
| 101 | node-red | running | Node-RED |
| 106 | homebox | running | Homebox |
| 107 | barnabee | stopped | Old version (kept for reference) |

---

## NixOS Configuration (Current)

**Location on VM:** `/etc/nixos/configuration.nix`
```nix
{ config, pkgs, ... }:

{
  imports = [
    ./hardware-configuration.nix
  ];

  boot.loader.systemd-boot.enable = true;
  boot.loader.efi.canTouchEfiVariables = true;

  networking.hostName = "barnabeenet";
  networking.networkmanager.enable = true;

  time.timeZone = "America/New_York";

  users.users.thom = {
    isNormalUser = true;
    extraGroups = [ "wheel" "networkmanager" ];
    openssh.authorizedKeys.keys = [
      "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOP6MkvsXW5bgQmDoSE6uWdckVgzhVFxh4xOuiiEpsBG thom.fife@gmail.com"
    ];
    subUidRanges = [{ startUid = 100000; count = 65536; }];
    subGidRanges = [{ startGid = 100000; count = 65536; }];
  };

  security.sudo.wheelNeedsPassword = false;

  services.openssh = {
    enable = true;
    settings = {
      PermitRootLogin = "prohibit-password";
      PasswordAuthentication = false;
    };
  };

  services.qemuGuest.enable = true;

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
    age sops
    jq yq tree unzip ffmpeg
  ];

  networking.firewall = {
    enable = true;
    allowedTCPPorts = [ 22 ];
  };

  nix.settings.experimental-features = [ "nix-command" "flakes" ];

  nix.gc = {
    automatic = true;
    dates = "weekly";
    options = "--delete-older-than 30d";
  };

  system.stateVersion = "24.11";
}
```

---

## Files Created This Session

```
barnabeenet/
├── pyproject.toml              # NEW
├── requirements.txt            # NEW
├── requirements-gpu.txt        # NEW
├── .env.example               # NEW
├── docs/
│   └── PATCH_Phase1_Updates.md # NEW
└── src/barnabeenet/
    ├── __init__.py             # UPDATED
    ├── config.py               # NEW
    ├── main.py                 # NEW
    ├── api/
    │   ├── __init__.py         # UPDATED
    │   └── routes/
    │       ├── __init__.py     # UPDATED
    │       ├── health.py       # NEW
    │       └── voice.py        # NEW
    ├── models/
    │   ├── __init__.py         # UPDATED
    │   └── schemas.py          # NEW
    └── services/
        ├── stt/
        │   └── __init__.py
        └── tts/
            └── __init__.py
```

---

## Session: January 17, 2026 (Evening)

### Completed: Phase 1 Steps 3-4

#### Step 3: STT Service (Distil-Whisper) ✅
- Installed `faster-whisper` package
- Created `src/barnabeenet/services/stt/distil_whisper.py`
- Fixed model name: use `distil-small.en` (not `distil-whisper/distil-small.en`)
- Fixed float32 casting issue in `np.interp` for VAD compatibility
- Fixed config field names: `whisper_model`, `whisper_device`, `whisper_compute_type`
- **Performance:** 2347ms for 10.5s audio on CPU

#### Step 4: TTS Service (Kokoro) ✅
- Installed `kokoro`, `soundfile`, `espeak-ng`
- Created `src/barnabeenet/services/tts/kokoro_tts.py`
- Created `src/barnabeenet/services/tts/pronunciation.py`
- **Voice selected:** `bm_fable` (British male) - closest to Australian accent
- **Pronunciation corrections:** Viola→Vyola, Xander→Zander
- Updated config default voice from `af_bella` to `bm_fable`
- **Performance:** 232-537ms latency for typical responses

#### API Routes Wired ✅
- Updated `src/barnabeenet/api/routes/voice.py` to use real STT/TTS services
- TTS endpoint tested and working
- STT endpoint needs API test (server restart issue)

### Files Modified
- `src/barnabeenet/services/stt/distil_whisper.py` (new)
- `src/barnabeenet/services/stt/__init__.py`
- `src/barnabeenet/services/tts/kokoro_tts.py` (new)
- `src/barnabeenet/services/tts/pronunciation.py` (new)
- `src/barnabeenet/services/tts/__init__.py`
- `src/barnabeenet/api/routes/voice.py`
- `src/barnabeenet/config.py` (voice default, model name fix)

### Next Session TODO
1. Kill stuck uvicorn: `kill -9 18609` then restart
2. Test STT API endpoint
3. Step 5: GPU Worker (Parakeet on Man-of-war)
4. Step 6: Deployment scripts
5. Step 7: Tests
6. Commit all changes to GitHub

### Test Commands for Next Session
```bash
# Start server
uvicorn barnabeenet.main:app --reload

# Test TTS
curl -X POST http://localhost:8000/api/v1/synthesize \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello Viola and Xander!"}'

# Test STT (use test_family.wav generated this session)
python -c "
import asyncio, base64, httpx
async def test():
    with open('test_family.wav', 'rb') as f:
        audio = base64.b64encode(f.read()).decode()
    async with httpx.AsyncClient(timeout=120) as c:
        r = await c.post('http://localhost:8000/api/v1/transcribe', json={'audio_base64': audio})
        print(r.json())
asyncio.run(test())
"
```

---

## Access Quick Reference

```bash
# Development (Man-of-war WSL)
cd ~/projects/barnabeenet
source .venv/bin/activate  # After setup

# SSH to BarnabeeNet VM
ssh thom@192.168.86.51

# SSH to Proxmox host
ssh root@192.168.86.64

# Proxmox Web UI
https://192.168.86.64:8006

# Check BarnabeeNet services
ssh thom@192.168.86.51 "podman ps"

# Redis CLI
ssh thom@192.168.86.51 "podman exec barnabeenet-redis redis-cli ping"

# Deploy to server (after git push)
ssh thom@192.168.86.51 "cd ~/barnabeenet && git pull"
```

---

## Cost Tracking

### Development Costs
| Date | Item | Cost |
|------|------|------|
| 2026-01-16 | Cursor Pro (monthly) | $20 |
| 2026-01-16 | Anthropic API credits | ~$5 used |

### Running Total
- **Development:** ~$25/month
- **Runtime:** $0 (not yet deployed)


---

## Session: January 17, 2026 - Copilot Workflow Setup
**Status:** ✅ Complete

### What Was Done
- [x] Evaluated GitHub Copilot agent capabilities vs Claude
- [x] Designed hybrid workflow (Claude for planning, Copilot for execution)
- [x] Created `.vscode/settings.json`, `tasks.json`, `extensions.json`
- [x] Created `.github/copilot-instructions.md` (agent behavior rules)
- [x] Created `.github/AGENTS.md` (capability reference)
- [x] Created `CONTEXT.md` (Copilot's persistent memory)
- [x] Created `scripts/validate.sh` (pre-commit validation)
- [x] Created `scripts/pre-commit.sh` (git hook)
- [x] Created `Makefile` (common commands)
- [x] Created `.copilot/templates/session-plan.md`
- [x] Validated Copilot can: read docs, run WSL commands, SSH to VM, create files
- [x] Validated Copilot understands full project architecture (comprehension test)
- [x] Added `docs/future/TOON_Optimization.md` (backlog item)

### Validation Results
- **test-001**: WSL commands ✅, SSH commands ✅, file creation ✅
- **test-002**: Deep comprehension test passed - agent understands multi-agent architecture, memory system, infrastructure, voice pipeline, privacy zones

### Files Created
```
.vscode/
├── settings.json
├── tasks.json
└── extensions.json
.github/
├── copilot-instructions.md
└── AGENTS.md
.copilot/
├── templates/session-plan.md
└── sessions/
    ├── test-001-validation.md
    ├── test-001-results.md
    ├── test-002-comprehension.md
    └── test-002-results.md
scripts/
├── validate.sh
└── pre-commit.sh
docs/future/
└── TOON_Optimization.md
CONTEXT.md
Makefile
```

### Next Session
Copilot can now continue autonomously. User says "continue the project" → Copilot reads CONTEXT.md → Creates session for MessageBus implementation.

---
---

## Session: January 17, 2026 - STT/TTS Testing + Copilot Setup
**Status:** ✅ Complete

### Part 1: STT/TTS Validation

#### STT (Distil-Whisper) Test Results
- **Input:** 504KB WAV file (~15.75 seconds)
- **Output:** "Good morning everyone. Tom, Elizabeth, Penelope, Viola, Sanda and Zachary. Breakfast is ready. Oh, and I see Bagheera and Shea Khan are waiting by their food bowls too."
- **Latency:** 30,689ms (first request, includes model load)
- **Warm latency:** ~2,400ms
- **Engine:** distil-whisper

#### TTS (Kokoro) Test Results
- **Voice:** bm_fable (British male)
- **Latency:** 232-537ms
- **Pronunciation fixes:** Viola→Vyola, Xander→Zander

### Part 2: Infrastructure Setup

- [x] Docker installed on Man-of-war WSL (`sudo apt install docker.io`)
- [x] Redis container running locally (`docker run -d --name redis -p 6379:6379 redis:7-alpine`)
- [x] BarnabeeNet connecting to local Redis confirmed

### Part 3: Copilot Workflow Setup

- [x] Created `.vscode/settings.json`, `tasks.json`, `extensions.json`
- [x] Created `.github/copilot-instructions.md`
- [x] Created `CONTEXT.md`
- [x] Created `scripts/validate.sh`, `pre-commit.sh`
- [x] Created `Makefile`
- [x] Validated Copilot agent can read docs, run commands, SSH to VM
- [x] Validated Copilot understands project architecture (comprehension test)
- [x] Created `docs/future/TOON_Optimization.md`

### Next Session
**GPU Worker (Parakeet TDT) setup on Man-of-war** - This is the critical path to achieving <100ms STT latency.

---

---

*Last Updated: January 2026 (doc sync with implementation)*
