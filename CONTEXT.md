# BarnabeeNet Project Context

> **This file is Copilot's "memory". Update it after each work session.**

## Last Updated
2025-01-17 (after Phase 1 Step 2 completion)

## Current Phase
**Phase 1: Core Services** - Step 2 Complete

## Project State

### What's Working
- [x] Development environment (WSL + Cursor)
- [x] BarnabeeNet VM running NixOS 24.11
- [x] Redis container auto-starting on VM
- [x] Basic project structure created
- [x] FastAPI app skeleton with health endpoint

### In Progress
- [ ] Message bus implementation (Redis Streams)
- [ ] Voice pipeline skeleton

### Not Started
- [ ] Agent implementations
- [ ] STT/TTS integration
- [ ] Memory system
- [ ] Home Assistant integration

## Environment Quick Reference

| Resource | Location |
|----------|----------|
| Dev workspace | `/home/thom/projects/barnabeenet` (WSL) |
| VM runtime | `thom@192.168.86.51:~/barnabeenet` |
| Redis | `192.168.86.51:6379` |
| GPU Worker | Man-of-war (192.168.86.100) - not yet set up |

## Recent Decisions

| Date | Decision | Rationale |
|------|----------|-----------|
| 2025-01-17 | FastAPI over Flask | Async-native, Pydantic integration |
| 2025-01-17 | Redis Streams for bus | Persistence, consumer groups, exactly-once |
| 2025-01-16 | NixOS for VM | Reproducible, declarative config |

## Files Changed Recently
```
src/barnabeenet/
├── config.py          # Settings via pydantic-settings
├── main.py            # FastAPI app factory
└── api/routes/
    ├── health.py      # Health check endpoint
    └── voice.py       # Voice endpoint skeleton
```

## Next Steps (Ordered)

1. Implement `MessageBus` class with Redis Streams
2. Create `VoicePipeline` skeleton
3. Implement `MetaAgent` (request router)
4. Add integration tests

## Blocking Issues

None currently.

## Session Notes

_Use this section for temporary notes during a session. Clear when done._

---