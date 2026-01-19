"""Memory API routes for dashboard and management.

Provides endpoints for:
- Viewing stored memories (long-term, episodic, semantic)
- Conversation history
- Diary/journal entries (with LLM-generated summaries)
- Memory statistics
- Manual memory management
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from barnabeenet.services.memory.storage import MemoryStorage, StoredMemory

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/memory", tags=["memory"])


# ============================================================================
# Response Models
# ============================================================================


class MemoryItem(BaseModel):
    """A single memory entry for API responses."""

    id: str
    content: str
    memory_type: str
    importance: float
    created_at: str
    last_accessed: str | None
    access_count: int
    participants: list[str]
    tags: list[str]
    time_context: str | None
    day_context: str | None


class MemoryListResponse(BaseModel):
    """Response for memory list queries."""

    memories: list[MemoryItem]
    total: int
    page: int
    page_size: int


class MemoryStatsResponse(BaseModel):
    """Memory system statistics."""

    total_memories: int
    by_type: dict[str, int]
    by_participant: dict[str, int]
    recent_24h: int
    recent_7d: int
    storage_backend: str  # redis or fallback


class ConversationEntry(BaseModel):
    """A single conversation message."""

    id: str
    timestamp: str
    speaker: str
    text: str
    response: str | None
    agent_used: str | None
    intent: str | None


class ConversationListResponse(BaseModel):
    """Response for conversation history."""

    conversations: list[ConversationEntry]
    total: int


class DiaryEntry(BaseModel):
    """A daily diary/journal entry."""

    date: str
    summary: str
    highlights: list[str]
    participants_mentioned: list[str]
    mood: str | None
    memory_count: int


class DiaryListResponse(BaseModel):
    """Response for diary entries."""

    entries: list[DiaryEntry]
    total: int


class StoreMemoryRequest(BaseModel):
    """Request to manually store a memory."""

    content: str = Field(..., description="Memory content")
    memory_type: str = Field(default="semantic", description="Type: semantic, episodic, procedural")
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    participants: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class SearchMemoryRequest(BaseModel):
    """Request to search memories."""

    query: str = Field(..., description="Search query")
    memory_type: str | None = Field(default=None, description="Filter by type")
    participant: str | None = Field(default=None, description="Filter by participant")
    limit: int = Field(default=10, ge=1, le=50)


class SearchMemoryResponse(BaseModel):
    """Response for memory search."""

    results: list[MemoryItem]
    query: str
    total: int


# ============================================================================
# Helper Functions
# ============================================================================


def _get_memory_storage() -> MemoryStorage:
    """Get memory storage instance."""
    from barnabeenet.main import app_state

    if not hasattr(app_state, "memory_storage") or app_state.memory_storage is None:
        raise HTTPException(status_code=503, detail="Memory storage not initialized")
    return app_state.memory_storage


def _stored_memory_to_item(mem: StoredMemory) -> MemoryItem:
    """Convert StoredMemory to API response item."""
    return MemoryItem(
        id=mem.id,
        content=mem.content,
        memory_type=mem.memory_type,
        importance=mem.importance,
        created_at=mem.created_at.isoformat(),
        last_accessed=mem.last_accessed.isoformat() if mem.last_accessed else None,
        access_count=mem.access_count,
        participants=mem.participants,
        tags=mem.tags,
        time_context=mem.time_context,
        day_context=mem.day_context,
    )


# ============================================================================
# Memory List & Stats Endpoints
# ============================================================================


@router.get("/", response_model=MemoryListResponse)
async def list_memories(
    memory_type: str | None = Query(default=None, description="Filter by type"),
    participant: str | None = Query(default=None, description="Filter by participant"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> MemoryListResponse:
    """List stored memories with optional filtering."""
    storage = _get_memory_storage()

    # Get all memories from storage
    memories = await storage.get_all_memories(
        memory_type=memory_type,
        participant=participant,
    )

    # Sort by created_at descending (newest first)
    memories.sort(key=lambda m: m.created_at, reverse=True)

    # Paginate
    total = len(memories)
    start = (page - 1) * page_size
    end = start + page_size
    page_memories = memories[start:end]

    return MemoryListResponse(
        memories=[_stored_memory_to_item(m) for m in page_memories],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/stats", response_model=MemoryStatsResponse)
async def get_memory_stats() -> MemoryStatsResponse:
    """Get memory system statistics."""
    storage = _get_memory_storage()

    all_memories = await storage.get_all_memories()

    # Count by type
    by_type: dict[str, int] = {}
    by_participant: dict[str, int] = {}
    now = datetime.now()
    recent_24h = 0
    recent_7d = 0

    for mem in all_memories:
        # By type
        by_type[mem.memory_type] = by_type.get(mem.memory_type, 0) + 1

        # By participant
        for p in mem.participants:
            by_participant[p] = by_participant.get(p, 0) + 1

        # Recent counts
        age = now - mem.created_at
        if age < timedelta(hours=24):
            recent_24h += 1
        if age < timedelta(days=7):
            recent_7d += 1

    return MemoryStatsResponse(
        total_memories=len(all_memories),
        by_type=by_type,
        by_participant=by_participant,
        recent_24h=recent_24h,
        recent_7d=recent_7d,
        storage_backend="redis" if storage._use_redis else "fallback",
    )


# ============================================================================
# Memory Search & Retrieval
# ============================================================================


@router.post("/search", response_model=SearchMemoryResponse)
async def search_memories(request: SearchMemoryRequest) -> SearchMemoryResponse:
    """Search memories by semantic similarity."""
    storage = _get_memory_storage()

    results = await storage.retrieve_memories(
        query=request.query,
        memory_type=request.memory_type,
        participant=request.participant,
        limit=request.limit,
    )

    return SearchMemoryResponse(
        results=[_stored_memory_to_item(m) for m in results],
        query=request.query,
        total=len(results),
    )


@router.get("/{memory_id}", response_model=MemoryItem)
async def get_memory(memory_id: str) -> MemoryItem:
    """Get a specific memory by ID."""
    storage = _get_memory_storage()

    memory = await storage.get_memory(memory_id)
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")

    return _stored_memory_to_item(memory)


# ============================================================================
# Memory Management
# ============================================================================


@router.post("/store", response_model=MemoryItem)
async def store_memory(request: StoreMemoryRequest) -> MemoryItem:
    """Manually store a new memory."""
    storage = _get_memory_storage()

    memory = await storage.store_memory(
        content=request.content,
        memory_type=request.memory_type,
        importance=request.importance,
        participants=request.participants,
        tags=request.tags,
    )

    logger.info(f"Manually stored memory: {memory.id}")
    return _stored_memory_to_item(memory)


@router.delete("/{memory_id}")
async def delete_memory(memory_id: str) -> dict[str, Any]:
    """Delete a memory by ID."""
    storage = _get_memory_storage()

    success = await storage.delete_memory(memory_id)
    if not success:
        raise HTTPException(status_code=404, detail="Memory not found")

    logger.info(f"Deleted memory: {memory_id}")
    return {"status": "deleted", "memory_id": memory_id}


# ============================================================================
# Conversation History
# ============================================================================


@router.get("/conversations", response_model=ConversationListResponse)
async def get_conversations(
    limit: int = Query(default=50, ge=1, le=200),
    speaker: str | None = Query(default=None),
) -> ConversationListResponse:
    """Get conversation history."""
    storage = _get_memory_storage()

    # Retrieve episodic memories that represent conversations
    conversations = await storage.get_all_memories(memory_type="episodic")

    # Filter for conversation-type memories
    conv_entries = []
    for mem in conversations:
        # Parse conversation format from content
        if "said:" in mem.content.lower() or "asked:" in mem.content.lower():
            entry = ConversationEntry(
                id=mem.id,
                timestamp=mem.created_at.isoformat(),
                speaker=mem.participants[0] if mem.participants else "Unknown",
                text=mem.content,
                response=None,  # Would need to be stored separately
                agent_used=mem.tags[0] if mem.tags else None,
                intent=None,
            )
            if speaker is None or entry.speaker.lower() == speaker.lower():
                conv_entries.append(entry)

    # Sort by timestamp descending
    conv_entries.sort(key=lambda c: c.timestamp, reverse=True)

    return ConversationListResponse(
        conversations=conv_entries[:limit],
        total=len(conv_entries),
    )


# ============================================================================
# Diary / Journal
# ============================================================================


@router.get("/diary", response_model=DiaryListResponse)
async def get_diary_entries(
    days: int = Query(default=7, ge=1, le=90),
) -> DiaryListResponse:
    """Get diary entries summarizing recent days.

    Diary entries are generated from memories grouped by day.
    """
    storage = _get_memory_storage()

    all_memories = await storage.get_all_memories()

    # Group memories by date
    memories_by_date: dict[str, list[StoredMemory]] = {}
    now = datetime.now()

    for mem in all_memories:
        age = now - mem.created_at
        if age > timedelta(days=days):
            continue

        date_str = mem.created_at.strftime("%Y-%m-%d")
        if date_str not in memories_by_date:
            memories_by_date[date_str] = []
        memories_by_date[date_str].append(mem)

    # Create diary entries for each day
    entries = []
    for date_str, day_memories in sorted(memories_by_date.items(), reverse=True):
        # Extract highlights (high importance memories)
        highlights = [m.content for m in day_memories if m.importance >= 0.7][:5]

        # Collect participants
        all_participants = set()
        for m in day_memories:
            all_participants.update(m.participants)

        # Simple summary
        summary = f"Recorded {len(day_memories)} memories"
        if highlights:
            summary += f" with {len(highlights)} notable events"

        entries.append(
            DiaryEntry(
                date=date_str,
                summary=summary,
                highlights=highlights,
                participants_mentioned=list(all_participants),
                mood=None,  # Could be derived from sentiment analysis
                memory_count=len(day_memories),
            )
        )

    return DiaryListResponse(
        entries=entries,
        total=len(entries),
    )


@router.post("/diary/generate")
async def generate_diary_entry(
    date: str = Query(..., description="Date in YYYY-MM-DD format"),
) -> DiaryEntry:
    """Generate a diary entry for a specific date using LLM.

    This creates a natural language summary of the day's memories,
    written from Barnabee's perspective as the family butler AI.
    """
    storage = _get_memory_storage()

    # Get memories for the specific date
    all_memories = await storage.get_all_memories()
    day_memories = [m for m in all_memories if m.created_at.strftime("%Y-%m-%d") == date]

    if not day_memories:
        raise HTTPException(status_code=404, detail=f"No memories found for {date}")

    # Collect information for the diary
    highlights = [m.content for m in day_memories if m.importance >= 0.6][:10]
    participants = set()
    memory_types: dict[str, int] = {}

    for m in day_memories:
        participants.update(m.participants)
        memory_types[m.memory_type] = memory_types.get(m.memory_type, 0) + 1

    # Build the LLM prompt
    memory_summary = "\n".join(f"- {m.content}" for m in day_memories[:20])

    prompt = f"""You are Barnabee, a friendly and helpful AI butler for the Fife family.
Write a short diary entry summarizing what happened on {date} based on the following memories.

Keep it warm, personal, and conversational - like you're writing in your own journal.
Focus on what the family did, any notable events, and your observations.
Keep it to 2-3 paragraphs maximum.

Memories from {date}:
{memory_summary}

Participants mentioned: {", ".join(participants) if participants else "None specified"}
Memory types: {memory_types}

Write your diary entry now:"""

    # Try to use LLM for generation
    try:
        from barnabeenet.main import app_state
        from barnabeenet.services.llm.openrouter import ChatMessage, OpenRouterClient
        from barnabeenet.services.secrets import get_secrets_service

        # Get Redis client from app state
        redis_client = app_state.redis_client
        if redis_client:
            secrets = await get_secrets_service(redis_client)
            api_key = await secrets.get_secret("openrouter_api_key")
        else:
            api_key = None

        if api_key:
            client = OpenRouterClient(api_key=api_key)
            await client.init()

            try:
                response = await client.chat(
                    messages=[ChatMessage(role="user", content=prompt)],
                    activity="diary.generate",
                    trace_id=f"diary_{date}",
                )
                summary = response.text.strip()
            finally:
                await client.shutdown()
        else:
            # Fallback if no API key
            summary = _generate_simple_summary(date, day_memories, participants)

    except Exception as e:
        logger.warning(f"LLM diary generation failed, using fallback: {e}")
        summary = _generate_simple_summary(date, day_memories, participants)

    # Detect mood from content (simple heuristic)
    mood = _detect_mood(day_memories)

    return DiaryEntry(
        date=date,
        summary=summary,
        highlights=highlights[:5],
        participants_mentioned=list(participants),
        mood=mood,
        memory_count=len(day_memories),
    )


def _generate_simple_summary(
    date: str, memories: list[StoredMemory], participants: set[str]
) -> str:
    """Generate a simple summary without LLM."""
    count = len(memories)
    p_list = ", ".join(participants) if participants else "the household"

    if count == 1:
        return f"A quiet day on {date}. Recorded one memory involving {p_list}."
    elif count < 5:
        return f"A light day on {date}. Recorded {count} memories with activity from {p_list}."
    else:
        return f"A busy day on {date}! Recorded {count} memories. The household was active with {p_list} involved in various activities."


def _detect_mood(memories: list[StoredMemory]) -> str | None:
    """Detect overall mood from memories using simple heuristics."""
    positive_words = ["happy", "great", "love", "fun", "enjoy", "excited", "wonderful", "good"]
    negative_words = ["sad", "angry", "upset", "frustrated", "tired", "annoyed", "bad", "worried"]

    content = " ".join(m.content.lower() for m in memories)

    positive_count = sum(1 for word in positive_words if word in content)
    negative_count = sum(1 for word in negative_words if word in content)

    if positive_count > negative_count + 2:
        return "positive"
    elif negative_count > positive_count + 2:
        return "concerned"
    else:
        return "neutral"


# ============================================================================
# Working Memory (Session Context)
# ============================================================================


@router.get("/working/{session_id}")
async def get_working_memory(
    session_id: str,
) -> dict[str, Any]:
    """Get working memory for a session."""
    storage = _get_memory_storage()

    # Get all working memory keys for this session
    context = await storage.get_working_memory(session_id, "context")
    recent_messages = await storage.get_working_memory(session_id, "recent_messages")
    current_topic = await storage.get_working_memory(session_id, "current_topic")

    return {
        "session_id": session_id,
        "context": context,
        "recent_messages": recent_messages,
        "current_topic": current_topic,
    }


@router.delete("/working/{session_id}")
async def clear_working_memory(session_id: str) -> dict[str, Any]:
    """Clear working memory for a session."""
    storage = _get_memory_storage()

    await storage.delete_working_memory(session_id)

    return {"status": "cleared", "session_id": session_id}
