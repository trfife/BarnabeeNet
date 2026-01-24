# BarnabeeNet

A privacy-first, multi-agent AI smart home assistant built on Home Assistant. Local STT/TTS; speaker from HA user, request, or family profiles; cloud LLM via OpenRouter.

## Overview

BarnabeeNet targets Alexa/Google-level responsiveness (<500ms) while keeping audio on your network. Voice capture, speech recognition, and TTS run locally. Speaker identity comes from Home Assistant user, request context, or family profiles (voice-based speaker ID is deferred). LLM reasoning uses OpenRouter; Azure STT is optional for mobile/remote.

## Architecture

- **Runtime:** BarnabeeNet VM (Beelink, NixOS) — Always-on: agents, API, dashboard, Redis, TTS, CPU STT fallback
- **GPU STT:** Man-of-war (Gaming PC) — Parakeet TDT worker for low-latency transcription
- **Platform:** Home Assistant with custom BarnabeeNet conversation agent

## Core Principles

1. **Privacy by Architecture** — Raw audio stays on the local network; only text goes to LLM providers
2. **Latency-Obsessed** — <500ms end-to-end for action-style commands when using GPU STT
3. **Family-Aware** — Speaker from HA, request, or profiles; permission-aware control
4. **Graceful Degradation** — CPU STT fallback, optional cloud STT; works when GPU or cloud is down
5. **Cost-Conscious** — Activity-based model choice, instant/action agents avoid LLM when possible
6. **Self-Improving** — *Planned* (Evolver Agent); not yet implemented

## Project Status

✅ **Phases 1–4 done** (Core, Voice, Agents, HA). 🔄 **Phases 5–6 partial** (dashboard, Azure STT, deploy, tests). Next: ViewAssist integration, mobile client.

- **Live status:** [CONTEXT.md](CONTEXT.md)
- **Phases and deferred:** [barnabeenet-project-log.md](barnabeenet-project-log.md)

## Documentation

| Doc | Purpose |
|-----|---------|
| [CONTEXT.md](CONTEXT.md) | Current status, next steps |
| [docs/architecture.md](docs/architecture.md) | As-built architecture |
| [docs/QUICK_REFERENCE.md](docs/QUICK_REFERENCE.md) | Stack, config, latency |
| [docs/INTEGRATION.md](docs/INTEGRATION.md) | HA, ViewAssist, Chat API |
| [barnabeenet-project-log.md](barnabeenet-project-log.md) | Phases, decisions, deferred |
| [docs/BarnabeeNet_Operations_Runbook.md](docs/BarnabeeNet_Operations_Runbook.md) | Operations |

## License

Private - All rights reserved
