# CLAUDE.md - Project Instructions for AI Agents

This file provides guidance for Claude Code and other AI agents working on BarnabeeNet.

## Project Overview

BarnabeeNet is a privacy-first, multi-agent AI smart home assistant. It uses:
- **FastAPI** backend with async Python
- **Multi-agent architecture** (Meta, Instant, Action, Interaction, Memory agents)
- **Home Assistant integration** for device control
- **Redis** for message bus and state
- **Vanilla JavaScript dashboard** (no frameworks)

## Key Directories

| Path | Purpose |
|------|---------|
| `src/barnabeenet/` | Main Python package |
| `src/barnabeenet/agents/` | Agent implementations (meta, instant, action, interaction, memory, self_improvement) |
| `src/barnabeenet/api/routes/` | FastAPI endpoints |
| `src/barnabeenet/static/` | Dashboard HTML/JS/CSS (single-page app) |
| `src/barnabeenet/prompts/` | Agent system prompts (`.txt` files) - **EDIT DIRECTLY, NO UI** |
| `tests/` | Pytest test suite |
| `config/` | YAML configuration files (llm.yaml, routing.yaml, patterns.yaml) |
| `scripts/` | Shell scripts and utilities |

## Dashboard Pages (Current)

| Page | Route | Purpose |
|------|-------|---------|
| Dashboard | `#dashboard` | System status, quick stats |
| Chat | `#chat` | Text/voice conversation with Barnabee |
| Memory | `#memory` | Memory management (facts, conversations, diary) |
| Logic | `#logic` | Pattern/routing/override browser and editor |
| Self-Improve | `#self-improve` | AI-assisted code improvement sessions |
| Logs | `#logs` | Performance graphs, log stream |
| Family | `#family` | Family member profiles |
| Entities | `#entities` | Home Assistant knowledge view |
| Configuration | `#config` | LLM providers, model selection, HA config |

**REMOVED:** Prompts page (edit prompt files directly in `src/barnabeenet/prompts/*.txt`)

## Model Configuration

**IMPORTANT:** Model selection is simplified. Each agent uses ONE model from `config/llm.yaml`:

```yaml
agents:
  meta: { model: "deepseek/deepseek-chat", ... }
  instant: { model: "deepseek/deepseek-chat", ... }
  action: { model: "openai/gpt-4o-mini", ... }
  interaction: { model: "anthropic/claude-3.5-sonnet", ... }
  memory: { model: "openai/gpt-4o-mini", ... }
```

- **Edit `config/llm.yaml` directly** to change models
- Dashboard shows current models (read-only display)
- Backend uses activity-based config internally (not exposed in UI)

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

**Current test count:** ~690 tests passing

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

**CRITICAL:** The app runs on a NixOS VM at `192.168.86.51`. WSL should NOT run the main API.

```bash
# Deploy and restart (use deploy script)
./scripts/deploy-vm.sh

# Or manually:
ssh thom@192.168.86.51 'cd ~/barnabeenet && git pull && bash scripts/restart.sh'
```

**WSL Usage:** Only for GPU workers (Parakeet STT, Kokoro TTS) when needed. Main API must run on VM.

## Common Development Patterns

### Modifying Agent Behavior
1. **Edit prompt file:** `src/barnabeenet/prompts/{agent}_agent.txt`
2. **Restart service:** Changes take effect after restart
3. **No UI needed:** Prompts are text files, edit directly

### Changing Agent Models
1. **Edit config:** `config/llm.yaml` → `agents.{agent}.model`
2. **Restart service:** Model changes require restart
3. **View in dashboard:** Configuration → Model Selection (read-only display)

### Adding Dashboard Page
1. **HTML:** Add `<div id="page-{name}">` in `index.html`
2. **Navigation:** Add nav link with `data-page="{name}"`
3. **JS:** Add page initialization in `app.js`
4. **CSS:** Add styles in `style.css`

### Adding API Endpoint
1. **Route file:** Add to `src/barnabeenet/api/routes/{name}.py`
2. **Register:** Add to `main.py` router registration
3. **Test:** Add tests in `tests/test_{name}.py`

## Architecture Quick Reference

### Agent Flow
```
User Input → MetaAgent.classify() → Route to Agent → Agent.process() → Response
```

### File Locations
- **Agent prompts:** `src/barnabeenet/prompts/*.txt` (edit directly)
- **Agent code:** `src/barnabeenet/agents/*.py`
- **Model config:** `config/llm.yaml` (agents section)
- **Routing rules:** `config/routing.yaml`
- **Patterns:** `config/patterns.yaml`
- **Orchestrator:** `src/barnabeenet/agents/orchestrator.py`

### Key Services
- **HomeAssistantClient:** `src/barnabeenet/services/homeassistant/client.py`
- **ProfileService:** `src/barnabeenet/services/profiles.py`
- **MemoryStorage:** `src/barnabeenet/services/memory/storage.py`
- **SecretsService:** `src/barnabeenet/services/secrets.py` (encrypted storage)
