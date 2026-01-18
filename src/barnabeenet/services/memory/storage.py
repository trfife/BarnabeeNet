"""Memory storage with Redis backend and vector search.

Provides:
- Working memory: Short-term session context (TTL-based in Redis)
- Long-term memory: Persistent storage with vector similarity search
- Fallback: In-memory storage when Redis unavailable
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

import numpy as np

from barnabeenet.services.memory.embedding import (
    EmbeddingService,
    get_embedding_service,
)

if TYPE_CHECKING:
    import redis.asyncio as redis
    from numpy.typing import NDArray

logger = logging.getLogger(__name__)


@dataclass
class MemoryStorageConfig:
    """Configuration for memory storage."""

    # Working memory
    working_memory_ttl_sec: int = 600  # 10 minutes
    working_memory_prefix: str = "barnabeenet:working:"

    # Long-term memory
    memory_prefix: str = "barnabeenet:memory:"
    memory_index_name: str = "barnabeenet:memory:idx"
    embedding_prefix: str = "barnabeenet:embedding:"

    # Retrieval settings
    max_retrieval_results: int = 10
    min_similarity_score: float = 0.3

    # Storage limits
    max_memories: int = 10000


@dataclass
class StoredMemory:
    """A memory entry in storage."""

    id: str
    content: str
    memory_type: str
    importance: float = 0.5
    created_at: datetime = field(default_factory=datetime.now)
    last_accessed: datetime | None = None
    access_count: int = 0
    participants: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    time_context: str | None = None
    day_context: str | None = None
    embedding: NDArray[np.float32] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "id": self.id,
            "content": self.content,
            "memory_type": self.memory_type,
            "importance": self.importance,
            "created_at": self.created_at.isoformat(),
            "last_accessed": self.last_accessed.isoformat() if self.last_accessed else None,
            "access_count": self.access_count,
            "participants": self.participants,
            "tags": self.tags,
            "time_context": self.time_context,
            "day_context": self.day_context,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StoredMemory:
        """Create StoredMemory from dictionary."""
        return cls(
            id=data["id"],
            content=data["content"],
            memory_type=data["memory_type"],
            importance=data.get("importance", 0.5),
            created_at=datetime.fromisoformat(data["created_at"]),
            last_accessed=(
                datetime.fromisoformat(data["last_accessed"]) if data.get("last_accessed") else None
            ),
            access_count=data.get("access_count", 0),
            participants=data.get("participants", []),
            tags=data.get("tags", []),
            time_context=data.get("time_context"),
            day_context=data.get("day_context"),
        )


class MemoryStorage:
    """Memory storage backend with Redis and vector search.

    Features:
    - Working memory: Redis with TTL for short-term session context
    - Long-term memory: Redis hashes with separate embedding storage
    - Vector search: Cosine similarity over embeddings
    - Fallback: In-memory storage when Redis unavailable
    """

    def __init__(
        self,
        redis_client: redis.Redis | None = None,
        embedding_service: EmbeddingService | None = None,
        config: MemoryStorageConfig | None = None,
    ) -> None:
        """Initialize memory storage.

        Args:
            redis_client: Optional Redis async client.
            embedding_service: Optional embedding service.
            config: Optional configuration.
        """
        self._redis = redis_client
        self._embedding_service = embedding_service
        self.config = config or MemoryStorageConfig()

        # In-memory fallback storage
        self._memory_fallback: dict[str, StoredMemory] = {}
        self._embedding_fallback: dict[str, NDArray[np.float32]] = {}
        self._working_memory_fallback: dict[str, dict[str, Any]] = {}

        self._initialized = False
        self._use_redis = False

    async def init(self) -> None:
        """Initialize storage."""
        if self._initialized:
            return

        # Initialize embedding service
        if self._embedding_service is None:
            self._embedding_service = get_embedding_service()
        await self._embedding_service.init()

        # Check Redis availability
        if self._redis:
            try:
                await self._redis.ping()
                self._use_redis = True
                logger.info("MemoryStorage using Redis backend")
            except Exception as e:
                logger.warning(f"Redis not available, using in-memory fallback: {e}")
                self._use_redis = False
        else:
            logger.info("MemoryStorage using in-memory fallback (no Redis client)")

        self._initialized = True
        logger.info("MemoryStorage initialized")

    async def shutdown(self) -> None:
        """Clean up resources."""
        if self._embedding_service:
            await self._embedding_service.shutdown()
        self._memory_fallback.clear()
        self._embedding_fallback.clear()
        self._working_memory_fallback.clear()
        self._initialized = False
        logger.info("MemoryStorage shutdown")

    # =========================================================================
    # Working Memory (TTL-based)
    # =========================================================================

    async def set_working_memory(
        self,
        session_id: str,
        key: str,
        value: Any,
        ttl_sec: int | None = None,
    ) -> None:
        """Set a working memory value.

        Args:
            session_id: Session identifier.
            key: Memory key.
            value: Value to store (will be JSON serialized).
            ttl_sec: Optional TTL override.
        """
        ttl = ttl_sec or self.config.working_memory_ttl_sec
        redis_key = f"{self.config.working_memory_prefix}{session_id}:{key}"

        if self._use_redis and self._redis:
            await self._redis.setex(redis_key, ttl, json.dumps(value))
        else:
            # In-memory fallback with expiry tracking
            self._working_memory_fallback[redis_key] = {
                "value": value,
                "expires_at": time.time() + ttl,
            }

    async def get_working_memory(self, session_id: str, key: str) -> Any | None:
        """Get a working memory value.

        Args:
            session_id: Session identifier.
            key: Memory key.

        Returns:
            Stored value or None if not found/expired.
        """
        redis_key = f"{self.config.working_memory_prefix}{session_id}:{key}"

        if self._use_redis and self._redis:
            data = await self._redis.get(redis_key)
            return json.loads(data) if data else None
        else:
            entry = self._working_memory_fallback.get(redis_key)
            if entry and entry["expires_at"] > time.time():
                return entry["value"]
            elif entry:
                del self._working_memory_fallback[redis_key]
            return None

    async def delete_working_memory(self, session_id: str, key: str | None = None) -> None:
        """Delete working memory.

        Args:
            session_id: Session identifier.
            key: Optional specific key. If None, deletes all session memory.
        """
        if key:
            redis_key = f"{self.config.working_memory_prefix}{session_id}:{key}"
            if self._use_redis and self._redis:
                await self._redis.delete(redis_key)
            else:
                self._working_memory_fallback.pop(redis_key, None)
        else:
            # Delete all keys for session
            pattern = f"{self.config.working_memory_prefix}{session_id}:*"
            if self._use_redis and self._redis:
                cursor = 0
                while True:
                    cursor, keys = await self._redis.scan(cursor, match=pattern, count=100)
                    if keys:
                        await self._redis.delete(*keys)
                    if cursor == 0:
                        break
            else:
                to_delete = [
                    k for k in self._working_memory_fallback if k.startswith(pattern.rstrip("*"))
                ]
                for k in to_delete:
                    del self._working_memory_fallback[k]

    # =========================================================================
    # Long-term Memory Storage
    # =========================================================================

    async def store_memory(
        self,
        content: str,
        memory_type: str,
        importance: float = 0.5,
        participants: list[str] | None = None,
        tags: list[str] | None = None,
        time_context: str | None = None,
        day_context: str | None = None,
        memory_id: str | None = None,
    ) -> StoredMemory:
        """Store a new memory with embedding.

        Args:
            content: Memory content text.
            memory_type: Type of memory (working, episodic, semantic, procedural).
            importance: Importance score 0.0-1.0.
            participants: People involved in the memory.
            tags: Topic tags for filtering.
            time_context: Time of day (morning, afternoon, evening, night).
            day_context: Day type (weekday, weekend).
            memory_id: Optional specific ID.

        Returns:
            Stored memory object.
        """
        # Generate embedding
        embedding = await self._embedding_service.embed(content)

        # Create memory object
        memory = StoredMemory(
            id=memory_id or f"mem_{uuid.uuid4().hex[:12]}",
            content=content,
            memory_type=memory_type,
            importance=importance,
            participants=participants or [],
            tags=tags or [],
            time_context=time_context,
            day_context=day_context,
            embedding=embedding,
        )

        # Store
        if self._use_redis and self._redis:
            await self._store_memory_redis(memory, embedding)
        else:
            self._store_memory_fallback(memory, embedding)

        logger.debug(f"Stored memory: {memory.id} ({memory_type})")
        return memory

    async def _store_memory_redis(
        self, memory: StoredMemory, embedding: NDArray[np.float32]
    ) -> None:
        """Store memory in Redis."""
        memory_key = f"{self.config.memory_prefix}{memory.id}"
        embedding_key = f"{self.config.embedding_prefix}{memory.id}"

        # Store memory data as JSON
        await self._redis.set(memory_key, json.dumps(memory.to_dict()))

        # Store embedding as binary (more efficient than JSON)
        await self._redis.set(embedding_key, embedding.tobytes())

        # Add to memory index (sorted set by importance for retrieval)
        await self._redis.zadd(
            f"{self.config.memory_prefix}index",
            {memory.id: memory.importance},
        )

        # Add to participant indices for filtering
        for participant in memory.participants:
            await self._redis.sadd(
                f"{self.config.memory_prefix}participant:{participant}",
                memory.id,
            )

        # Add to type index
        await self._redis.sadd(
            f"{self.config.memory_prefix}type:{memory.memory_type}",
            memory.id,
        )

    def _store_memory_fallback(self, memory: StoredMemory, embedding: NDArray[np.float32]) -> None:
        """Store memory in fallback storage."""
        self._memory_fallback[memory.id] = memory
        self._embedding_fallback[memory.id] = embedding

    async def get_memory(self, memory_id: str) -> StoredMemory | None:
        """Get a specific memory by ID.

        Args:
            memory_id: Memory identifier.

        Returns:
            Memory object or None if not found.
        """
        if self._use_redis and self._redis:
            memory_key = f"{self.config.memory_prefix}{memory_id}"
            data = await self._redis.get(memory_key)
            if data:
                memory = StoredMemory.from_dict(json.loads(data))
                # Load embedding
                embedding_key = f"{self.config.embedding_prefix}{memory_id}"
                emb_bytes = await self._redis.get(embedding_key)
                if emb_bytes:
                    memory.embedding = np.frombuffer(emb_bytes, dtype=np.float32)
                return memory
            return None
        else:
            return self._memory_fallback.get(memory_id)

    async def delete_memory(self, memory_id: str) -> bool:
        """Delete a memory.

        Args:
            memory_id: Memory identifier.

        Returns:
            True if deleted, False if not found.
        """
        if self._use_redis and self._redis:
            memory_key = f"{self.config.memory_prefix}{memory_id}"
            embedding_key = f"{self.config.embedding_prefix}{memory_id}"

            # Get memory data for index cleanup
            data = await self._redis.get(memory_key)
            if not data:
                return False

            memory = StoredMemory.from_dict(json.loads(data))

            # Delete from indices
            await self._redis.zrem(f"{self.config.memory_prefix}index", memory_id)
            for participant in memory.participants:
                await self._redis.srem(
                    f"{self.config.memory_prefix}participant:{participant}",
                    memory_id,
                )
            await self._redis.srem(
                f"{self.config.memory_prefix}type:{memory.memory_type}",
                memory_id,
            )

            # Delete memory and embedding
            await self._redis.delete(memory_key, embedding_key)
            return True
        else:
            if memory_id in self._memory_fallback:
                del self._memory_fallback[memory_id]
                self._embedding_fallback.pop(memory_id, None)
                return True
            return False

    # =========================================================================
    # Memory Retrieval with Vector Search
    # =========================================================================

    async def search_memories(
        self,
        query: str,
        memory_type: str | None = None,
        participants: list[str] | None = None,
        max_results: int | None = None,
        min_score: float | None = None,
    ) -> list[tuple[StoredMemory, float]]:
        """Search memories by semantic similarity.

        Args:
            query: Search query text.
            memory_type: Optional filter by memory type.
            participants: Optional filter by participants.
            max_results: Maximum results to return.
            min_score: Minimum similarity score threshold.

        Returns:
            List of (memory, similarity_score) tuples sorted by relevance.
        """
        max_results = max_results or self.config.max_retrieval_results
        min_score = min_score or self.config.min_similarity_score

        # Generate query embedding
        query_embedding = await self._embedding_service.embed(query)

        if self._use_redis and self._redis:
            return await self._search_memories_redis(
                query_embedding, memory_type, participants, max_results, min_score
            )
        else:
            return self._search_memories_fallback(
                query_embedding, memory_type, participants, max_results, min_score
            )

    async def _search_memories_redis(
        self,
        query_embedding: NDArray[np.float32],
        memory_type: str | None,
        participants: list[str] | None,
        max_results: int,
        min_score: float,
    ) -> list[tuple[StoredMemory, float]]:
        """Search memories in Redis."""
        # Get candidate memory IDs
        candidate_ids: set[str] | None = None

        # Filter by type
        if memory_type:
            type_key = f"{self.config.memory_prefix}type:{memory_type}"
            type_ids = await self._redis.smembers(type_key)
            candidate_ids = set(type_ids)

        # Filter by participants
        if participants:
            participant_ids: set[str] = set()
            for p in participants:
                p_key = f"{self.config.memory_prefix}participant:{p}"
                p_ids = await self._redis.smembers(p_key)
                participant_ids.update(p_ids)
            if candidate_ids is not None:
                candidate_ids &= participant_ids
            else:
                candidate_ids = participant_ids

        # If no filters, get all memory IDs
        if candidate_ids is None:
            all_ids = await self._redis.zrange(f"{self.config.memory_prefix}index", 0, -1)
            candidate_ids = set(all_ids)

        if not candidate_ids:
            return []

        # Load embeddings and compute similarities
        results: list[tuple[StoredMemory, float]] = []

        for memory_id in candidate_ids:
            embedding_key = f"{self.config.embedding_prefix}{memory_id}"
            emb_bytes = await self._redis.get(embedding_key)
            if not emb_bytes:
                continue

            embedding = np.frombuffer(emb_bytes, dtype=np.float32)
            similarity = float(np.dot(query_embedding, embedding))

            if similarity >= min_score:
                memory = await self.get_memory(memory_id)
                if memory:
                    results.append((memory, similarity))

        # Sort by similarity and limit
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:max_results]

    def _search_memories_fallback(
        self,
        query_embedding: NDArray[np.float32],
        memory_type: str | None,
        participants: list[str] | None,
        max_results: int,
        min_score: float,
    ) -> list[tuple[StoredMemory, float]]:
        """Search memories in fallback storage."""
        results: list[tuple[StoredMemory, float]] = []

        for memory_id, memory in self._memory_fallback.items():
            # Apply filters
            if memory_type and memory.memory_type != memory_type:
                continue
            if participants:
                if not any(p in memory.participants for p in participants):
                    continue

            # Get embedding
            embedding = self._embedding_fallback.get(memory_id)
            if embedding is None:
                continue

            # Compute similarity
            similarity = float(np.dot(query_embedding, embedding))

            if similarity >= min_score:
                results.append((memory, similarity))

        # Sort by similarity and limit
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:max_results]

    async def get_recent_memories(
        self,
        limit: int = 10,
        memory_type: str | None = None,
    ) -> list[StoredMemory]:
        """Get most recent memories.

        Args:
            limit: Maximum memories to return.
            memory_type: Optional type filter.

        Returns:
            List of memories sorted by creation time (newest first).
        """
        if self._use_redis and self._redis:
            if memory_type:
                memory_ids = list(
                    await self._redis.smembers(f"{self.config.memory_prefix}type:{memory_type}")
                )
            else:
                memory_ids = await self._redis.zrevrange(
                    f"{self.config.memory_prefix}index", 0, limit - 1
                )

            memories = []
            for mid in memory_ids[:limit]:
                memory = await self.get_memory(mid)
                if memory:
                    memories.append(memory)

            # Sort by creation time
            memories.sort(key=lambda m: m.created_at, reverse=True)
            return memories[:limit]
        else:
            memories = list(self._memory_fallback.values())
            if memory_type:
                memories = [m for m in memories if m.memory_type == memory_type]
            memories.sort(key=lambda m: m.created_at, reverse=True)
            return memories[:limit]

    async def get_memory_count(self, memory_type: str | None = None) -> int:
        """Get total memory count.

        Args:
            memory_type: Optional type filter.

        Returns:
            Number of memories.
        """
        if self._use_redis and self._redis:
            if memory_type:
                return await self._redis.scard(f"{self.config.memory_prefix}type:{memory_type}")
            return await self._redis.zcard(f"{self.config.memory_prefix}index")
        else:
            if memory_type:
                return len(
                    [m for m in self._memory_fallback.values() if m.memory_type == memory_type]
                )
            return len(self._memory_fallback)

    # =========================================================================
    # Batch Operations
    # =========================================================================

    async def update_memory_access(self, memory_id: str) -> None:
        """Update memory access metadata.

        Args:
            memory_id: Memory to update.
        """
        memory = await self.get_memory(memory_id)
        if not memory:
            return

        memory.last_accessed = datetime.now()
        memory.access_count += 1

        if self._use_redis and self._redis:
            memory_key = f"{self.config.memory_prefix}{memory_id}"
            await self._redis.set(memory_key, json.dumps(memory.to_dict()))
        else:
            self._memory_fallback[memory_id] = memory


# Global singleton
_memory_storage: MemoryStorage | None = None


def get_memory_storage(redis_client: redis.Redis | None = None) -> MemoryStorage:
    """Get the global memory storage instance.

    Args:
        redis_client: Optional Redis client. If provided on first call, will be used.
    """
    global _memory_storage
    if _memory_storage is None:
        # Try to get redis from app state if not provided
        if redis_client is None:
            try:
                from barnabeenet.main import app_state

                redis_client = app_state.redis_client
            except Exception:
                pass
        _memory_storage = MemoryStorage(redis_client=redis_client)
    return _memory_storage
