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

# Extended conversation templates for generating a month of realistic data
CONVERSATION_TEMPLATES: list[dict[str, Any]] = [
    # Morning routines
    {"speaker": "thom", "room": "kitchen", "intent": "action", "category": "morning",
     "exchanges": [("Turn on the coffee maker", "I've turned on the coffee maker."),
                   ("What's the weather today?", "It's 65°F and partly cloudy. High of 72°F expected.")]},
    {"speaker": "elizabeth", "room": "bedroom", "intent": "action", "category": "morning",
     "exchanges": [("Set an alarm for 6:30 tomorrow", "Alarm set for 6:30 AM tomorrow."),
                   ("What's on my calendar today?", "You have a dentist appointment at 2pm and pickup at 3:30.")]},
    {"speaker": "penelope", "room": "bedroom", "intent": "instant", "category": "morning",
     "exchanges": [("What time is it?", "It's 7:15 AM."),
                   ("How do you spell necessary?", "N-E-C-E-S-S-A-R-Y")]},
    # Device control
    {"speaker": "thom", "room": "office", "intent": "action", "category": "device",
     "exchanges": [("Turn on the office lights", "I've turned on the office lights."),
                   ("Set brightness to 80 percent", "Office lights set to 80% brightness.")]},
    {"speaker": "elizabeth", "room": "living_room", "intent": "action", "category": "device",
     "exchanges": [("Turn off all the downstairs lights", "I've turned off all downstairs lights."),
                   ("Is the front door locked?", "Yes, the front door is locked.")]},
    {"speaker": "xander", "room": "bedroom", "intent": "action", "category": "device",
     "exchanges": [("Turn on my fan", "I've turned on your bedroom fan."),
                   ("Play some music", "Playing your favorite playlist on the bedroom speaker.")]},
    # Homework help
    {"speaker": "penelope", "room": "kitchen", "intent": "conversation", "category": "homework",
     "exchanges": [("Can you help me with my history homework?", "Of course! What topic are you studying?"),
                   ("The American Revolution", "Great topic! What specifically do you need help with?"),
                   ("When did it start?", "The American Revolution began in 1775 with the battles of Lexington and Concord.")]},
    {"speaker": "xander", "room": "living_room", "intent": "instant", "category": "homework",
     "exchanges": [("What's 156 times 23?", "156 times 23 equals 3,588."),
                   ("What's the capital of France?", "The capital of France is Paris.")]},
    {"speaker": "zachary", "room": "kitchen", "intent": "conversation", "category": "homework",
     "exchanges": [("How do dinosaurs become fossils?", "When a dinosaur died, sometimes it got buried under mud or sand. Over millions of years, the bones turned into rock. That's how we find them today!")]},
    # Dinner planning
    {"speaker": "elizabeth", "room": "kitchen", "intent": "conversation", "category": "dinner",
     "exchanges": [("What should we make for dinner?", "How about tacos? Everyone likes those, and we have all the ingredients."),
                   ("Good idea, can you remind me to start cooking at 5?", "I'll remind you at 5 PM to start cooking dinner.")]},
    {"speaker": "thom", "room": "kitchen", "intent": "conversation", "category": "dinner",
     "exchanges": [("What's for dinner tonight?", "Elizabeth mentioned tacos earlier."),
                   ("Perfect, I'll help with the prep", "That sounds great! Dinner should be ready around 6.")]},
    # Bedtime routines
    {"speaker": "viola", "room": "bedroom", "intent": "conversation", "category": "bedtime",
     "exchanges": [("Can you tell me a story?", "Once upon a time, there was a little bunny named Whiskers who loved to explore the forest..."),
                   ("What happened next?", "Whiskers found a magical garden full of carrots that glowed in the moonlight!")]},
    {"speaker": "zachary", "room": "bedroom", "intent": "action", "category": "bedtime",
     "exchanges": [("Turn on my nightlight", "I've turned on your nightlight."),
                   ("Goodnight Barnabee", "Goodnight Zachary! Sweet dreams.")]},
    # Entertainment
    {"speaker": "xander", "room": "living_room", "intent": "conversation", "category": "entertainment",
     "exchanges": [("What's a good movie to watch?", "How about How to Train Your Dragon? It has adventure and dragons!"),
                   ("Yeah! Can you turn on the TV?", "I've turned on the living room TV.")]},
    {"speaker": "penelope", "room": "bedroom", "intent": "action", "category": "entertainment",
     "exchanges": [("Play Taylor Swift", "Playing Taylor Swift on your bedroom speaker."),
                   ("Turn it up", "Volume increased.")]},
    # Questions and curiosity
    {"speaker": "viola", "room": "kitchen", "intent": "conversation", "category": "curiosity",
     "exchanges": [("Why is the sky blue?", "The sky looks blue because sunlight bounces off tiny bits in the air, and blue light bounces the most! Like how a bouncy ball bounces everywhere."),
                   ("That's cool!", "I think so too! The world is full of amazing things.")]},
    {"speaker": "zachary", "room": "living_room", "intent": "conversation", "category": "curiosity",
     "exchanges": [("How do airplanes fly?", "Airplanes have special shaped wings that make air move faster over the top. This creates a push upward called lift that keeps them in the sky!"),
                   ("Can I be a pilot?", "Absolutely! Pilots are very important and help people travel all over the world.")]},
    # Reminders and schedules
    {"speaker": "elizabeth", "room": "kitchen", "intent": "action", "category": "schedule",
     "exchanges": [("Remind me to call mom at 3pm", "I'll remind you to call mom at 3 PM."),
                   ("What time is soccer practice?", "Soccer practice is at 4 PM on Tuesdays and Thursdays.")]},
    {"speaker": "thom", "room": "office", "intent": "action", "category": "schedule",
     "exchanges": [("Set a timer for 25 minutes", "Timer set for 25 minutes."),
                   ("What meetings do I have tomorrow?", "You have a team standup at 9 AM and a project review at 2 PM.")]},
    # Home management
    {"speaker": "thom", "room": "garage", "intent": "action", "category": "home",
     "exchanges": [("Is the garage door closed?", "Yes, the garage door is closed."),
                   ("Turn on the porch light", "I've turned on the porch light.")]},
    {"speaker": "elizabeth", "room": "laundry", "intent": "action", "category": "home",
     "exchanges": [("Set a timer for the laundry 45 minutes", "Timer set for 45 minutes for the laundry."),
                   ("Remind me to switch the clothes", "I'll remind you in 45 minutes to switch the laundry.")]},
    # Cooking help
    {"speaker": "elizabeth", "room": "kitchen", "intent": "conversation", "category": "cooking",
     "exchanges": [("How long do I bake chicken at 375?", "Bake chicken breasts at 375F for about 25-30 minutes, until the internal temperature reaches 165F."),
                   ("Thanks! Set a timer for 27 minutes", "Timer set for 27 minutes.")]},
    {"speaker": "thom", "room": "kitchen", "intent": "conversation", "category": "cooking",
     "exchanges": [("What's a good marinade for steak?", "A classic marinade is olive oil, soy sauce, garlic, and a little Worcestershire sauce. Let it sit for at least 30 minutes."),
                   ("Perfect, I'll try that", "Enjoy! Let me know how it turns out.")]},
    # Weather checks
    {"speaker": "penelope", "room": "bedroom", "intent": "instant", "category": "weather",
     "exchanges": [("Do I need a jacket today?", "Yes, it's going to be cool today around 58F. A light jacket would be good.")]},
    {"speaker": "xander", "room": "kitchen", "intent": "instant", "category": "weather",
     "exchanges": [("Is it going to rain?", "There's a 30% chance of rain this afternoon. You might want to bring an umbrella just in case.")]},
    # Goodnight routines
    {"speaker": "thom", "room": "living_room", "intent": "action", "category": "goodnight",
     "exchanges": [("Goodnight mode", "Goodnight! I've turned off the downstairs lights, locked the doors, and set the thermostat to 68F.")]},
    {"speaker": "elizabeth", "room": "bedroom", "intent": "action", "category": "goodnight",
     "exchanges": [("Are all the kids in bed?", "I can see activity in Viola's room. The other kids' rooms are quiet."),
                   ("Thanks, I'll check on her", "You're welcome. Goodnight!")]},
    # Weekend activities
    {"speaker": "thom", "room": "kitchen", "intent": "conversation", "category": "weekend",
     "exchanges": [("What's the plan for today?", "It's Saturday! Xander has a soccer game at 10, and the family was planning to go to the park after lunch.")]},
    {"speaker": "elizabeth", "room": "living_room", "intent": "conversation", "category": "weekend",
     "exchanges": [("Should we go out for dinner tonight?", "That sounds nice! It's been a while since you all went out together. What kind of food is everyone in the mood for?")]},
    # Health and wellness
    {"speaker": "elizabeth", "room": "kitchen", "intent": "conversation", "category": "health",
     "exchanges": [("Remind me about Viola's doctor appointment", "Viola has a checkup scheduled for next Tuesday at 10 AM with Dr. Patterson.")]},
    {"speaker": "penelope", "room": "bedroom", "intent": "instant", "category": "health",
     "exchanges": [("What helps a sore throat?", "Warm liquids like tea with honey, rest, and gargling salt water can help. Let your parents know if it doesn't get better.")]},
    # School related
    {"speaker": "xander", "room": "kitchen", "intent": "conversation", "category": "school",
     "exchanges": [("I have a science project due", "What's the project about? I can help you plan it out."),
                   ("It's about the solar system", "That's a great topic! Would you like to start by listing the planets in order?")]},
    {"speaker": "zachary", "room": "living_room", "intent": "instant", "category": "school",
     "exchanges": [("How do you spell dinosaur?", "D-I-N-O-S-A-U-R")]},
    # Fun facts
    {"speaker": "viola", "room": "kitchen", "intent": "conversation", "category": "facts",
     "exchanges": [("Tell me something fun", "Did you know that butterflies taste with their feet? They land on flowers and can tell if they're yummy!")]},
    {"speaker": "zachary", "room": "bedroom", "intent": "conversation", "category": "facts",
     "exchanges": [("What's the biggest animal?", "The blue whale is the biggest animal ever! It's even bigger than the biggest dinosaurs were. A blue whale's heart is as big as a car!")]},
]

# Rooms where each family member typically interacts
MEMBER_ROOMS = {
    "thom": ["office", "kitchen", "living_room", "garage", "bedroom"],
    "elizabeth": ["kitchen", "bedroom", "living_room", "laundry"],
    "penelope": ["bedroom", "kitchen", "living_room"],
    "xander": ["bedroom", "living_room", "kitchen"],
    "zachary": ["bedroom", "living_room", "kitchen"],
    "viola": ["bedroom", "kitchen", "living_room"],
}

# Time distributions (hour of day) for different speakers
ACTIVITY_HOURS = {
    "thom": list(range(6, 23)),  # 6 AM to 11 PM
    "elizabeth": list(range(6, 23)),
    "penelope": list(range(7, 22)),  # 7 AM to 10 PM
    "xander": list(range(7, 21)),  # 7 AM to 9 PM
    "zachary": list(range(7, 21)),
    "viola": list(range(7, 20)),  # 7 AM to 8 PM
}


# ============================================================================
# Request/Response Models
# ============================================================================


class GenerateMockDataRequest(BaseModel):
    """Request to generate mock data."""

    include_family: bool = Field(default=True, description="Generate family profiles")
    include_memories: bool = Field(default=True, description="Generate memories")
    include_conversations: bool = Field(default=True, description="Generate conversation history")
    include_audit_log: bool = Field(default=True, description="Populate audit log with history")
    days_of_history: int = Field(default=7, ge=1, le=30, description="Days of history to generate")
    conversations_per_day: int = Field(default=10, ge=1, le=50, description="Avg conversations per day")


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
        "audit_entries": 0,
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

    # Generate conversation history (as episodic memories and audit log entries)
    if request.include_conversations:
        memory_storage = await _get_memory_storage()
        audit_log = None
        if request.include_audit_log:
            try:
                from barnabeenet.services.audit.log import AuditLogEntry, get_audit_log
                audit_log = get_audit_log()
            except Exception as e:
                logger.warning(f"Could not get audit log: {e}")

        # Generate conversations for each day
        for day in range(request.days_of_history):
            # Number of conversations varies by day (weekends have more)
            base_date = datetime.now(UTC) - timedelta(days=day)
            is_weekend = base_date.weekday() >= 5
            num_convs = request.conversations_per_day + (5 if is_weekend else 0)
            num_convs = random.randint(int(num_convs * 0.7), int(num_convs * 1.3))

            for _ in range(num_convs):
                # Pick a random template
                template = random.choice(CONVERSATION_TEMPLATES)
                speaker = template["speaker"]

                # Pick a time appropriate for this speaker
                hours = ACTIVITY_HOURS.get(speaker, list(range(8, 21)))
                hour = random.choice(hours)
                minute = random.randint(0, 59)
                conv_time = base_date.replace(hour=hour, minute=minute, second=0, microsecond=0)

                # Use template room or pick from member's typical rooms
                room = template.get("room") or random.choice(MEMBER_ROOMS.get(speaker, ["living_room"]))
                conv_id = f"conv_{room}_{uuid.uuid4().hex[:8]}"

                try:
                    for user_text, assistant_response in template["exchanges"]:
                        # Store as episodic memory
                        if memory_storage:
                            content = f"{speaker.title()} asked: '{user_text}' in the {room}. I responded: '{assistant_response}'"
                            await memory_storage.store_memory(
                                content=content,
                                memory_type="episodic",
                                importance=0.5,
                                participants=[speaker],
                                tags=["conversation", "mock_data", room, template.get("category", "general")],
                            )

                        # Also add to audit log
                        if audit_log:
                            entry = AuditLogEntry(
                                timestamp=conv_time,
                                conversation_id=conv_id,
                                speaker=speaker,
                                room=room,
                                user_text=user_text,
                                assistant_response=assistant_response,
                                intent=template.get("intent", "conversation"),
                                agent="mock_data",
                            )
                            await audit_log.log_conversation(entry)
                            results["audit_entries"] += 1

                        results["conversation_turns"] += 1
                        # Advance time slightly for multi-turn conversations
                        conv_time = conv_time + timedelta(seconds=random.randint(5, 30))

                    results["conversations"] += 1
                except Exception as e:
                    logger.warning(f"Failed to create conversation: {e}")

    message = f"Generated {results['family_profiles']} profiles, {results['memories']} memories, {results['conversations']} conversations ({results['conversation_turns']} turns), {results['audit_entries']} audit entries"
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
