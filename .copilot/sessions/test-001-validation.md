# Copilot Agent Validation Session

**Session ID:** test-001
**Date:** 2025-01-17
**Purpose:** Validate agent can read, execute, and report

---

## Instructions

Complete each task in order. After ALL tasks are complete, write your results to:
`.copilot/sessions/test-001-results.md`

Do NOT commit anything. This is a read/validation test only.

---

## Task 1: Project Understanding (Read Only)

1. Read `CONTEXT.md` and identify:
   - Current phase
   - What's working
   - Next steps listed

2. Read `.github/copilot-instructions.md` and confirm you understand:
   - The two-machine setup (WSL + VM)
   - The validation requirement before commits

3. Read `barnabeenet-project-log.md` and identify:
   - VM IP address
   - What services are running on the VM

---

## Task 2: WSL Command Execution

Run these commands in the WSL terminal and capture output:
````bash
# 1. Confirm current directory
pwd

# 2. Show git status
git status --short

# 3. Check Python version
python3 --version

# 4. List project structure (top level)
ls -la

# 5. Check if .venv exists
ls -la .venv/bin/python 2>/dev/null || echo "No .venv found"
````

---

## Task 3: SSH to VM (Read Only)

SSH to the BarnabeeNet VM and run read-only commands:
````bash
# 1. Test SSH connection
ssh thom@192.168.86.51 'echo "SSH connection successful"'

# 2. Check VM hostname
ssh thom@192.168.86.51 'hostname'

# 3. Check if Redis is running
ssh thom@192.168.86.51 'podman ps --format "{{.Names}} {{.Status}}"'

# 4. Check disk space
ssh thom@192.168.86.51 'df -h / | tail -1'
````

---

## Task 4: File Creation Test

Create a new file at `docs/future/TOON_Optimization.md` with this content:
````markdown
# TOON Format - Future Optimization

**Status:** 📋 Backlog (Phase 3+)
**Added:** 2025-01-17
**Source:** https://www.freecodecamp.org/news/what-is-toon-how-token-oriented-object-notation-could-change-how-ai-sees-data/

## What is TOON?

Token-Oriented Object Notation - a data format designed to reduce token usage when exchanging structured data with LLMs.

## Token Savings

- 30-50% fewer tokens compared to JSON for uniform data
- Eliminates repeated keys, quotes, braces

## Example

**JSON (current):**
```json
{
  "devices": [
    {"entity_id": "light.living_room", "state": "on", "brightness": 80},
    {"entity_id": "light.kitchen", "state": "off", "brightness": 0}
  ]
}
```

**TOON equivalent:**
````
devices[2]{entity_id,state,brightness}:
  light.living_room,on,80
  light.kitchen,off,0
````

## BarnabeeNet Applications

Consider TOON for:
- Home state context in LLM prompts
- Memory retrieval results sent to agents
- Device lists in action planning
- Any repeated structured data in prompts

## Libraries

- Python: `pip install python-toon`
- JavaScript: `npm install @toon-format/toon`

## Decision

Defer until core system is working. Revisit when optimizing API costs.

---

*Added by Copilot agent during validation test*
````

---

## Task 5: Write Results

Create `.copilot/sessions/test-001-results.md` with:

1. **Task 1 Results:** Summary of what you learned about the project
2. **Task 2 Results:** Command outputs from WSL
3. **Task 3 Results:** Command outputs from SSH
4. **Task 4 Results:** Confirm file created, show path
5. **Issues Encountered:** Any problems or errors
6. **Agent Self-Assessment:** How well did instructions work?

---

## Completion Checklist

- [ ] Task 1: Project files read and understood
- [ ] Task 2: WSL commands executed successfully
- [ ] Task 3: SSH commands executed successfully
- [ ] Task 4: TOON doc created at correct path
- [ ] Task 5: Results file written

**Do NOT run `git commit` or `git push` - this is validation only.**
