"""Testing API routes for development and QA.

Provides endpoints for:
- Generating mock data (family profiles, memories, conversations)
- Clearing all data for production reset
- Health checks for testing infrastructure

WARNING: These endpoints are for development/testing only.
Do not expose in production without proper authentication.
"""

from __future__ import annotations

import logging
import random
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/testing", tags=["testing"])


# ============================================================================
# Mock Data Definitions
# ============================================================================

MOCK_FAMILY: list[dict[str, Any]] = [
    {
        "id": "thom",
        "name": "Thom",
        "relationship": "self",
        "preferences": {
            "preferred_temperature": 72,
            "wake_time": "06:30",
            "favorite_music": "jazz",
        },
    },
    {
        "id": "elizabeth",
        "name": "Elizabeth",
        "relationship": "spouse",
        "preferences": {
            "preferred_temperature": 74,
            "wake_time": "07:00",
            "favorite_music": "classical",
        },
    },
    {
        "id": "penelope",
        "name": "Penelope",
        "relationship": "child",
        "age": 14,
        "preferences": {
            "bedtime": "21:30",
            "favorite_color": "purple",
        },
    },
    {
        "id": "xander",
        "name": "Xander",
        "relationship": "child",
        "age": 11,
        "preferences": {
            "bedtime": "21:00",
            "favorite_game": "Minecraft",
        },
    },
    {
        "id": "zachary",
        "name": "Zachary",
        "relationship": "child",
        "age": 8,
        "preferences": {
            "bedtime": "20:30",
            "favorite_color": "blue",
        },
    },
    {
        "id": "viola",
        "name": "Viola",
        "relationship": "child",
        "age": 5,
        "preferences": {
            "bedtime": "20:00",
            "favorite_animal": "bunny",
        },
    },
]

MOCK_CONVERSATIONS: list[dict[str, Any]] = [
    {
        "speaker": "elizabeth",
        "room": "kitchen",
        "exchanges": [
            ("What should we make for dinner tonight?", "How about lasagna? It's been a while since we had Italian."),
            ("That sounds good, do we have all the ingredients?", "You might need ricotta and Italian sausage from the store."),
            ("I'll add those to the list", "Great! I've noted that you're planning lasagna for tonight."),
        ],
    },
    {
        "speaker": "xander",
        "room": "living_room",
        "exchanges": [
            ("How do you spell dinosaur?", "Dinosaur is spelled D-I-N-O-S-A-U-R. Would you like that one letter at a time?"),
            ("No thanks", "Okay! Let me know if you need help with anything else."),
        ],
    },
    {
        "speaker": "thom",
        "room": "office",
        "exchanges": [
            ("Turn on the office light", "Done! I've turned on the office light."),
            ("What's the temperature in here?", "The office is currently 72 degrees Fahrenheit."),
            ("Set a timer for 30 minutes", "Timer set for 30 minutes. I'll let you know when it's done."),
        ],
    },
    {
        "speaker": "penelope",
        "room": "bedroom",
        "exchanges": [
            ("Tell me a bedtime story", "Once upon a time, in a cozy little cottage by the sea, there lived a curious cat named Whiskers..."),
            ("What time is it?", "It's 8:45 PM - you have about 45 minutes until bedtime!"),
        ],
    },
    {
        "speaker": "viola",
        "room": "playroom",
        "exchanges": [
            ("What sound does a cow make?", "A cow says moo! Mooooo! Do you want to hear another animal sound?"),
            ("Yes! What about a lion?", "A lion goes ROAR! Lions are called the kings of the jungle."),
        ],
    },
]

MOCK_MEMORIES: list[dict[str, Any]] = [
    {
        "content": "Elizabeth's favorite color is purple",
        "memory_type": "semantic",
        "participants": ["elizabeth"],
        "importance": 0.8,
        "tags": ["preference", "color"],
    },
    {
        "content": "Thom prefers the office temperature at 72 degrees Fahrenheit",
        "memory_type": "semantic",
        "participants": ["thom"],
        "importance": 0.7,
        "tags": ["preference", "temperature", "comfort"],
    },
    {
        "content": "Xander is learning to spell in school and often asks for help",
        "memory_type": "semantic",
        "participants": ["xander"],
        "importance": 0.6,
        "tags": ["education", "spelling"],
    },
    {
        "content": "The family enjoys Italian food, especially lasagna",
        "memory_type": "semantic",
        "participants": ["family"],
        "importance": 0.7,
        "tags": ["food", "preference", "italian"],
    },
    {
        "content": "Penelope's bedtime is 9:30 PM on school nights",
        "memory_type": "procedural",
        "participants": ["penelope"],
        "importance": 0.8,
        "tags": ["routine", "bedtime"],
    },
    {
        "content": "Viola loves stories about animals, especially bunnies",
        "memory_type": "semantic",
        "participants": ["viola"],
        "importance": 0.6,
        "tags": ["preference", "stories", "animals"],
    },
    {
        "content": "Zachary's favorite game is Minecraft and he plays after homework",
        "memory_type": "semantic",
        "participants": ["zachary"],
        "importance": 0.6,
        "tags": ["preference", "games", "routine"],
    },
    {
        "content": "Elizabeth and Thom prefer to wake up around 6:30-7:00 AM",
        "memory_type": "procedural",
        "participants": ["elizabeth", "thom"],
        "importance": 0.7,
        "tags": ["routine", "morning"],
    },
    {
        "content": "The family has dinner together most evenings around 6 PM",
        "memory_type": "procedural",
        "participants": ["family"],
        "importance": 0.8,
        "tags": ["routine", "dinner", "family"],
    },
    {
        "content": "Thom works from home in the office and prefers not to be disturbed during work hours",
        "memory_type": "semantic",
        "participants": ["thom"],
        "importance": 0.9,
        "tags": ["work", "preference", "schedule"],
    },
]


# ============================================================================
# Request/Response Models
# ============================================================================


class GenerateMockDataRequest(BaseModel):
    """Request to generate mock data."""

    include_family: bool = Field(default=True, description="Generate family profiles")
    include_memories: bool = Field(default=True, description="Generate memories")
    include_conversations: bool = Field(default=True, description="Generate conversation history")
    days_of_history: int = Field(default=7, ge=1, le=30, description="Days of history to generate")


class GenerateMockDataResponse(BaseModel):
    """Response from mock data generation."""

    success: bool
    generated: dict[str, int]
    message: str


class ClearDataRequest(BaseModel):
    """Request to clear all data."""

    confirm: bool = Field(default=False, description="Must be true to confirm deletion")
    clear_memories: bool = Field(default=True, description="Clear all memories")
    clear_conversations: bool = Field(default=True, description="Clear conversation contexts")
    clear_family_profiles: bool = Field(default=True, description="Clear family profiles")
    clear_audit_log: bool = Field(default=False, description="Clear immutable audit log (production reset only)")


class ClearDataResponse(BaseModel):
    """Response from clearing data."""

    success: bool
    cleared: dict[str, int]
    message: str


# ============================================================================
# Helper Functions
# ============================================================================


from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from barnabeenet.services.memory.storage import MemoryStorage
    from barnabeenet.services.profiles import ProfileService
    import redis.asyncio as redis


async def _get_memory_storage() -> "MemoryStorage | None":
    """Get memory storage instance."""
    try:
        from barnabeenet.main import app_state
        if hasattr(app_state, "memory_storage") and app_state.memory_storage:
            return app_state.memory_storage
    except Exception:
        pass
    return None


async def _get_profile_service() -> "ProfileService | None":
    """Get profile service instance."""
    try:
        from barnabeenet.services.profiles import get_profile_service
        return await get_profile_service()
    except Exception:
        pass
    return None


async def _get_redis_client() -> "redis.Redis | None":
    """Get Redis client."""
    try:
        from barnabeenet.main import app_state
        if hasattr(app_state, "redis_client") and app_state.redis_client:
            return app_state.redis_client
    except Exception:
        pass
    return None


# ============================================================================
# Endpoints
# ============================================================================


@router.post("/generate-mock-data", response_model=GenerateMockDataResponse)
async def generate_mock_data(request: GenerateMockDataRequest | None = None) -> GenerateMockDataResponse:
    """Generate mock data for testing.

    Creates sample family profiles, memories, and conversation history
    to populate the dashboard for testing purposes.
    """
    if request is None:
        request = GenerateMockDataRequest()

    results = {
        "family_profiles": 0,
        "memories": 0,
        "conversations": 0,
        "conversation_turns": 0,
    }

    # Generate family profiles
    if request.include_family:
        profile_service = await _get_profile_service()
        if profile_service:
            for member in MOCK_FAMILY:
                try:
                    # Check if profile already exists
                    existing = await profile_service.get_profile(member["id"])
                    if existing is None:
                        await profile_service.create_profile(
                            member_id=member["id"],
                            name=member["name"],
                            relationship=member.get("relationship", "family"),
                        )
                        results["family_profiles"] += 1
                        logger.info(f"Created mock family profile: {member['name']}")
                except Exception as e:
                    logger.warning(f"Failed to create profile for {member['id']}: {e}")

    # Generate memories
    if request.include_memories:
        memory_storage = await _get_memory_storage()
        if memory_storage:
            for mem in MOCK_MEMORIES:
                try:
                    # Randomize creation time within the specified days
                    days_ago = random.randint(0, request.days_of_history)
                    hours_ago = random.randint(0, 23)
                    created_at = datetime.now(UTC) - timedelta(days=days_ago, hours=hours_ago)

                    await memory_storage.store_memory(
                        content=mem["content"],
                        memory_type=mem["memory_type"],
                        importance=mem["importance"],
                        participants=mem["participants"],
                        tags=mem.get("tags", []) + ["mock_data"],
                    )
                    results["memories"] += 1
                except Exception as e:
                    logger.warning(f"Failed to create memory: {e}")

    # Generate conversation history (as episodic memories)
    if request.include_conversations:
        memory_storage = await _get_memory_storage()
        if memory_storage:
            for conv in MOCK_CONVERSATIONS:
                try:
                    # Randomize conversation time
                    days_ago = random.randint(0, request.days_of_history)
                    hours_ago = random.randint(8, 21)  # Daytime hours

                    for user_text, assistant_response in conv["exchanges"]:
                        # Store as episodic memory
                        content = f"{conv['speaker'].title()} asked: '{user_text}' in the {conv['room']}. I responded: '{assistant_response}'"
                        await memory_storage.store_memory(
                            content=content,
                            memory_type="episodic",
                            importance=0.5,
                            participants=[conv["speaker"]],
                            tags=["conversation", "mock_data", conv["room"]],
                        )
                        results["conversation_turns"] += 1

                    results["conversations"] += 1
                except Exception as e:
                    logger.warning(f"Failed to create conversation: {e}")

    message = f"Generated {results['family_profiles']} profiles, {results['memories']} memories, {results['conversations']} conversations ({results['conversation_turns']} turns)"
    logger.info(f"Mock data generation complete: {message}")

    return GenerateMockDataResponse(
        success=True,
        generated=results,
        message=message,
    )


@router.post("/clear-all-data", response_model=ClearDataResponse)
async def clear_all_data(request: ClearDataRequest) -> ClearDataResponse:
    """Clear all data for production reset.

    WARNING: This permanently deletes data. Requires confirm=true.
    Use this when preparing the system for production use after testing.
    """
    if not request.confirm:
        raise HTTPException(
            status_code=400,
            detail="Must set confirm=true to clear all data. This action is irreversible!",
        )

    results = {
        "memories_deleted": 0,
        "conversations_deleted": 0,
        "family_profiles_deleted": 0,
        "audit_entries_deleted": 0,
        "redis_keys_deleted": 0,
    }

    # Clear memories
    if request.clear_memories:
        memory_storage = await _get_memory_storage()
        if memory_storage:
            try:
                # Get all memories and delete them
                all_memories = await memory_storage.get_all_memories()
                for mem in all_memories:
                    await memory_storage.delete_memory(mem.id)
                    results["memories_deleted"] += 1
                logger.info(f"Deleted {results['memories_deleted']} memories")
            except Exception as e:
                logger.warning(f"Failed to clear memories: {e}")

    # Clear family profiles
    if request.clear_family_profiles:
        profile_service = await _get_profile_service()
        if profile_service:
            try:
                # Get all profiles and delete them
                all_profiles = await profile_service.list_profiles()
                for profile in all_profiles:
                    await profile_service.delete_profile(profile.id)
                    results["family_profiles_deleted"] += 1
                logger.info(f"Deleted {results['family_profiles_deleted']} family profiles")
            except Exception as e:
                logger.warning(f"Failed to clear family profiles: {e}")

    # Clear conversation contexts from Redis
    if request.clear_conversations:
        redis_client = await _get_redis_client()
        if redis_client:
            try:
                # Clear conversation-related keys
                patterns = [
                    "barnabeenet:conversation:*",
                    "barnabeenet:working_memory:*",
                    "barnabeenet:context:*",
                ]
                for pattern in patterns:
                    keys = await redis_client.keys(pattern)
                    if keys:
                        await redis_client.delete(*keys)
                        results["conversations_deleted"] += len(keys)
                logger.info(f"Deleted {results['conversations_deleted']} conversation contexts")
            except Exception as e:
                logger.warning(f"Failed to clear conversations: {e}")

    # Clear audit log (only for production reset)
    if request.clear_audit_log:
        redis_client = await _get_redis_client()
        if redis_client:
            try:
                # Clear audit log keys
                keys = await redis_client.keys("barnabeenet:audit:*")
                if keys:
                    await redis_client.delete(*keys)
                    results["audit_entries_deleted"] += len(keys)
                logger.info(f"Deleted {results['audit_entries_deleted']} audit log entries")
            except Exception as e:
                logger.warning(f"Failed to clear audit log: {e}")

    total_deleted = sum(results.values())
    message = f"Cleared {total_deleted} items total"
    logger.warning(f"DATA CLEAR: {message} - {results}")

    return ClearDataResponse(
        success=True,
        cleared=results,
        message=message,
    )


@router.get("/status")
async def get_testing_status() -> dict[str, Any]:
    """Get status of testing infrastructure.

    Returns information about what services are available
    and current data counts.
    """
    status = {
        "memory_storage": False,
        "profile_service": False,
        "redis": False,
        "counts": {
            "memories": 0,
            "family_profiles": 0,
        },
    }

    # Check memory storage
    memory_storage = await _get_memory_storage()
    if memory_storage:
        status["memory_storage"] = True
        try:
            memories = await memory_storage.get_all_memories()
            status["counts"]["memories"] = len(memories)
        except Exception:
            pass

    # Check profile service
    profile_service = await _get_profile_service()
    if profile_service:
        status["profile_service"] = True
        try:
            profiles = await profile_service.list_profiles()
            status["counts"]["family_profiles"] = len(profiles)
        except Exception:
            pass

    # Check Redis
    redis_client = await _get_redis_client()
    if redis_client:
        try:
            await redis_client.ping()
            status["redis"] = True
        except Exception:
            pass

    return status


@router.delete("/mock-data")
async def delete_mock_data() -> dict[str, Any]:
    """Delete only mock data (data tagged with 'mock_data').

    This is safer than clear-all-data as it only removes
    test data, not real user data.
    """
    results = {
        "memories_deleted": 0,
    }

    memory_storage = await _get_memory_storage()
    if memory_storage:
        try:
            all_memories = await memory_storage.get_all_memories()
            for mem in all_memories:
                if "mock_data" in mem.tags:
                    await memory_storage.delete_memory(mem.id)
                    results["memories_deleted"] += 1
            logger.info(f"Deleted {results['memories_deleted']} mock memories")
        except Exception as e:
            logger.warning(f"Failed to delete mock data: {e}")

    return {
        "success": True,
        "deleted": results,
        "message": f"Deleted {results['memories_deleted']} mock data items",
    }
