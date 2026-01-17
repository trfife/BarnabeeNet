# BarnabeeNet Copilot Agent Instructions

## Project Overview

BarnabeeNet is a privacy-first, multi-agent AI smart home assistant inspired by SkyrimNet's architecture. It runs locally on a NixOS VM with GPU offload to a Windows machine for STT.

## Environment

| Machine | Role | Access |
|---------|------|--------|
| Man-of-war (WSL) | Development | Local workspace |
| barnabeenet VM (192.168.86.51) | Runtime | `ssh thom@192.168.86.51` |

## Critical Rules

### 1. NEVER Commit Without Validation
Before ANY `git commit`, you MUST run:
```bash
./scripts/validate.sh
```
If validation fails, fix the issues before committing.

### 2. ALWAYS Update Context
After completing work, update `CONTEXT.md` with:
- What was accomplished
- Current state of the system
- Next steps

### 3. SSH Commands
When running commands on the VM:
```bash
ssh thom@192.168.86.51 'command here'
```
For multi-line or complex operations:
```bash
ssh thom@192.168.86.51 << 'EOF'
cd ~/barnabeenet
command1
command2
EOF
```

### 4. Test Before Deploy
Run tests locally before deploying to VM:
```bash
source .venv/bin/activate
pytest -xvs
```

### 5. Logging
- Log significant actions to the terminal
- After completing a session task, summarize what was done
- If something fails, capture the error output

## Code Standards

### Python
- Python 3.12, strict typing
- Use Pydantic v2 for models
- Async-first (all I/O operations)
- Follow existing patterns in `src/barnabeenet/`

### File Naming
- Python: `snake_case.py`
- Prompts: `snake_case.prompt` or `snake_case.j2`
- Tests: `test_<module>.py`

### Imports
```python
# Standard library
from __future__ import annotations
import asyncio
from typing import TYPE_CHECKING

# Third-party
from pydantic import BaseModel
import redis.asyncio as redis

# Local
from barnabeenet.config import settings
```

### Type Hints
```python
# Required for all functions
async def process_request(
    request: VoiceRequest,
    context: RequestContext,
) -> VoiceResponse:
    ...
```

## Project Structure
```
barnabeenet/
├── src/barnabeenet/         # Main application code
│   ├── agents/              # Multi-agent system
│   ├── api/                 # FastAPI routes
│   ├── models/              # Pydantic schemas
│   ├── services/            # STT, TTS, LLM clients
│   └── voice/               # Voice pipeline
├── tests/                   # Pytest tests (mirror src structure)
├── workers/                 # GPU worker scripts
├── prompts/                 # Jinja2 prompt templates
├── config/                  # YAML configuration
├── scripts/                 # Utility scripts
└── docs/                    # Documentation
```

## Key Files to Reference

When working on:
- **Architecture decisions**: Read `docs/BarnabeeNet_Technical_Architecture.md`
- **Agent patterns**: Read `SkyrimNet_Deep_Research_For_BarnabeeNet.md` (in project knowledge)
- **Current state**: Read `CONTEXT.md`
- **Project log**: Read `barnabeenet-project-log.md`

## Common Tasks

### Create New Agent
1. Copy pattern from `src/barnabeenet/agents/action_agent.py`
2. Create corresponding test in `tests/agents/test_<name>_agent.py`
3. Register in `src/barnabeenet/agents/__init__.py`
4. Add prompt template in `prompts/agents/<name>.prompt`

### Add API Endpoint
1. Create route in `src/barnabeenet/api/routes/<name>.py`
2. Register in `src/barnabeenet/api/routes/__init__.py`
3. Add tests in `tests/api/test_<name>.py`

### Deploy to VM
```bash
# From WSL workspace
git push
ssh thom@192.168.86.51 'cd ~/barnabeenet && git pull'
```

---

## Session-Based Workflow

### Starting a Session

When the user says **"continue the project"** or **"what's next"**:

1. **Read current state**:
   - `CONTEXT.md` - Current phase, what's working, next steps
   - `barnabeenet-project-log.md` - Detailed history

2. **Create a session plan** at `.copilot/sessions/session-<DATE>-<NAME>.md`:
```markdown
   # Session: [Next Task from CONTEXT.md]

   **Date:** YYYY-MM-DD
   **Goal:** [From CONTEXT.md next steps]

   ## Current State
   [Summary from CONTEXT.md]

   ## Tasks
   1. [ ] First task
   2. [ ] Second task
   3. [ ] Validate and test
   4. [ ] Update CONTEXT.md

   ## Success Criteria
   - [ ] What indicates completion
```

3. **Execute the session plan**

4. **Write results** to `.copilot/sessions/session-<DATE>-<NAME>-results.md`

5. **Update CONTEXT.md** with new state

### Session File Naming
```
.copilot/sessions/
├── session-2026-01-17-messagebus.md
├── session-2026-01-17-messagebus-results.md
├── session-2026-01-18-voicepipeline.md
└── ...
```

### Continuing Work

If a previous session exists but wasn't completed:
1. Check for incomplete tasks in the most recent session file
2. Resume from where it left off
3. Don't create a new session file—continue the existing one

### Blocked or Unclear

If the next step is unclear or blocked:
1. Document the blocker in CONTEXT.md under "Blocking Issues"
2. Tell the user: "The next task is [X] but I need clarification on [Y]"
3. Wait for user input before proceeding


## Key Files to Reference

When working on:
- **Architecture decisions**: Read `docs/BarnabeeNet_Technical_Architecture.md`
- **Agent patterns**: Read project knowledge for SkyrimNet research
- **Current state**: Read `CONTEXT.md` ← **START HERE**
- **Project log**: Read `barnabeenet-project-log.md`
- **STT/TTS services**: `src/barnabeenet/services/stt/`, `src/barnabeenet/services/tts/`
- **GPU Worker**: `workers/gpu_stt_worker.py` (to be created)
---

## Forbidden Actions

- **NEVER** commit secrets or API keys
- **NEVER** modify `.env` files (use `.env.example`)
- **NEVER** skip tests before commit
- **NEVER** force push to main
- **NEVER** delete production data without explicit confirmation
