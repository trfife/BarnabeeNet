# BarnabeeNet Development Guide

Quick reference for AI agents (Claude, Copilot, Cursor) working on BarnabeeNet.

## Quick Start

1. **Read:** `CONTEXT.md` for current state
2. **Understand:** `CLAUDE.md` for architecture
3. **Follow:** `.github/copilot-instructions.md` for workflow

## Architecture Summary

### Agents
- **MetaAgent**: Intent classification (every request)
- **InstantAgent**: Pattern-matched responses (no LLM)
- **ActionAgent**: Device control via Home Assistant
- **InteractionAgent**: Complex conversations (Claude/GPT-4)
- **MemoryAgent**: Memory storage/retrieval
- **SelfImprovementAgent**: AI-assisted code improvements

### Key Files
- **Prompts:** `src/barnabeenet/prompts/*.txt` - **EDIT DIRECTLY, NO UI**
- **Models:** `config/llm.yaml` - one model per agent
- **Dashboard:** `src/barnabeenet/static/` (HTML/JS/CSS)
- **API:** `src/barnabeenet/api/routes/`

### Dashboard Pages
Dashboard, Chat, Memory, Logic, Self-Improve, Logs, Family, Entities, Config

**REMOVED:** Prompts page (edit files directly)

## Common Tasks

### Change Agent Behavior
1. Edit `src/barnabeenet/prompts/{agent}_agent.txt`
2. Restart service: `ssh thom@192.168.86.51 'cd ~/barnabeenet && bash scripts/restart.sh'`

### Change Agent Model
1. Edit `config/llm.yaml` → `agents.{agent}.model`
2. Restart service

### Add Dashboard Page
1. Add `<div id="page-{name}">` in `index.html`
2. Add nav link with `data-page="{name}"`
3. Add JS initialization in `app.js`
4. Add CSS styles in `style.css`

### Add API Endpoint
1. Create `src/barnabeenet/api/routes/{name}.py`
2. Register in `main.py`
3. Add tests in `tests/test_{name}.py`

## Testing

```bash
pytest              # Fast incremental (testmon)
pytest --no-testmon # Full test suite
```

~690 tests currently passing

## Deployment

```bash
./scripts/deploy-vm.sh
# Or manually:
ssh thom@192.168.86.51 'cd ~/barnabeenet && git pull && bash scripts/restart.sh'
```

**WSL:** Only for GPU workers, NOT main API

## Safety

- Never modify `secrets/`, `.env`, authentication code
- Never run destructive commands
- Never commit secrets
- Never run main API in WSL
