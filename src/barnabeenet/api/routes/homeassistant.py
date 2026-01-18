"""Home Assistant API routes.

Dashboard endpoints for Home Assistant integration:
- Connection status and configuration
- Entity browsing and search
- Device and area discovery
- Service call execution
- Automation management
- Error log viewing
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from barnabeenet.config import get_settings
from barnabeenet.services.homeassistant.client import HomeAssistantClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/homeassistant", tags=["Home Assistant"])


# =============================================================================
# Response Models
# =============================================================================


class HAConnectionStatus(BaseModel):
    """Home Assistant connection status."""

    connected: bool = Field(description="Whether BarnabeeNet is connected to Home Assistant")
    url: str | None = Field(None, description="Home Assistant URL (if configured)")
    version: str | None = Field(None, description="Home Assistant version")
    location_name: str | None = Field(None, description="Home instance name")
    error: str | None = Field(None, description="Connection error message if any")


class HAConfig(BaseModel):
    """Home Assistant configuration (for saving)."""

    url: str = Field(description="Home Assistant URL")
    token: str = Field(description="Long-lived access token")


class EntitySummary(BaseModel):
    """Summary of a Home Assistant entity."""

    entity_id: str
    domain: str
    friendly_name: str
    state: str
    device_class: str | None = None
    area_id: str | None = None
    area_name: str | None = None
    last_changed: str | None = None
    icon: str | None = None
    is_on: bool | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class DeviceSummary(BaseModel):
    """Summary of a Home Assistant device."""

    id: str
    name: str
    manufacturer: str | None = None
    model: str | None = None
    area_id: str | None = None
    area_name: str | None = None
    entity_count: int = 0
    is_enabled: bool = True


class AreaSummary(BaseModel):
    """Summary of a Home Assistant area."""

    id: str
    name: str
    icon: str | None = None
    floor_id: str | None = None
    device_count: int = 0
    entity_count: int = 0


class AutomationSummary(BaseModel):
    """Summary of a Home Assistant automation."""

    entity_id: str
    name: str
    state: str  # on, off, unavailable
    last_triggered: str | None = None
    mode: str = "single"
    description: str | None = None


class IntegrationSummary(BaseModel):
    """Summary of a Home Assistant integration."""

    entry_id: str
    domain: str
    title: str
    state: str  # loaded, setup_error, etc.
    is_loaded: bool = True
    has_error: bool = False


class LogEntrySummary(BaseModel):
    """Summary of a log entry."""

    timestamp: str
    level: str
    source: str
    message: str


class HAOverview(BaseModel):
    """Overview of Home Assistant data for dashboard."""

    connection: HAConnectionStatus
    snapshot: dict[str, Any]
    domain_counts: dict[str, int] = Field(
        default_factory=dict, description="Count of entities per domain"
    )


class EntitiesResponse(BaseModel):
    """Response containing entities list."""

    entities: list[EntitySummary]
    total: int
    domains: list[str] = Field(default_factory=list)


class DevicesResponse(BaseModel):
    """Response containing devices list."""

    devices: list[DeviceSummary]
    total: int


class AreasResponse(BaseModel):
    """Response containing areas list."""

    areas: list[AreaSummary]
    total: int


class AutomationsResponse(BaseModel):
    """Response containing automations list."""

    automations: list[AutomationSummary]
    total: int


class IntegrationsResponse(BaseModel):
    """Response containing integrations list."""

    integrations: list[IntegrationSummary]
    total: int


class LogResponse(BaseModel):
    """Response containing log entries."""

    entries: list[LogEntrySummary]
    total: int


class ServiceCallRequest(BaseModel):
    """Request to call a Home Assistant service."""

    entity_id: str = Field(description="Entity ID to control")
    service: str = Field(description="Service to call (e.g., 'light.turn_on')")
    data: dict[str, Any] = Field(default_factory=dict, description="Service data")


class ServiceCallResponse(BaseModel):
    """Response from a service call."""

    success: bool
    service: str
    entity_id: str
    message: str


# =============================================================================
# Client Management
# =============================================================================

# Global client instance (lazy initialization)
_ha_client: HomeAssistantClient | None = None


async def get_ha_client() -> HomeAssistantClient | None:
    """Get or create the Home Assistant client."""
    global _ha_client

    settings = get_settings()

    # Check if HA is configured
    if not settings.homeassistant.url or not settings.homeassistant.token:
        return None

    # Create client if not exists
    if _ha_client is None:
        _ha_client = HomeAssistantClient(
            url=settings.homeassistant.url,
            token=settings.homeassistant.token,
            timeout=10.0,
            verify_ssl=settings.homeassistant.verify_ssl,
        )

    # Connect if not connected
    if not _ha_client.connected:
        try:
            await _ha_client.connect()
        except Exception as e:
            logger.error("Failed to connect to Home Assistant: %s", e)
            return _ha_client  # Return anyway for status check

    return _ha_client


async def close_ha_client() -> None:
    """Close the Home Assistant client."""
    global _ha_client
    if _ha_client:
        await _ha_client.close()
        _ha_client = None


# =============================================================================
# API Endpoints
# =============================================================================


@router.get("/status", response_model=HAConnectionStatus)
async def get_connection_status() -> HAConnectionStatus:
    """Get Home Assistant connection status.

    Returns current connection state, HA version, and any errors.
    """
    settings = get_settings()

    # Check if configured
    if not settings.homeassistant.url:
        return HAConnectionStatus(
            connected=False,
            url=None,
            error="Home Assistant URL not configured",
        )

    if not settings.homeassistant.token:
        return HAConnectionStatus(
            connected=False,
            url=settings.homeassistant.url,
            error="Home Assistant token not configured",
        )

    # Try to connect and get config
    client = await get_ha_client()
    if not client or not client.connected:
        return HAConnectionStatus(
            connected=False,
            url=settings.homeassistant.url,
            error="Unable to connect to Home Assistant",
        )

    # Get HA config for version info
    config = await client.get_config()
    if config:
        return HAConnectionStatus(
            connected=True,
            url=settings.homeassistant.url,
            version=config.get("version"),
            location_name=config.get("location_name"),
        )

    return HAConnectionStatus(
        connected=True,
        url=settings.homeassistant.url,
    )


@router.get("/overview", response_model=HAOverview)
async def get_overview() -> HAOverview:
    """Get complete Home Assistant overview for dashboard.

    Includes connection status, snapshot summary, and domain counts.
    """
    status = await get_connection_status()

    client = await get_ha_client()
    if not client or not client.connected:
        return HAOverview(
            connection=status,
            snapshot={},
            domain_counts={},
        )

    # Get domain counts from entity registry
    domain_counts: dict[str, int] = {}
    for entity in client.entities:
        domain_counts[entity.domain] = domain_counts.get(entity.domain, 0) + 1

    return HAOverview(
        connection=status,
        snapshot=client.snapshot.to_dict(),
        domain_counts=domain_counts,
    )


@router.post("/refresh")
async def refresh_all_data() -> dict[str, Any]:
    """Refresh all Home Assistant data.

    Reloads entities, devices, areas, automations, and integrations.
    """
    client = await get_ha_client()
    if not client or not client.connected:
        raise HTTPException(status_code=503, detail="Home Assistant not connected")

    # Refresh all data
    entities_count = await client.refresh_entities()
    devices_count = await client.refresh_devices()
    areas_count = await client.refresh_areas()
    automations_count = await client.refresh_automations()
    integrations_count = await client.refresh_integrations()

    return {
        "success": True,
        "refreshed": {
            "entities": entities_count,
            "devices": devices_count,
            "areas": areas_count,
            "automations": automations_count,
            "integrations": integrations_count,
        },
    }


@router.get("/entities", response_model=EntitiesResponse)
async def get_entities(
    domain: str | None = Query(None, description="Filter by domain (light, switch, etc.)"),
    area: str | None = Query(None, description="Filter by area ID"),
    search: str | None = Query(None, description="Search in entity name"),
    limit: int = Query(100, ge=1, le=500, description="Max entities to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
) -> EntitiesResponse:
    """Get Home Assistant entities.

    Supports filtering by domain, area, and search query.
    """
    client = await get_ha_client()
    if not client or not client.connected:
        return EntitiesResponse(entities=[], total=0, domains=[])

    # Get all entities
    all_entities = list(client.entities)

    # Apply filters
    filtered = all_entities

    if domain:
        filtered = [e for e in filtered if e.domain == domain]

    if area:
        filtered = [e for e in filtered if e.area_id == area]

    if search:
        filtered = [e for e in filtered if e.matches_name(search)]

    # Sort by domain then name
    filtered.sort(key=lambda e: (e.domain, e.friendly_name.lower()))

    # Get unique domains
    domains = sorted({e.domain for e in all_entities})

    # Pagination
    total = len(filtered)
    paginated = filtered[offset : offset + limit]

    # Build area lookup
    area_names = {a.id: a.name for a in client.areas.values()}

    # Convert to response model
    entity_summaries = []
    for e in paginated:
        state_str = ""
        last_changed = None
        attrs = {}
        is_on = None
        icon = None

        if e.state:
            state_str = e.state.state
            last_changed = e.state.last_changed
            attrs = e.state.attributes
            is_on = e.state.is_on if e.domain in ("light", "switch", "fan", "climate") else None
            icon = attrs.get("icon")

        entity_summaries.append(
            EntitySummary(
                entity_id=e.entity_id,
                domain=e.domain,
                friendly_name=e.friendly_name,
                state=state_str,
                device_class=e.device_class,
                area_id=e.area_id,
                area_name=area_names.get(e.area_id) if e.area_id else None,
                last_changed=last_changed,
                icon=icon,
                is_on=is_on,
                attributes=attrs,
            )
        )

    return EntitiesResponse(
        entities=entity_summaries,
        total=total,
        domains=domains,
    )


@router.get("/entities/{entity_id}", response_model=EntitySummary)
async def get_entity(entity_id: str) -> EntitySummary:
    """Get a specific entity by ID."""
    client = await get_ha_client()
    if not client or not client.connected:
        raise HTTPException(status_code=503, detail="Home Assistant not connected")

    entity = client.entities.get(entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail=f"Entity {entity_id} not found")

    area_names = {a.id: a.name for a in client.areas.values()}

    state_str = ""
    last_changed = None
    attrs = {}
    is_on = None
    icon = None

    if entity.state:
        state_str = entity.state.state
        last_changed = entity.state.last_changed
        attrs = entity.state.attributes
        is_on = entity.state.is_on if entity.domain in ("light", "switch", "fan") else None
        icon = attrs.get("icon")

    return EntitySummary(
        entity_id=entity.entity_id,
        domain=entity.domain,
        friendly_name=entity.friendly_name,
        state=state_str,
        device_class=entity.device_class,
        area_id=entity.area_id,
        area_name=area_names.get(entity.area_id) if entity.area_id else None,
        last_changed=last_changed,
        icon=icon,
        is_on=is_on,
        attributes=attrs,
    )


@router.get("/devices", response_model=DevicesResponse)
async def get_devices(
    area: str | None = Query(None, description="Filter by area ID"),
    search: str | None = Query(None, description="Search in device name"),
) -> DevicesResponse:
    """Get Home Assistant devices."""
    client = await get_ha_client()
    if not client or not client.connected:
        return DevicesResponse(devices=[], total=0)

    # Get devices
    devices = list(client.devices.values())

    # Apply filters
    if area:
        devices = [d for d in devices if d.area_id == area]

    if search:
        search_lower = search.lower()
        devices = [d for d in devices if search_lower in d.display_name.lower()]

    # Sort by name
    devices.sort(key=lambda d: d.display_name.lower())

    # Build area lookup and entity counts
    area_names = {a.id: a.name for a in client.areas.values()}

    # Entity count per device would require device_id mapping in entities
    # For now, return 0 as entity count
    entity_counts: dict[str, int] = {}

    # Convert to response model
    device_summaries = [
        DeviceSummary(
            id=d.id,
            name=d.display_name,
            manufacturer=d.manufacturer,
            model=d.model,
            area_id=d.area_id,
            area_name=area_names.get(d.area_id) if d.area_id else None,
            entity_count=entity_counts.get(d.id, 0),
            is_enabled=d.is_enabled,
        )
        for d in devices
    ]

    return DevicesResponse(devices=device_summaries, total=len(device_summaries))


@router.get("/areas", response_model=AreasResponse)
async def get_areas() -> AreasResponse:
    """Get Home Assistant areas (rooms/zones)."""
    client = await get_ha_client()
    if not client or not client.connected:
        return AreasResponse(areas=[], total=0)

    areas = list(client.areas.values())
    areas.sort(key=lambda a: a.name.lower())

    # Count devices and entities per area
    device_counts: dict[str, int] = {}
    entity_counts: dict[str, int] = {}

    for device in client.devices.values():
        if device.area_id:
            device_counts[device.area_id] = device_counts.get(device.area_id, 0) + 1

    for entity in client.entities:
        if entity.area_id:
            entity_counts[entity.area_id] = entity_counts.get(entity.area_id, 0) + 1

    area_summaries = [
        AreaSummary(
            id=a.id,
            name=a.name,
            icon=a.icon,
            floor_id=a.floor_id,
            device_count=device_counts.get(a.id, 0),
            entity_count=entity_counts.get(a.id, 0),
        )
        for a in areas
    ]

    return AreasResponse(areas=area_summaries, total=len(area_summaries))


@router.get("/automations", response_model=AutomationsResponse)
async def get_automations() -> AutomationsResponse:
    """Get Home Assistant automations."""
    client = await get_ha_client()
    if not client or not client.connected:
        return AutomationsResponse(automations=[], total=0)

    automations = list(client.automations.values())
    automations.sort(key=lambda a: a.name.lower())

    automation_summaries = [
        AutomationSummary(
            entity_id=a.entity_id,
            name=a.name,
            state=a.state.value,
            last_triggered=a.last_triggered.isoformat() if a.last_triggered else None,
            mode=a.mode,
            description=a.description,
        )
        for a in automations
    ]

    return AutomationsResponse(automations=automation_summaries, total=len(automation_summaries))


@router.get("/integrations", response_model=IntegrationsResponse)
async def get_integrations() -> IntegrationsResponse:
    """Get Home Assistant integrations."""
    client = await get_ha_client()
    if not client or not client.connected:
        return IntegrationsResponse(integrations=[], total=0)

    integrations = list(client.integrations.values())
    integrations.sort(key=lambda i: i.title.lower())

    integration_summaries = [
        IntegrationSummary(
            entry_id=i.entry_id,
            domain=i.domain,
            title=i.title,
            state=i.state,
            is_loaded=i.is_loaded,
            has_error=i.has_error,
        )
        for i in integrations
    ]

    return IntegrationsResponse(
        integrations=integration_summaries, total=len(integration_summaries)
    )


@router.get("/logs", response_model=LogResponse)
async def get_error_logs(
    level: str | None = Query(None, description="Filter by log level"),
    limit: int = Query(50, ge=1, le=200, description="Max entries to return"),
) -> LogResponse:
    """Get Home Assistant error logs."""
    client = await get_ha_client()
    if not client or not client.connected:
        return LogResponse(entries=[], total=0)

    # Fetch logs
    logs = await client.get_error_log()

    # Apply filter
    if level:
        level_upper = level.upper()
        logs = [log for log in logs if log.level.upper() == level_upper]

    # Limit results
    logs = logs[:limit]

    log_summaries = [
        LogEntrySummary(
            timestamp=log.timestamp.isoformat(),
            level=log.level,
            source=log.source,
            message=log.message,
        )
        for log in logs
    ]

    return LogResponse(entries=log_summaries, total=len(log_summaries))


@router.post("/services/call", response_model=ServiceCallResponse)
async def call_service(request: ServiceCallRequest) -> ServiceCallResponse:
    """Call a Home Assistant service.

    Execute a service like light.turn_on, switch.turn_off, etc.
    """
    client = await get_ha_client()
    if not client or not client.connected:
        raise HTTPException(status_code=503, detail="Home Assistant not connected")

    try:
        result = await client.call_service(
            request.service,
            entity_id=request.entity_id,
            **request.data,
        )
        return ServiceCallResponse(
            success=result.success,
            service=result.service,
            entity_id=result.entity_id or request.entity_id,
            message=result.message,
        )
    except Exception as e:
        logger.error("Service call failed: %s", e)
        return ServiceCallResponse(
            success=False,
            service=request.service,
            entity_id=request.entity_id,
            message=f"Service call failed: {e}",
        )


@router.post("/entities/{entity_id}/toggle", response_model=ServiceCallResponse)
async def toggle_entity(entity_id: str) -> ServiceCallResponse:
    """Toggle an entity on/off."""
    client = await get_ha_client()
    if not client or not client.connected:
        raise HTTPException(status_code=503, detail="Home Assistant not connected")

    entity = client.entities.get(entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail=f"Entity {entity_id} not found")

    # Determine service based on domain
    domain = entity.domain
    if domain not in ("light", "switch", "fan", "climate", "cover", "lock", "input_boolean"):
        raise HTTPException(
            status_code=400, detail=f"Entity domain '{domain}' does not support toggle"
        )

    # Use appropriate toggle service
    if domain in ("light", "switch", "fan", "input_boolean"):
        service = f"{domain}.toggle"
    elif domain == "cover":
        service = "cover.toggle"
    elif domain == "lock":
        # Locks use lock/unlock
        is_locked = entity.state and entity.state.state == "locked"
        service = "lock.unlock" if is_locked else "lock.lock"
    else:
        service = f"{domain}.toggle"

    try:
        result = await client.call_service(service, entity_id=entity_id)
        return ServiceCallResponse(
            success=result.success,
            service=service,
            entity_id=entity_id,
            message=result.message,
        )
    except Exception as e:
        return ServiceCallResponse(
            success=False,
            service=service,
            entity_id=entity_id,
            message=f"Toggle failed: {e}",
        )
