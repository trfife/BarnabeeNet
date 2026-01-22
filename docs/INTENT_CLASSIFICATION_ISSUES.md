# Intent Classification Issues - Needs to be Fixed

**Date:** January 21, 2026
**Test Results:** 36/49 passed (73%)
**Issues Found:** 13

---

## Summary

The Meta Agent intent classification needs pattern improvements to correctly route certain phrasings. Most issues are edge cases where similar phrasings are classified differently.

---

## Issues by Category

### 1. Instant Agent - Time/Date Queries (5 issues)

These should be classified as `instant` but are being misclassified:

#### Time Queries

- ❌ **"Tell me the time"** → `conversation` (should be `instant`)
- ❌ **"What time?"** → `query` (should be `instant`)

#### Date Queries

- ❌ **"What date is it?"** → `query` (should be `instant`)
- ❌ **"Tell me the date"** → `conversation` (should be `instant`)
- ❌ **"Current date"** → `conversation` (should be `instant`)

**Root Cause:** Patterns likely match "What time is it?" and "What's the date?" but miss variations like "Tell me the time/date" and "What time?".

**Fix Needed:** Add patterns to `src/barnabeenet/agents/meta.py`:

- Pattern: `tell me the time|tell me the date`
- Pattern: `what time\?|what date\?` (short form)
- Pattern: `current time|current date`

---

### 2. Memory Agent - Retrieval Queries (4 issues)

These should be classified as `memory` but are being classified as `query`:

- ❌ **"What do I like?"** → `query` (should be `memory`)
- ❌ **"What's my preference?"** → `query` (should be `memory`)
- ❌ **"What temperature do I prefer?"** → `query` (should be `memory`)
- ❌ **"Remember: I don't like loud music"** → `conversation` (should be `memory`)

**Root Cause:** Memory retrieval patterns likely match "What did I tell you about X?" but miss:

- Generic preference queries ("What do I like?")
- Self-referential queries ("What's my preference?")
- Colon-separated remember statements ("Remember: ...")

**Fix Needed:** Add patterns to `src/barnabeenet/agents/meta.py`:

- Pattern: `what do I (like|prefer|want|need)`
- Pattern: `what's my (preference|preference|favorite)`
- Pattern: `remember:\s+` (colon-separated remember statements)

---

### 3. Interaction Agent - Question Classification (4 issues)

These are routing correctly to `interaction` agent, but intent classification could be more consistent:

- ⚠️ **"What's the weather like?"** → `query` (expected `conversation`, but routes correctly)
- ⚠️ **"What can you do?"** → `query` (expected `conversation`, but routes correctly)
- ⚠️ **"What is artificial intelligence?"** → `query` (expected `conversation`, but routes correctly)
- ⚠️ **"Explain photosynthesis"** → `conversation` (expected `query`, but routes correctly)

**Note:** These are lower priority since they all route to the `interaction` agent correctly. The intent classification difference (`query` vs `conversation`) doesn't affect functionality, but consistency would be better.

**Optional Fix:** If we want consistent classification:

- Questions starting with "What's" or "What is" could be classified as `query` consistently
- "Explain X" could be classified as `query` instead of `conversation`

---

## Priority

### High Priority (Must Fix)

1. **Instant Agent patterns** - Users expect time/date queries to work consistently
2. **Memory retrieval patterns** - Generic preference queries should retrieve memories

### Medium Priority (Should Fix)

3. **Memory store pattern** - Colon-separated "Remember:" statements

### Low Priority (Nice to Have)

4. **Intent classification consistency** - Doesn't affect functionality, but improves consistency

---

## Files to Update

1. **`src/barnabeenet/agents/meta.py`**
   - Add patterns for instant agent variations
   - Add patterns for memory retrieval variations
   - Add pattern for colon-separated remember statements

2. **`src/barnabeenet/agents/instant.py`** (if needed)
   - Ensure patterns match the new Meta Agent patterns

---

## Test Cases to Add

After fixes, these should pass:

- "Tell me the time" → `instant`
- "What time?" → `instant`
- "What date is it?" → `instant`
- "Tell me the date" → `instant`
- "Current date" → `instant`
- "What do I like?" → `memory`
- "What's my preference?" → `memory`
- "What temperature do I prefer?" → `memory`
- "Remember: I don't like loud music" → `memory`

---

## Implementation Notes

1. **Pattern Matching:** Use case-insensitive matching with word boundaries where appropriate
2. **Priority:** Instant agent patterns should have higher priority than general conversation patterns
3. **Testing:** Re-run `test_all_intents.sh` after fixes to verify

---

## Related Files

- `src/barnabeenet/agents/meta.py` - Intent classification patterns
- `src/barnabeenet/agents/instant.py` - Instant agent patterns
- `src/barnabeenet/agents/memory.py` - Memory agent patterns
- `test_all_intents.sh` - Test suite
