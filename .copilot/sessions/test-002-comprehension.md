# Copilot Agent Comprehension Test

**Session ID:** test-002
**Date:** 2025-01-17
**Purpose:** Prove deep understanding of BarnabeeNet architecture and design patterns

---

## Instructions

This is a **read-only comprehension test**. Do NOT create any code files.

Read the project documentation thoroughly, then answer the questions below. Write all answers to:
`.copilot/sessions/test-002-results.md`

Your answers should demonstrate that you understand the WHY behind design decisions, not just the WHAT.

---

## Part 1: Multi-Agent Architecture (Read: docs/, project knowledge)

Answer these questions by synthesizing information across multiple documents:

### Q1.1: Agent Mapping
BarnabeeNet's agent architecture is inspired by SkyrimNet's 7-agent pattern. Create a table mapping:
- Each SkyrimNet agent → Its BarnabeeNet equivalent
- The purpose of each
- Why this mapping makes sense for a smart home context

### Q1.2: Model Tiering Strategy
Explain the model tiering strategy (which agents use expensive vs cheap models). Why is the Meta Agent assigned to a "fast/cheap" model while the Interaction Agent gets a "quality" model? What would happen if you reversed this?

### Q1.3: Why Not One Agent?
The project could use a single LLM for everything. Explain in 3-4 sentences why the multi-agent approach was chosen instead. Reference specific benefits mentioned in the documentation.

---

## Part 2: Memory System (Read: docs/, SkyrimNet research)

### Q2.1: First-Person Memory
SkyrimNet uses "first-person, per-character memory." How does BarnabeeNet adapt this pattern? Who is the "character" in BarnabeeNet's case, and why does this matter for a smart home assistant?

### Q2.2: Memory Tiers
Describe the three memory tiers in BarnabeeNet's design:
- What each tier stores
- Retention period
- Access pattern (how/when it's retrieved)

### Q2.3: Anti-Hallucination
What specific techniques does the prompt engineering documentation recommend to prevent the LLM from hallucinating device states or family member information?

---

## Part 3: Infrastructure Understanding (Read: project-log, CONTEXT.md, infrastructure/)

### Q3.1: Machine Roles
Explain the role of each machine in the architecture:
| Machine | Role | Why this machine? |
|---------|------|-------------------|

Include: Man-of-war, Battlestation, BarnabeeNet VM

### Q3.2: GPU Offload
Why is STT (Speech-to-Text) running on Man-of-war instead of the BarnabeeNet VM? What are the latency implications? What would need to change to run STT on the VM?

### Q3.3: Why NixOS?
The VM runs NixOS instead of Ubuntu or Debian. Based on the project documentation, explain why NixOS was chosen and what benefit it provides for this project.

---

## Part 4: Voice Pipeline (Read: technical architecture, implementation guide)

### Q4.1: Latency Budget
The project has specific latency targets. What is the total round-trip latency budget for a voice interaction? Break it down by component:
- Wake word detection
- STT
- LLM inference
- TTS
- Total

### Q4.2: Privacy Zones
Explain the three privacy zones and give an example of what type of request falls into each:
1. Zone 1 (Local-only)
2. Zone 2 (Cloud-allowed)
3. Zone 3 (Never)

### Q4.3: Speaker Recognition
Why does BarnabeeNet need speaker recognition? How does it affect the response? Give an example where identifying the speaker as "Penelope" (a child) vs "Thom" (an adult) would change the system's behavior.

---

## Part 5: Implementation State (Read: CONTEXT.md, project-log)

### Q5.1: Current Progress
Without looking at the file tree, based only on documentation:
- What phase is the project in?
- What has been completed?
- What are the next 3 implementation steps?

### Q5.2: Blocking Dependencies
If you were to implement the Memory Agent today, what dependencies would need to exist first? (Hint: think about what the Memory Agent needs to function)

### Q5.3: Test Strategy
Based on the documentation, how should agents be tested? What's the recommended approach for testing prompts without the full system running?

---

## Part 6: Synthesis Question

### Q6.1: Architecture Decision Record
Write a brief ADR (Architecture Decision Record) for this question:

**Decision:** Why does BarnabeeNet use Redis Streams instead of a simple in-memory queue for the message bus?

Format:
```
## Decision
[What was decided]

## Context
[Why this decision was needed]

## Consequences
[What this enables and what tradeoffs it creates]
```

---

## Part 7: Edge Case Reasoning

### Q7.1: Conflicting Information
If the user says "turn off all the lights" but the LLM's training data suggests there are 5 lights in a typical living room, while Home Assistant reports only 3 lights exist, what should happen? Which source of truth wins and why?

### Q7.2: Proactive Agent Boundaries
The Proactive Agent can observe patterns and make suggestions. Give an example of:
1. An appropriate proactive suggestion
2. A suggestion that would violate user trust/privacy
3. How the system prevents the second type

---

## Grading Criteria

For each answer, demonstrate:
- [ ] Accurate facts from documentation
- [ ] Understanding of WHY, not just WHAT
- [ ] Ability to connect concepts across multiple documents
- [ ] Smart home domain reasoning (not just repeating text)

---

## Output Format

Write your answers to `.copilot/sessions/test-002-results.md` with clear section headers matching the question numbers (Q1.1, Q1.2, etc.)

**Do NOT create any code. Do NOT commit. Read and answer only.**
