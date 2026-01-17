# BarnabeeNet Copilot Agent Instructions

## Core Loop (ONE TASK PER SESSION)

When user says "continue the project":

1. **READ**: `CONTEXT.md` for current state
2. **DO ONE TASK**: Execute the FIRST item in "Next Steps" only
3. **VALIDATE**: Run `./scripts/validate.sh`
4. **UPDATE**: Edit `CONTEXT.md` - move task to "What's Working", update date
5. **COMMIT**: `git add -A && git commit -m "<type>: <description>" && git push`
6. **STOP & REPORT**: Tell user what you did. Do NOT continue to next task.

## Why One Task Per Session?

- Avoids hitting request limits
- Creates clean git history  
- Each session = one focused task
- User starts fresh session with updated context

## Checkpoint Pattern

After EVERY completed task:
```bash
git add -A
git commit -m "<type>: <description>"
git push
```
Then STOP. User will say "continue the project" in a NEW session.

## Environment

| Machine | Access |
|---------|--------|
| Man-of-war (WSL) | Local, passwordless sudo |
| VM (192.168.86.51) | `ssh thom@192.168.86.51 'command'` |

## CONTEXT.md Updates

After completing a task:
- Move completed item from "Next Steps" to "What's Working"
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
