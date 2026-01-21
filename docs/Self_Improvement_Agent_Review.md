# Self-Improvement Agent Review & Recommendations

**Date:** 2026-01-20  
**Issue:** Self-improvement agent (Claude Code) unable to fix issues effectively  
**Root Cause Analysis:** Insufficient context about system architecture and file locations

---

## Problem Statement

The self-improvement agent uses Claude Code CLI to modify the codebase, but it's struggling to:
1. Understand where agent prompts are stored
2. Know how agents are initialized and configured
3. Access the actual files that control agent behavior
4. Understand the full architecture

## Root Cause Analysis

### Current State

The self-improvement agent has **hardcoded system prompts** in `src/barnabeenet/agents/self_improvement.py`:
- `DIAGNOSIS_SYSTEM_PROMPT` - Generic debugging instructions
- `IMPLEMENTATION_SYSTEM_PROMPT` - Generic implementation instructions

**Problems:**
1. ❌ Prompts don't reference actual file locations
2. ❌ No mention of where agent prompts are stored (`src/barnabeenet/prompts/*.txt`)
3. ❌ No mention of configuration files (`config/*.yaml`)
4. ❌ No architecture overview
5. ❌ Doesn't explain how agents are initialized
6. ❌ Missing context about orchestrator flow

### What Claude Code Needs to Know

#### 1. Agent Prompt Files
- **Location:** `src/barnabeenet/prompts/*.txt`
- **Files:**
  - `meta_agent.txt` - Intent classification prompt
  - `action_agent.txt` - Device control prompt
  - `interaction_agent.txt` - Conversation prompt
  - `memory_agent.txt` - Memory operations prompt
  - `instant_agent.txt` - Quick responses prompt

#### 2. Configuration Files
- **Location:** `config/` directory
- **Files:**
  - `config/llm.yaml` - LLM model configurations per agent
  - `config/routing.yaml` - Routing rules and patterns
  - Other YAML configs for various services

#### 3. Agent Initialization
- **Orchestrator:** `src/barnabeenet/agents/orchestrator.py`
  - Initializes all agents in `init()` method
  - Creates agents: MetaAgent, InstantAgent, ActionAgent, InteractionAgent, MemoryAgent
  - Agents are initialized with LLM client from `OpenRouterClient`

#### 4. Agent Architecture
- **Base Class:** `src/barnabeenet/agents/base.py` (Agent base class)
- **Flow:**
  1. MetaAgent classifies intent
  2. Routes to appropriate agent (Instant/Action/Interaction/Memory)
  3. Agent processes request using its prompt from `prompts/` directory
  4. Response generated and returned

#### 5. Key Architecture Files
- `src/barnabeenet/main.py` - Application entry point
- `src/barnabeenet/config.py` - Settings and configuration loading
- `src/barnabeenet/core/logic_registry.py` - Logic registry for editable patterns
- `docs/BarnabeeNet_Technical_Architecture.md` - Full architecture docs
- `docs/BarnabeeNet_MetaAgent_Specification.md` - Meta agent details

## Recommendations

### 1. Update System Prompts with Architecture Context

Add comprehensive architecture information to both prompts:

**For DIAGNOSIS_SYSTEM_PROMPT:**
- List all agent prompt file locations
- Explain the orchestrator flow
- Reference key architecture files
- Include config file locations

**For IMPLEMENTATION_SYSTEM_PROMPT:**
- Same architecture context
- Specific instructions on which files to modify for different types of fixes
- How to test changes (agent initialization, prompt reloading)

### 2. Add File Location Reference Section

Create a clear reference section in prompts:
```
KEY FILE LOCATIONS:
- Agent prompts: src/barnabeenet/prompts/*.txt
- Agent code: src/barnabeenet/agents/*.py
- Config files: config/*.yaml
- Orchestrator: src/barnabeenet/agents/orchestrator.py
- Architecture docs: docs/BarnabeeNet_Technical_Architecture.md
```

### 3. Simplify Prompt Complexity

The current prompts are too generic. Make them more specific:
- If fixing agent behavior → modify `prompts/{agent}_agent.txt`
- If fixing routing → modify `config/routing.yaml` or `agents/meta.py`
- If fixing initialization → modify `agents/orchestrator.py`

### 4. Add Architecture Documentation Reference

Point Claude Code to the actual architecture docs:
- `docs/BarnabeeNet_Technical_Architecture.md`
- `docs/BarnabeeNet_MetaAgent_Specification.md`
- `docs/BarnabeeNet_Prompt_Engineering.md`

## Implementation Plan

1. ✅ Review current prompts (DONE)
2. ⏳ Update DIAGNOSIS_SYSTEM_PROMPT with architecture context
3. ⏳ Update IMPLEMENTATION_SYSTEM_PROMPT with architecture context
4. ⏳ Add file location reference section
5. ⏳ Test with a simple improvement request

## Testing

After updating prompts, test with:
1. "Fix the meta agent prompt to handle typos better"
2. "Update the action agent to be more verbose"
3. "Change the interaction agent's personality"

These should now work because Claude Code will know:
- Where the prompts are (`prompts/meta_agent.txt`, etc.)
- How to modify them
- How to verify changes

---

## Summary

The self-improvement agent is failing because it lacks context about:
- **Where** files are located
- **How** the system is structured
- **What** files control agent behavior

By adding comprehensive architecture context to the system prompts, Claude Code will be able to:
- Find the right files to modify
- Understand the system structure
- Make targeted fixes
- Verify changes work correctly
