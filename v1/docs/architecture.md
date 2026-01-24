# BarnabeeNet Architecture

> As-built architecture for the BarnabeeNet smart home AI system.  
> For vision and deferred items (e.g. ECAPA, SQLite, Proactive/Evolver), see **BarnabeeNet_README_v3.2.md** and **BarnabeeNet_Technical_Architecture.md**.

## Quick Reference

| Component | Technology | Location / Notes |
|-----------|------------|------------------|
| Hypervisor | Proxmox VE 8.x | Battlestation |
| VM OS | NixOS 24.11 | BarnabeeNet VM |
| Containers | Podman (rootless) | BarnabeeNet VM (e.g. Redis) |
| Home Assistant | HA Core | Separate; BarnabeeNet talks via REST + WebSocket |
| LLM | OpenRouter | 12 providers, activity-based; no LiteLLM |
| STT (CPU) | Distil-Whisper | VM fallback (~2.4s) |
| STT (GPU) | Parakeet TDT 0.6B v2 | Man-of-war worker (~45ms); Azure optional for remote |
| TTS | Kokoro-82M | VM, voice `bm_fable` |
| Speaker | Contextual | HA user, request, or family profiles. *Voice-based ECAPA-TDNN not implemented.* |
| Agents | Custom | Meta, Instant, Action, Interaction, Memory, Profile; Orchestrator |
| Memory | Redis | Working + long-term, embeddings (all-MiniLM-L6-v2), vector similarity. *SQLite/sqlite-vec not used.* |
| Cache / Bus | Redis | Streams, signals, config, secrets |
| Observability | Prometheus + Grafana | See `infrastructure/` |

## Network Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Home Network                              │
│                                                              │
│  ┌─────────────────┐         ┌─────────────────────────┐    │
│  │  Battlestation  │         │     Smart Devices       │    │
│  │    (Beelink)    │◄───────►│  (Zigbee/Z-Wave/WiFi)   │    │
│  │  192.168.86.64  │         └─────────────────────────┘    │
│  │                 │                                         │
│  │  ┌───────────┐  │         ┌─────────────────────────┐    │
│  │  │ Proxmox   │  │         │      Man-of-war         │    │
│  │  │           │  │◄───────►│     (Gaming PC)         │    │
│  │  │ ┌───────┐ │  │         │   On-demand compute     │    │
│  │  │ │BarNet │ │  │         └─────────────────────────┘    │
│  │  │ │  VM   │ │  │                                         │
│  │  │ └───────┘ │  │                                         │
│  │  └───────────┘  │                                         │
│  └─────────────────┘                                         │
└─────────────────────────────────────────────────────────────┘
```

## Multi-Agent Architecture

```
                    ┌──────────────────┐
                    │   Input (Voice,  │
                    │   Text, HA/      │
                    │   ViewAssist)    │
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │  STT Pipeline    │  ← Speaker from HA user, request, or profiles
                    │  (or text)       │
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │   Meta Agent     │
                    │  (Router/Triage) │
                    └────────┬─────────┘
           ┌─────────────────┼─────────────────┬─────────────────┐
           │                 │                 │                 │
    ┌──────▼──────┐  ┌───────▼───────┐  ┌──────▼──────┐  ┌───────▼───────┐
    │   Instant   │  │    Action     │  │ Interaction │  │    Memory     │
    │   (~3ms)    │  │   (~50ms)     │  │  (~1-3s)    │  │   + Profile   │
    └─────────────┘  └───────────────┘  └─────────────┘  └───────────────┘
```

*Proactive and Evolver agents are not implemented.*

## Latency (As-Built)

| Stage | Observed / Target | Implementation |
|-------|-------------------|----------------|
| Wake word | — | *Out of scope:* handled by HA Cloud / ViewAssist / client |
| Speech-to-Text (GPU) | ~45ms | Parakeet TDT 0.6B v2 (primary) |
| Speech-to-Text (CPU) | ~2.4s | Distil-Whisper small.en (fallback) |
| Speaker | — | From context (HA, request, profiles); no voice-based ID |
| Meta Agent | <20ms | Pattern + LLM fallback |
| Action / Instant | <100ms | HA call or template |
| Interaction | <3s | OpenRouter LLM |
| Text-to-Speech | 232–537ms | Kokoro-82M |
| **Total (action path)** | **<500ms** | When GPU STT and fast path used |

## More

- **CONTEXT.md** – Current status and next steps  
- **docs/QUICK_REFERENCE.md** – Stack and config  
- **BarnabeeNet_README_v3.2.md**, **BarnabeeNet_Technical_Architecture.md** – Full spec (includes deferred pieces)
