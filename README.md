# BarnabeeNet

A privacy-first, multi-agent AI smart home assistant built on Home Assistant.

## Overview

BarnabeeNet provides Alexa/Google-level responsiveness (<500ms) while maintaining complete data sovereignty. All voice and gesture data is processed locally unless explicitly requested otherwise.

## Architecture

- **Runtime Server:** Beelink EQi12 (Battlestation) - Always-on edge processing
- **Compute Server:** Gaming PC (Man-of-war) - On-demand heavy LLM inference
- **Core Platform:** Home Assistant with custom BarnabeeNet integration

## Core Principles

1. **Privacy by Architecture** — Voice data never leaves the local network unless explicitly requested
2. **Latency-Obsessed** — Target <500ms end-to-end for common commands
3. **Family-Aware** — Speaker recognition enables permission-based control
4. **Graceful Degradation** — System remains functional when cloud services are unavailable
5. **Cost-Conscious** — Intelligent routing minimizes expensive LLM calls
6. **Self-Improving** — Evolves its own prompts and models within scoped boundaries

## Project Status

🚧 **Phase 0: Foundation Setup** - In Progress

See [docs/project-log.md](docs/project-log.md) for detailed progress.

## Documentation

- [Architecture](docs/architecture.md) - Full system design
- [Project Log](docs/project-log.md) - Build progress and decisions
- [Runbook](docs/runbook.md) - Operations guide (coming soon)

## License

Private - All rights reserved
