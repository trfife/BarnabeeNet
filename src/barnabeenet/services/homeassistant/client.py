"""Home Assistant API client.

Async client for communicating with Home Assistant's REST API.
Handles:
- Authentication via long-lived access token
- Service calls (turn_on, turn_off, etc.)
- State retrieval
- Entity discovery
- Device/Area/Automation/Integration registries
- Error log fetching
- Event subscriptions (via WebSocket in future)
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx

from barnabeenet.services.homeassistant.entities import Entity, EntityRegistry, EntityState
from barnabeenet.services.homeassistant.models import (
    Area,
    Automation,
    AutomationState,
    Device,
    HADataSnapshot,
    Integration,
    LogEntry,
)

logger = logging.getLogger(__name__)


@dataclass
class ServiceCallResult:
    """Result of a Home Assistant service call."""

    success: bool
    service: str
    entity_id: str | None
    message: str
    response_data: dict[str, Any] | None = None


class HomeAssistantClient:
    """Async client for Home Assistant REST API.

    Example:
        async with HomeAssistantClient(url, token) as client:
            # Check connection
            if await client.ping():
                # Get all light entities
                lights = await client.get_entities("light")

                # Turn on a light
                result = await client.call_service(
                    "light.turn_on",
                    entity_id="light.living_room",
                    brightness=255,
                )
    """

    def __init__(
        self,
        url: str,
        token: str,
        timeout: float = 10.0,
        verify_ssl: bool = True,
    ) -> None:
        """Initialize the Home Assistant client.

        Args:
            url: Home Assistant base URL (e.g., "http://homeassistant.local:8123")
            token: Long-lived access token for authentication
            timeout: Request timeout in seconds
            verify_ssl: Whether to verify SSL certificates
        """
        self._url = url.rstrip("/")
        self._token = token
        self._timeout = timeout
        self._verify_ssl = verify_ssl
        self._client: httpx.AsyncClient | None = None
        self._entity_registry: EntityRegistry = EntityRegistry()
        self._connected: bool = False

        # Extended registries
        self._devices: dict[str, Device] = {}
        self._areas: dict[str, Area] = {}
        self._automations: dict[str, Automation] = {}
        self._integrations: dict[str, Integration] = {}
        self._snapshot: HADataSnapshot = HADataSnapshot()

    @property
    def url(self) -> str:
        """Get the Home Assistant URL."""
        return self._url

    @property
    def connected(self) -> bool:
        """Check if client is connected."""
        return self._connected

    @property
    def entities(self) -> EntityRegistry:
        """Get the entity registry."""
        return self._entity_registry

    @property
    def devices(self) -> dict[str, Device]:
        """Get the device registry."""
        return self._devices

    @property
    def areas(self) -> dict[str, Area]:
        """Get the area registry."""
        return self._areas

    @property
    def automations(self) -> dict[str, Automation]:
        """Get the automations registry."""
        return self._automations

    @property
    def integrations(self) -> dict[str, Integration]:
        """Get the integrations registry."""
        return self._integrations

    @property
    def snapshot(self) -> HADataSnapshot:
        """Get the current data snapshot summary."""
        return self._snapshot

    async def __aenter__(self) -> HomeAssistantClient:
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Async context manager exit."""
        await self.close()

    async def connect(self) -> None:
        """Initialize the HTTP client and verify connection."""
        if self._client is not None:
            return

        self._client = httpx.AsyncClient(
            base_url=self._url,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json",
            },
            timeout=self._timeout,
            verify=self._verify_ssl,
        )

        # Verify connection
        if await self.ping():
            self._connected = True
            logger.info("Connected to Home Assistant at %s", self._url)

            # Load entity registry
            await self.refresh_entities()
        else:
            logger.warning("Failed to connect to Home Assistant at %s", self._url)

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
            self._connected = False
            logger.info("Disconnected from Home Assistant")

    async def ping(self) -> bool:
        """Check if Home Assistant is reachable.

        Returns:
            True if the API is accessible, False otherwise.
        """
        if not self._client:
            return False

        try:
            response = await self._client.get("/api/")
            return response.status_code == 200
        except httpx.RequestError as e:
            logger.warning("Home Assistant ping failed: %s", e)
            return False

    async def get_config(self) -> dict[str, Any] | None:
        """Get Home Assistant configuration.

        Returns:
            Configuration dict or None if request failed.
        """
        if not self._client:
            return None

        try:
            response = await self._client.get("/api/config")
            response.raise_for_status()
            return response.json()
        except httpx.RequestError as e:
            logger.error("Failed to get HA config: %s", e)
            return None

    async def refresh_entities(self) -> int:
        """Refresh the entity registry from Home Assistant.

        Returns:
            Number of entities loaded.
        """
        if not self._client:
            return 0

        try:
            response = await self._client.get("/api/states")
            response.raise_for_status()
            states = response.json()

            self._entity_registry.clear()
            for state_data in states:
                entity = self._parse_entity(state_data)
                self._entity_registry.add(entity)

            logger.info("Loaded %d entities from Home Assistant", len(self._entity_registry))
            self._snapshot.entities_count = len(self._entity_registry)
            self._snapshot.last_refresh["entities"] = datetime.now()
            return len(self._entity_registry)

        except httpx.RequestError as e:
            logger.error("Failed to refresh entities: %s", e)
            return 0

    async def refresh_devices(self) -> int:
        """Refresh the device registry from Home Assistant.

        Uses the internal config registry endpoint.
        Devices change infrequently - recommended to cache.

        Returns:
            Number of devices loaded.
        """
        if not self._client:
            return 0

        try:
            # Try the websocket-like endpoint (works on newer HA versions)
            response = await self._client.get("/api/config/device_registry")
            if response.status_code == 404:
                logger.warning("Device registry endpoint not available (HA version may be old)")
                return 0
            response.raise_for_status()
            devices_data = response.json()

            self._devices.clear()
            for device_data in devices_data:
                device = self._parse_device(device_data)
                self._devices[device.id] = device

            logger.info("Loaded %d devices from Home Assistant", len(self._devices))
            self._snapshot.devices_count = len(self._devices)
            self._snapshot.last_refresh["devices"] = datetime.now()
            return len(self._devices)

        except httpx.RequestError as e:
            logger.error("Failed to refresh devices: %s", e)
            return 0

    async def refresh_areas(self) -> int:
        """Refresh the area registry from Home Assistant.

        Areas (rooms/zones) change very infrequently.

        Returns:
            Number of areas loaded.
        """
        if not self._client:
            return 0

        try:
            response = await self._client.get("/api/config/area_registry")
            if response.status_code == 404:
                logger.warning("Area registry endpoint not available")
                return 0
            response.raise_for_status()
            areas_data = response.json()

            self._areas.clear()
            for area_data in areas_data:
                area = self._parse_area(area_data)
                self._areas[area.id] = area

            logger.info("Loaded %d areas from Home Assistant", len(self._areas))
            self._snapshot.areas_count = len(self._areas)
            self._snapshot.last_refresh["areas"] = datetime.now()
            return len(self._areas)

        except httpx.RequestError as e:
            logger.error("Failed to refresh areas: %s", e)
            return 0

    async def refresh_automations(self) -> int:
        """Refresh automations from Home Assistant states.

        Parses automation.* entities from the entity registry.

        Returns:
            Number of automations loaded.
        """
        if not self._client:
            return 0

        try:
            # Automations are exposed as entities with domain "automation"
            response = await self._client.get("/api/states")
            response.raise_for_status()
            states = response.json()

            self._automations.clear()
            for state_data in states:
                entity_id = state_data.get("entity_id", "")
                if entity_id.startswith("automation."):
                    automation = self._parse_automation(state_data)
                    self._automations[automation.entity_id] = automation

            logger.info("Loaded %d automations from Home Assistant", len(self._automations))
            self._snapshot.automations_count = len(self._automations)
            self._snapshot.last_refresh["automations"] = datetime.now()
            return len(self._automations)

        except httpx.RequestError as e:
            logger.error("Failed to refresh automations: %s", e)
            return 0

    async def refresh_integrations(self) -> int:
        """Refresh integrations (config entries) from Home Assistant.

        Returns:
            Number of integrations loaded.
        """
        if not self._client:
            return 0

        try:
            response = await self._client.get("/api/config/config_entries/entry")
            if response.status_code == 404:
                logger.warning("Config entries endpoint not available")
                return 0
            response.raise_for_status()
            entries_data = response.json()

            self._integrations.clear()
            for entry_data in entries_data:
                integration = self._parse_integration(entry_data)
                self._integrations[integration.entry_id] = integration

            logger.info("Loaded %d integrations from Home Assistant", len(self._integrations))
            self._snapshot.integrations_count = len(self._integrations)
            self._snapshot.last_refresh["integrations"] = datetime.now()
            return len(self._integrations)

        except httpx.RequestError as e:
            logger.error("Failed to refresh integrations: %s", e)
            return 0

    async def refresh_all(self) -> HADataSnapshot:
        """Refresh all registries from Home Assistant.

        Returns:
            HADataSnapshot with counts and timestamps.
        """
        await self.refresh_entities()
        await self.refresh_devices()
        await self.refresh_areas()
        await self.refresh_automations()
        await self.refresh_integrations()
        return self._snapshot

    async def get_error_log(self, max_lines: int = 500) -> list[LogEntry]:
        """Fetch the Home Assistant error log.

        Args:
            max_lines: Maximum number of log lines to return.

        Returns:
            List of parsed LogEntry objects.
        """
        if not self._client:
            return []

        try:
            response = await self._client.get("/api/error_log")
            response.raise_for_status()
            log_text = response.text

            entries = self._parse_error_log(log_text, max_lines)
            logger.info("Fetched %d log entries from Home Assistant", len(entries))
            return entries

        except httpx.RequestError as e:
            logger.error("Failed to fetch error log: %s", e)
            return []

    def _parse_device(self, device_data: dict[str, Any]) -> Device:
        """Parse device data from HA device registry."""
        return Device(
            id=device_data.get("id", ""),
            name=device_data.get("name"),
            manufacturer=device_data.get("manufacturer"),
            model=device_data.get("model"),
            sw_version=device_data.get("sw_version"),
            hw_version=device_data.get("hw_version"),
            area_id=device_data.get("area_id"),
            config_entry_ids=device_data.get("config_entries", []),
            identifiers=[
                tuple(i)
                for i in device_data.get("identifiers", [])
                if isinstance(i, (list, tuple)) and len(i) == 2
            ],
            connections=[
                tuple(c)
                for c in device_data.get("connections", [])
                if isinstance(c, (list, tuple)) and len(c) == 2
            ],
            via_device_id=device_data.get("via_device_id"),
            disabled_by=device_data.get("disabled_by"),
        )

    def _parse_area(self, area_data: dict[str, Any]) -> Area:
        """Parse area data from HA area registry."""
        return Area(
            id=area_data.get("area_id", area_data.get("id", "")),
            name=area_data.get("name", ""),
            picture=area_data.get("picture"),
            aliases=area_data.get("aliases", []),
            floor_id=area_data.get("floor_id"),
            icon=area_data.get("icon"),
            labels=area_data.get("labels", []),
        )

    def _parse_automation(self, state_data: dict[str, Any]) -> Automation:
        """Parse automation from HA state data."""
        attributes = state_data.get("attributes", {})
        state_str = state_data.get("state", "unavailable")

        # Parse last_triggered timestamp
        last_triggered = None
        last_triggered_str = attributes.get("last_triggered")
        if last_triggered_str:
            try:
                last_triggered = datetime.fromisoformat(last_triggered_str.replace("Z", "+00:00"))
            except ValueError:
                pass

        return Automation(
            entity_id=state_data.get("entity_id", ""),
            name=attributes.get("friendly_name", state_data.get("entity_id", "")),
            state=AutomationState(state_str)
            if state_str in ("on", "off")
            else AutomationState.UNAVAILABLE,
            last_triggered=last_triggered,
            mode=attributes.get("mode", "single"),
            current_activity=attributes.get("current", 0),
            max_activity=attributes.get("max"),
            description=attributes.get("description"),
            icon=attributes.get("icon"),
        )

    def _parse_integration(self, entry_data: dict[str, Any]) -> Integration:
        """Parse integration from HA config entry data."""
        return Integration(
            entry_id=entry_data.get("entry_id", ""),
            domain=entry_data.get("domain", ""),
            title=entry_data.get("title", ""),
            state=entry_data.get("state", "unknown"),
            version=entry_data.get("version", 1),
            source=entry_data.get("source", "user"),
            disabled_by=entry_data.get("disabled_by"),
            supports_options=entry_data.get("supports_options", False),
            supports_remove_device=entry_data.get("supports_remove_device", False),
            supports_unload=entry_data.get("supports_unload", False),
            supports_reconfigure=entry_data.get("supports_reconfigure", False),
            pref_disable_new_entities=entry_data.get("pref_disable_new_entities", False),
            pref_disable_polling=entry_data.get("pref_disable_polling", False),
        )

    def _parse_error_log(self, log_text: str, max_lines: int) -> list[LogEntry]:
        """Parse Home Assistant error log text into LogEntry objects."""
        entries: list[LogEntry] = []

        # HA log format: "YYYY-MM-DD HH:MM:SS.mmm LEVEL (source) [logger.name] message"
        # or simpler: "YYYY-MM-DD HH:MM:SS LEVEL logger.name: message"
        log_pattern = re.compile(
            r"^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})(?:\.\d+)?\s+"
            r"(DEBUG|INFO|WARNING|ERROR|CRITICAL)\s+"
            r"(?:\(([^)]+)\)\s+)?(?:\[([^\]]+)\]\s+)?(.+)$",
            re.MULTILINE,
        )

        for match in log_pattern.finditer(log_text):
            timestamp_str, level, source1, source2, message = match.groups()
            source = source1 or source2 or "unknown"

            try:
                timestamp = datetime.fromisoformat(timestamp_str)
            except ValueError:
                timestamp = datetime.now()

            entries.append(
                LogEntry(
                    timestamp=timestamp,
                    level=level,
                    source=source,
                    message=message.strip(),
                )
            )

            if len(entries) >= max_lines:
                break

        return entries

    def get_device(self, device_id: str) -> Device | None:
        """Get a device by ID."""
        return self._devices.get(device_id)

    def get_area(self, area_id: str) -> Area | None:
        """Get an area by ID."""
        return self._areas.get(area_id)

    def get_automation(self, entity_id: str) -> Automation | None:
        """Get an automation by entity_id."""
        if not entity_id.startswith("automation."):
            entity_id = f"automation.{entity_id}"
        return self._automations.get(entity_id)

    def get_integration(self, entry_id: str) -> Integration | None:
        """Get an integration by entry ID."""
        return self._integrations.get(entry_id)

    def find_area_by_name(self, name: str) -> Area | None:
        """Find an area by name (case-insensitive)."""
        for area in self._areas.values():
            if area.matches_name(name):
                return area
        return None

    def get_devices_in_area(self, area_id: str) -> list[Device]:
        """Get all devices in a specific area."""
        return [d for d in self._devices.values() if d.area_id == area_id]

    def get_entities_in_area(self, area_id: str) -> list[Entity]:
        """Get all entities in a specific area."""
        return self._entity_registry.get_by_area(area_id)

    async def get_state(self, entity_id: str) -> EntityState | None:
        """Get the current state of an entity.

        Args:
            entity_id: The entity ID (e.g., "light.living_room")

        Returns:
            EntityState or None if not found.
        """
        if not self._client:
            return None

        try:
            response = await self._client.get(f"/api/states/{entity_id}")
            if response.status_code == 404:
                return None
            response.raise_for_status()
            data = response.json()
            return EntityState(
                state=data.get("state", "unknown"),
                attributes=data.get("attributes", {}),
                last_changed=data.get("last_changed"),
                last_updated=data.get("last_updated"),
            )
        except httpx.RequestError as e:
            logger.error("Failed to get state for %s: %s", entity_id, e)
            return None

    async def call_service(
        self,
        service: str,
        entity_id: str | None = None,
        **service_data: Any,
    ) -> ServiceCallResult:
        """Call a Home Assistant service.

        Args:
            service: Service name in format "domain.service" (e.g., "light.turn_on")
            entity_id: Target entity ID (optional for some services)
            **service_data: Additional service data (e.g., brightness=255)

        Returns:
            ServiceCallResult with success status and details.
        """
        if not self._client:
            return ServiceCallResult(
                success=False,
                service=service,
                entity_id=entity_id,
                message="Client not connected",
            )

        try:
            # Parse domain and service name
            if "." not in service:
                return ServiceCallResult(
                    success=False,
                    service=service,
                    entity_id=entity_id,
                    message=f"Invalid service format: {service}. Expected 'domain.service'",
                )

            domain, service_name = service.split(".", 1)

            # Build request data
            data: dict[str, Any] = dict(service_data)
            if entity_id:
                data["entity_id"] = entity_id

            # Make the API call
            response = await self._client.post(
                f"/api/services/{domain}/{service_name}",
                json=data,
            )
            response.raise_for_status()

            # HA returns array of affected states
            affected_states = response.json()

            logger.info(
                "Service call %s on %s successful, affected %d entities",
                service,
                entity_id or "all",
                len(affected_states) if affected_states else 0,
            )

            return ServiceCallResult(
                success=True,
                service=service,
                entity_id=entity_id,
                message="Service call successful",
                response_data={"affected_states": affected_states},
            )

        except httpx.HTTPStatusError as e:
            logger.error("Service call failed with status %d: %s", e.response.status_code, e)
            return ServiceCallResult(
                success=False,
                service=service,
                entity_id=entity_id,
                message=f"HTTP error: {e.response.status_code}",
            )
        except httpx.RequestError as e:
            logger.error("Service call failed: %s", e)
            return ServiceCallResult(
                success=False,
                service=service,
                entity_id=entity_id,
                message=f"Request error: {e}",
            )

    async def get_entities(self, domain: str | None = None) -> list[Entity]:
        """Get entities, optionally filtered by domain.

        Args:
            domain: Optional domain filter (e.g., "light", "switch")

        Returns:
            List of matching entities.
        """
        if domain:
            return self._entity_registry.get_by_domain(domain)
        return list(self._entity_registry.all())

    def resolve_entity(self, name: str, domain: str | None = None) -> Entity | None:
        """Resolve a friendly name to an entity.

        Args:
            name: Friendly name or entity_id to resolve
            domain: Optional domain hint to narrow search

        Returns:
            Matching Entity or None.
        """
        return self._entity_registry.find_by_name(name, domain)

    def _parse_entity(self, state_data: dict[str, Any]) -> Entity:
        """Parse entity data from HA state response."""
        entity_id = state_data.get("entity_id", "")
        attributes = state_data.get("attributes", {})

        # Extract domain from entity_id
        domain = entity_id.split(".")[0] if "." in entity_id else "unknown"

        return Entity(
            entity_id=entity_id,
            domain=domain,
            friendly_name=attributes.get("friendly_name", entity_id),
            device_class=attributes.get("device_class"),
            area_id=attributes.get("area_id"),
            state=EntityState(
                state=state_data.get("state", "unknown"),
                attributes=attributes,
                last_changed=state_data.get("last_changed"),
                last_updated=state_data.get("last_updated"),
            ),
        )
