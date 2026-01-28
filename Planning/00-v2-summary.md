# BarnabeeNet V2: Implementation Summary

**Version:** 2.0  
**Date:** January 2026  
**Status:** Implementation Planning  

---

## Executive Summary

BarnabeeNet V2 is a greenfield rebuild addressing V1's critical failures: latency variance (50ms–2500ms), brittle pattern matching (378 regex patterns), unsafe self-improvement (production crashes), and missing household context. The rebuild prioritizes local-first processing on RTX 4070 Ti, sub-second command latency, and isolated self-improvement.

### V1 → V2 Migration Goals

| Metric | V1 Current | V2 Target | Improvement |
|--------|-----------|-----------|-------------|
| Command latency (P95) | 2,500ms | <800ms | 3x faster |
| Intent accuracy | ~70% (estimated) | >95% | +25 points |
| Self-improvement incidents | 3+ production crashes | Zero | Eliminated |
| HA context awareness | None ("I don't track locations") | Full | Complete |
| Persona consistency | Multiple personalities | Single Barnabee | Unified |

### Core Architectural Decisions

| Decision | V1 Approach | V2 Approach | Rationale |
|----------|-------------|-------------|-----------|
| STT | External (HA/Mentra) | Local (Parakeet) | Eliminates 300-500ms hop |
| TTS | External (HA/Mentra) | Local (Kokoro) | Eliminates 200-400ms hop |
| Intent classification | 378 regex + LLM fallback | Embedding classifier + LLM fallback | 95%+ accuracy, <50ms |
| Data layer | SQLite + 12 LLM providers | SQLite + sqlite-vss + Redis (session only) | Simplified, adequate |
| Voice pipeline | Custom sequential | Pipecat (full-duplex) | Production-tested, handles complexity |
| Self-improvement | Direct code modification | Data-only changes + human approval | Prevents cascading failures |
| **Error handling** | **"I don't know"** | **LLM intelligent fallback** | **Always make an attempt** |

### Design Philosophy: Graceful Fallbacks

**Critical Principle:** The system should NEVER respond with "I don't know" or "I can't find that."

When the fast path fails (pattern match, entity resolution, etc.), the LLM is used as an intelligent fallback with FULL CONTEXT:
- All Home Assistant entities
- User's current location
- Recent commands
- The original utterance

With this context, the LLM can always make an intelligent guess. The system executes the most likely interpretation and offers to correct if wrong. Corrections feed into self-improvement.

See `03-intent-classification.md` section 9.3 for implementation.

---

## Implementation Areas

The V2 implementation is divided into **24 discrete areas**, each with its own specification document. Areas are designed to be implemented sequentially with clear integration points.

### Area Index

| Area | Name | Dependencies | Phase |
|------|------|--------------|-------|
| 01 | Core Data Layer | None | Infrastructure |
| 02 | Voice Pipeline | Area 01 | Infrastructure |
| 03 | Intent Classification & NLU | Area 01 | Backbone |
| 04 | Home Assistant Integration | Area 01, 03 | Backbone |
| 05 | Memory System | Area 01, 03 | Data |
| 06 | Response Generation & Persona | Area 01, 03, 04, 05 | Core Functionality |
| 07 | Meeting/Scribe System | Area 01, 02, 05 | Extended Functionality |
| 08 | Self-Improvement Pipeline | Area 01, 03 | Extended Functionality |
| 09 | Dashboard & Admin | Area 01, 05, 07 | Extended Functionality |
| 10 | Testing & Observability | All | Parallel (all phases) |
| 11 | Deployment & Infrastructure | All | Parallel (all phases) |
| 12 | Calendar & Email Integration | Area 01 | Extended Functionality |
| 13 | Notifications | Area 01, 09 | Extended Functionality |
| 14 | Multi-Device Coordination | Area 01, 02 | Extended Functionality |
| 15 | API Contracts | All | Parallel (all phases) |
| 16 | Migration Runbook | All | Migration |
| 17 | Security | Area 01, 09, 11, 15 | Parallel (all phases) |
| 18 | Cost Tracking | Area 01, 09, 15 | Extended Functionality |
| 19 | Personal Finance | Area 01, 03, 09, 13, 17 | Extended Functionality |
| 20 | Native Mobile Apps | Area 02, 14, 15 | Extended Functionality |
| 21 | User Profiles | Area 01, 05, 06, 07, 09 | Extended Functionality |
| 22 | Extended Features | Area 01, 03, 04, 06, 09, 13, 21 | Extended Functionality |
| 23 | Implementation Additions | All | Gap Fills & Enhancements |
| 24 | Agent Implementation Guide | All | Execution Guide |

### Area Descriptions

**Area 01: Core Data Layer**  
SQLite database with sqlite-vss for vector search, FTS5 for full-text search, Redis for session state only. Schema for memories, conversations, meetings, HA entity cache, calendar/email cache, todos, notifications, and operational logs.

**Area 02: Voice Pipeline**  
Pipecat integration for full-duplex audio. Local wake word (openWakeWord), VAD (Silero), streaming STT (Parakeet), streaming TTS (Kokoro). WebRTC transport with WebSocket fallback. Barge-in handling and filler audio injection.

**Area 03: Intent Classification & NLU**  
Three-stage classification: fast pattern matching (<10ms), local embedding classifier (<50ms), LLM fallback (<500ms). Entity resolution for HA devices. Intent taxonomy covering home control, information queries, tasks, memory operations, and mode control.

**Area 04: Home Assistant Integration**  
WebSocket subscription for real-time state changes. Entity caching with semantic enhancement (keywords, aliases). Smart context injection (not all 2,291 entities—filtered by relevance). Speculative execution for high-confidence commands.

**Area 05: Memory System**  
Three-tier memory architecture: active (user-facing), soft-deleted (recoverable), operational logs (admin-only). Memory creation from explicit requests, conversations, meetings, and journals. Embedding-based retrieval with progressive narrowing for search.

**Area 06: Response Generation & Persona**  
Unified Barnabee persona across all response paths. Context assembly from memories, HA state, calendar, and email. Response length management with email/SMS delivery for long content. Consistent warm, concise, natural tone.

**Area 07: Meeting/Scribe System**  
Notes mode with continuous transcription. Post-meeting speaker identification workflow. Action item extraction with todo integration. Audio storage with scheduled deletion (30-day default). Meeting search by topic, date, and attendee.

**Area 08: Self-Improvement Pipeline**  
Data-only automated changes (classifier weights, entity aliases, keywords). Human-approved staged changes for patterns and routing. Forbidden tier for core code modifications. Shadow deployment with drift detection. Golden dataset maintenance.

**Area 09: Dashboard & Admin**  
Memory browser with search/edit/delete. Meeting dashboard with transcript playback. Admin-only features: operational log search, deleted memory recovery, system health monitoring, classification metrics.

**Area 10: Testing & Observability**  
Golden dataset (500+ labeled utterances). Property-based testing for NLU invariants. Conversation flow testing. Chaos testing for graceful degradation. Request tracing with latency histograms. Error rate monitoring per component.

**Area 23: Implementation Additions**  
Concurrent multi-user session support with GPU task queuing. GPU health monitoring and OOM recovery. Model version management with rollback. Graceful shutdown with session draining. LLM provider automatic failover. Voice command rate limiting. Wake word false positive tracking. Database maintenance scheduling.

**Area 24: Agent Implementation Guide**  
Step-by-step execution guide for AI coding agents (Cursor/Copilot). Git workflow and commit standards. Testing requirements and coverage targets. Service management with Docker Compose and systemd. Human check-in protocol at phase boundaries. Dashboard build process. Credential management. Error handling guidance. Phase-by-phase implementation checklist.

---

## Implementation Phases

### Phase 1: Infrastructure
**Areas:** 01 (Core Data Layer), 02 (Voice Pipeline)

Foundation that everything else depends on. No features work without these.

**Area 01 - Core Data Layer:**
- Repository setup with clean structure
- SQLite schema implementation
- sqlite-vss integration for vector search
- Redis setup for session state
- Basic CRUD operations
- Migration scripts for V1 data

**Area 02 - Voice Pipeline:**
- Pipecat server deployment
- Wake word model (openWakeWord)
- Local STT (Parakeet on RTX 4070 Ti)
- Local TTS (Kokoro on RTX 4070 Ti)
- WebRTC transport layer
- Filler audio generation and injection

**Milestone:** Voice input → text → voice output working end-to-end

### Phase 2: Backbone
**Areas:** 03 (Intent Classification), 04 (Home Assistant Integration)

The intelligence layer that interprets user intent and connects to the smart home.

**Area 03 - Intent Classification & NLU:**
- Embedding-based local classifier
- Training pipeline from labeled data
- LLM fallback with logging
- Entity extraction
- Golden dataset v1 (200 utterances)

**Area 04 - Home Assistant Integration:**
- HA WebSocket state subscription
- Entity caching with semantic enhancement
- Context injection into prompts
- Speculative execution for high-confidence commands

**Milestone:** "Turn on the lights" and "Where is Thom?" work correctly

### Phase 3: Data
**Areas:** 05 (Memory System)

Persistent knowledge that makes Barnabee actually useful over time.

**Area 05 - Memory System:**
- Memory schema and CRUD
- Embedding generation (ada-002 or local)
- Retrieval with progressive narrowing
- Memory creation from conversations
- Memory deletion with soft-delete

**Milestone:** "Remember that..." and "What did I say about..." work correctly

### Phase 4: Core Functionality
**Areas:** 06 (Response Generation & Persona)

The unified personality and response assembly that ties everything together.

**Area 06 - Response Generation & Persona:**
- Unified Barnabee persona
- Context assembly from memories, HA state, calendar, email
- Long content delivery (email/SMS)
- Consistent warm, concise, natural tone

**Milestone:** Consistent personality across all interaction types

### Phase 5: Extended Functionality
**Areas:** 07 (Meeting/Scribe), 08 (Self-Improvement), 09 (Dashboard)

Advanced features that build on the stable foundation.

**Area 07 - Meeting/Scribe System:**
- Notes mode continuous transcription
- Speaker diarization and identification
- Action item extraction → todo creation
- Audio storage with scheduled deletion

**Area 08 - Self-Improvement Pipeline:**
- Self-improvement data layer
- Shadow deployment infrastructure
- Drift detection and alerting
- Human approval workflow

**Area 09 - Dashboard & Admin:**
- Memory dashboard
- Meeting dashboard with playback
- Admin dashboard (super user features)

**Milestone:** Full meeting captured with action items, self-improvement running safely in shadow mode

### Parallel: Testing & Observability
**Area:** 10 (Testing & Observability)

Runs alongside all phases, expanding as features are added.

- Golden dataset expansion (target: 500+)
- Property-based testing for NLU invariants
- Conversation flow testing
- Chaos testing suite
- Request tracing implementation
- Monitoring dashboards

**Milestone:** 99%+ uptime over soak test, all critical paths covered

---

## Technology Stack

### Core Infrastructure

| Component | Technology | Version | Notes |
|-----------|------------|---------|-------|
| Language | Python | 3.11+ | Async, type hints |
| Web framework | FastAPI | 0.109+ | High performance async |
| Database | SQLite | 3.45+ | With WAL mode |
| Vector search | sqlite-vss | 0.1.2+ | Embedded vector similarity |
| Full-text search | SQLite FTS5 | Built-in | Fast text search |
| Session cache | Redis | 7.2+ | Session state only |
| Task queue | ARQ | 0.26+ | Redis-based, async |

### Voice Pipeline

| Component | Technology | Notes |
|-----------|------------|-------|
| Orchestration | Pipecat | Full-duplex audio framework |
| Transport | WebRTC | Primary, with WebSocket fallback |
| Wake word | openWakeWord | Trainable, HA-integrated |
| VAD | Silero VAD | With SmartTurn for semantic detection |
| STT | NVIDIA Parakeet | Local, <50ms latency |
| TTS | Kokoro | Local, custom voice |

### LLM Integration

| Tier | Provider | Use Case | Latency Budget |
|------|----------|----------|----------------|
| Local | Ollama (Mistral 7B) | Intent classification fallback | <200ms |
| Cloud | Azure OpenAI (GPT-4o) | Complex reasoning, memory extraction | <800ms |
| Cloud | Azure OpenAI (ada-002) | Embeddings | <100ms |

### Hardware

| Component | Specification |
|-----------|--------------|
| Server | Beast (Ubuntu Server) |
| GPU | RTX 4070 Ti Super (16GB VRAM) |
| RAM | 64GB |
| Storage | NVMe SSD |

### System Startup & Pre-Warming

**Critical:** The first request must be as fast as subsequent requests. All models and connections are pre-warmed on startup before accepting traffic.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         STARTUP SEQUENCE                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1. SERVICE STARTUP                                                          │
│     └── Docker containers start                                              │
│     └── Health checks begin failing (expected)                               │
│                                                                              │
│  2. PRE-WARMING PHASE (runs before accepting traffic)                        │
│     ├── GPU Models (sequential, ~30s)                                       │
│     │   ├── STT (Parakeet): Load model, run dummy inference                 │
│     │   ├── TTS (Kokoro): Load model, synthesize "ready" audio              │
│     │   └── Embedding: Load model, embed test query                         │
│     │                                                                        │
│     ├── Database & Cache (parallel, ~2s)                                    │
│     │   ├── SQLite: Open connection, run test query                         │
│     │   └── Redis: Connect, ping, set/get test key                          │
│     │                                                                        │
│     ├── External Connections (parallel, ~5s)                                │
│     │   ├── Home Assistant: WebSocket connect, fetch entities               │
│     │   └── LLM Provider: Test API connection                               │
│     │                                                                        │
│     └── Intent Classifier (~5s)                                             │
│         └── Run 3-5 test classifications to warm caches                     │
│                                                                              │
│  3. HEALTH CHECK PASSES                                                      │
│     └── /health returns 200                                                  │
│     └── Service accepts traffic                                              │
│                                                                              │
│  Total warmup time: ~40-60 seconds                                          │
│  First request latency: Same as subsequent requests                          │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Implementation:** See `scaffold/src/barnabee/warmup.py`

---

## Success Metrics

### Latency Targets

| Path | P50 | P95 | P99 |
|------|-----|-----|-----|
| Fast (command, pattern match) | 400ms | 600ms | 800ms |
| Standard (command, LLM classify) | 800ms | 1,200ms | 1,500ms |
| Conversation (multi-turn) | 1,000ms | 1,500ms | 2,000ms |
| Memory search | 1,200ms | 1,800ms | 2,500ms |

### Accuracy Targets

| Metric | Target |
|--------|--------|
| Intent classification accuracy | >95% |
| Entity resolution accuracy | >98% |
| Wake word false negative rate | <2% |
| Wake word false positive rate | <0.5/hour |

### Reliability Targets

| Metric | Target |
|--------|--------|
| System uptime | >99.5% |
| Mean time to recovery (MTTR) | <5 minutes |
| Self-improvement incidents | 0 |
| Data loss incidents | 0 |

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Pipecat integration complexity | Medium | High | Early PoC in Phase 1, fallback to sequential pipeline |
| Local STT accuracy insufficient | Low | High | Benchmark Parakeet vs Whisper, cloud fallback option |
| Self-improvement causes regression | Medium | Critical | Data-only changes, shadow deployment, human approval |
| Embedding classifier accuracy plateau | Medium | Medium | Expand training data, ensemble with patterns |
| Family adoption resistance | Medium | High | Gradual rollout, start with power users |

---

## Build Approach

### Greenfield Implementation

This is a **greenfield build** - no migration from V1. The system is built from scratch following the planning documents.

### Implementation Guide

See `24-agent-implementation-guide.md` and `START-HERE.md` for:
- Step-by-step build instructions
- Agent autonomy rules
- Progress tracking
- Phase milestones

---

## Document Inventory

| Document | Status | Description |
|----------|--------|-------------|
| 00-v2-summary.md | Complete | This document |
| 01-core-data-layer.md | Complete | Database schema, caching, migrations |
| 02-voice-pipeline.md | Complete | Pipecat integration, audio processing |
| 03-intent-classification.md | Complete | NLU pipeline, entity resolution |
| 04-home-assistant.md | Complete | HA integration, context injection |
| 05-memory-system.md | Complete | Memory tiers, retrieval, progressive narrowing |
| 06-response-generation.md | Complete | Persona, context assembly, delivery |
| 07-meeting-scribe.md | Complete | Transcription, speaker ID, action items |
| 08-self-improvement.md | Complete | Safe improvement pipeline |
| 09-dashboard.md | Complete | Admin interfaces |
| 10-testing-observability.md | Complete | Test strategy, monitoring |
| 11-deployment-infrastructure.md | Complete | Proxmox, Docker, GPU passthrough, backup |
| 12-calendar-email.md | Complete | Google Calendar/Gmail integration |
| 13-notifications.md | Complete | Push, SMS, voice notifications |
| 14-multi-device.md | Complete | Wake word arbitration, device coordination |
| 15-api-contracts.md | Complete | OpenAPI spec, LLM abstraction |
| 16-migration-runbook.md | Reference | Deployment procedures (V1 migration not needed - greenfield) |
| 17-security.md | Complete | Home network security, auth, secrets |
| 18-cost-tracking.md | Complete | Operating cost analysis, budgets |
| 19-personal-finance.md | Complete | SimpleFIN integration, budgets, goals |
| 20-native-apps.md | Complete | Android/iOS apps, default assistant |
| 21-user-profiles.md | Complete | Enhanced profiles, personalization |
| 22-extended-features.md | Complete | Shopping, recipes, packages, routines, kids, habits, inventory, language learning, guest mode, briefings, intercom, appliances |
| 23-implementation-additions.md | Complete | Concurrent sessions, GPU recovery, model versioning, graceful shutdown, LLM failover, rate limiting, wake word tracking, DB maintenance |
| 24-agent-implementation-guide.md | Complete | Agent execution guide, git workflow, testing requirements, service management, check-in protocol, phase checklists |
| 25-agent-guide-addendum.md | Complete | Parallelization opportunities, mock HA testing, dashboard config management, scaffold usage |
| START-HERE.md | Complete | **Kickoff prompt** - copy/paste to start the agent building |
| scaffold/ | Complete | **Implementation scaffold** - pre-built project structure, dependencies, interfaces, test fixtures |

---

## Immediate Next Steps

1. **Review this summary document** for alignment with goals
2. **Approve or modify** area boundaries and phase sequencing
3. **Proceed to Area 01** (Core Data Layer) specification
4. **Iterate** through remaining areas with review after each

---

## Appendix A: V1 Critical Failures (Reference)

These failures drive V2 architectural decisions:

### Failure 1: Latency Variance (50ms–2500ms)
**Root cause:** Bimodal pattern matching—commands that should match patterns sometimes don't, triggering full LLM pipeline.  
**V2 fix:** Embedding-based classification with consistent latency profile.

### Failure 2: Pattern Brittleness (378 Regex)
**Root cause:** Anchored patterns (`^what time is it$`) fail on minor variations.  
**V2 fix:** Embedding similarity handles natural language variation.

### Failure 3: Self-Improvement Instability
**Root cause:** Direct code modification without isolation, testing, or rollback.  
**V2 fix:** Data-only automated changes, staged human-approved changes, forbidden code tier.

### Failure 4: Missing HA Context
**Root cause:** LLM doesn't know household state—returns "I don't track locations" when HA has data.  
**V2 fix:** Smart context injection from HA entity cache.

### Failure 5: Persona Inconsistency
**Root cause:** Different agents with different response styles (joke agent vs. timer agent).  
**V2 fix:** Single response generation path with unified Barnabee persona.

---

## Appendix B: Glossary

| Term | Definition |
|------|------------|
| **Barge-in** | User interruption during system audio output |
| **Embedding** | Vector representation of text for similarity search |
| **Entity resolution** | Mapping natural language to HA entity IDs |
| **Filler** | Pre-generated audio played during processing |
| **Golden dataset** | Curated test cases from production corrections |
| **Progressive narrowing** | Multi-turn search refinement (show 3, ask if more) |
| **Shadow deployment** | Testing new models against production traffic without affecting responses |
| **SmartTurn** | Semantic end-of-turn detection (vs. silence-based) |
| **Soft delete** | Hidden but recoverable (vs. hard delete) |
| **Speculative execution** | Starting action before response generation for high-confidence commands |
| **sqlite-vss** | SQLite extension for vector similarity search |
| **VAD** | Voice Activity Detection |

---

**End of V2 Summary Document**
