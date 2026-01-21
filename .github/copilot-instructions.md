# BarnabeeNet Copilot Agent Instructions

## Core Loop

When user says "continue the project":

1. **READ**: `CONTEXT.md` for current state
2. **DO TASKS**: Execute items from "Next Steps" until complete
3. **VALIDATE**: Run `./scripts/validate.sh` before commits
4. **UPDATE**: Edit `CONTEXT.md` - move tasks to "What's Working", update date
5. **COMMIT**: `git add -A && git commit -m "<type>: <description>" && git push`
6. **CONTINUE**: Keep working until the overall task/feature is done

## Checkpoint Pattern

After completing significant work:
```bash
git add -A
git commit -m "<type>: <description>"
git push
```

## Environment

| Machine | Access |
|---------|--------|
| Man-of-war (WSL) | Local, passwordless sudo |
| VM (192.168.86.51) | `ssh thom@192.168.86.51 'command'` |

## CONTEXT.md Updates

After completing tasks:
- Move completed items from "Next Steps" to "What's Working"
- Update "Last Updated" date
- Add any new blockers or decisions

## Git Commit Types

- `feat:` new features
- `fix:` bug fixes
- `docs:` documentation
- `chore:` maintenance

## Code Standards

Python 3.12, strict typing, Pydantic v2, async-first.

## SSH Command Patterns

### CRITICAL: Avoid SSH Hanging

When running background processes via SSH, **always** include `</dev/null` to detach stdin. Without this, SSH will hang waiting for file descriptors to close.

**WRONG (will hang):**
```bash
ssh host 'nohup command > /tmp/log 2>&1 &'
```

**CORRECT:**
```bash
ssh host 'nohup command > /tmp/log 2>&1 </dev/null &'
```

### BarnabeeNet VM Restart - MANDATORY

**Always use the restart script to restart BarnabeeNet. Never run uvicorn inline via SSH.**
```bash
ssh -o ConnectTimeout=5 thom@192.168.86.51 'cd ~/barnabeenet && bash scripts/restart.sh'
```

DO NOT attempt inline nohup/uvicorn commands - they will hang SSH.

## Forbidden

- Never commit secrets
- Never skip validation before commit
- Never force push
- Never do multiple tasks in one session
