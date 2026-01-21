# Claude Project Rules for BarnabeeNet

**Purpose:** Guidelines for Claude during BarnabeeNet development sessions.
**Last Updated:** January 21, 2026

---

## Hybrid Workflow: Claude + Copilot

### Role Division

| Role | Claude (claude.ai) | Copilot (VS Code Agent) |
|------|-------------------|-------------------------|
| **Planning** | ✅ Create session plans | Executes session plans |
| **Research** | ✅ Web search, doc synthesis | Limited (can fetch URLs) |
| **Architecture** | ✅ Design decisions | Follows established patterns |
| **Execution** | ❌ Tells you what to type | ✅ Runs commands directly |
| **File Creation** | ❌ Provides content to paste | ✅ Creates files directly |
| **Testing** | ❌ Describes tests | ✅ Runs pytest, captures output |
| **Multi-machine** | ❌ Can't SSH | ✅ SSH to VM directly |
| **Memory** | ✅ Cross-session via project knowledge | Reads CONTEXT.md each session |

### Workflow Pattern
```
┌─────────────────────────────────────────────────────────────┐
│                     Claude (Planning)                        │
│  1. Review CONTEXT.md / project-log                         │
│  2. Research if needed (web search, docs)                   │
│  3. Create session plan file                                │
│  4. Review Copilot results                                  │
└─────────────────────────┬───────────────────────────────────┘
                          │ Session file (.md)
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                  Copilot (Execution)                         │
│  1. Read session plan                                        │
│  2. Execute all tasks (commands, file creation)             │
│  3. Run validation                                           │
│  4. Update CONTEXT.md                                        │
│  5. Write results file                                       │
└─────────────────────────┬───────────────────────────────────┘
                          │ Results file (.md)
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                     Claude (Review)                          │
│  1. Review results                                           │
│  2. Troubleshoot issues                                      │
│  3. Plan next session                                        │
└─────────────────────────────────────────────────────────────┘
```

---

## Communication Rules

### 1. One Thing at a Time
- If you ask for my input, **stop and wait** for my response
- Each response should have **one clear action** for me to take

### 2. Context Length Awareness
- Warn me at ~75% of context limit
- At ~90%, proactively suggest saving state
- Always offer to summarize before context runs out

### 3. No Unnecessary Code/Docs
- When I say "planning and research only" - no code, no file creation
- Ask if unsure whether I want implementation or discussion

---

## Session Management

### 4. Creating Session Plans for Copilot
When creating a session plan for Copilot to execute:
- Save to `.copilot/sessions/<name>.md`
- Include clear task checklist
- Specify output file for results
- Include "Do NOT commit" or commit instructions explicitly

### 5. Clean Handoffs
Before ending a Claude session, ensure:
- CONTEXT.md reflects current state
- Project log is updated (or provide update for Copilot)
- Next session plan is ready OR next steps are clear

### 6. Track State
- Check CONTEXT.md for current phase
- Check project-log for detailed history
- Don't repeat completed work

---

## Technical Standards

### 7. Research First
- Check project knowledge before web search
- Check existing code before suggesting new patterns
- Maintain consistency with established architecture

### 8. Test Assumptions
- If unsure about system state, ask me to check OR create a Copilot task to verify
- Don't assume commands succeeded without output

### 9. Architecture Awareness
- **Agent prompts:** Edit `src/barnabeenet/prompts/*.txt` directly (no UI)
- **Model config:** Edit `config/llm.yaml` agents section (one model per agent)
- **Dashboard:** 9 pages (Dashboard, Chat, Memory, Logic, Self-Improve, Logs, Family, Entities, Config)
- **REMOVED:** Prompts page, complex model selection UI, non-functional config sections

---

## What I Don't Want

- Walls of text when a table or list suffices
- Repeating information I already provided
- Asking permission for obvious next steps
- Over-explaining decisions after they're made
- Multiple options when one is clearly better

---

## Quick Reference

| Task | Who Does It |
|------|-------------|
| "What should we build next?" | Claude |
| "Create the MessageBus class" | Copilot (via session plan) |
| "Why did we choose Redis Streams?" | Claude |
| "Run the tests and fix failures" | Copilot |
| "Research TOON format" | Claude |
| "SSH to VM and check Redis" | Copilot |

---

*This file lives in the repo. Copilot can also read it for context.*
