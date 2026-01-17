# BarnabeeNet Project Context

> **This file is Copilot's "memory". Update it after each work session.**

## Last Updated
2026-01-17 (after GPU Worker setup - Parakeet TDT 0.6B v2)

## Current Phase
**Phase 1: Core Services** - Steps 1-5 Complete, GPU Worker operational

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

### In Progress
- [ ] **STT Router (GPU primary, CPU fallback)** - NEXT
- [ ] WSL port forwarding for VM→GPU Worker access

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
| GPU Worker | `localhost:8001` (Man-of-war WSL, Parakeet TDT) |
| GPU venv | `.venv-gpu/` (separate from main `.venv/`) |

---

## Next Steps (Ordered)

1. **Configure WSL2 port forwarding for VM access** ← NEXT
   - Run in PowerShell (Admin): `netsh interface portproxy add v4tov4 ...`
   - Add Windows Firewall rule for port 8001
   - Test: VM should reach `http://192.168.86.100:8001/health`

2. **Implement STT Router (GPU primary, CPU fallback)**
   - Create `src/barnabeenet/services/stt/router.py`
   - Health-check GPU worker, fallback to Distil-Whisper

3. Deployment scripts

4. Tests for STT/TTS services

5. Message bus implementation (Redis Streams)

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
| 2026-01-17 | Parakeet TDT 0.6B v2 for GPU STT | 45ms latency, 53x faster than CPU |
| 2026-01-17 | Separate .venv-gpu for GPU worker | Isolate heavy NeMo deps from main venv |
| 2026-01-17 | Hybrid Claude+Copilot workflow | Claude for planning, Copilot for execution |
| 2026-01-17 | Docker on Man-of-war for local dev | Redis needed locally during development |
| 2026-01-17 | Voice: bm_fable (British male) | Best fit for Barnabee persona |

---

## Blocking Issues

**WSL2 Network Access**: GPU worker runs on WSL NAT network (172.31.x.x). VM cannot reach it directly. Requires Windows port forwarding:
```powershell
# In PowerShell (Admin):
netsh interface portproxy add v4tov4 listenport=8001 listenaddress=0.0.0.0 connectport=8001 connectaddress=$(wsl hostname -I | cut -d' ' -f1)
New-NetFirewallRule -DisplayName "WSL GPU Worker" -Direction Inbound -LocalPort 8001 -Protocol TCP -Action Allow
```

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
