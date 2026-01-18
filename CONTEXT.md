# BarnabeeNet Project Context

> **This file is Copilot's "memory". Update it after each work session.**

## Last Updated
2026-01-17 (after ActionAgent implementation)

## Current Phase
**Phase 1: Core Services** - Steps 1-9 Complete + MetaAgent + InstantAgent + ActionAgent

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
- [x] **OpenRouter LLM client** - Multi-agent model config, full signal logging
- [x] **Signal logging system** - Every LLM call logged for dashboard visibility
- [x] **MetaAgent** - Intent classification, context/mood evaluation, memory query generation
- [x] **InstantAgent** - Zero-latency responses for time, date, greetings, math
- [x] **ActionAgent** - Device control parsing, rule-based + LLM fallback, HA service calls

### In Progress
- [ ] Remaining agent implementations (interaction, memory)

### Not Started
- [ ] Agent implementations
- [ ] Memory system
- [ ] Home Assistant integration

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

1. Remaining agent implementations (interaction, memory) ← NEXT

2. Memory system

3. Home Assistant integration

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
