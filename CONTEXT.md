# BarnabeeNet Project Context

> **This file is Copilot's "memory". Update it after each work session.**

## Last Updated
2026-01-18 (after Activity-Based LLM Configuration)

## Current Phase
**Phase 1: Core Services** - DASHBOARD OBSERVABILITY COMPLETE

## Development Workflow

**Hybrid Claude + Copilot workflow is active:**
- Claude (claude.ai): Planning, research, architecture decisions
- Copilot (VS Code): Execution, file creation, testing, SSH commands
- Session files: `.copilot/sessions/`

To continue: Read this file → Check next steps → Create/execute session plan.

---

## Project State

### What's Working
- [x] Development environment (WSL + VS Code)
- [x] BarnabeeNet VM running NixOS 24.11 (192.168.86.51)
- [x] Redis container on VM (auto-starting)
- [x] Redis container on Man-of-war (Docker, for local dev)
- [x] Docker installed on Man-of-war WSL
- [x] Basic project structure + FastAPI skeleton
- [x] **STT (Distil-Whisper)** - Working, ~2.4s latency (CPU fallback)
- [x] **TTS (Kokoro)** - Working, 232-537ms latency, voice: bm_fable
- [x] Pronunciation fixes (Viola→Vyola, Xander→Zander)
- [x] Copilot agent configuration validated
- [x] **GPU Worker (Parakeet TDT 0.6B v2)** - Working locally, **45ms latency!**
- [x] **STT Router** - GPU primary, CPU fallback, with tests
- [x] **WSL port forwarding** - VM can reach GPU worker at `192.168.86.61:8001`
- [x] **Deployment scripts** - start/stop GPU worker, deploy to VM, status check
- [x] **Tests for STT/TTS services** - 54 tests covering all services

- [x] Message bus (Redis Streams)
- [x] Voice pipeline integration
- [x] **LLM Provider Abstraction** - Pluggable providers: OpenRouter, OpenAI, Anthropic, Azure, Google, Grok, Hugging Face
- [x] **Signal logging system** - Every LLM call logged for dashboard visibility
- [x] **MetaAgent** - Intent classification, context/mood evaluation, memory query generation
- [x] **InstantAgent** - Zero-latency responses for time, date, greetings, math
- [x] **ActionAgent** - Device control parsing, rule-based + LLM fallback, HA service calls
- [x] **InteractionAgent** - Complex conversations with LLM (Claude/GPT-4), Barnabee persona
- [x] **MemoryAgent** - Memory storage/retrieval/generation, working memory, conversation extraction
- [x] **AgentOrchestrator** - Full pipeline: classify → memory retrieve → route to agent → store memories
- [x] **Voice Pipeline + Orchestrator Integration** - Full voice-to-voice with multi-agent AI
- [x] **Memory Storage System** - EmbeddingService (all-MiniLM-L6-v2), MemoryStorage with Redis + in-memory fallback, vector similarity search
- [x] **Home Assistant Integration** - HomeAssistantClient with REST API, EntityRegistry with fuzzy name matching, service call execution
- [x] **Dashboard Phase 1** - Dashboard API endpoints (activity feed, signal details, stats), Prometheus metrics, Grafana + Prometheus compose config
- [x] **Dashboard Phase 2** - WebSocket endpoint (/ws/activity) for real-time signal streaming, ConnectionManager with filtering, SignalStreamer background task reading from Redis Streams
- [x] **VM Deployment** - BarnabeeNet running on VM (192.168.86.51:8000), NixOS firewall configured, all services healthy
- [x] **Web Dashboard UI** - SkyrimNet-style dark theme dashboard at http://192.168.86.51:8000/
- [x] **Pipeline Signal Logging** - Full request tracing with PipelineLogger, SignalType enum (25+ types), RequestTrace model
- [x] **Dashboard Trace Visualization** - Request traces list, expandable trace details showing complete data flow (input → classify → agent → response)
- [x] **Activity-Based LLM Configuration** - Granular model selection per activity (16+ activities like meta.classify_intent, interaction.respond, memory.generate). Configurable via YAML (config/llm.yaml), environment variables (LLM_ACTIVITY_*), or defaults. Different models for classification vs conversation vs memory tasks.

### In Progress
- [ ] End-to-end voice testing

### Not Started
- [ ] End-to-end voice testing

---

## Deployment Architecture

| Component | Location | Purpose |
|-----------|----------|---------|
| **BarnabeeNet App** | VM (192.168.86.51:8000) | Main runtime - agents, API, dashboard |
| **Redis** | VM (192.168.86.51:6379) | Message bus, signals, memory cache |
| **Prometheus** | VM (192.168.86.51:9090) | Metrics storage |
| **Grafana** | VM (192.168.86.51:3000) | Dashboard UI |
| **GPU STT Worker** | Man-of-war (192.168.86.61:8001) | Fast transcription via RTX 4070 Ti |

**Deployment flow:**
1. Develop & test locally on Man-of-war
2. `./scripts/deploy-vm.sh` pushes to VM and restarts services
3. VM runs production, Man-of-war provides GPU acceleration

---

## Environment Quick Reference

| Resource | Location |
|----------|----------|
| Dev workspace | `/home/thom/projects/barnabeenet` (WSL) |
| VM runtime | `thom@192.168.86.51:~/barnabeenet` |
| Redis (VM) | `192.168.86.51:6379` |
| Redis (local) | `localhost:6379` (Docker on Man-of-war) |
| GPU Worker | `localhost:8001` (WSL) / `192.168.86.61:8001` (from VM) |
| GPU venv | `.venv-gpu/` (separate from main `.venv/`) |
| Windows Host (LAN) | `192.168.86.61` |

---

## Next Steps (Ordered)

1. End-to-end voice testing ← NEXT (test full voice pipeline from VM)
2. Home Assistant entity discovery
3. Family profile system

---

## STT/TTS Performance Baseline

| Service | Engine | Latency | Notes |
|---------|--------|---------|-------|
| STT (CPU) | Distil-Whisper | ~2,400ms | Fallback option |
| STT (GPU) | Parakeet TDT 0.6B v2 | **45ms** ✅ | 53x faster than CPU! |
| TTS | Kokoro-82M | 232-537ms | Working, voice: bm_fable |

### GPU Worker Details
- Location: `workers/gpu_stt_worker.py`
- Model: nvidia/parakeet-tdt-0.6b-v2
- GPU: RTX 4070 Ti (CUDA 12.4)
- Endpoints: `/health`, `/transcribe`
- Start: `screen -dmS gpu_worker python -m uvicorn workers.gpu_stt_worker:app --host 0.0.0.0 --port 8001`

---

## Recent Decisions

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-01-18 | Activity-based LLM config | Granular control: fast/cheap models for classification, quality models for conversation |
| 2026-01-17 | OpenRouter for LLM API | Multi-model support, good pricing, reliable |
| 2026-01-17 | Multi-agent model config | Different models per agent type (SkyrimNet pattern) |
| 2026-01-17 | Signal logging to Redis | Full observability for dashboard request inspector |
| 2026-01-17 | Parakeet TDT 0.6B v2 for GPU STT | 45ms latency, 53x faster than CPU |
| 2026-01-17 | Separate .venv-gpu for GPU worker | Isolate heavy NeMo deps from main venv |
| 2026-01-17 | Hybrid Claude+Copilot workflow | Claude for planning, Copilot for execution |
| 2026-01-17 | Docker on Man-of-war for local dev | Redis needed locally during development |
| 2026-01-17 | Voice: bm_fable (British male) | Best fit for Barnabee persona |

---

## Blocking Issues

None currently.

### Resolved
- **WSL2 Network Access** (2026-01-17): Configured Windows port forwarding. VM reaches GPU worker at `192.168.86.61:8001`

---

## Session Notes

_Use this section for temporary notes during a session. Clear when done._

---

## Files Reference

| File | Purpose |
|------|---------|
| `CONTEXT.md` | This file - Copilot's memory |
| `barnabeenet-project-log.md` | Detailed project history |
| `claude-project-rules.md` | Rules for Claude sessions |
| `.github/copilot-instructions.md` | Rules for Copilot agent |
| `.copilot/sessions/` | Session plans and results |
