# BarnabeeNet Quick Reference

**Last Updated:** January 2026  
**Status:** 📚 Reference

> **Live status:** See **CONTEXT.md** for “what’s working” and next steps.

---

## Technology Stack (Current)

| Component | Technology | Location / Notes |
|-----------|------------|------------------|
| **STT (Primary)** | Parakeet TDT 0.6B v2 | Man-of-war GPU (~45ms); VM reaches worker at `192.168.86.61:8001` |
| **STT (Fallback)** | Distil-Whisper | VM/Beelink CPU (~2.4s) |
| **STT (Cloud)** | Azure Speech | Optional; mobile/remote |
| **TTS** | Kokoro-82M | VM (in-process), voice `bm_fable`, ~232–537ms |
| **Speaker** | Contextual | From HA user, request `speaker`/`room`, or family profiles. *Voice-based ECAPA-TDNN not implemented.* |
| **LLM** | OpenRouter (primary) | 12 providers, activity-based models, encrypted secrets in Redis |
| **Memory** | Redis | Embeddings (all-MiniLM-L6-v2), vector similarity, working + long-term. *SQLite/sqlite-vec not used.* |
| **Cache / Bus** | Redis | Streams, signals, secrets, config |
| **Platform** | Home Assistant | REST + WebSocket; custom conversation agent in `ha-integration/` |

---

## LLM Models (OpenRouter Format)

### Fast Tier (Meta Agent, Action Agent)
- **Primary:** `deepseek/deepseek-v3`
- **Fallback:** `google/gemini-2.0-flash-001`, `anthropic/claude-3-haiku`

### Quality Tier (Interaction Agent)
- **Primary:** `anthropic/claude-3.5-sonnet`
- **Fallback:** `openai/gpt-4o`

### Summarization Tier (Memory Agent)
- **Primary:** `openai/gpt-4o-mini`
- **Fallback:** `anthropic/claude-3-haiku`

---

## Latency (Observed / Targets)

| Stage | Observed | Notes |
|-------|----------|-------|
| STT (GPU) | ~45ms | Parakeet TDT 0.6B v2 |
| STT (CPU) | ~2.4s | Distil-Whisper |
| TTS | 232–537ms | Kokoro, bm_fable |
| Meta Agent | <20ms | Pattern + LLM fallback |
| Action Agent | <100ms | Cloud LLM + HA call |
| Interaction Agent | <3s | Cloud LLM |
| **Total (action path)** | **<500ms** | When GPU STT and fast models used |

---

## Hardware

| System | IP | Role |
|--------|-----|------|
| **Man-of-war** | 192.168.86.100 | GPU worker (Parakeet STT) |
| **Battlestation** | 192.168.86.64 | Proxmox host |
| **BarnabeeNet VM** | 192.168.86.51 | Runtime (Beelink) |

---

## Voice Configuration

```yaml
tts:
  engine: kokoro
  voice: bm_fable   # British male; also af_bella, af_nicole, am_adam, am_michael
  speed: 1.0
  sample_rate: 24000

stt:
  gpu_worker_host: 192.168.86.61   # from VM; Man-of-war via port forward
  gpu_worker_port: 8001
  # fallback: distil-whisper (distil-small.en) on CPU
```

---

## Key Design Decisions

- **Cloud LLM only:** All LLM via OpenRouter (12 providers, activity-based models). *Evolver Agent and Azure ML not implemented.*
- **Dual-path STT:** Parakeet (GPU) primary, Distil-Whisper (CPU) fallback; Azure for mobile/remote.
- **Local:** Audio capture, STT, TTS on our hardware. **Speaker:** from HA user, request, or family profiles (voice-based ECAPA-TDNN deferred).
- **Memory:** Redis for working + long-term memory and vector similarity; no SQLite/sqlite-vec in use.
- **Privacy:** Raw audio stays on the network; only text goes to LLM providers.

---

## Project Status

**Phases 1–4:** ✅ Complete (Core, Voice, Agents, HA). **Phase 5–6:** 🔄 Partial (dashboard, Azure STT, tiered STT, VM deploy, tests; ViewAssist, mobile, Proactive/Evolver deferred).

- [x] STT (Parakeet + Distil-Whisper + Azure), TTS (Kokoro), GPU worker, health-check routing
- [x] Meta, Instant, Action, Interaction, Memory, Profile agents; Orchestrator
- [x] HA client, topology, compound commands, timers, conversation agent, mock HA for E2E
- [x] Dashboard (Chat, Memory, HA, Config, Prompts, Logs), observability
- [ ] ViewAssist integration (APIs ready), mobile client (placeholder), Proactive/Evolver, voice Speaker ID

See **barnabeenet-project-log.md** for phase details; **CONTEXT.md** for live checklist.

---

## Documentation Status

| Document | Status |
|----------|--------|
| **CONTEXT.md** | ✅ Live status, next steps |
| **barnabeenet-project-log.md** | ✅ Phases, decisions, deferred |
| **docs/architecture.md** | 📚 As-built reference |
| **docs/INTEGRATION.md** | ✅ HA, ViewAssist, Chat API |
| **docs/QUICK_REFERENCE.md** | 📚 This file |
| **BarnabeeNet_README_v3.2.md** | 📚 Vision and spec |
| **BarnabeeNet_Technical_Architecture.md** | 📚 Spec (some parts ahead of code) |
| **BarnabeeNet_Implementation_Guide.md** | 📚 Spec (SQLite, ECAPA, etc. deferred) |
| **BarnabeeNet_Operations_Runbook.md** | 📚 Ops reference |
| **docs/BarnabeeNet_Pipeline_Management_Dashboard.md** | 📋 Planned (Phase 7, after HA); implementation spec |
| **docs/future/MOBILE_STT_CLIENT.md** | 📋 Placeholder |

**Legend:** 📋 Planning/placeholder | 📚 Reference | ✅ Maintained
