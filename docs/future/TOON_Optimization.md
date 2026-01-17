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
```
devices[2]{entity_id,state,brightness}:
  light.living_room,on,80
  light.kitchen,off,0
```

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
