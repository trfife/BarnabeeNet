"""Profile API routes for family profile management.

Provides endpoints for:
- CRUD operations on family profiles
- Profile event tracking
- Profile update generation and approval
- Guest profile management
- Profile context retrieval
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime
from typing import Any

import redis.asyncio as redis
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from barnabeenet.models.profiles import (
    CreateProfileRequest,
    DiffEntry,
    FamilyMemberProfile,
    GuestProfile,
    PrivacyZone,
    ProfileContextResponse,
    ProfileEventType,
    ProfileStatsResponse,
    UpdateProfileRequest,
)
from barnabeenet.services.profiles import ProfileService, get_profile_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/profiles", tags=["profiles"])


# ============================================================================
# Response Models
# ============================================================================


class ProfileListResponse(BaseModel):
    """Response for profile list queries."""

    profiles: list[FamilyMemberProfile]
    total: int


class ProfileResponse(BaseModel):
    """Response for a single profile."""

    profile: FamilyMemberProfile
    has_pending_update: bool = False


class ProfileDiffPreview(BaseModel):
    """Preview of a profile diff for the dashboard."""

    member_id: str
    name: str
    current_version: int
    summary: str
    additions: list[dict[str, Any]]
    modifications: list[dict[str, Any]]
    removals: list[dict[str, Any]]
    triggering_events: list[str]
    confidence_notes: str | None = None


class PendingUpdateItem(BaseModel):
    """A profile with a pending update."""

    member_id: str
    name: str
    current_version: int
    generated_at: str | None
    trigger_count: int


class GuestResponse(BaseModel):
    """Response for guest operations."""

    guest: GuestProfile
    message: str


class ActionResponse(BaseModel):
    """Generic action response."""

    success: bool
    message: str


# ============================================================================
# Helper Functions
# ============================================================================


async def _get_service(with_ha_client: bool = False) -> ProfileService:
    """Get or create the profile service.

    Args:
        with_ha_client: If True, also initialize the HA client for location lookups
    """
    from barnabeenet.api.routes.homeassistant import get_ha_client as get_ha

    try:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        redis_client = redis.from_url(redis_url, decode_responses=True)
        ha_client = await get_ha() if with_ha_client else None
        return await get_profile_service(redis_client, ha_client=ha_client)
    except Exception as e:
        logger.warning(f"Could not connect to Redis: {e}")
        return await get_profile_service(None)


def _format_diff_entry(entry: DiffEntry) -> dict[str, Any]:
    """Format a diff entry for API response."""
    return {
        "block": entry.block,
        "block_display": "🌐 Public" if entry.block == "public" else "🔒 Private",
        "field": entry.field_path,
        "type": entry.diff_type.value,
        "old": entry.old_value,
        "new": entry.new_value,
        "reason": entry.reason,
    }


# ============================================================================
# Profile CRUD Endpoints
# ============================================================================


@router.get("", response_model=ProfileListResponse)
async def list_profiles():
    """List all family member profiles."""
    service = await _get_service()
    profiles = await service.get_all_profiles()
    return ProfileListResponse(profiles=profiles, total=len(profiles))


@router.post("", response_model=ProfileResponse)
async def create_profile(request: CreateProfileRequest):
    """Create a new family member profile."""
    service = await _get_service()

    try:
        profile = await service.create_profile(request)
        return ProfileResponse(profile=profile, has_pending_update=False)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None


@router.get("/stats", response_model=ProfileStatsResponse)
async def get_profile_stats():
    """Get profile system statistics."""
    service = await _get_service()
    return await service.get_stats()


@router.get("/pending-updates")
async def list_pending_updates():
    """List all profiles with pending updates awaiting review."""
    service = await _get_service()
    profiles = await service.get_profiles_with_pending_updates()

    return {
        "pending_updates": [
            PendingUpdateItem(
                member_id=p.member_id,
                name=p.name,
                current_version=p.version,
                generated_at=(
                    p.pending_update_generated.isoformat() if p.pending_update_generated else None
                ),
                trigger_count=len(p.pending_update.triggering_events) if p.pending_update else 0,
            )
            for p in profiles
        ],
        "total": len(profiles),
    }


@router.get("/{member_id}", response_model=ProfileResponse)
async def get_profile(member_id: str):
    """Get a specific profile by member ID."""
    service = await _get_service()
    profile = await service.get_profile(member_id)

    if not profile:
        raise HTTPException(status_code=404, detail=f"Profile not found: {member_id}")

    return ProfileResponse(
        profile=profile,
        has_pending_update=profile.pending_update is not None,
    )


@router.put("/{member_id}", response_model=ProfileResponse)
async def update_profile(member_id: str, request: UpdateProfileRequest):
    """Update a profile (manual edit)."""
    service = await _get_service()

    try:
        profile = await service.update_profile(
            member_id,
            public=request.public,
            private=request.private,
        )
        return ProfileResponse(profile=profile, has_pending_update=False)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from None


@router.delete("/{member_id}", response_model=ActionResponse)
async def delete_profile(member_id: str):
    """Delete a profile."""
    service = await _get_service()
    deleted = await service.delete_profile(member_id)

    if not deleted:
        raise HTTPException(status_code=404, detail=f"Profile not found: {member_id}")

    return ActionResponse(success=True, message=f"Profile {member_id} deleted")


# ============================================================================
# Profile Events
# ============================================================================


@router.post("/{member_id}/events", response_model=ActionResponse)
async def add_event(
    member_id: str,
    event_type: str = Query(..., description="Event type (e.g., explicit_preference)"),
    description: str = Query(..., description="Event description"),
    conversation_id: str | None = Query(None, description="Source conversation ID"),
):
    """Add a profile event for potential update triggering."""
    service = await _get_service()

    # Validate event type
    try:
        event_type_enum = ProfileEventType(event_type)
    except ValueError:
        valid_types = [t.value for t in ProfileEventType]
        raise HTTPException(
            status_code=400, detail=f"Invalid event type. Valid types: {valid_types}"
        ) from None

    # Verify profile exists
    profile = await service.get_profile(member_id)
    if not profile:
        raise HTTPException(status_code=404, detail=f"Profile not found: {member_id}")

    await service.add_event(
        member_id=member_id,
        event_type=event_type_enum,
        description=description,
        conversation_id=conversation_id,
    )

    return ActionResponse(success=True, message="Event added")


@router.get("/{member_id}/events")
async def get_events(member_id: str, include_processed: bool = Query(False)):
    """Get profile events for a member."""
    service = await _get_service()

    # Verify profile exists
    profile = await service.get_profile(member_id)
    if not profile:
        raise HTTPException(status_code=404, detail=f"Profile not found: {member_id}")

    events = await service.get_unprocessed_events(member_id)
    accumulated = await service.get_accumulated_significance(member_id)

    return {
        "events": [
            {
                "id": e.id,
                "type": e.event_type.value,
                "description": e.description,
                "significance": e.significance_score,
                "occurred_at": e.occurred_at.isoformat(),
                "processed": e.processed,
            }
            for e in events
        ],
        "total": len(events),
        "accumulated_significance": accumulated,
        "update_threshold": 3.0,  # Standard threshold
    }


# ============================================================================
# Profile Updates
# ============================================================================


@router.post("/{member_id}/generate-update", response_model=ProfileDiffPreview)
async def generate_profile_update(member_id: str):
    """Generate a profile update for review (requires LLM)."""
    from barnabeenet.agents.profile import ProfileAgent

    service = await _get_service()

    # Verify profile exists
    profile = await service.get_profile(member_id)
    if not profile:
        raise HTTPException(status_code=404, detail=f"Profile not found: {member_id}")

    # Check if update is needed
    should_update, triggers = await service.should_trigger_update(member_id)
    if not should_update:
        # Still allow manual generation
        triggers = ["manual_request"]

    # Get dependencies (late import to avoid circular import)
    from barnabeenet.main import app_state

    llm_client = getattr(app_state, "llm_client", None)
    memory_storage = getattr(app_state, "memory_storage", None)

    # Create agent and generate update
    agent = ProfileAgent(
        llm_client=llm_client,
        profile_service=service,
        memory_storage=memory_storage,
    )
    await agent.init()

    diff = await agent.generate_profile_update(member_id, triggers)

    if not diff:
        raise HTTPException(status_code=500, detail="Failed to generate profile update")

    # Return preview
    return ProfileDiffPreview(
        member_id=member_id,
        name=profile.name,
        current_version=profile.version,
        summary=diff.llm_summary,
        additions=[_format_diff_entry(e) for e in diff.additions],
        modifications=[_format_diff_entry(e) for e in diff.modifications],
        removals=[_format_diff_entry(e) for e in diff.removals],
        triggering_events=diff.triggering_events,
        confidence_notes=diff.confidence_notes,
    )


@router.get("/{member_id}/pending-update", response_model=ProfileDiffPreview)
async def get_pending_update(member_id: str):
    """Get the pending update preview for a profile."""
    service = await _get_service()

    profile = await service.get_profile(member_id)
    if not profile:
        raise HTTPException(status_code=404, detail=f"Profile not found: {member_id}")

    if not profile.pending_update:
        raise HTTPException(status_code=404, detail="No pending update for this profile")

    diff = profile.pending_update

    return ProfileDiffPreview(
        member_id=member_id,
        name=profile.name,
        current_version=profile.version,
        summary=diff.llm_summary,
        additions=[_format_diff_entry(e) for e in diff.additions],
        modifications=[_format_diff_entry(e) for e in diff.modifications],
        removals=[_format_diff_entry(e) for e in diff.removals],
        triggering_events=diff.triggering_events,
        confidence_notes=diff.confidence_notes,
    )


@router.post("/{member_id}/approve-update", response_model=ProfileResponse)
async def approve_pending_update(member_id: str):
    """Approve and apply the pending profile update."""
    service = await _get_service()

    try:
        profile = await service.apply_pending_update(member_id)
        return ProfileResponse(profile=profile, has_pending_update=False)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None


@router.post("/{member_id}/reject-update", response_model=ActionResponse)
async def reject_pending_update(
    member_id: str,
    reason: str | None = Query(None, description="Rejection reason"),
):
    """Reject and discard the pending profile update."""
    service = await _get_service()

    profile = await service.get_profile(member_id)
    if not profile or not profile.pending_update:
        raise HTTPException(status_code=404, detail="No pending update to reject")

    await service.reject_pending_update(member_id, reason)
    return ActionResponse(success=True, message="Pending update rejected")


# ============================================================================
# Version History
# ============================================================================


@router.get("/{member_id}/history")
async def get_profile_history(member_id: str):
    """Get version history for a profile."""
    service = await _get_service()

    profile = await service.get_profile(member_id)
    if not profile:
        raise HTTPException(status_code=404, detail=f"Profile not found: {member_id}")

    history = await service.get_version_history(member_id)

    return {
        "member_id": member_id,
        "current_version": profile.version,
        "history": history,
    }


# ============================================================================
# Profile Context (for Agent Use)
# ============================================================================


@router.get("/{member_id}/context", response_model=ProfileContextResponse)
async def get_profile_context(
    member_id: str,
    participants: str | None = Query(None, description="Comma-separated participant IDs"),
    privacy_zone: str = Query("common_area_alone", description="Current privacy zone"),
):
    """Get profile context for agent injection.

    This endpoint returns the appropriate profile context based on
    privacy settings - public only vs full private context.
    """
    service = await _get_service(with_ha_client=True)  # Need HA client for location

    # Parse participants
    participant_list = participants.split(",") if participants else None

    # Parse privacy zone
    try:
        zone = PrivacyZone(privacy_zone)
    except ValueError:
        zone = PrivacyZone.COMMON_AREA_ALONE

    return await service.get_profile_context(
        speaker_id=member_id,
        conversation_participants=participant_list,
        privacy_zone=zone,
    )


# ============================================================================
# Guest Profiles
# ============================================================================


@router.post("/guests", response_model=GuestResponse)
async def create_guest(
    name: str | None = Query(None, description="Guest display name"),
    introduced_by: str | None = Query(None, description="Member who introduced guest"),
    allowed_rooms: str | None = Query(None, description="Comma-separated room names"),
):
    """Create a guest profile."""
    service = await _get_service()

    rooms = allowed_rooms.split(",") if allowed_rooms else None
    guest = await service.create_guest(
        display_name=name,
        introduced_by=introduced_by,
        allowed_rooms=rooms,
    )

    return GuestResponse(guest=guest, message="Guest profile created")


@router.delete("/guests/{guest_id}", response_model=ActionResponse)
async def end_guest_visit(guest_id: str):
    """End a guest's visit and remove their profile."""
    service = await _get_service()
    await service.end_guest_visit(guest_id)
    return ActionResponse(success=True, message="Guest visit ended")


# ============================================================================
# Trigger Check
# ============================================================================


@router.get("/{member_id}/check-update-trigger")
async def check_update_trigger(member_id: str):
    """Check if a profile update should be triggered."""
    service = await _get_service()

    profile = await service.get_profile(member_id)
    if not profile:
        raise HTTPException(status_code=404, detail=f"Profile not found: {member_id}")

    should_update, triggers = await service.should_trigger_update(member_id)
    accumulated = await service.get_accumulated_significance(member_id)

    return {
        "member_id": member_id,
        "should_update": should_update,
        "triggers": triggers,
        "accumulated_significance": accumulated,
        "threshold": 3.0,
        "days_since_update": (datetime.now(UTC) - profile.last_updated.replace(tzinfo=UTC)).days,
    }


# ============================================================================
# Home Assistant Sync
# ============================================================================


class HASyncResult(BaseModel):
    """Result of syncing profiles from Home Assistant."""

    created: list[str]
    updated: list[str]
    unchanged: list[str]
    errors: list[str]


@router.post("/sync-from-ha", response_model=HASyncResult)
async def sync_profiles_from_ha():
    """Sync family profiles from Home Assistant person entities.

    Creates new profiles for HA persons that don't exist in BarnabeeNet,
    and updates existing profiles with ha_person_entity links if missing.
    """
    from barnabeenet.api.routes.homeassistant import get_ha_client

    service = await _get_service()
    ha_client = await get_ha_client()

    if not ha_client or not ha_client.connected:
        raise HTTPException(status_code=503, detail="Home Assistant not connected")

    created: list[str] = []
    updated: list[str] = []
    unchanged: list[str] = []
    errors: list[str] = []

    # Get all person entities from HA
    try:
        entities = await ha_client.get_entities("person")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get HA entities: {e}") from None

    existing_profiles = await service.get_all_profiles()
    existing_by_ha_entity = {p.ha_person_entity: p for p in existing_profiles if p.ha_person_entity}
    existing_by_name = {p.name.lower(): p for p in existing_profiles}

    for entity in entities:
        entity_id = entity.entity_id
        friendly_name = entity.name or entity_id.replace("person.", "").replace("_", " ").title()

        try:
            # Check if already linked by ha_person_entity
            if entity_id in existing_by_ha_entity:
                unchanged.append(f"{friendly_name} (already linked)")
                continue

            # Check if exists by name match (update with ha_person_entity)
            name_key = friendly_name.lower()
            if name_key in existing_by_name:
                profile = existing_by_name[name_key]
                if not profile.ha_person_entity:
                    # Update with HA entity link
                    await service.update_profile(
                        profile.member_id,
                        ha_person_entity=entity_id,
                        increment_version=False,
                    )
                    updated.append(f"{friendly_name} → {entity_id}")
                else:
                    unchanged.append(f"{friendly_name} (already linked)")
                continue

            # Create new profile
            member_id = entity_id.replace("person.", "")
            request = CreateProfileRequest(
                member_id=member_id,
                name=friendly_name,
                ha_person_entity=entity_id,
            )
            await service.create_profile(request)
            created.append(f"{friendly_name} ({entity_id})")

        except Exception as e:
            errors.append(f"{friendly_name}: {e}")
            logger.exception(f"Error syncing profile for {entity_id}")

    return HASyncResult(
        created=created,
        updated=updated,
        unchanged=unchanged,
        errors=errors,
    )
