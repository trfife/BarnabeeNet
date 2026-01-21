# CLAUDE.md - Project Instructions for AI Agents

This file provides guidance for Claude Code and other AI agents working on BarnabeeNet.

## Project Overview

BarnabeeNet is a privacy-first, multi-agent AI smart home assistant. It uses:
- **FastAPI** backend with async Python
- **Multi-agent architecture** (Meta, Instant, Action, Interaction, Memory agents)
- **Home Assistant integration** for device control
- **Redis** for message bus and state
- **Vue.js-style dashboard** (vanilla JS)

## Key Directories

| Path | Purpose |
|------|---------|
| `src/barnabeenet/` | Main Python package |
| `src/barnabeenet/agents/` | Agent implementations |
| `src/barnabeenet/api/routes/` | FastAPI endpoints |
| `src/barnabeenet/static/` | Dashboard HTML/JS/CSS |
| `tests/` | Pytest test suite |
| `config/` | YAML configuration files |
| `scripts/` | Shell scripts and utilities |

## Testing

BarnabeeNet uses **pytest-testmon** for fast incremental testing and **pytest-xdist** for parallel execution.

```bash
# Run only tests affected by recent changes (fast, ~1-10s)
pytest

# Run ALL tests (bypass testmon, for CI/pre-push)
pytest --no-testmon

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_action_agent.py
```

**Note:** Just run `pytest` after making changes. Testmon automatically determines which tests need to run based on file dependencies. Tests run in parallel automatically via xdist.

## Validation

Always run validation before committing:

```bash
./scripts/validate.sh         # Fast validation (testmon)
./scripts/validate.sh --full  # Full validation (all tests)
```

## Debugging

Use the debug script to inspect runtime logs:

```bash
./scripts/debug-logs.sh traces 10      # Recent conversation traces
./scripts/debug-logs.sh trace <id>     # Specific trace
./scripts/debug-logs.sh activity 50    # Activity feed
./scripts/debug-logs.sh errors         # Recent errors
./scripts/debug-logs.sh llm-calls 20   # LLM requests
./scripts/debug-logs.sh ha-errors      # Home Assistant errors
```

## Code Style

- Python 3.12+ with strict typing
- Pydantic v2 models
- Async-first design
- Ruff for formatting and linting

## Safety Rules

**DO NOT modify:**
- `secrets/`, `.env`, `infrastructure/secrets/`
- Authentication or security code
- Privacy zone configurations

**DO NOT run:**
- `rm -rf`, `sudo`, `chmod 777`
- Piping curl/wget to shell

## Deployment

The app runs on a NixOS VM at `192.168.86.51`:

```bash
# Deploy and restart
ssh thom@192.168.86.51 'cd ~/barnabeenet && git pull && bash scripts/restart.sh'
```
