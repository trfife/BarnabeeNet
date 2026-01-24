"""LLM response caching with semantic similarity matching.

Caches LLM responses based on semantic similarity to avoid redundant API calls.
Uses embeddings to match similar queries and return cached responses when appropriate.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import numpy as np

from barnabeenet.services.memory.embedding import EmbeddingService, get_embedding_service

if TYPE_CHECKING:
    import redis.asyncio as redis
    from numpy.typing import NDArray

logger = logging.getLogger(__name__)

# Cache configuration
CACHE_PREFIX = "barnabeenet:llm_cache:"
CACHE_EMBEDDING_PREFIX = "barnabeenet:llm_cache_emb:"
CACHE_TTL_FACTUAL_HOURS = 24  # Factual queries (time, date, status)
CACHE_TTL_CONVERSATIONAL_HOURS = 1  # Conversational queries
SEMANTIC_SIMILARITY_THRESHOLD = 0.95  # Cosine similarity threshold for cache hits
MAX_CACHE_ENTRIES = 10000  # Maximum cache entries per agent type


class LLMCacheEntry:
    """A cached LLM response entry."""

    def __init__(
        self,
        response_text: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
        embedding: NDArray[np.float32],
        created_at: datetime | None = None,
        hit_count: int = 0,
        last_accessed: datetime | None = None,
    ):
        self.response_text = response_text
        self.model = model
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.cost_usd = cost_usd
        self.embedding = embedding
        self.created_at = created_at or datetime.now(UTC)
        self.hit_count = hit_count
        self.last_accessed = last_accessed or datetime.now(UTC)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "response_text": self.response_text,
            "model": self.model,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost_usd": self.cost_usd,
            "embedding": self.embedding.tolist(),  # Convert numpy array to list
            "created_at": self.created_at.isoformat(),
            "hit_count": self.hit_count,
            "last_accessed": self.last_accessed.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LLMCacheEntry:
        """Create from dictionary."""
        return cls(
            response_text=data["response_text"],
            model=data["model"],
            input_tokens=data["input_tokens"],
            output_tokens=data["output_tokens"],
            cost_usd=data["cost_usd"],
            embedding=np.array(data["embedding"], dtype=np.float32),
            created_at=datetime.fromisoformat(data["created_at"]),
            hit_count=data.get("hit_count", 0),
            last_accessed=datetime.fromisoformat(data["last_accessed"]),
        )


class LLMResponseCache:
    """Cache for LLM responses with semantic similarity matching.

    Caches responses based on:
    - Agent type / activity
    - Model used
    - Semantic similarity of input (via embeddings)
    - Temperature (affects response variability)
    """

    def __init__(
        self,
        redis_client: redis.Redis | None = None,
        embedding_service: EmbeddingService | None = None,
        enabled: bool = True,
    ):
        """Initialize the cache.

        Args:
            redis_client: Optional Redis client for persistent caching.
            embedding_service: Optional embedding service for semantic matching.
            enabled: Whether caching is enabled.
        """
        self._redis = redis_client
        self._embedding_service = embedding_service
        self._enabled = enabled
        self._use_redis = False

        # In-memory fallback cache (LRU-style, limited size)
        self._memory_cache: dict[str, LLMCacheEntry] = {}
        self._memory_cache_embeddings: dict[str, NDArray[np.float32]] = {}
        self._max_memory_entries = 1000

    async def init(self) -> None:
        """Initialize the cache."""
        if not self._enabled:
            logger.info("LLM response cache disabled")
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
                logger.info("LLM response cache using Redis backend")
            except Exception as e:
                logger.warning(f"Redis not available for LLM cache, using in-memory: {e}")
                self._use_redis = False
        else:
            logger.info("LLM response cache using in-memory fallback")

    def _generate_cache_key(
        self,
        agent_type: str,
        model: str,
        temperature: float,
        query_embedding: NDArray[np.float32],
    ) -> str:
        """Generate a cache key for a query.

        Uses embedding hash for semantic matching.
        """
        # Create a hash from the embedding (first 16 bytes for key)
        embedding_hash = hashlib.sha256(query_embedding.tobytes()).hexdigest()[:16]
        # Round temperature to 1 decimal for key grouping
        temp_key = f"{temperature:.1f}"
        return f"{agent_type}:{model}:{temp_key}:{embedding_hash}"

    def _is_factual_query(self, query_text: str) -> bool:
        """Determine if a query is factual (time, date, status) vs conversational.

        Factual queries can be cached longer.
        """
        query_lower = query_text.lower()
        factual_patterns = [
            "what time",
            "what's the time",
            "what date",
            "what's the date",
            "what day",
            "what's the weather",
            "temperature",
            "status",
            "is",
            "are",
            "how many",
        ]
        return any(pattern in query_lower for pattern in factual_patterns)

    async def get(
        self,
        query_text: str,
        agent_type: str,
        model: str,
        temperature: float,
    ) -> LLMCacheEntry | None:
        """Get a cached response if available.

        Args:
            query_text: The user's query text.
            agent_type: Agent type or activity (e.g., "meta", "interaction.respond").
            model: Model used for the request.
            temperature: Temperature setting.

        Returns:
            Cached entry if found, None otherwise.
        """
        if not self._enabled:
            return None

        try:
            # Generate embedding for query
            query_embedding = await self._embedding_service.embed(query_text)

            # Search for similar cached entries
            if self._use_redis and self._redis:
                cached = await self._search_redis_cache(
                    query_embedding, agent_type, model, temperature
                )
            else:
                cached = await self._search_memory_cache(
                    query_embedding, agent_type, model, temperature
                )

            if cached:
                # Update access stats
                cached.hit_count += 1
                cached.last_accessed = datetime.now(UTC)
                await self._update_cache_entry(cached, agent_type, model, temperature, query_embedding)
                logger.debug(
                    "LLM cache hit",
                    agent_type=agent_type,
                    model=model,
                    hit_count=cached.hit_count,
                )
                return cached

            return None

        except Exception as e:
            logger.warning(f"LLM cache lookup failed: {e}")
            return None

    async def _search_redis_cache(
        self,
        query_embedding: NDArray[np.float32],
        agent_type: str,
        model: str,
        temperature: float,
    ) -> LLMCacheEntry | None:
        """Search Redis cache for similar entries."""
        # Get all cache keys for this agent/model/temp combination
        pattern = f"{CACHE_PREFIX}{agent_type}:{model}:{temperature:.1f}:*"
        cursor = 0
        best_match: tuple[LLMCacheEntry, float] | None = None

        while True:
            cursor, keys = await self._redis.scan(cursor, match=pattern, count=100)
            if not keys:
                if cursor == 0:
                    break
                continue

            # Load entries and compare embeddings
            for key in keys:
                try:
                    entry_data = await self._redis.get(key)
                    if not entry_data:
                        continue

                    entry = LLMCacheEntry.from_dict(json.loads(entry_data))
                    # Compute similarity
                    similarity = np.dot(query_embedding, entry.embedding)  # Both normalized
                    if similarity >= SEMANTIC_SIMILARITY_THRESHOLD:
                        if best_match is None or similarity > best_match[1]:
                            best_match = (entry, similarity)

                except Exception as e:
                    logger.debug(f"Error loading cache entry {key}: {e}")
                    continue

            if cursor == 0:
                break

        return best_match[0] if best_match else None

    async def _search_memory_cache(
        self,
        query_embedding: NDArray[np.float32],
        agent_type: str,
        model: str,
        temperature: float,
    ) -> LLMCacheEntry | None:
        """Search in-memory cache for similar entries."""
        best_match: tuple[LLMCacheEntry, float] | None = None
        temp_key = f"{temperature:.1f}"

        for key, entry in self._memory_cache.items():
            # Check if agent/model/temp match
            if not key.startswith(f"{agent_type}:{model}:{temp_key}:"):
                continue

            # Compute similarity
            similarity = np.dot(query_embedding, entry.embedding)
            if similarity >= SEMANTIC_SIMILARITY_THRESHOLD:
                if best_match is None or similarity > best_match[1]:
                    best_match = (entry, similarity)

        return best_match[0] if best_match else None

    async def set(
        self,
        query_text: str,
        response_text: str,
        agent_type: str,
        model: str,
        temperature: float,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
    ) -> None:
        """Store a response in the cache.

        Args:
            query_text: The user's query text.
            response_text: The LLM response text.
            agent_type: Agent type or activity.
            model: Model used.
            temperature: Temperature setting.
            input_tokens: Input token count.
            output_tokens: Output token count.
            cost_usd: Cost in USD.
        """
        if not self._enabled:
            return

        try:
            # Generate embedding for query
            query_embedding = await self._embedding_service.embed(query_text)

            # Determine TTL based on query type
            is_factual = self._is_factual_query(query_text)
            ttl_hours = CACHE_TTL_FACTUAL_HOURS if is_factual else CACHE_TTL_CONVERSATIONAL_HOURS

            # Create cache entry
            entry = LLMCacheEntry(
                response_text=response_text,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost_usd,
                embedding=query_embedding,
            )

            # Generate cache key
            cache_key = self._generate_cache_key(agent_type, model, temperature, query_embedding)

            # Store in cache
            if self._use_redis and self._redis:
                await self._store_redis_entry(cache_key, entry, ttl_hours)
            else:
                await self._store_memory_entry(cache_key, entry)

            logger.debug(
                "LLM response cached",
                agent_type=agent_type,
                model=model,
                ttl_hours=ttl_hours,
            )

        except Exception as e:
            logger.warning(f"Failed to cache LLM response: {e}")

    async def _store_redis_entry(
        self, cache_key: str, entry: LLMCacheEntry, ttl_hours: int
    ) -> None:
        """Store entry in Redis."""
        full_key = f"{CACHE_PREFIX}{cache_key}"
        ttl_seconds = ttl_hours * 3600

        entry_data = json.dumps(entry.to_dict())
        await self._redis.setex(full_key, ttl_seconds, entry_data)

    async def _store_memory_entry(self, cache_key: str, entry: LLMCacheEntry) -> None:
        """Store entry in memory cache with LRU eviction."""
        # Evict oldest if at capacity
        if len(self._memory_cache) >= self._max_memory_entries:
            # Remove oldest accessed entry
            oldest_key = min(
                self._memory_cache.keys(),
                key=lambda k: self._memory_cache[k].last_accessed,
            )
            del self._memory_cache[oldest_key]
            self._memory_cache_embeddings.pop(oldest_key, None)

        self._memory_cache[cache_key] = entry
        self._memory_cache_embeddings[cache_key] = entry.embedding

    async def _update_cache_entry(
        self,
        entry: LLMCacheEntry,
        agent_type: str,
        model: str,
        temperature: float,
        query_embedding: NDArray[np.float32],
    ) -> None:
        """Update cache entry with new access stats."""
        cache_key = self._generate_cache_key(agent_type, model, temperature, query_embedding)

        if self._use_redis and self._redis:
            full_key = f"{CACHE_PREFIX}{cache_key}"
            # Get current TTL and preserve it
            ttl = await self._redis.ttl(full_key)
            if ttl > 0:
                entry_data = json.dumps(entry.to_dict())
                await self._redis.setex(full_key, ttl, entry_data)
        else:
            # Update in-memory entry
            if cache_key in self._memory_cache:
                self._memory_cache[cache_key] = entry

    async def clear(self, agent_type: str | None = None) -> None:
        """Clear cache entries.

        Args:
            agent_type: Optional agent type to clear. If None, clears all.
        """
        if agent_type:
            pattern = f"{CACHE_PREFIX}{agent_type}:*"
        else:
            pattern = f"{CACHE_PREFIX}*"

        if self._use_redis and self._redis:
            cursor = 0
            while True:
                cursor, keys = await self._redis.scan(cursor, match=pattern, count=100)
                if keys:
                    await self._redis.delete(*keys)
                if cursor == 0:
                    break
        else:
            # Clear from memory cache
            keys_to_delete = [
                k for k in self._memory_cache.keys() if not agent_type or k.startswith(f"{agent_type}:")
            ]
            for k in keys_to_delete:
                del self._memory_cache[k]
                self._memory_cache_embeddings.pop(k, None)

        logger.info(f"LLM cache cleared", agent_type=agent_type or "all")


# Global cache instance
_llm_cache: LLMResponseCache | None = None


def get_llm_cache() -> LLMResponseCache | None:
    """Get the global LLM cache instance."""
    return _llm_cache


async def init_llm_cache(
    redis_client: redis.Redis | None = None,
    enabled: bool = True,
) -> LLMResponseCache:
    """Initialize the global LLM cache."""
    global _llm_cache
    _llm_cache = LLMResponseCache(redis_client=redis_client, enabled=enabled)
    await _llm_cache.init()
    return _llm_cache
