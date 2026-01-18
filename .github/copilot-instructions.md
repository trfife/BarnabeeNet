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

## Forbidden

- Never commit secrets
- Never skip validation before commit
- Never force push
- Never do multiple tasks in one session
