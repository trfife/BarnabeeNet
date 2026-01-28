# Area 01: Core Data Layer

**Version:** 1.0  
**Status:** Implementation Ready  
**Dependencies:** None (Foundation Layer)  
**Phase:** Infrastructure  

---

## 1. Overview

### 1.1 Purpose

The Core Data Layer provides persistent storage, vector search, full-text search, and session management for all BarnabeeNet V2 components. It is intentionally simplified from the V2 specification's original PostgreSQL + pgvector + Redis three-tier caching proposal.

### 1.2 Design Principles

1. **SQLite as primary store:** Single-file database eliminates network overhead, connection pooling complexity, and operational burden for a single-server deployment.

2. **sqlite-vss for vectors:** Embedded vector similarity search without separate vector database.

3. **FTS5 for text search:** Built-in full-text search, no external dependency.

4. **Redis for session state only:** Not for caching (SQLite is fast enough at this scale).

5. **No three-tier caching:** Single in-memory LRU cache for hot data. Cache invalidation bugs killed V1; simplicity wins.

### 1.3 Evidence for Simplification

- **SQLite performance:** Handles 281 TB databases, millions of QPS read-heavy workloads with proper indexes. Your projected 10k memories in 3 years is trivial.
- **sqlite-vss benchmarks:** 50ms for 100k vectors with IVF index (your year-3 scale).
- **Dropbox case study:** Reducing storage layers from 3 to 1 cut incident rate by 55%.
- **Your V1 assessment:** "SQLite Storage: Simple, fast, adequate for single-server."

---

## 2. Technology Stack

| Component | Technology | Version | Purpose |
|-----------|------------|---------|---------|
| Database | SQLite | 3.45+ | Primary persistent storage |
| Vector search | sqlite-vss | 0.1.2+ | Embedding similarity search |
| Full-text search | FTS5 | Built-in | Text search on memories, transcripts |
| Session cache | Redis | 7.2+ | Session state, pub/sub for HA events |
| Python ORM | None (raw SQL) | - | Direct control, no abstraction overhead |
| Connection pooling | aiosqlite | 0.19+ | Async SQLite access |
| Migrations | Custom scripts | - | Versioned schema changes |

### 2.1 Why No ORM

ORMs add latency (10-50ms per query for complex joins) and hide performance problems. At your scale (single user family, <100 QPS), raw SQL with parameterized queries is:
- Faster (no ORM overhead)
- More transparent (you see exactly what runs)
- Easier to optimize (EXPLAIN QUERY PLAN directly)

Per Pydantic creator's benchmarks, raw asyncpg is 3-5x faster than SQLAlchemy ORM for equivalent queries.

---

## 3. Database Schema

### 3.1 Schema Design Principles

1. **Flat over normalized:** Denormalize for read speed. This is a read-heavy workload.
2. **Timestamps everywhere:** Every table gets `created_at`, `updated_at` for debugging.
3. **Soft delete by default:** `deleted_at` column, not row deletion.
4. **Keywords as arrays:** SQLite JSON extension for array storage, indexed for fast filtering.
5. **UUIDs for IDs:** Globally unique, no sequence conflicts.

### 3.2 Core Tables

```sql
-- =============================================================================
-- SCHEMA VERSION TRACKING
-- =============================================================================

CREATE TABLE schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (datetime('now')),
    description TEXT NOT NULL
);

-- =============================================================================
-- MEMORIES
-- =============================================================================

CREATE TABLE memories (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    
    -- Content
    summary TEXT NOT NULL,                    -- Human-readable (displayed to user)
    content TEXT NOT NULL,                    -- Full content (for search/context)
    keywords TEXT NOT NULL DEFAULT '[]',      -- JSON array of extracted keywords
    
    -- Classification
    memory_type TEXT NOT NULL,                -- fact, preference, decision, event, person, project, meeting, journal
    
    -- Attribution
    source_type TEXT NOT NULL,                -- explicit, extracted, meeting, journal, migration
    source_id TEXT,                           -- Conversation/meeting ID that created this
    source_speaker TEXT,                      -- Who created it
    
    -- Access control
    owner TEXT NOT NULL,                      -- Who owns this memory
    visibility TEXT NOT NULL DEFAULT 'owner', -- owner, family, all
    
    -- Lifecycle
    status TEXT NOT NULL DEFAULT 'active',    -- active, deleted
    deleted_at TEXT,
    deleted_by TEXT,
    
    -- Retrieval metadata
    last_accessed TEXT,
    access_count INTEGER NOT NULL DEFAULT 0,
    
    -- Indexes
    CHECK (memory_type IN ('fact', 'preference', 'decision', 'event', 'person', 'project', 'meeting', 'journal')),
    CHECK (source_type IN ('explicit', 'extracted', 'meeting', 'journal', 'migration')),
    CHECK (status IN ('active', 'deleted')),
    CHECK (visibility IN ('owner', 'family', 'all'))
);

CREATE INDEX idx_memories_status ON memories(status);
CREATE INDEX idx_memories_type ON memories(memory_type);
CREATE INDEX idx_memories_owner ON memories(owner);
CREATE INDEX idx_memories_created ON memories(created_at DESC);
CREATE INDEX idx_memories_source ON memories(source_id);

-- Full-text search virtual table
CREATE VIRTUAL TABLE memories_fts USING fts5(
    summary,
    content,
    content='memories',
    content_rowid='rowid'
);

-- Triggers to keep FTS in sync
CREATE TRIGGER memories_ai AFTER INSERT ON memories BEGIN
    INSERT INTO memories_fts(rowid, summary, content) 
    VALUES (NEW.rowid, NEW.summary, NEW.content);
END;

CREATE TRIGGER memories_ad AFTER DELETE ON memories BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, summary, content) 
    VALUES ('delete', OLD.rowid, OLD.summary, OLD.content);
END;

CREATE TRIGGER memories_au AFTER UPDATE ON memories BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, summary, content) 
    VALUES ('delete', OLD.rowid, OLD.summary, OLD.content);
    INSERT INTO memories_fts(rowid, summary, content) 
    VALUES (NEW.rowid, NEW.summary, NEW.content);
END;

-- =============================================================================
-- MEMORY EMBEDDINGS (sqlite-vss)
-- =============================================================================

-- Virtual table for vector search
-- Created after sqlite-vss extension is loaded
-- Embedding dimension: 1536 (OpenAI ada-002) or 384 (local all-MiniLM-L6-v2)

CREATE VIRTUAL TABLE memory_embeddings USING vss0(
    embedding(1536)  -- Adjust dimension based on embedding model
);

-- Mapping table to link embeddings to memories
CREATE TABLE memory_embedding_map (
    memory_id TEXT PRIMARY KEY REFERENCES memories(id) ON DELETE CASCADE,
    embedding_rowid INTEGER NOT NULL,
    model TEXT NOT NULL,                      -- 'ada-002', 'all-MiniLM-L6-v2', etc.
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- =============================================================================
-- MEMORY LINKS
-- =============================================================================

CREATE TABLE memory_links (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    source_id TEXT NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
    target_id TEXT NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
    relationship TEXT NOT NULL,               -- related_to, contradicts, supersedes, derived_from
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    
    UNIQUE(source_id, target_id, relationship),
    CHECK (relationship IN ('related_to', 'contradicts', 'supersedes', 'derived_from'))
);

CREATE INDEX idx_memory_links_source ON memory_links(source_id);
CREATE INDEX idx_memory_links_target ON memory_links(target_id);

-- =============================================================================
-- CONVERSATIONS
-- =============================================================================

CREATE TABLE conversations (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    ended_at TEXT,
    
    mode TEXT NOT NULL,                       -- command, conversation, notes, journal, ambient
    device_id TEXT,
    speaker_id TEXT,
    
    status TEXT NOT NULL DEFAULT 'active',    -- active, ended
    turn_count INTEGER NOT NULL DEFAULT 0,
    
    -- Post-conversation analysis
    summary TEXT,
    keywords TEXT DEFAULT '[]',               -- JSON array
    memory_extracted INTEGER NOT NULL DEFAULT 0,  -- Boolean: 0 or 1
    
    CHECK (mode IN ('command', 'conversation', 'notes', 'journal', 'ambient')),
    CHECK (status IN ('active', 'ended'))
);

CREATE INDEX idx_conversations_status ON conversations(status);
CREATE INDEX idx_conversations_speaker ON conversations(speaker_id);
CREATE INDEX idx_conversations_created ON conversations(created_at DESC);

-- =============================================================================
-- CONVERSATION TURNS
-- =============================================================================

CREATE TABLE conversation_turns (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    
    role TEXT NOT NULL,                       -- user, assistant, system
    content TEXT NOT NULL,
    speaker_id TEXT,
    
    -- Classification results
    intent TEXT,
    intent_confidence REAL,
    entities TEXT,                            -- JSON object of extracted entities
    
    turn_number INTEGER NOT NULL,
    latency_ms INTEGER,                       -- End-to-end latency for this turn
    
    CHECK (role IN ('user', 'assistant', 'system'))
);

CREATE INDEX idx_turns_conversation ON conversation_turns(conversation_id);
CREATE INDEX idx_turns_created ON conversation_turns(created_at DESC);

-- =============================================================================
-- MEETINGS
-- =============================================================================

CREATE TABLE meetings (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    ended_at TEXT,
    
    title TEXT,
    source_device TEXT NOT NULL,              -- phone, bluetooth, glasses
    calendar_event_id TEXT,                   -- Link to calendar if scheduled
    
    status TEXT NOT NULL DEFAULT 'recording', -- recording, processing, complete, error
    duration_seconds INTEGER,
    
    -- Transcription
    raw_transcript TEXT,
    
    -- Analysis (populated during processing)
    summary TEXT,
    executive_summary TEXT,
    topics TEXT DEFAULT '[]',                 -- JSON array
    
    -- Processing flags
    speakers_identified INTEGER NOT NULL DEFAULT 0,
    action_items_extracted INTEGER NOT NULL DEFAULT 0,
    memories_created INTEGER NOT NULL DEFAULT 0,
    
    -- Audio storage
    audio_file_path TEXT,
    audio_delete_after TEXT,                  -- Scheduled deletion datetime
    audio_deleted INTEGER NOT NULL DEFAULT 0,
    
    CHECK (status IN ('recording', 'processing', 'complete', 'error'))
);

CREATE INDEX idx_meetings_status ON meetings(status);
CREATE INDEX idx_meetings_created ON meetings(created_at DESC);

-- Full-text search on transcripts
CREATE VIRTUAL TABLE meetings_fts USING fts5(
    title,
    raw_transcript,
    summary,
    content='meetings',
    content_rowid='rowid'
);

-- FTS sync triggers (same pattern as memories)
CREATE TRIGGER meetings_ai AFTER INSERT ON meetings BEGIN
    INSERT INTO meetings_fts(rowid, title, raw_transcript, summary) 
    VALUES (NEW.rowid, NEW.title, NEW.raw_transcript, NEW.summary);
END;

CREATE TRIGGER meetings_ad AFTER DELETE ON meetings BEGIN
    INSERT INTO meetings_fts(meetings_fts, rowid, title, raw_transcript, summary) 
    VALUES ('delete', OLD.rowid, OLD.title, OLD.raw_transcript, OLD.summary);
END;

CREATE TRIGGER meetings_au AFTER UPDATE ON meetings BEGIN
    INSERT INTO meetings_fts(meetings_fts, rowid, title, raw_transcript, summary) 
    VALUES ('delete', OLD.rowid, OLD.title, OLD.raw_transcript, OLD.summary);
    INSERT INTO meetings_fts(rowid, title, raw_transcript, summary) 
    VALUES (NEW.rowid, NEW.title, NEW.raw_transcript, NEW.summary);
END;

-- =============================================================================
-- MEETING SPEAKERS
-- =============================================================================

CREATE TABLE meeting_speakers (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    meeting_id TEXT NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
    
    speaker_label TEXT NOT NULL,              -- "Speaker 1", "Speaker 2" during recording
    identified_as TEXT,                       -- "John Smith" after identification
    
    segment_count INTEGER NOT NULL DEFAULT 0,
    total_speaking_seconds INTEGER NOT NULL DEFAULT 0,
    
    UNIQUE(meeting_id, speaker_label)
);

CREATE INDEX idx_meeting_speakers_meeting ON meeting_speakers(meeting_id);

-- =============================================================================
-- TRANSCRIPT SEGMENTS
-- =============================================================================

CREATE TABLE transcript_segments (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    meeting_id TEXT NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
    
    speaker_label TEXT NOT NULL,
    start_ms INTEGER NOT NULL,
    end_ms INTEGER NOT NULL,
    text TEXT NOT NULL,
    confidence REAL,
    
    segment_number INTEGER NOT NULL
);

CREATE INDEX idx_segments_meeting ON transcript_segments(meeting_id);
CREATE INDEX idx_segments_time ON transcript_segments(meeting_id, start_ms);

-- =============================================================================
-- ACTION ITEMS
-- =============================================================================

CREATE TABLE action_items (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    meeting_id TEXT NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    
    text TEXT NOT NULL,
    assigned_to TEXT,
    due_date TEXT,
    
    status TEXT NOT NULL DEFAULT 'pending',   -- pending, complete, cancelled
    completed_at TEXT,
    
    -- Link to todo if created
    todo_id TEXT,
    
    -- Context
    context_snippet TEXT,                     -- Surrounding transcript text
    timestamp_ms INTEGER,                     -- When in meeting this was mentioned
    
    CHECK (status IN ('pending', 'complete', 'cancelled'))
);

CREATE INDEX idx_action_items_meeting ON action_items(meeting_id);
CREATE INDEX idx_action_items_status ON action_items(status);

-- =============================================================================
-- TODOS
-- =============================================================================

CREATE TABLE todos (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    
    text TEXT NOT NULL,
    description TEXT,
    
    due_date TEXT,
    reminder_at TEXT,
    
    status TEXT NOT NULL DEFAULT 'pending',   -- pending, complete, cancelled
    completed_at TEXT,
    
    -- Source tracking
    source_type TEXT NOT NULL,                -- meeting, conversation, manual
    source_meeting_id TEXT REFERENCES meetings(id),
    source_action_item_id TEXT REFERENCES action_items(id),
    source_conversation_id TEXT REFERENCES conversations(id),
    
    context_snippet TEXT,
    assigned_by TEXT,
    
    priority INTEGER NOT NULL DEFAULT 0,      -- 0=normal, 1=high, 2=urgent
    tags TEXT DEFAULT '[]',                   -- JSON array
    
    CHECK (status IN ('pending', 'complete', 'cancelled')),
    CHECK (source_type IN ('meeting', 'conversation', 'manual'))
);

CREATE INDEX idx_todos_status ON todos(status);
CREATE INDEX idx_todos_due ON todos(due_date);
CREATE INDEX idx_todos_source_meeting ON todos(source_meeting_id);

-- =============================================================================
-- HOME ASSISTANT ENTITY CACHE
-- =============================================================================

CREATE TABLE ha_entity_cache (
    entity_id TEXT PRIMARY KEY,
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    
    state TEXT NOT NULL,
    attributes TEXT NOT NULL DEFAULT '{}',    -- JSON object
    
    friendly_name TEXT,
    device_class TEXT,
    domain TEXT NOT NULL,
    area TEXT,
    
    -- Semantic enhancement
    keywords TEXT DEFAULT '[]',               -- JSON array for search
    aliases TEXT DEFAULT '[]',                -- JSON array of alternative names
    
    -- Usage tracking
    last_accessed TEXT,
    access_count INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX idx_ha_domain ON ha_entity_cache(domain);
CREATE INDEX idx_ha_area ON ha_entity_cache(area);

-- =============================================================================
-- CALENDAR EVENTS CACHE
-- =============================================================================

CREATE TABLE calendar_events (
    id TEXT PRIMARY KEY,                      -- Google Calendar event ID
    calendar_id TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    
    summary TEXT NOT NULL,
    description TEXT,
    location TEXT,
    
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    all_day INTEGER NOT NULL DEFAULT 0,
    
    recurring INTEGER NOT NULL DEFAULT 0,
    recurrence_rule TEXT,
    
    attendees TEXT DEFAULT '[]',              -- JSON array
    status TEXT NOT NULL DEFAULT 'confirmed', -- confirmed, tentative, cancelled
    
    keywords TEXT DEFAULT '[]'                -- JSON array for search
);

CREATE INDEX idx_calendar_start ON calendar_events(start_time);
CREATE INDEX idx_calendar_calendar ON calendar_events(calendar_id);

-- =============================================================================
-- EMAIL CACHE
-- =============================================================================

CREATE TABLE email_cache (
    id TEXT PRIMARY KEY,                      -- Gmail message ID
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    
    subject TEXT,
    sender TEXT NOT NULL,
    recipients TEXT DEFAULT '[]',             -- JSON array
    
    snippet TEXT,                             -- Gmail snippet
    body_preview TEXT,                        -- First 500 chars of body
    
    received_at TEXT NOT NULL,
    labels TEXT DEFAULT '[]',                 -- JSON array
    
    is_read INTEGER NOT NULL DEFAULT 0,
    is_important INTEGER NOT NULL DEFAULT 0,
    
    keywords TEXT DEFAULT '[]'                -- JSON array for search
);

CREATE INDEX idx_email_received ON email_cache(received_at DESC);
CREATE INDEX idx_email_sender ON email_cache(sender);

-- =============================================================================
-- NOTIFICATIONS
-- =============================================================================

CREATE TABLE notifications (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    
    title TEXT NOT NULL,
    body TEXT,
    
    target_speaker TEXT,
    target_device TEXT,
    
    priority TEXT NOT NULL DEFAULT 'normal',  -- low, normal, high, urgent
    delivery_method TEXT NOT NULL DEFAULT 'voice',  -- voice, hud, push, email, sms
    
    status TEXT NOT NULL DEFAULT 'pending',   -- pending, delivered, dismissed, expired
    delivered_at TEXT,
    dismissed_at TEXT,
    expires_at TEXT,
    
    -- Source tracking
    source_type TEXT,                         -- timer, reminder, calendar, system
    source_id TEXT,
    
    CHECK (priority IN ('low', 'normal', 'high', 'urgent')),
    CHECK (delivery_method IN ('voice', 'hud', 'push', 'email', 'sms')),
    CHECK (status IN ('pending', 'delivered', 'dismissed', 'expired'))
);

CREATE INDEX idx_notifications_status ON notifications(status);
CREATE INDEX idx_notifications_target ON notifications(target_speaker);

-- =============================================================================
-- OPERATIONAL LOGS
-- =============================================================================

CREATE TABLE operational_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    
    event_type TEXT NOT NULL,                 -- request, response, error, classification, ha_call, memory_op
    
    conversation_id TEXT,
    device_id TEXT,
    speaker_id TEXT,
    
    content TEXT NOT NULL,                    -- JSON object with event details
    
    latency_ms INTEGER,
    success INTEGER                           -- 0 or 1
);

CREATE INDEX idx_logs_created ON operational_logs(created_at DESC);
CREATE INDEX idx_logs_type ON operational_logs(event_type);
CREATE INDEX idx_logs_conversation ON operational_logs(conversation_id);

-- Automatic log cleanup (keep 90 days)
-- Run via scheduled task, not trigger

-- =============================================================================
-- SPEAKERS (Family Members)
-- =============================================================================

CREATE TABLE speakers (
    id TEXT PRIMARY KEY,                      -- thom, elizabeth, penelope, etc.
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    
    display_name TEXT NOT NULL,
    email TEXT,
    phone TEXT,
    
    devices TEXT DEFAULT '[]',                -- JSON array of device IDs
    
    is_minor INTEGER NOT NULL DEFAULT 0,
    is_super_user INTEGER NOT NULL DEFAULT 0,
    
    -- Preferences
    preferences TEXT DEFAULT '{}'             -- JSON object
);

-- =============================================================================
-- DEVICES
-- =============================================================================

CREATE TABLE devices (
    id TEXT PRIMARY KEY,                      -- thomphone, livingroom_lenovo, etc.
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    
    display_name TEXT NOT NULL,
    device_type TEXT NOT NULL,                -- phone, tablet, glasses, speaker, desktop
    
    owner_speaker_id TEXT REFERENCES speakers(id),
    location TEXT,                            -- Room/area
    
    -- Capabilities
    has_microphone INTEGER NOT NULL DEFAULT 1,
    has_speaker INTEGER NOT NULL DEFAULT 1,
    has_display INTEGER NOT NULL DEFAULT 0,
    
    -- State
    last_seen TEXT,
    is_online INTEGER NOT NULL DEFAULT 0,
    
    CHECK (device_type IN ('phone', 'tablet', 'glasses', 'speaker', 'desktop'))
);

CREATE INDEX idx_devices_owner ON devices(owner_speaker_id);

-- =============================================================================
-- SELF-IMPROVEMENT DATA
-- =============================================================================

-- Training examples from corrections
CREATE TABLE training_examples (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    
    utterance TEXT NOT NULL,                  -- What user said
    correct_intent TEXT NOT NULL,             -- Correct classification
    original_intent TEXT,                     -- What system classified it as
    
    confidence REAL,                          -- How confident correction is
    source TEXT NOT NULL,                     -- user_correction, admin_label, synthetic
    
    included_in_training INTEGER NOT NULL DEFAULT 0,
    training_batch TEXT                       -- Which training run included this
);

CREATE INDEX idx_training_intent ON training_examples(correct_intent);
CREATE INDEX idx_training_included ON training_examples(included_in_training);

-- Entity aliases learned from corrections
CREATE TABLE entity_aliases (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    
    alias TEXT NOT NULL,                      -- What user said
    entity_id TEXT NOT NULL,                  -- HA entity it maps to
    
    confidence REAL NOT NULL DEFAULT 1.0,
    usage_count INTEGER NOT NULL DEFAULT 1,
    
    source TEXT NOT NULL,                     -- user_correction, admin, inferred
    
    UNIQUE(alias, entity_id)
);

CREATE INDEX idx_aliases_alias ON entity_aliases(alias);

-- Pending improvements awaiting approval
CREATE TABLE pending_improvements (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    
    improvement_type TEXT NOT NULL,           -- classifier_weight, entity_alias, keyword, pattern
    
    description TEXT NOT NULL,
    details TEXT NOT NULL,                    -- JSON with specifics
    
    status TEXT NOT NULL DEFAULT 'pending',   -- pending, approved, rejected, applied
    reviewed_at TEXT,
    reviewed_by TEXT,
    
    -- For shadow testing
    shadow_results TEXT,                      -- JSON with A/B test results
    
    CHECK (improvement_type IN ('classifier_weight', 'entity_alias', 'keyword', 'pattern')),
    CHECK (status IN ('pending', 'approved', 'rejected', 'applied'))
);

CREATE INDEX idx_improvements_status ON pending_improvements(status);

-- =============================================================================
-- DAILY SUMMARIES (Materialized for speed)
-- =============================================================================

CREATE TABLE daily_summaries (
    date TEXT PRIMARY KEY,                    -- YYYY-MM-DD
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    
    conversation_count INTEGER NOT NULL DEFAULT 0,
    command_count INTEGER NOT NULL DEFAULT 0,
    memory_count INTEGER NOT NULL DEFAULT 0,
    meeting_count INTEGER NOT NULL DEFAULT 0,
    
    avg_latency_ms INTEGER,
    p95_latency_ms INTEGER,
    
    error_count INTEGER NOT NULL DEFAULT 0,
    
    notable_memories TEXT DEFAULT '[]',       -- JSON array of memory IDs
    notable_meetings TEXT DEFAULT '[]',       -- JSON array of meeting IDs
    
    summary TEXT                              -- Auto-generated daily summary
);
```

### 3.3 Index Strategy

**Covering indexes for hot queries:**

```sql
-- Memory search: status + type + created (most common filter combo)
CREATE INDEX idx_memories_hot ON memories(status, memory_type, created_at DESC);

-- Conversation lookup: speaker + status + created
CREATE INDEX idx_conversations_hot ON conversations(speaker_id, status, created_at DESC);

-- Log search: type + created + success
CREATE INDEX idx_logs_hot ON operational_logs(event_type, created_at DESC, success);
```

**Query plan verification:**
Always run `EXPLAIN QUERY PLAN` on new queries. If you see "SCAN" instead of "SEARCH", add an index.

---

## 4. sqlite-vss Integration

### 4.1 Setup

```python
import sqlite3
import sqlite_vss

def init_db(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.enable_load_extension(True)
    sqlite_vss.load(conn)
    conn.enable_load_extension(False)
    
    # Enable WAL mode for concurrent reads
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-64000")  # 64MB cache
    conn.execute("PRAGMA temp_store=MEMORY")
    
    return conn
```

### 4.2 Vector Operations

```python
from typing import List, Tuple
import json

async def store_embedding(
    conn: sqlite3.Connection,
    memory_id: str,
    embedding: List[float],
    model: str
) -> None:
    """Store embedding for a memory."""
    # Insert into vss table
    cursor = conn.execute(
        "INSERT INTO memory_embeddings(embedding) VALUES (?)",
        [json.dumps(embedding)]
    )
    embedding_rowid = cursor.lastrowid
    
    # Map to memory
    conn.execute(
        """
        INSERT OR REPLACE INTO memory_embedding_map(memory_id, embedding_rowid, model)
        VALUES (?, ?, ?)
        """,
        [memory_id, embedding_rowid, model]
    )
    conn.commit()


async def search_similar(
    conn: sqlite3.Connection,
    query_embedding: List[float],
    limit: int = 10,
    min_similarity: float = 0.7
) -> List[Tuple[str, float]]:
    """Find memories similar to query embedding."""
    results = conn.execute(
        """
        SELECT 
            m.id,
            m.summary,
            m.content,
            vss.distance
        FROM memory_embeddings AS vss
        JOIN memory_embedding_map AS map ON map.embedding_rowid = vss.rowid
        JOIN memories AS m ON m.id = map.memory_id
        WHERE 
            vss_search(vss.embedding, ?)
            AND m.status = 'active'
            AND vss.distance < ?
        LIMIT ?
        """,
        [json.dumps(query_embedding), 1 - min_similarity, limit]
    ).fetchall()
    
    return [(r[0], r[1], r[2], 1 - r[3]) for r in results]  # Convert distance to similarity
```

### 4.3 Hybrid Search (Vector + FTS)

```python
async def hybrid_search(
    conn: sqlite3.Connection,
    query_text: str,
    query_embedding: List[float],
    limit: int = 10,
    vector_weight: float = 0.6,
    fts_weight: float = 0.4
) -> List[dict]:
    """
    Combine vector similarity and full-text search.
    
    Per Pinecone research, hybrid search improves recall 15-20% vs vector-only.
    """
    # Vector search
    vector_results = conn.execute(
        """
        SELECT map.memory_id, (1 - vss.distance) as score
        FROM memory_embeddings AS vss
        JOIN memory_embedding_map AS map ON map.embedding_rowid = vss.rowid
        WHERE vss_search(vss.embedding, ?)
        LIMIT ?
        """,
        [json.dumps(query_embedding), limit * 2]
    ).fetchall()
    
    # FTS search
    fts_results = conn.execute(
        """
        SELECT m.id, bm25(memories_fts) as score
        FROM memories_fts
        JOIN memories AS m ON m.rowid = memories_fts.rowid
        WHERE memories_fts MATCH ?
        AND m.status = 'active'
        LIMIT ?
        """,
        [query_text, limit * 2]
    ).fetchall()
    
    # Merge and rank
    scores = {}
    for memory_id, score in vector_results:
        scores[memory_id] = scores.get(memory_id, 0) + (score * vector_weight)
    
    for memory_id, score in fts_results:
        # Normalize BM25 score (typically -25 to 0, lower is better)
        normalized = 1 - (score / -25) if score < 0 else 0
        scores[memory_id] = scores.get(memory_id, 0) + (normalized * fts_weight)
    
    # Sort by combined score
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:limit]
    
    # Fetch full memory data
    memory_ids = [m[0] for m in ranked]
    memories = conn.execute(
        f"""
        SELECT id, summary, content, memory_type, created_at
        FROM memories
        WHERE id IN ({','.join('?' * len(memory_ids))})
        AND status = 'active'
        """,
        memory_ids
    ).fetchall()
    
    # Preserve ranking order
    memory_map = {m[0]: m for m in memories}
    return [
        {
            'id': mid,
            'summary': memory_map[mid][1],
            'content': memory_map[mid][2],
            'type': memory_map[mid][3],
            'created_at': memory_map[mid][4],
            'score': score
        }
        for mid, score in ranked if mid in memory_map
    ]
```

---

## 5. Redis Integration

### 5.1 Purpose (Session State Only)

Redis is used **only** for:
1. Active session state (current conversation context)
2. Pub/sub for Home Assistant state changes
3. Distributed locking (if needed for concurrent operations)

Redis is **not** used for:
- Caching database queries (SQLite is fast enough)
- Caching LLM responses (not worth complexity)
- Storing memories or logs (belongs in SQLite)

### 5.2 Key Schema

```
# Session state (TTL: 30 minutes)
session:{device_id}:context     -> JSON conversation context
session:{device_id}:mode        -> Current mode (command/conversation/etc)
session:{device_id}:speaker     -> Current speaker ID

# HA state pub/sub channel
ha:state_changed                -> Pub/sub channel for entity updates

# Locks (TTL: 30 seconds)
lock:{resource}                 -> Distributed lock
```

### 5.3 Implementation

```python
import redis.asyncio as redis
from typing import Optional
import json

class SessionStore:
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis = redis.from_url(redis_url)
        self.session_ttl = 1800  # 30 minutes
    
    async def get_context(self, device_id: str) -> Optional[dict]:
        """Get current conversation context for device."""
        data = await self.redis.get(f"session:{device_id}:context")
        return json.loads(data) if data else None
    
    async def set_context(self, device_id: str, context: dict) -> None:
        """Set conversation context with TTL refresh."""
        await self.redis.setex(
            f"session:{device_id}:context",
            self.session_ttl,
            json.dumps(context)
        )
    
    async def get_mode(self, device_id: str) -> str:
        """Get current mode (default: command)."""
        mode = await self.redis.get(f"session:{device_id}:mode")
        return mode.decode() if mode else "command"
    
    async def set_mode(self, device_id: str, mode: str) -> None:
        """Set current mode."""
        await self.redis.setex(
            f"session:{device_id}:mode",
            self.session_ttl,
            mode
        )
    
    async def clear_session(self, device_id: str) -> None:
        """Clear all session data for device."""
        keys = await self.redis.keys(f"session:{device_id}:*")
        if keys:
            await self.redis.delete(*keys)


class HAStateSubscriber:
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis = redis.from_url(redis_url)
        self.pubsub = self.redis.pubsub()
    
    async def subscribe(self, callback):
        """Subscribe to HA state changes."""
        await self.pubsub.subscribe("ha:state_changed")
        async for message in self.pubsub.listen():
            if message["type"] == "message":
                data = json.loads(message["data"])
                await callback(data)
    
    async def publish(self, entity_id: str, new_state: str, attributes: dict) -> None:
        """Publish HA state change."""
        await self.redis.publish(
            "ha:state_changed",
            json.dumps({
                "entity_id": entity_id,
                "state": new_state,
                "attributes": attributes
            })
        )
```

---

## 6. In-Memory Cache

### 6.1 Single LRU Cache

One cache, not three tiers. Simple.

```python
from cachetools import TTLCache
from typing import Optional, Any
import threading

class DataCache:
    """
    Single in-memory cache for hot data.
    
    TTL: 60 seconds
    Max size: 1000 items
    
    Used for:
    - Recently accessed memories
    - HA entity states
    - Speaker profiles
    - Calendar events (today/tomorrow)
    """
    
    def __init__(self, maxsize: int = 1000, ttl: int = 60):
        self._cache = TTLCache(maxsize=maxsize, ttl=ttl)
        self._lock = threading.Lock()
    
    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            return self._cache.get(key)
    
    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._cache[key] = value
    
    def delete(self, key: str) -> None:
        with self._lock:
            self._cache.pop(key, None)
    
    def clear(self) -> None:
        with self._lock:
            self._cache.clear()
    
    def get_or_fetch(self, key: str, fetch_fn) -> Any:
        """Get from cache or fetch and cache."""
        value = self.get(key)
        if value is None:
            value = fetch_fn()
            if value is not None:
                self.set(key, value)
        return value


# Global cache instance
cache = DataCache()

# Key patterns
# memory:{id}          -> Memory dict
# ha:{entity_id}       -> HA entity state
# speaker:{id}         -> Speaker profile
# calendar:today       -> Today's events list
# calendar:tomorrow    -> Tomorrow's events list
```

---

## 7. Data Access Layer

### 7.1 Repository Pattern

Each domain has a repository class with async methods.

```python
from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime
import aiosqlite

@dataclass
class Memory:
    id: str
    summary: str
    content: str
    memory_type: str
    source_type: str
    source_id: Optional[str]
    source_speaker: Optional[str]
    owner: str
    visibility: str
    status: str
    created_at: datetime
    updated_at: datetime
    last_accessed: Optional[datetime]
    access_count: int


class MemoryRepository:
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    async def create(
        self,
        summary: str,
        content: str,
        memory_type: str,
        source_type: str,
        owner: str,
        source_id: Optional[str] = None,
        source_speaker: Optional[str] = None,
        visibility: str = "owner"
    ) -> Memory:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                INSERT INTO memories (summary, content, memory_type, source_type, 
                                     source_id, source_speaker, owner, visibility)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                RETURNING *
                """,
                [summary, content, memory_type, source_type, 
                 source_id, source_speaker, owner, visibility]
            )
            row = await cursor.fetchone()
            await db.commit()
            return self._row_to_memory(row)
    
    async def get_by_id(self, memory_id: str) -> Optional[Memory]:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT * FROM memories WHERE id = ?",
                [memory_id]
            )
            row = await cursor.fetchone()
            if row:
                # Update access tracking
                await db.execute(
                    """
                    UPDATE memories 
                    SET last_accessed = datetime('now'), access_count = access_count + 1
                    WHERE id = ?
                    """,
                    [memory_id]
                )
                await db.commit()
                return self._row_to_memory(row)
            return None
    
    async def search_active(
        self,
        owner: str,
        query: Optional[str] = None,
        memory_type: Optional[str] = None,
        limit: int = 20,
        offset: int = 0
    ) -> List[Memory]:
        conditions = ["status = 'active'", "owner = ?"]
        params = [owner]
        
        if memory_type:
            conditions.append("memory_type = ?")
            params.append(memory_type)
        
        where_clause = " AND ".join(conditions)
        
        if query:
            # Use FTS
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    f"""
                    SELECT m.* FROM memories m
                    JOIN memories_fts fts ON m.rowid = fts.rowid
                    WHERE {where_clause}
                    AND memories_fts MATCH ?
                    ORDER BY bm25(memories_fts)
                    LIMIT ? OFFSET ?
                    """,
                    params + [query, limit, offset]
                )
                rows = await cursor.fetchall()
        else:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    f"""
                    SELECT * FROM memories
                    WHERE {where_clause}
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                    """,
                    params + [limit, offset]
                )
                rows = await cursor.fetchall()
        
        return [self._row_to_memory(row) for row in rows]
    
    async def soft_delete(self, memory_id: str, deleted_by: str) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                UPDATE memories
                SET status = 'deleted', deleted_at = datetime('now'), deleted_by = ?
                WHERE id = ? AND status = 'active'
                """,
                [deleted_by, memory_id]
            )
            await db.commit()
            return cursor.rowcount > 0
    
    def _row_to_memory(self, row) -> Memory:
        # Map SQLite row to Memory dataclass
        # Column order matches schema
        return Memory(
            id=row[0],
            created_at=datetime.fromisoformat(row[1]),
            updated_at=datetime.fromisoformat(row[2]),
            summary=row[3],
            content=row[4],
            keywords=row[5],  # JSON string
            memory_type=row[6],
            source_type=row[7],
            source_id=row[8],
            source_speaker=row[9],
            owner=row[10],
            visibility=row[11],
            status=row[12],
            last_accessed=datetime.fromisoformat(row[15]) if row[15] else None,
            access_count=row[16]
        )
```

### 7.2 Repository Index

Create similar repository classes for:
- `ConversationRepository`
- `MeetingRepository`
- `TodoRepository`
- `HAEntityRepository`
- `SpeakerRepository`
- `OperationalLogRepository`
- `TrainingExampleRepository`

---

## 8. Migration System

### 8.1 Migration Runner

```python
import os
import sqlite3
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).parent / "migrations"

def get_current_version(conn: sqlite3.Connection) -> int:
    try:
        result = conn.execute(
            "SELECT MAX(version) FROM schema_version"
        ).fetchone()
        return result[0] or 0
    except sqlite3.OperationalError:
        return 0

def run_migrations(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    current = get_current_version(conn)
    
    # Get migration files
    migrations = sorted([
        f for f in MIGRATIONS_DIR.glob("*.sql")
        if f.stem.split("_")[0].isdigit()
    ])
    
    for migration_file in migrations:
        version = int(migration_file.stem.split("_")[0])
        if version > current:
            print(f"Applying migration {version}: {migration_file.name}")
            
            sql = migration_file.read_text()
            conn.executescript(sql)
            
            conn.execute(
                "INSERT INTO schema_version (version, description) VALUES (?, ?)",
                [version, migration_file.stem]
            )
            conn.commit()
            print(f"  ✓ Applied")
    
    conn.close()
```

### 8.2 Migration Files

```
migrations/
├── 001_initial_schema.sql
├── 002_add_fts_tables.sql
├── 003_add_vss_tables.sql
├── 004_add_self_improvement.sql
└── ...
```

### 8.3 V1 Data Migration

```python
import sqlite3
import json

def migrate_v1_profiles(v1_db_path: str, v2_db_path: str) -> None:
    """Migrate V1 profile facts to V2 memories."""
    v1 = sqlite3.connect(v1_db_path)
    v2 = sqlite3.connect(v2_db_path)
    
    # Assuming V1 has a profiles or facts table
    facts = v1.execute("SELECT person, fact FROM profile_facts").fetchall()
    
    for person, fact in facts:
        v2.execute(
            """
            INSERT INTO memories (summary, content, memory_type, source_type, owner, source_speaker)
            VALUES (?, ?, 'fact', 'migration', ?, ?)
            """,
            [fact, fact, person.lower(), 'v1_migration']
        )
    
    v2.commit()
    print(f"Migrated {len(facts)} profile facts to memories")
    
    v1.close()
    v2.close()


def migrate_v1_patterns(v1_patterns_dir: str, v2_db_path: str) -> None:
    """Convert V1 YAML patterns to training examples."""
    import yaml
    
    v2 = sqlite3.connect(v2_db_path)
    
    for yaml_file in Path(v1_patterns_dir).glob("*.yaml"):
        with open(yaml_file) as f:
            data = yaml.safe_load(f)
        
        for pattern_def in data.get("patterns", []):
            # Extract intent from handler name
            handler = pattern_def.get("handler", "")
            intent = handler.replace("_handler", "")
            
            # Create synthetic utterances from regex
            # This is a simplified example - real implementation would
            # generate variations from the pattern
            pattern = pattern_def.get("pattern", "")
            if pattern:
                # Strip regex anchors for utterance
                utterance = pattern.strip("^$")
                
                v2.execute(
                    """
                    INSERT INTO training_examples (utterance, correct_intent, source)
                    VALUES (?, ?, 'migration')
                    """,
                    [utterance, intent]
                )
    
    v2.commit()
    v2.close()
```

---

## 9. Configuration

### 9.1 Settings

```python
from pydantic_settings import BaseSettings
from pathlib import Path

class DatabaseSettings(BaseSettings):
    # SQLite
    sqlite_path: Path = Path("/home/barnabee/data/barnabee.db")
    sqlite_wal_mode: bool = True
    sqlite_cache_size_mb: int = 64
    
    # Redis
    redis_url: str = "redis://localhost:6379"
    session_ttl_seconds: int = 1800
    
    # Vector search
    embedding_model: str = "text-embedding-ada-002"  # or "all-MiniLM-L6-v2" for local
    embedding_dimension: int = 1536  # 384 for MiniLM
    
    # Cache
    cache_max_size: int = 1000
    cache_ttl_seconds: int = 60
    
    # Logs
    log_retention_days: int = 90
    
    class Config:
        env_prefix = "BARNABEE_DB_"
```

---

## 10. Testing

### 10.1 Database Tests

```python
import pytest
import tempfile
from pathlib import Path

@pytest.fixture
def test_db():
    """Create temporary test database."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    
    # Run migrations
    run_migrations(db_path)
    
    yield db_path
    
    # Cleanup
    Path(db_path).unlink()
    Path(db_path + "-wal").unlink(missing_ok=True)
    Path(db_path + "-shm").unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_memory_crud(test_db):
    repo = MemoryRepository(test_db)
    
    # Create
    memory = await repo.create(
        summary="Test memory",
        content="This is a test memory content",
        memory_type="fact",
        source_type="explicit",
        owner="thom"
    )
    assert memory.id is not None
    assert memory.summary == "Test memory"
    
    # Read
    fetched = await repo.get_by_id(memory.id)
    assert fetched is not None
    assert fetched.access_count == 1
    
    # Search
    results = await repo.search_active("thom", query="test")
    assert len(results) == 1
    
    # Soft delete
    deleted = await repo.soft_delete(memory.id, "thom")
    assert deleted is True
    
    # Verify not in active search
    results = await repo.search_active("thom", query="test")
    assert len(results) == 0


@pytest.mark.asyncio
async def test_vector_search(test_db):
    # Requires sqlite-vss extension
    conn = init_db(test_db)
    
    # Create test memory with embedding
    memory_id = "test-memory-1"
    embedding = [0.1] * 1536  # Dummy embedding
    
    await store_embedding(conn, memory_id, embedding, "test")
    
    # Search with similar embedding
    results = await search_similar(conn, embedding, limit=5)
    assert len(results) > 0
    assert results[0][0] == memory_id
```

### 10.2 Performance Tests

```python
import time
import random

def test_memory_search_performance(test_db):
    """Memory search should complete in <50ms for 10k memories."""
    repo = MemoryRepository(test_db)
    
    # Seed with 10k memories
    for i in range(10000):
        repo.create_sync(
            summary=f"Test memory {i}",
            content=f"Content for memory {i} with some random words {random.random()}",
            memory_type="fact",
            source_type="explicit",
            owner="thom"
        )
    
    # Benchmark search
    start = time.perf_counter()
    results = repo.search_active_sync("thom", query="memory 5000", limit=10)
    elapsed_ms = (time.perf_counter() - start) * 1000
    
    assert elapsed_ms < 50, f"Search took {elapsed_ms}ms, expected <50ms"
    assert len(results) > 0
```

---

## 11. File Structure

```
barnabeenet-v2/
├── src/
│   └── barnabee/
│       ├── __init__.py
│       ├── config.py
│       └── data/
│           ├── __init__.py
│           ├── database.py          # Connection management, init_db()
│           ├── cache.py             # DataCache class
│           ├── session.py           # SessionStore, HAStateSubscriber
│           ├── repositories/
│           │   ├── __init__.py
│           │   ├── memory.py
│           │   ├── conversation.py
│           │   ├── meeting.py
│           │   ├── todo.py
│           │   ├── ha_entity.py
│           │   ├── speaker.py
│           │   ├── operational_log.py
│           │   └── training.py
│           ├── migrations/
│           │   ├── __init__.py
│           │   ├── runner.py
│           │   └── sql/
│           │       ├── 001_initial_schema.sql
│           │       ├── 002_add_fts.sql
│           │       └── 003_add_vss.sql
│           └── vector/
│               ├── __init__.py
│               ├── embeddings.py    # Embedding generation
│               └── search.py        # Vector + hybrid search
├── tests/
│   └── data/
│       ├── test_repositories.py
│       ├── test_vector_search.py
│       ├── test_migrations.py
│       └── test_performance.py
├── scripts/
│   ├── migrate_v1.py
│   └── init_db.py
└── data/
    └── .gitkeep
```

---

## 12. Implementation Checklist

### Core Schema & Storage

- [ ] Project setup (pyproject.toml, directory structure)
- [ ] SQLite schema implementation (001_initial_schema.sql)
- [ ] FTS5 tables and triggers (002_add_fts.sql)
- [ ] sqlite-vss integration (003_add_vss.sql)
- [ ] Migration runner
- [ ] Database connection management with WAL mode

### Repositories

- [ ] MemoryRepository with CRUD + search
- [ ] ConversationRepository
- [ ] MeetingRepository
- [ ] TodoRepository
- [ ] HAEntityRepository
- [ ] SpeakerRepository
- [ ] OperationalLogRepository
- [ ] TrainingExampleRepository

### Supporting Infrastructure

- [ ] Redis session store
- [ ] In-memory cache
- [ ] V1 data migration scripts

### Validation

- [ ] Unit tests for all repositories
- [ ] Performance benchmarks (10k memories)
- [ ] Integration tests

### Acceptance Criteria

1. **Memory search <50ms** for 10k memories
2. **Vector search <100ms** for 100k embeddings
3. **FTS search <30ms** for full-text queries
4. **All V1 data migrated** (profiles → memories, patterns → training examples)
5. **Zero data loss** during migration
6. **WAL mode enabled** for concurrent read access

---

## 12.1 Extended Schema (Cross-References)

Additional database tables are defined in the following specification documents:

| Document | Tables Added |
|----------|--------------|
| 17-security.md | `registered_devices`, `encrypted_tokens` |
| 18-cost-tracking.md | `cost_records`, `usage_tracking`, `cost_budgets`, `budget_alerts` |
| 19-personal-finance.md | `finance_accounts`, `finance_transactions`, `finance_budgets`, `finance_goals`, `finance_recurring`, `finance_category_rules`, `finance_sync_status` |
| 21-user-profiles.md | `user_profiles`, `user_interests`, `user_relationships`, `user_important_dates`, `user_usage_patterns`, `profile_extraction_queue` |

These tables follow the same conventions (TEXT PRIMARY KEY with hex ID, created_at/updated_at timestamps) as the core tables defined above.

---

## 13. Handoff Notes for Implementation Agent

### Critical Points

1. **Use aiosqlite for async access.** All repository methods must be async.

2. **Enable WAL mode immediately after connection.** This is required for concurrent reads during voice processing.

3. **sqlite-vss requires extension loading.** The `enable_load_extension` call is required but must be disabled immediately after loading for security.

4. **FTS triggers must stay in sync.** If you modify the memories table schema, update the FTS triggers.

5. **UUID generation uses randomblob(16).** SQLite doesn't have native UUID, this is the standard pattern.

6. **JSON arrays stored as TEXT.** Use Python's json.dumps/loads for keywords, aliases, etc.

7. **Test with realistic data volumes.** Seed 10k memories before declaring performance targets met.

### Common Pitfalls

- Forgetting `await db.commit()` after writes
- Not handling `aiosqlite.OperationalError` for locked database
- Assuming FTS match syntax is the same as LIKE (it's not)
- Not escaping FTS special characters in user queries

---

**End of Area 01: Core Data Layer**
