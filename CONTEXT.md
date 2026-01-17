# BarnabeeNet Project Context

> **This file is Copilot's "memory". Update it after each work session.**

## Last Updated
2026-01-17 (after STT/TTS testing + Copilot workflow setup)

## Current Phase
**Phase 1: Core Services** - Steps 1-4 Complete, Step 5 Next

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
- [x] **STT (Distil-Whisper)** - Working, ~2.4s latency (warm), ~30s first request
- [x] **TTS (Kokoro)** - Working, 232-537ms latency, voice: bm_fable
- [x] Pronunciation fixes (Viola→Vyola, Xander→Zander)
- [x] Copilot agent configuration validated

### In Progress
- [ ] **GPU Worker (Parakeet on Man-of-war)** - HIGH PRIORITY

### Not Started
- [ ] Message bus (Redis Streams)
- [ ] Voice pipeline integration
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
| GPU Worker | Man-of-war RTX 4070 Ti - **NOT YET SET UP** |

---

## Next Steps (Ordered)

1. **Set up GPU Worker (Parakeet TDT) on Man-of-war** ← NEXT
   - Install CUDA toolkit in WSL
   - Install PyTorch with CUDA
   - Install NeMo/Parakeet
   - Create FastAPI worker at `workers/gpu_stt_worker.py`
   - Test: Should achieve ~20-40ms STT latency

2. Implement STT Router (GPU primary, CPU fallback)

3. Deployment scripts

4. Tests for STT/TTS services

5. Message bus implementation (Redis Streams)

---

## STT/TTS Performance Baseline

| Service | Engine | Latency | Notes |
|---------|--------|---------|-------|
| STT (CPU) | Distil-Whisper | ~2.4s warm, ~30s cold | Fallback option |
| STT (GPU) | Parakeet TDT 0.6B | ~20-40ms target | NOT YET SET UP |
| TTS | Kokoro-82M | 232-537ms | Working, voice: bm_fable |

---

## Recent Decisions

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-01-17 | Hybrid Claude+Copilot workflow | Claude for planning, Copilot for execution |
| 2026-01-17 | GPU Worker is next priority | CPU STT too slow (2.4s), need <100ms |
| 2026-01-17 | Docker on Man-of-war for local dev | Redis needed locally during development |
| 2026-01-17 | Voice: bm_fable (British male) | Best fit for Barnabee persona |

---

## Blocking Issues

None currently.

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
