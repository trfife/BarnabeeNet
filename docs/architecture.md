# BarnabeeNet Architecture

> Full architecture documentation for the BarnabeeNet smart home AI system.

## Quick Reference

| Component | Technology | Location |
|-----------|------------|----------|
| Hypervisor | Proxmox VE 8.x | Battlestation |
| VM OS | NixOS 24.11 (or Ubuntu 24.04) | BarnabeeNet VM |
| Containers | Podman (rootless) | BarnabeeNet VM |
| Home Automation | Home Assistant Core | Container |
| LLM Gateway | LiteLLM Proxy | Container |
| STT (CPU) | Distil-Whisper | BarnabeeNet Core |
| STT (GPU) | Parakeet TDT 0.6B v2 | Man-of-war Worker |
| TTS | Kokoro | BarnabeeNet Core |
| Speaker ID | Pyannote 3.x | Container |
| Agent Framework | PydanticAI | BarnabeeNet Core |
| Database | SQLite + sqlite-vec | Local |
| Cache | Redis (Valkey) | Container |
| Observability | VictoriaMetrics + Grafana | Containers |

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
                    │   Multi-Modal    │
                    │   Input (Voice/  │
                    │   Gesture/AR)    │
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │  Speaker ID +    │
                    │  STT Pipeline    │
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │   Meta Agent     │
                    │  (Router/Triage) │
                    └────────┬─────────┘
           ┌─────────────────┼─────────────────┐
           │                 │                 │
    ┌──────▼──────┐  ┌───────▼───────┐  ┌──────▼──────┐
    │   Instant   │  │    Action     │  │ Interaction │
    │   Response  │  │    Agent      │  │    Agent    │
    │   (~3ms)    │  │   (~50ms)     │  │  (~1-3s)    │
    └─────────────┘  └───────────────┘  └─────────────┘
```

## Latency Budget

| Stage | Target | Implementation |
|-------|--------|----------------|
| Wake word | 0ms | OpenWakeWord (always listening) |
| Audio capture | ~100ms | Streaming buffer |
| Speech-to-Text | <150ms | Faster-Whisper distil-small |
| Speaker ID | ~20ms | Pyannote embeddings |
| Meta Agent routing | <20ms | Rule-based + LLM fallback |
| Specialized agent | <200ms | Varies by type |
| Text-to-Speech | <100ms | Piper |
| **Total (action)** | **<500ms** | |

## Full Documentation

For the complete architecture specification, see the original design document in the project files.
