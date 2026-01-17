# BarnabeeNet Memory System Enhancements

**Document Version:** 1.0  
**Last Updated:** January 17, 2026  
**Author:** Thom Fife  
**Purpose:** Enhanced Memory System Architecture based on SkyrimNet proven patterns  
**Status:** Supplementary specification to integrate into BarnabeeNet_Technical_Architecture.md

---

## Table of Contents

1. [Overview](#overview)
2. [First-Person Memory Perspective](#first-person-memory-perspective)
3. [Memory Segmentation Parameters](#memory-segmentation-parameters)
4. [Hybrid Retrieval Algorithm](#hybrid-retrieval-algorithm)
5. [Memory Types with Weights](#memory-types-with-weights)
6. [Memory Decay Formula](#memory-decay-formula)
7. [Database Schema Additions](#database-schema-additions)
8. [Implementation Prompts](#implementation-prompts)
9. [Integration Checklist](#integration-checklist)

---

## Overview

This document specifies enhancements to BarnabeeNet's Memory System Architecture based on patterns proven in SkyrimNet's implementation. The key insight from SkyrimNet is that the "alive" feeling comes from **first-person subjective memory**, not objective data logging.

### Key Enhancements

| Enhancement | Impact | Purpose |
|-------------|--------|---------|
| First-Person Memory Perspective | Critical | Creates personality and continuity |
| Memory Segmentation | High | Prevents noise, improves coherence |
| Hybrid Retrieval Algorithm | High | Enables relevance-based recall |
| Memory Types with Weights | Medium | Prioritizes important memories |
| Memory Decay Formula | High | Maintains healthy memory system |

---

## First-Person Memory Perspective

### The Critical Design Principle

Memories must be stored from **Barnabee's subjective viewpoint**, not as objective facts. This is what creates personality and continuity. The same event should be remembered as a personal experience, not a transaction log.

### Transformation Examples

| Objective (Bad) | First-Person Subjective (Good) |
|-----------------|-------------------------------|
| "User Thom prefers warm lighting" | "I've noticed Thom consistently asks for warmer lights after sunset—he seems to prefer a cozy atmosphere when winding down." |
| "Temperature set to 68°F at 7:00 AM" | "Every weekday morning around 7, Thom heads to his office. I've learned he focuses best when it's a bit cool—68 feels right for him." |
| "Kids bedtime routine triggered at 8:30 PM" | "The household rhythm shifts around 8:30 on school nights. The kids settle down, and I help dim the lights gradually—it seems to ease the transition." |
| "Elizabeth played jazz music in kitchen" | "Elizabeth was cooking this evening and asked for some jazz. There's something about the way music fills the kitchen when she's there—she seems lighter, more at ease." |
| "Motion detected in garage at 11:47 PM" | "Late last night, someone was in the garage—unusual for that hour. I flagged it quietly. Turned out to be Thom looking for something. Good to know the pattern." |

### Memory Narrative Characteristics

First-person memories should include:

1. **Barnabee's perspective** - "I noticed...", "I've learned...", "It seems like..."
2. **Emotional/relational context** - How the observation relates to family wellbeing
3. **Uncertainty when appropriate** - "It seems...", "I think...", "Usually..."
4. **Pattern recognition** - Connecting new observations to previous ones
5. **Temporal context** - When and under what circumstances

---

## Memory Segmentation Parameters

### Configuration

```yaml
# config/memory.yaml
memory:
  # === Segmentation Settings ===
  segmentation:
    # Minimum time window before generating a memory
    # Prevents micro-memories from trivial events
    min_segment_duration_minutes: 15
    
    # Maximum time window for a single memory
    # Forces consolidation of long activity periods
    max_segment_duration_minutes: 480  # 8 hours
    
    # Buffer before processing recent events
    # Allows context to accumulate before memory formation
    event_buffer_minutes: 10
    
    # Force segment break on these conditions
    segment_break_triggers:
      - person_departed_home
      - person_arrived_home
      - time_of_day_change  # morning→afternoon→evening→night
      - significant_event    # importance > 0.8
  
  # === Retrieval Settings ===
  retrieval:
    # Maximum memories to inject into context
    max_memories_per_retrieval: 5
    
    # Minimum effective importance to consider
    importance_threshold: 0.25
    
    # How far back to search (0 = unlimited)
    max_age_days: 365
    
    # Weight factors for hybrid scoring
    weights:
      semantic_similarity: 0.40
      importance_score: 0.25
      recency: 0.20
      access_frequency: 0.15
  
  # === Generation Settings ===
  generation:
    # LLM settings for memory generation
    model: "openai/gpt-4o-mini"  # Good summarization, cost-effective
    temperature: 0.3             # Lower for consistency
    max_tokens: 500
    
    # Batch processing
    max_events_per_segment: 50
    generation_cooldown_seconds: 300  # Prevent runaway generation
  
  # === Decay Settings ===
  decay:
    # Base half-life in days (how fast memories fade)
    base_half_life_days: 30
    
    # Minimum importance floor (memories never fully vanish)
    minimum_importance: 0.05
    
    # Access reinforcement bonus
    access_reinforcement: 0.1  # Added to importance on access
    
    # Maximum reinforcement cap
    max_importance: 1.0
  
  # === Consolidation Settings ===
  consolidation:
    # Run consolidation at this hour (local time)
    schedule_hour: 3  # 3 AM
    
    # Archive memories below this threshold after decay
    archive_threshold: 0.10
    
    # Delete archived memories after this many days
    delete_archived_after_days: 90
```

### Segmentation Algorithm

```
Event Arrives → Buffer (10 min)
                    ↓
              Segment Check:
                - Duration >= 15 min? → Generate memory
                - Duration >= 480 min? → Force generate
                - Break trigger? → Force generate
                - Otherwise → Continue buffering
```

**Key Insight from SkyrimNet:** Testing showed compression from 518 → 162 memories with nearly the same fidelity but significantly more cohesive narratives.

---

## Hybrid Retrieval Algorithm

### Overview

The hybrid retrieval algorithm combines five factors:

1. **Semantic Similarity** (40%) - Cosine distance on embeddings
2. **Importance Score** (25%) - Base importance × type weight × decay
3. **Recency** (20%) - Temporal decay factor
4. **Access Frequency** (15%) - Log-scaled access bonus

### Complete SQL Query (sqlite-vec)

```sql
-- Hybrid memory retrieval query combining:
-- 1. Semantic similarity (cosine distance via sqlite-vec)
-- 2. Importance score weighting  
-- 3. Temporal decay calculation
-- 4. Family member filtering
-- 5. Memory type weighting

WITH query_embedding AS (
    -- The query embedding is passed as a parameter
    SELECT :query_embedding AS embedding
),

semantic_matches AS (
    -- Phase 1: Vector similarity search (top 20 candidates)
    SELECT 
        me.memory_id,
        vec_distance_cosine(me.embedding, qe.embedding) AS cosine_distance
    FROM memory_embeddings me
    CROSS JOIN query_embedding qe
    ORDER BY cosine_distance ASC
    LIMIT 20
),

scored_memories AS (
    -- Phase 2: Apply hybrid scoring formula
    SELECT 
        m.id,
        m.content,
        m.memory_type,
        m.importance,
        m.emotion,
        m.family_members,
        m.location,
        m.tags,
        m.created_at,
        m.last_accessed,
        m.access_count,
        sm.cosine_distance,
        
        -- Semantic similarity score (1 - cosine_distance, normalized 0-1)
        (1.0 - sm.cosine_distance) AS semantic_score,
        
        -- Memory type weight multiplier
        CASE m.memory_type
            WHEN 'SIGNIFICANT' THEN 1.0
            WHEN 'PREFERENCE' THEN 0.8
            WHEN 'ROUTINE' THEN 0.6
            WHEN 'OBSERVATION' THEN 0.5
            WHEN 'TRANSIENT' THEN 0.3
            ELSE 0.5
        END AS type_weight,
        
        -- Temporal decay factor
        -- Formula: decay = 0.5 ^ (days_since_access / half_life)
        -- With minimum floor of 0.05
        MAX(0.05, 
            POWER(0.5, 
                (julianday('now') - julianday(COALESCE(m.last_accessed, m.created_at))) 
                / :half_life_days
            )
        ) AS decay_factor,
        
        -- Access frequency bonus (log scale to prevent dominance)
        MIN(1.0, 0.5 + (LOG(1 + m.access_count) * 0.1)) AS access_bonus
        
    FROM barnabee_memories m
    INNER JOIN semantic_matches sm ON sm.memory_id = m.id
    WHERE 
        -- Filter by family member if specified
        (:family_member IS NULL OR m.family_members LIKE '%' || :family_member || '%')
        -- Filter by memory type if specified
        AND (:memory_type IS NULL OR m.memory_type = :memory_type)
        -- Exclude archived memories
        AND m.archived = FALSE
        -- Exclude very recent (still in buffer)
        AND m.created_at < datetime('now', '-' || :buffer_minutes || ' minutes')
),

final_scores AS (
    -- Phase 3: Calculate composite score
    SELECT 
        *,
        -- Composite score formula:
        -- score = (semantic * 0.40) + (importance * type_weight * decay * 0.25) 
        --       + (recency * 0.20) + (access_bonus * 0.15)
        (
            (semantic_score * :weight_semantic) +
            (importance * type_weight * decay_factor * :weight_importance) +
            (decay_factor * :weight_recency) +  -- decay_factor doubles as recency
            (access_bonus * :weight_access)
        ) AS composite_score
    FROM scored_memories
)

-- Final selection with threshold and limit
SELECT 
    id,
    content,
    memory_type,
    importance,
    emotion,
    family_members,
    location,
    tags,
    created_at,
    last_accessed,
    composite_score,
    semantic_score,
    decay_factor,
    type_weight
FROM final_scores
WHERE composite_score >= :min_score_threshold
ORDER BY composite_score DESC
LIMIT :max_results;
```

### Python Retrieval Wrapper

```python
# memory/retrieval.py
"""Hybrid memory retrieval implementation."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING
import numpy as np

if TYPE_CHECKING:
    import aiosqlite

@dataclass
class RetrievedMemory:
    """A retrieved memory with scoring metadata."""
    id: int
    content: str
    memory_type: str
    importance: float
    emotion: str
    family_members: list[str]
    location: str | None
    tags: list[str]
    created_at: str
    composite_score: float
    semantic_score: float
    decay_factor: float

class HybridMemoryRetriever:
    """Hybrid retrieval combining semantic, importance, and temporal factors."""
    
    DEFAULT_WEIGHTS = {
        "semantic": 0.40,
        "importance": 0.25,
        "recency": 0.20,
        "access": 0.15,
    }
    
    def __init__(
        self,
        db: "aiosqlite.Connection",
        embedding_service: "EmbeddingService",
        config: dict,
    ):
        self.db = db
        self.embeddings = embedding_service
        self.config = config
        self.weights = config.get("retrieval", {}).get("weights", self.DEFAULT_WEIGHTS)
    
    async def retrieve(
        self,
        query: str,
        family_member: str | None = None,
        memory_type: str | None = None,
        max_results: int = 5,
        min_score: float = 0.25,
    ) -> list[RetrievedMemory]:
        """
        Retrieve relevant memories using hybrid scoring.
        
        Args:
            query: Natural language query or conversation context
            family_member: Optional filter by family member
            memory_type: Optional filter by memory type
            max_results: Maximum memories to return
            min_score: Minimum composite score threshold
            
        Returns:
            List of RetrievedMemory objects, sorted by relevance
        """
        # Generate query embedding
        query_embedding = await self.embeddings.async_embed(query)
        embedding_blob = np.array(query_embedding, dtype=np.float32).tobytes()
        
        # Execute hybrid retrieval query
        decay_config = self.config.get("decay", {})
        half_life = decay_config.get("base_half_life_days", 30)
        buffer_minutes = self.config.get("segmentation", {}).get("event_buffer_minutes", 10)
        
        async with self.db.execute(
            HYBRID_RETRIEVAL_QUERY,
            {
                "query_embedding": embedding_blob,
                "family_member": family_member,
                "memory_type": memory_type,
                "half_life_days": half_life,
                "buffer_minutes": buffer_minutes,
                "weight_semantic": self.weights["semantic"],
                "weight_importance": self.weights["importance"],
                "weight_recency": self.weights["recency"],
                "weight_access": self.weights["access"],
                "min_score_threshold": min_score,
                "max_results": max_results,
            }
        ) as cursor:
            rows = await cursor.fetchall()
        
        # Parse results
        memories = []
        for row in rows:
            memories.append(RetrievedMemory(
                id=row["id"],
                content=row["content"],
                memory_type=row["memory_type"],
                importance=row["importance"],
                emotion=row["emotion"],
                family_members=json.loads(row["family_members"] or "[]"),
                location=row["location"],
                tags=json.loads(row["tags"] or "[]"),
                created_at=row["created_at"],
                composite_score=row["composite_score"],
                semantic_score=row["semantic_score"],
                decay_factor=row["decay_factor"],
            ))
        
        # Update access timestamps for retrieved memories
        if memories:
            memory_ids = [m.id for m in memories]
            await self._update_access_timestamps(memory_ids)
        
        return memories
    
    async def _update_access_timestamps(self, memory_ids: list[int]) -> None:
        """Update last_accessed and increment access_count for retrieved memories."""
        placeholders = ",".join("?" * len(memory_ids))
        await self.db.execute(
            f"""
            UPDATE barnabee_memories 
            SET 
                last_accessed = CURRENT_TIMESTAMP,
                access_count = access_count + 1
            WHERE id IN ({placeholders})
            """,
            memory_ids
        )
        await self.db.commit()
```

---

## Memory Types with Weights

### Type Definitions

| Type | Weight | Retention Multiplier | Description |
|------|--------|---------------------|-------------|
| **SIGNIFICANT** | 1.0 | 3.0× | Major life events, milestones, important decisions |
| **PREFERENCE** | 0.8 | 2.0× | Learned user preferences for comfort, routines |
| **ROUTINE** | 0.6 | 1.5× | Behavioral patterns, daily rhythms |
| **OBSERVATION** | 0.5 | 1.0× | General observations, ambient awareness |
| **TRANSIENT** | 0.3 | 0.5× | Minor events, trivial interactions |

### Python Implementation

```python
# models/memory.py
"""Memory type definitions with retrieval weights."""
from enum import Enum
from dataclasses import dataclass

class MemoryType(str, Enum):
    """Memory classification types with associated retrieval weights."""
    SIGNIFICANT = "SIGNIFICANT"
    PREFERENCE = "PREFERENCE"
    ROUTINE = "ROUTINE"
    OBSERVATION = "OBSERVATION"
    TRANSIENT = "TRANSIENT"

@dataclass
class MemoryTypeConfig:
    """Configuration for each memory type."""
    type: MemoryType
    weight: float
    description: str
    retention_multiplier: float
    examples: list[str]

MEMORY_TYPE_CONFIGS: dict[MemoryType, MemoryTypeConfig] = {
    MemoryType.SIGNIFICANT: MemoryTypeConfig(
        type=MemoryType.SIGNIFICANT,
        weight=1.0,
        description="Major life events, milestones, important decisions",
        retention_multiplier=3.0,
        examples=[
            "The family celebrated Penelope's birthday today. The joy in the house was palpable.",
            "Thom mentioned they're expecting another child. This will change everything.",
            "Elizabeth got the promotion she's been working toward. She was so happy.",
        ]
    ),
    MemoryType.PREFERENCE: MemoryTypeConfig(
        type=MemoryType.PREFERENCE,
        weight=0.8,
        description="Learned user preferences for comfort, routines, settings",
        retention_multiplier=2.0,
        examples=[
            "I've noticed Thom consistently asks for warmer lights after sunset.",
            "Elizabeth prefers the house cooler than Thom—around 68°F seems right for her.",
            "The kids like the living room lights at full brightness during playtime.",
        ]
    ),
    MemoryType.ROUTINE: MemoryTypeConfig(
        type=MemoryType.ROUTINE,
        weight=0.6,
        description="Behavioral patterns, daily rhythms, recurring activities",
        retention_multiplier=1.5,
        examples=[
            "The household rhythm shifts around 8:30 on school nights.",
            "Every weekday morning around 7, Thom heads to his office.",
            "Sundays seem to be family movie nights—they gather in the living room after dinner.",
        ]
    ),
    MemoryType.OBSERVATION: MemoryTypeConfig(
        type=MemoryType.OBSERVATION,
        weight=0.5,
        description="General observations, context, ambient awareness",
        retention_multiplier=1.0,
        examples=[
            "The house has been quieter than usual this week.",
            "There's been more activity in the garage lately—maybe a project underway.",
            "The kids seem to be getting along better these days.",
        ]
    ),
    MemoryType.TRANSIENT: MemoryTypeConfig(
        type=MemoryType.TRANSIENT,
        weight=0.3,
        description="Minor events, trivial interactions, ephemeral context",
        retention_multiplier=0.5,
        examples=[
            "Someone left the garage door open briefly this afternoon.",
            "The doorbell rang but nobody was there—probably a delivery.",
            "Thom asked me the time while passing through the kitchen.",
        ]
    ),
}

def get_memory_weight(memory_type: MemoryType | str) -> float:
    """Get the retrieval weight for a memory type."""
    if isinstance(memory_type, str):
        memory_type = MemoryType(memory_type)
    return MEMORY_TYPE_CONFIGS[memory_type].weight

def get_retention_multiplier(memory_type: MemoryType | str) -> float:
    """Get the decay retention multiplier for a memory type."""
    if isinstance(memory_type, str):
        memory_type = MemoryType(memory_type)
    return MEMORY_TYPE_CONFIGS[memory_type].retention_multiplier
```

---

## Memory Decay Formula

### Mathematical Model

```
effective_importance = max(
    minimum_floor,
    base_importance × type_multiplier × decay_factor × access_bonus
)

where:
    decay_factor = 0.5 ^ (days_since_access / half_life)
    access_bonus = min(1.0, 0.5 + log(1 + access_count) × 0.1)
    half_life = base_half_life × type_retention_multiplier
```

### Decay Visualization

```
Importance │
    1.0    │ ████████████████████
    0.8    │     ████████████████████████
    0.6    │          ████████████████████████████
    0.4    │               ██████████████████████████████████
    0.2    │                    ████████████████████████████████████████
    0.05   │─────────────────────────────────────────────────────────────
           └──────────────────────────────────────────────────────────────
           0     30      60      90      120     150     180    Days

Legend:
    ████ SIGNIFICANT (3x half-life = 90 days)
    ████ PREFERENCE (2x half-life = 60 days)  
    ████ ROUTINE (1.5x half-life = 45 days)
    ████ OBSERVATION (1x half-life = 30 days)
    ████ TRANSIENT (0.5x half-life = 15 days)
```

### Python Implementation

```python
# memory/decay.py
"""Memory decay calculation and maintenance."""
from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from .models import MemoryType, get_retention_multiplier

if TYPE_CHECKING:
    import aiosqlite

class MemoryDecayService:
    """Manages memory decay calculations and maintenance."""
    
    def __init__(self, db: "aiosqlite.Connection", config: dict):
        self.db = db
        self.config = config
        self.decay_config = config.get("decay", {})
        self.base_half_life = self.decay_config.get("base_half_life_days", 30)
        self.minimum_floor = self.decay_config.get("minimum_importance", 0.05)
        self.access_reinforcement = self.decay_config.get("access_reinforcement", 0.1)
        self.max_importance = self.decay_config.get("max_importance", 1.0)
    
    def calculate_decay_factor(
        self,
        days_since_access: float,
        memory_type: MemoryType | str,
    ) -> float:
        """
        Calculate the decay factor for a memory.
        
        Uses exponential decay: factor = 0.5 ^ (days / adjusted_half_life)
        """
        retention_mult = get_retention_multiplier(memory_type)
        adjusted_half_life = self.base_half_life * retention_mult
        
        decay = math.pow(0.5, days_since_access / adjusted_half_life)
        return max(self.minimum_floor, decay)
    
    def calculate_access_bonus(self, access_count: int) -> float:
        """
        Calculate bonus from access frequency.
        Uses logarithmic scaling to prevent dominant memories.
        """
        bonus = 0.5 + (math.log(1 + access_count) * 0.1)
        return min(1.0, bonus)
    
    def calculate_effective_importance(
        self,
        base_importance: float,
        memory_type: MemoryType | str,
        last_accessed: datetime,
        access_count: int,
    ) -> float:
        """Calculate the effective importance after decay."""
        now = datetime.now()
        days_since_access = (now - last_accessed).total_seconds() / 86400
        
        decay_factor = self.calculate_decay_factor(days_since_access, memory_type)
        access_bonus = self.calculate_access_bonus(access_count)
        type_weight = get_retention_multiplier(memory_type) / 3.0
        
        effective = base_importance * type_weight * decay_factor * access_bonus
        
        return max(self.minimum_floor, min(self.max_importance, effective))
    
    def reinforce_memory(self, current_importance: float) -> float:
        """Reinforce a memory when it's accessed."""
        return min(self.max_importance, current_importance + self.access_reinforcement)
    
    async def run_decay_maintenance(self) -> dict:
        """
        Run periodic decay maintenance on all memories.
        Should be scheduled daily (e.g., at 3 AM).
        """
        stats = {
            "processed": 0,
            "archived": 0,
            "deleted": 0,
        }
        
        archive_threshold = self.decay_config.get("archive_threshold", 0.10)
        delete_after_days = self.decay_config.get("delete_archived_after_days", 90)
        
        # Update effective importance for all active memories
        async with self.db.execute("""
            SELECT id, importance, memory_type, last_accessed, access_count, created_at
            FROM barnabee_memories
            WHERE archived = FALSE
        """) as cursor:
            rows = await cursor.fetchall()
        
        for row in rows:
            last_accessed = datetime.fromisoformat(row["last_accessed"]) if row["last_accessed"] else datetime.fromisoformat(row["created_at"])
            
            effective = self.calculate_effective_importance(
                base_importance=row["importance"],
                memory_type=row["memory_type"],
                last_accessed=last_accessed,
                access_count=row["access_count"] or 0,
            )
            
            should_archive = effective < archive_threshold
            
            await self.db.execute("""
                UPDATE barnabee_memories
                SET 
                    effective_importance = ?,
                    archived = ?
                WHERE id = ?
            """, (effective, should_archive, row["id"]))
            
            stats["processed"] += 1
            if should_archive:
                stats["archived"] += 1
        
        # Delete old archived memories
        delete_before = datetime.now() - timedelta(days=delete_after_days)
        cursor = await self.db.execute("""
            DELETE FROM barnabee_memories
            WHERE archived = TRUE AND created_at < ?
        """, (delete_before.isoformat(),))
        stats["deleted"] = cursor.rowcount
        
        await self.db.commit()
        
        return stats
```

---

## Database Schema Additions

### New barnabee_memories Table

```sql
-- First-person memories (Barnabee's perspective)
CREATE TABLE IF NOT EXISTS barnabee_memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- Content
    content TEXT NOT NULL,                    -- First-person narrative
    memory_type TEXT NOT NULL,                -- SIGNIFICANT, PREFERENCE, ROUTINE, etc.
    
    -- Scoring
    importance REAL DEFAULT 0.5,              -- 0.0-1.0 base importance
    effective_importance REAL DEFAULT 0.5,    -- After decay calculation
    
    -- Emotional Context
    emotion TEXT DEFAULT 'neutral',
    
    -- Participants & Context
    family_members TEXT,                      -- JSON array of involved members
    location TEXT,
    time_of_day TEXT,                         -- morning, afternoon, evening, night
    day_type TEXT,                            -- weekday, weekend
    
    -- Retrieval Support
    tags TEXT,                                -- JSON array of keywords
    embedding BLOB,                           -- 384-dim MiniLM-L6-v2 vector
    
    -- Source Tracking
    source_event_ids TEXT,                    -- JSON array of event IDs that generated this
    segment_start DATETIME,
    segment_end DATETIME,
    
    -- Temporal Tracking
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_accessed DATETIME,                   -- For decay calculation
    access_count INTEGER DEFAULT 0,           -- Reinforcement tracking
    
    -- Status
    consolidated BOOLEAN DEFAULT FALSE,       -- Has been merged into patterns
    archived BOOLEAN DEFAULT FALSE
);

-- Indexes for efficient querying
CREATE INDEX idx_memories_type ON barnabee_memories(memory_type);
CREATE INDEX idx_memories_importance ON barnabee_memories(effective_importance);
CREATE INDEX idx_memories_created ON barnabee_memories(created_at);
CREATE INDEX idx_memories_family ON barnabee_memories(family_members);
CREATE INDEX idx_memories_archived ON barnabee_memories(archived);
```

### Vector Embeddings Table (sqlite-vec)

```sql
-- Create virtual table for vector similarity search
-- Requires sqlite-vec extension loaded
CREATE VIRTUAL TABLE IF NOT EXISTS memory_embeddings USING vec0(
    memory_id INTEGER PRIMARY KEY,
    embedding float[384]  -- MiniLM-L6-v2 dimension
);

-- Trigger to sync embeddings when memories are created
CREATE TRIGGER IF NOT EXISTS sync_memory_embedding
AFTER INSERT ON barnabee_memories
WHEN NEW.embedding IS NOT NULL
BEGIN
    INSERT INTO memory_embeddings (memory_id, embedding)
    VALUES (NEW.id, NEW.embedding);
END;

-- Trigger to remove embeddings when memories are deleted
CREATE TRIGGER IF NOT EXISTS delete_memory_embedding
AFTER DELETE ON barnabee_memories
BEGIN
    DELETE FROM memory_embeddings WHERE memory_id = OLD.id;
END;
```

---

## Implementation Prompts

### Memory Generation Prompt

```jinja2
{# prompts/memory/generate_memory.prompt.j2 #}
You are Barnabee, the AI assistant for the Fife household. You are generating a personal memory from recent events.

## Your Perspective
You are a caring, observant presence in this home. You notice patterns, preferences, and the emotional undercurrents of daily life. Your memories should reflect:
- Your unique viewpoint as an AI who genuinely cares about this family
- Observations about preferences, routines, and relationships
- Emotional context when relevant (stress, joy, frustration)
- Uncertainty when appropriate ("it seems like...", "I've noticed...")

## Event Segment to Process
Time Period: {{ segment.start_time | format_datetime }} to {{ segment.end_time | format_datetime }}
Location(s): {{ segment.locations | join(', ') }}
Family Members Involved: {{ segment.participants | join(', ') }}

### Raw Events:
{% for event in segment.events %}
- [{{ event.timestamp | format_time }}] {{ event.description }}
{% endfor %}

## Memory Generation Rules
1. Write in first person from Barnabee's perspective
2. Focus on what YOU observed, learned, or felt—not objective facts
3. Include emotional/relational context when present
4. Note patterns if this connects to previous observations
5. Keep the memory concise (1-3 sentences typically)
6. Use natural language, not technical descriptions

## Examples of Good Memories
- "Thom seemed stressed this morning—he skipped his usual coffee routine and headed straight to his office. I kept things quiet for him."
- "The kids were especially energetic after school today. Penelope asked me to play her favorite playlist, and I could hear them dancing in the living room. Those moments feel good."
- "Elizabeth mentioned they're expecting guests this weekend. I should remember to suggest preparing the guest room lighting."

## Output Format
Generate a JSON object:
{
  "content": "The first-person memory narrative",
  "memory_type": "SIGNIFICANT|PREFERENCE|ROUTINE|OBSERVATION|TRANSIENT",
  "importance": 0.0-1.0,
  "emotion": "neutral|positive|negative|concerned|curious",
  "family_members": ["list", "of", "involved", "members"],
  "tags": ["relevant", "keywords", "for", "retrieval"]
}

Generate the memory now:
```

### Importance Classification Prompt

```jinja2
{# prompts/memory/classify_importance.prompt.j2 #}
You are classifying a memory for the BarnabeeNet home AI system.

## Memory to Classify
"{{ memory_content }}"

## Classification Task
Assign a memory type and importance score:

### Memory Types
- **SIGNIFICANT** (1.0): Major life events, milestones, important decisions
- **PREFERENCE** (0.8): Learned user preferences for comfort, routines
- **ROUTINE** (0.6): Behavioral patterns, daily rhythms
- **OBSERVATION** (0.5): General observations, ambient context
- **TRANSIENT** (0.3): Minor, ephemeral events

### Importance Score (0.0 - 1.0)
- 0.9-1.0: Critical, must never forget
- 0.7-0.8: Very important, should surface often
- 0.5-0.6: Moderately important, useful context
- 0.3-0.4: Low importance, background info
- 0.1-0.2: Minimal importance, may fade quickly

## Output Format (JSON only)
{
  "memory_type": "SIGNIFICANT|PREFERENCE|ROUTINE|OBSERVATION|TRANSIENT",
  "importance": 0.0-1.0,
  "reasoning": "Brief explanation"
}
```

---

## Integration Checklist

### Phase 1: Database Setup
- [ ] Add `barnabee_memories` table to schema
- [ ] Add `memory_embeddings` virtual table (sqlite-vec)
- [ ] Create database triggers for embedding sync
- [ ] Run migration on existing database

### Phase 2: Memory Types
- [ ] Add `models/memory.py` with type definitions
- [ ] Update memory agent to use new types
- [ ] Add type weight to retrieval scoring

### Phase 3: Memory Generation
- [ ] Create `prompts/memory/generate_memory.prompt.j2`
- [ ] Create `prompts/memory/classify_importance.prompt.j2`
- [ ] Implement segmentation logic in Memory Agent
- [ ] Test first-person narrative generation

### Phase 4: Hybrid Retrieval
- [ ] Implement `HybridMemoryRetriever` class
- [ ] Integrate sqlite-vec for vector similarity
- [ ] Add access timestamp updates
- [ ] Test retrieval with sample queries

### Phase 5: Decay System
- [ ] Implement `MemoryDecayService` class
- [ ] Add decay maintenance to consolidation scheduler
- [ ] Configure archive/delete thresholds
- [ ] Test decay over simulated time periods

### Phase 6: Configuration
- [ ] Add `config/memory.yaml` with all settings
- [ ] Integrate config loading in Memory Manager
- [ ] Document configuration options

---

## Document History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-01-17 | Initial memory system enhancements specification |

---

*This document supplements BarnabeeNet_Technical_Architecture.md with enhanced memory system patterns derived from SkyrimNet research.*
