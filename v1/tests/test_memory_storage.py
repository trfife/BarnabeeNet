"""Tests for memory storage service with vector search."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from barnabeenet.services.memory.embedding import (
    EMBEDDING_DIM,
    EmbeddingService,
    get_embedding_service,
)
from barnabeenet.services.memory.storage import (
    MemoryStorage,
    MemoryStorageConfig,
    StoredMemory,
    get_memory_storage,
)

# ============================================================================
# EmbeddingService Tests
# ============================================================================


class TestEmbeddingService:
    """Tests for EmbeddingService."""

    @pytest.fixture
    def mock_model(self):
        """Create mock sentence transformer model."""
        model = MagicMock()
        model.encode.return_value = np.random.randn(EMBEDDING_DIM).astype(np.float32)
        model.get_sentence_embedding_dimension.return_value = EMBEDDING_DIM
        return model

    @pytest.mark.asyncio
    async def test_init_loads_model(self, mock_model):
        """Init should load sentence transformer model."""
        with patch.dict(
            "sys.modules",
            {
                "sentence_transformers": MagicMock(
                    SentenceTransformer=MagicMock(return_value=mock_model)
                )
            },
        ):
            service = EmbeddingService()
            await service.init()

            assert service.is_available()
            assert service.embedding_dim == EMBEDDING_DIM

    @pytest.mark.asyncio
    async def test_embed_returns_correct_shape(self, mock_model):
        """Embed should return 384-dim vector."""
        with patch.dict(
            "sys.modules",
            {
                "sentence_transformers": MagicMock(
                    SentenceTransformer=MagicMock(return_value=mock_model)
                )
            },
        ):
            service = EmbeddingService()
            await service.init()

            embedding = await service.embed("Test text")

            assert embedding.shape == (EMBEDDING_DIM,)
            assert embedding.dtype == np.float32

    @pytest.mark.asyncio
    async def test_embed_batch_returns_correct_shape(self, mock_model):
        """Batch embed should return (n, 384) array."""
        mock_model.encode.return_value = np.random.randn(3, EMBEDDING_DIM).astype(np.float32)

        with patch.dict(
            "sys.modules",
            {
                "sentence_transformers": MagicMock(
                    SentenceTransformer=MagicMock(return_value=mock_model)
                )
            },
        ):
            service = EmbeddingService()
            await service.init()

            embeddings = await service.embed_batch(["text1", "text2", "text3"])

            assert embeddings.shape == (3, EMBEDDING_DIM)
            assert embeddings.dtype == np.float32

    def test_cosine_similarity_normalized_vectors(self):
        """Cosine similarity should work correctly with normalized vectors."""
        # Create normalized vectors
        query = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        vectors = np.array(
            [
                [1.0, 0.0, 0.0],  # Same as query
                [0.0, 1.0, 0.0],  # Orthogonal
                [0.707, 0.707, 0.0],  # 45 degrees
            ],
            dtype=np.float32,
        )

        similarities = EmbeddingService.cosine_similarity(query, vectors)

        assert len(similarities) == 3
        assert similarities[0] == pytest.approx(1.0)  # Same vector
        assert similarities[1] == pytest.approx(0.0)  # Orthogonal
        assert similarities[2] == pytest.approx(0.707, rel=1e-2)  # 45 degrees

    def test_cosine_similarity_empty_vectors(self):
        """Cosine similarity should handle empty vectors."""
        query = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        vectors = np.array([], dtype=np.float32).reshape(0, 3)

        similarities = EmbeddingService.cosine_similarity(query, vectors)

        assert len(similarities) == 0

    @pytest.mark.asyncio
    async def test_shutdown_clears_model(self, mock_model):
        """Shutdown should clear model reference."""
        with patch.dict(
            "sys.modules",
            {
                "sentence_transformers": MagicMock(
                    SentenceTransformer=MagicMock(return_value=mock_model)
                )
            },
        ):
            service = EmbeddingService()
            await service.init()
            assert service.is_available()

            await service.shutdown()

            assert not service.is_available()


# ============================================================================
# StoredMemory Tests
# ============================================================================


class TestStoredMemory:
    """Tests for StoredMemory dataclass."""

    def test_to_dict_and_from_dict(self):
        """Should serialize and deserialize correctly."""
        memory = StoredMemory(
            id="mem_123",
            content="Test memory content",
            memory_type="semantic",
            importance=0.8,
            participants=["thom", "viola"],
            tags=["test", "memory"],
            time_context="morning",
            day_context="weekday",
        )

        data = memory.to_dict()
        restored = StoredMemory.from_dict(data)

        assert restored.id == memory.id
        assert restored.content == memory.content
        assert restored.memory_type == memory.memory_type
        assert restored.importance == memory.importance
        assert restored.participants == memory.participants
        assert restored.tags == memory.tags


# ============================================================================
# MemoryStorage Tests (In-memory fallback)
# ============================================================================


class TestMemoryStorageFallback:
    """Tests for MemoryStorage with in-memory fallback."""

    @pytest.fixture
    def mock_embedding_service(self):
        """Create mock embedding service."""
        service = AsyncMock()
        service.init = AsyncMock()
        service.shutdown = AsyncMock()
        service.embed = AsyncMock(return_value=np.random.randn(EMBEDDING_DIM).astype(np.float32))
        service.embed_batch = AsyncMock(
            return_value=np.random.randn(5, EMBEDDING_DIM).astype(np.float32)
        )
        return service

    @pytest.fixture
    def storage(self, mock_embedding_service):
        """Create storage with fallback mode."""
        return MemoryStorage(
            redis_client=None,  # Force fallback mode
            embedding_service=mock_embedding_service,
        )

    @pytest.mark.asyncio
    async def test_init_without_redis(self, storage):
        """Should initialize in fallback mode without Redis."""
        await storage.init()
        assert storage._initialized
        assert not storage._use_redis

    @pytest.mark.asyncio
    async def test_store_and_get_memory(self, storage, mock_embedding_service):
        """Should store and retrieve memory."""
        await storage.init()

        stored = await storage.store_memory(
            content="Thom prefers coffee in the morning",
            memory_type="semantic",
            importance=0.7,
            participants=["thom"],
            tags=["coffee", "preference"],
        )

        assert stored.id.startswith("mem_")
        assert stored.content == "Thom prefers coffee in the morning"
        assert stored.memory_type == "semantic"

        # Retrieve
        retrieved = await storage.get_memory(stored.id)
        assert retrieved is not None
        assert retrieved.content == stored.content

    @pytest.mark.asyncio
    async def test_delete_memory(self, storage, mock_embedding_service):
        """Should delete memory."""
        await storage.init()

        stored = await storage.store_memory(
            content="Test memory",
            memory_type="episodic",
        )

        deleted = await storage.delete_memory(stored.id)
        assert deleted

        # Should not exist anymore
        retrieved = await storage.get_memory(stored.id)
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_search_memories_by_similarity(self, storage, mock_embedding_service):
        """Should search memories by vector similarity."""
        await storage.init()

        # Create unique embedding for each memory
        embeddings = [
            np.array([1.0] + [0.0] * (EMBEDDING_DIM - 1), dtype=np.float32),
            np.array([0.9, 0.1] + [0.0] * (EMBEDDING_DIM - 2), dtype=np.float32),
            np.array([0.0, 1.0] + [0.0] * (EMBEDDING_DIM - 2), dtype=np.float32),
        ]
        mock_embedding_service.embed.side_effect = embeddings + [
            embeddings[0]
        ]  # Query matches first

        # Store memories
        await storage.store_memory(content="Coffee preference", memory_type="semantic")
        await storage.store_memory(content="Tea preference", memory_type="semantic")
        await storage.store_memory(content="Sleep routine", memory_type="procedural")

        # Search
        results = await storage.search_memories(
            query="Coffee preference",
            min_score=0.0,  # Accept all
        )

        assert len(results) > 0
        # Results should be sorted by similarity
        similarities = [score for _, score in results]
        assert similarities == sorted(similarities, reverse=True)

    @pytest.mark.asyncio
    async def test_search_memories_filter_by_type(self, storage, mock_embedding_service):
        """Should filter search results by memory type."""
        await storage.init()

        # Store different types
        await storage.store_memory(content="Semantic memory", memory_type="semantic")
        await storage.store_memory(content="Episodic memory", memory_type="episodic")
        await storage.store_memory(content="Another semantic", memory_type="semantic")

        # Search only semantic
        results = await storage.search_memories(
            query="memory",
            memory_type="semantic",
            min_score=0.0,
        )

        for memory, _ in results:
            assert memory.memory_type == "semantic"

    @pytest.mark.asyncio
    async def test_search_memories_filter_by_participants(self, storage, mock_embedding_service):
        """Should filter search results by participants."""
        await storage.init()

        await storage.store_memory(
            content="Thom's preference",
            memory_type="semantic",
            participants=["thom"],
        )
        await storage.store_memory(
            content="Viola's preference",
            memory_type="semantic",
            participants=["viola"],
        )

        # Search for Thom only
        results = await storage.search_memories(
            query="preference",
            participants=["thom"],
            min_score=0.0,
        )

        for memory, _ in results:
            assert "thom" in memory.participants

    @pytest.mark.asyncio
    async def test_get_recent_memories(self, storage, mock_embedding_service):
        """Should return most recent memories."""
        await storage.init()

        await storage.store_memory(content="First memory", memory_type="episodic")
        await storage.store_memory(content="Second memory", memory_type="episodic")
        await storage.store_memory(content="Third memory", memory_type="episodic")

        recent = await storage.get_recent_memories(limit=2)

        assert len(recent) == 2
        # Should be sorted by creation time (newest first)
        assert recent[0].created_at >= recent[1].created_at

    @pytest.mark.asyncio
    async def test_get_memory_count(self, storage, mock_embedding_service):
        """Should count memories correctly."""
        await storage.init()

        await storage.store_memory(content="Memory 1", memory_type="semantic")
        await storage.store_memory(content="Memory 2", memory_type="semantic")
        await storage.store_memory(content="Memory 3", memory_type="episodic")

        total = await storage.get_memory_count()
        semantic = await storage.get_memory_count(memory_type="semantic")
        episodic = await storage.get_memory_count(memory_type="episodic")

        assert total == 3
        assert semantic == 2
        assert episodic == 1


# ============================================================================
# Working Memory Tests
# ============================================================================


class TestWorkingMemory:
    """Tests for working memory (TTL-based)."""

    @pytest.fixture
    def mock_embedding_service(self):
        """Create mock embedding service."""
        service = AsyncMock()
        service.init = AsyncMock()
        service.shutdown = AsyncMock()
        return service

    @pytest.fixture
    def storage(self, mock_embedding_service):
        """Create storage with short TTL for testing."""
        config = MemoryStorageConfig(working_memory_ttl_sec=1)  # 1 second TTL
        return MemoryStorage(
            redis_client=None,
            embedding_service=mock_embedding_service,
            config=config,
        )

    @pytest.mark.asyncio
    async def test_set_and_get_working_memory(self, storage):
        """Should store and retrieve working memory."""
        await storage.init()

        await storage.set_working_memory(
            session_id="session_123",
            key="context",
            value={"topic": "coffee", "mood": "happy"},
        )

        result = await storage.get_working_memory(
            session_id="session_123",
            key="context",
        )

        assert result == {"topic": "coffee", "mood": "happy"}

    @pytest.mark.asyncio
    async def test_working_memory_returns_none_for_missing(self, storage):
        """Should return None for missing working memory."""
        await storage.init()

        result = await storage.get_working_memory(
            session_id="nonexistent",
            key="context",
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_delete_specific_working_memory(self, storage):
        """Should delete specific working memory key."""
        await storage.init()

        await storage.set_working_memory("session_1", "key1", "value1")
        await storage.set_working_memory("session_1", "key2", "value2")

        await storage.delete_working_memory("session_1", "key1")

        assert await storage.get_working_memory("session_1", "key1") is None
        assert await storage.get_working_memory("session_1", "key2") == "value2"


# ============================================================================
# Global Singleton Tests
# ============================================================================


class TestGlobalSingletons:
    """Tests for global singleton functions."""

    def test_get_embedding_service_returns_singleton(self):
        """Should return same instance."""
        service1 = get_embedding_service()
        service2 = get_embedding_service()
        assert service1 is service2

    def test_get_memory_storage_returns_singleton(self):
        """Should return same instance."""
        storage1 = get_memory_storage()
        storage2 = get_memory_storage()
        assert storage1 is storage2
