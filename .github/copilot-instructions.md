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

## Forbidden Actions

- **NEVER** commit secrets or API keys
- **NEVER** modify `.env` files (use `.env.example`)
- **NEVER** skip tests before commit
- **NEVER** force push to main
- **NEVER** delete production data without explicit confirmation