# BarnabeeNet Quick Reference

**Last Updated:** January 17, 2026  
**Status:** 📚 Reference

---

## Technology Stack (Current)

| Component | Technology | Version | Location |
|-----------|------------|---------|----------|
| **STT (Primary)** | Parakeet TDT 0.6B v2 | 1.22+ | Man-of-war GPU (192.168.86.100) |
| **STT (Fallback)** | Distil-Whisper | 1.0+ | Beelink CPU (192.168.86.51) |
| **TTS** | Kokoro | 0.3+ | Beelink (in-process) |
| **Speaker ID** | ECAPA-TDNN | 1.0+ | Beelink (SpeechBrain) |
| **LLM Gateway** | OpenRouter | 1.0+ | Cloud (primary) |
| **LLM Benchmarking** | Azure ML | 2.0+ | Cloud (Evolver Agent only) |
| **Database** | SQLite + sqlite-vec | 3.45+ | Beelink |
| **Cache** | Redis | 7.0+ | Beelink |
| **Platform** | Home Assistant | 2025.12+ | Beelink |

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

## Latency Targets

| Stage | Target | Implementation |
|-------|--------|----------------|
| STT (GPU) | ~20-40ms | Parakeet TDT |
| STT (CPU) | ~150-300ms | Distil-Whisper |
| TTS | ~50ms | Kokoro |
| Speaker ID | ~20ms | ECAPA-TDNN |
| Meta Agent | <20ms | Rule-based |
| Action Agent | <100ms | Cloud LLM |
| Interaction Agent | <3s | Cloud LLM |
| **Total (Action)** | **<500ms** | End-to-end |

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
  voice: af_bella  # Options: af_bella, af_nicole, am_adam, am_michael
  speed: 1.0
  sample_rate: 24000

stt:
  primary:
    engine: parakeet
    model: nvidia/parakeet-tdt-0.6b-v2
    device: cuda
    host: 192.168.86.100
    port: 8001
  fallback:
    engine: distil-whisper
    model: distil-whisper/distil-small.en
    device: cpu
```

---

## Key Design Decisions

- **Cloud LLM Only:** All LLM reasoning via OpenRouter (no local LLM)
- **Azure ML:** Only for Evolver Agent benchmarking/evaluations
- **Dual-Path STT:** GPU primary (fast), CPU fallback (reliable)
- **Local Processing:** Audio capture, STT, TTS, Speaker ID all local
- **Privacy:** Raw audio never leaves network; only text transcripts to LLM

---

## Project Status

**Current Phase:** Phase 1 - Core Services (In Progress)

- [x] Foundation setup (VM, Redis)
- [ ] STT pipeline (Distil-Whisper + Parakeet)
- [ ] TTS pipeline (Kokoro)
- [ ] GPU worker setup
- [ ] Health check routing

---

## Documentation Status

| Document | Status |
|----------|--------|
| Technical Architecture | 📋 Planning |
| Implementation Guide | 📋 Planning |
| Features & Use Cases | 📚 Reference |
| Theory Research | 📚 Reference |
| Operations Runbook | 📋 Planning |
| Hardware Specs | 📚 Reference |

**Legend:** 📋 Planning | 🔄 In Progress | ✅ Implemented | 📚 Reference
