"""Home Assistant API client.

Async client for communicating with Home Assistant's REST API and WebSocket API.
Handles:
- Authentication via long-lived access token
- Service calls (turn_on, turn_off, etc.)
- State retrieval
- Entity discovery
- Device/Area/Automation/Integration registries (via WebSocket)
- Error log fetching
- Event subscriptions (via WebSocket)
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx
import websockets
from websockets.exceptions import WebSocketException

from barnabeenet.services.homeassistant.entities import Entity, EntityRegistry, EntityState
from barnabeenet.services.homeassistant.models import (
    Area,
    Automation,
    AutomationState,
    Device,
    HADataSnapshot,
    Integration,
    LogEntry,
    StateChangeEvent,
)

logger = logging.getLogger(__name__)


class HAAuthenticationError(Exception):
    """Raised when Home Assistant authentication fails (invalid token)."""

    pass


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

        # Event subscription state
        self._state_changes: deque[StateChangeEvent] = deque(maxlen=500)  # Rolling buffer
        self._event_task: asyncio.Task[None] | None = None
        self._event_callbacks: list[Callable[[StateChangeEvent], None]] = []
        self._ws_connected: bool = False

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

    @property
    def state_changes(self) -> list[StateChangeEvent]:
        """Get recent state change events (newest first)."""
        return list(self._state_changes)

    @property
    def is_subscribed(self) -> bool:
        """Check if subscribed to state change events."""
        return self._ws_connected and self._event_task is not None

    def add_state_change_callback(self, callback: Callable[[StateChangeEvent], None]) -> None:
        """Add a callback to be called when state changes occur."""
        self._event_callbacks.append(callback)

    def remove_state_change_callback(self, callback: Callable[[StateChangeEvent], None]) -> None:
        """Remove a state change callback."""
        if callback in self._event_callbacks:
            self._event_callbacks.remove(callback)

    async def __aenter__(self) -> HomeAssistantClient:
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Async context manager exit."""
        await self.close()

    async def connect(self) -> None:
        """Initialize the HTTP client and verify connection."""
        # If client exists but token changed, recreate it
        if self._client is not None:
            # Check if token needs updating
            try:
                from barnabeenet.api.routes.homeassistant import _ha_config_cache
                from barnabeenet.config import get_settings

                settings = get_settings()
                cached_token = _ha_config_cache.get("token")
                settings_token = settings.homeassistant.token
                new_token = cached_token or settings_token

                if new_token and new_token != self._token:
                    logger.info("Token changed, recreating HTTP client")
                    await self._client.aclose()
                    self._client = None
                    self._token = new_token
            except Exception:
                pass  # Continue with existing client if we can't check

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

            # Don't auto-load all entities - use just-in-time loading via HAContextService
            # Only load lightweight metadata (devices, areas) which change infrequently
            # Entity states are loaded just-in-time when agents need them
            try:
                await self.refresh_devices()  # Lightweight, changes infrequently
                await self.refresh_areas()  # Lightweight, changes infrequently
            except Exception as e:
                logger.debug("Could not refresh devices/areas on connect: %s", e)

            # Start event subscription for real-time updates
            await self.subscribe_to_events()
        else:
            logger.warning("Failed to connect to Home Assistant at %s", self._url)

    async def close(self) -> None:
        """Close the HTTP client and event subscription."""
        # Stop event subscription
        await self.unsubscribe_from_events()

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
            is_ok = response.status_code == 200
            if is_ok and not self._connected:
                self._connected = True
                logger.info("Home Assistant connection restored")
            elif not is_ok and self._connected:
                self._connected = False
                logger.warning("Home Assistant returned status %d", response.status_code)
            return is_ok
        except httpx.RequestError as e:
            if self._connected:
                self._connected = False
                logger.warning("Home Assistant connection lost: %s", e)
            return False

    async def ensure_connected(self) -> bool:
        """Verify connection is alive and reconnect if needed.

        Returns:
            True if connected (or successfully reconnected), False otherwise.
        """
        # Quick check - if we think we're connected, verify with ping
        if self._connected:
            if await self.ping():
                return True
            # Ping failed, mark disconnected
            self._connected = False
            logger.warning("Home Assistant connection stale, attempting reconnect...")

        # Try to refresh token from config before reconnecting
        # This handles the case where the token was updated in Redis but the client wasn't recreated
        try:
            from barnabeenet.api.routes.homeassistant import _ha_config_cache
            from barnabeenet.config import get_settings

            settings = get_settings()

            # Check if there's a newer token in cache or settings
            cached_token = _ha_config_cache.get("token")
            settings_token = settings.homeassistant.token

            # Use cached token if available, otherwise settings token
            new_token = cached_token or settings_token

            # If we have a new token and it's different, update it
            if new_token and new_token != self._token:
                logger.info("Updating HA token from config cache")
                self._token = new_token
        except Exception as e:
            logger.debug("Could not refresh token from config: %s", e)
            # Continue with existing token

        # Try to reconnect
        try:
            # Close existing client if any
            if self._client:
                await self._client.aclose()
                self._client = None

            # Reinitialize with potentially updated token
            await self.connect()
            return self._connected
        except Exception as e:
            logger.error("Home Assistant reconnection failed: %s", e)
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

        Loads entity states from REST API and enriches with entity registry
        data (including area_id) from WebSocket API.

        Returns:
            Number of entities loaded.
        """
        if not self._client:
            return 0

        try:
            # Get entity states from REST API
            response = await self._client.get("/api/states")
            response.raise_for_status()
            states = response.json()

            # Try to get entity registry from WebSocket for area assignments
            entity_registry_data = await self._ws_command("config/entity_registry/list")
            entity_registry_map: dict[str, dict[str, Any]] = {}
            if entity_registry_data:
                for entry in entity_registry_data:
                    entity_id = entry.get("entity_id")
                    if entity_id:
                        entity_registry_map[entity_id] = entry
                logger.debug(
                    "Loaded %d entity registry entries via WebSocket", len(entity_registry_map)
                )

            self._entity_registry.clear()
            for state_data in states:
                entity = self._parse_entity(state_data)

                # Enrich with entity registry data (area_id, device_id, etc.)
                entity_id = state_data.get("entity_id", "")
                if entity_id in entity_registry_map:
                    registry_entry = entity_registry_map[entity_id]
                    entity.area_id = registry_entry.get("area_id")
                    entity.device_id = registry_entry.get("device_id")

                self._entity_registry.add(entity)

            logger.info("Loaded %d entities from Home Assistant", len(self._entity_registry))
            self._snapshot.entities_count = len(self._entity_registry)
            self._snapshot.last_refresh["entities"] = datetime.now()
            return len(self._entity_registry)

        except httpx.RequestError as e:
            logger.error("Failed to refresh entities: %s", e)
            return 0

    async def _ws_command(self, command_type: str) -> list[dict[str, Any]] | None:
        """Execute a WebSocket command and return the result.

        Home Assistant's WebSocket API flow:
        1. Connect to ws://host:port/api/websocket
        2. Receive {"type": "auth_required"}
        3. Send {"type": "auth", "access_token": "token"}
        4. Receive {"type": "auth_ok"} or {"type": "auth_invalid"}
        5. Send command with {"id": 1, "type": "command_type"}
        6. Receive {"id": 1, "type": "result", "success": true, "result": [...]}

        Args:
            command_type: The WebSocket command type (e.g., "config/device_registry/list")

        Returns:
            List of results or None if failed.
        """
        # Convert HTTP URL to WebSocket URL
        ws_url = self._url.replace("http://", "ws://").replace("https://", "wss://")
        ws_url = f"{ws_url}/api/websocket"

        try:
            async with websockets.connect(ws_url) as ws:
                # Step 1: Wait for auth_required
                msg = json.loads(await ws.recv())
                if msg.get("type") != "auth_required":
                    logger.error("Unexpected WebSocket message: %s", msg)
                    return None

                # Step 2: Send auth
                await ws.send(json.dumps({"type": "auth", "access_token": self._token}))

                # Step 3: Wait for auth response
                msg = json.loads(await ws.recv())
                if msg.get("type") == "auth_invalid":
                    logger.error("WebSocket auth failed: %s", msg.get("message"))
                    return None
                if msg.get("type") != "auth_ok":
                    logger.error("Unexpected auth response: %s", msg)
                    return None

                logger.debug("WebSocket authenticated successfully")

                # Step 4: Send command
                await ws.send(json.dumps({"id": 1, "type": command_type}))

                # Step 5: Wait for result
                msg = json.loads(await ws.recv())
                if msg.get("type") == "result" and msg.get("success"):
                    return msg.get("result", [])
                else:
                    logger.error("WebSocket command failed: %s", msg)
                    return None

        except WebSocketException as e:
            logger.warning("WebSocket error for %s: %s", command_type, e)
            return None
        except Exception as e:
            logger.warning("WebSocket connection failed for %s: %s", command_type, e)
            return None

    async def refresh_devices(self) -> int:
        """Refresh the device registry from Home Assistant.

        Uses WebSocket API (preferred) with REST fallback.
        Devices change infrequently - recommended to cache.

        Returns:
            Number of devices loaded.
        """
        # Try WebSocket API first (required for newer HA versions)
        devices_data = await self._ws_command("config/device_registry/list")

        if devices_data is None and self._client:
            # Fallback to REST API (may work on older HA versions)
            try:
                response = await self._client.get("/api/config/device_registry")
                if response.status_code == 200:
                    devices_data = response.json()
            except httpx.RequestError:
                pass

        if devices_data is None:
            logger.warning("Device registry not available via WebSocket or REST API")
            return 0

        self._devices.clear()
        for device_data in devices_data:
            device = self._parse_device(device_data)
            self._devices[device.id] = device

        logger.info("Loaded %d devices from Home Assistant", len(self._devices))
        self._snapshot.devices_count = len(self._devices)
        self._snapshot.last_refresh["devices"] = datetime.now()
        return len(self._devices)

    async def refresh_areas(self) -> int:
        """Refresh the area registry from Home Assistant.

        Uses WebSocket API (preferred) with REST fallback.
        Areas (rooms/zones) change very infrequently.

        Returns:
            Number of areas loaded.
        """
        # Try WebSocket API first (required for newer HA versions)
        areas_data = await self._ws_command("config/area_registry/list")

        if areas_data is None and self._client:
            # Fallback to REST API (may work on older HA versions)
            try:
                response = await self._client.get("/api/config/area_registry")
                if response.status_code == 200:
                    areas_data = response.json()
            except httpx.RequestError:
                pass

        if areas_data is None:
            logger.warning("Area registry not available via WebSocket or REST API")
            return 0

        self._areas.clear()
        for area_data in areas_data:
            area = self._parse_area(area_data)
            self._areas[area.id] = area

        logger.info("Loaded %d areas from Home Assistant", len(self._areas))
        self._snapshot.areas_count = len(self._areas)
        self._snapshot.last_refresh["areas"] = datetime.now()
        return len(self._areas)

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

        except (httpx.RequestError, httpx.HTTPStatusError) as e:
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
        target: dict[str, Any] | None = None,
        **service_data: Any,
    ) -> ServiceCallResult:
        """Call a Home Assistant service.

        Args:
            service: Service name in format "domain.service" (e.g., "light.turn_on")
            entity_id: Target entity ID (optional for some services)
            target: Target specification with floor_id, area_id, or entity_id arrays
                    e.g., {"floor_id": ["first_floor", "second_floor"]}
                    or {"area_id": ["living_room", "kitchen"]}
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

            # Support HA's target parameter for floor/area/entity targeting
            # The REST API expects target keys at the root level, not nested in "target"
            if target:
                # Merge target keys directly into data
                # HA REST API expects: {"floor_id": [...]} or {"area_id": [...]} at root
                data.update(target)
            elif entity_id:
                data["entity_id"] = entity_id

            # Make the API call
            response = await self._client.post(
                f"/api/services/{domain}/{service_name}",
                json=data,
            )
            response.raise_for_status()

            # HA returns array of affected states
            affected_states = response.json()

            # Build description of what was targeted
            target_desc = entity_id or "all"
            if target:
                if "floor_id" in target:
                    target_desc = f"floors: {target['floor_id']}"
                elif "area_id" in target:
                    target_desc = f"areas: {target['area_id']}"

            logger.info(
                "Service call %s on %s successful, affected %d entities",
                service,
                target_desc,
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
            # Mark disconnected on auth errors
            if e.response.status_code in (401, 403):
                self._connected = False
                logger.warning("HA authentication failed - marking disconnected")
            return ServiceCallResult(
                success=False,
                service=service,
                entity_id=entity_id,
                message=f"HTTP error: {e.response.status_code}",
            )
        except httpx.RequestError as e:
            # Network error - mark connection as failed
            self._connected = False
            logger.error("Service call failed (connection lost): %s", e)
            return ServiceCallResult(
                success=False,
                service=service,
                entity_id=entity_id,
                message=f"Connection error: {e}",
            )

    async def get_person_entity_details(self, person_entity_id: str) -> dict[str, Any] | None:
        """Get detailed information about a person entity including linked devices and entities.

        Args:
            person_entity_id: The person entity ID (e.g., "person.thom")

        Returns:
            Dict with person details including:
            - state: Current state (home, not_home, zone name)
            - attributes: All person entity attributes
            - device_trackers: List of device tracker entities
            - linked_devices: List of devices linked to this person
            - linked_entities: List of entities from linked devices (notifications, alarms, etc.)
            - location: Location info (latitude, longitude, zone)
            - address: Home address if available from zone
        """
        if not self._client:
            return None

        try:
            # Get person entity state
            state = await self.get_state(person_entity_id)
            if not state:
                return None

            attrs = state.attributes or {}
            result = {
                "state": state.state,
                "attributes": attrs,
                "device_trackers": attrs.get("device_trackers", []),
                "linked_devices": [],
                "linked_entities": [],
                "location": {
                    "latitude": attrs.get("latitude"),
                    "longitude": attrs.get("longitude"),
                    "gps_accuracy": attrs.get("gps_accuracy"),
                    "source": attrs.get("source"),
                },
                "address": None,
            }

            # Get device trackers and find their devices
            device_trackers = attrs.get("device_trackers", [])
            for tracker_id in device_trackers:
                tracker_entity = self._entity_registry.get(tracker_id)
                if tracker_entity and tracker_entity.device_id:
                    # Find device
                    device = self._devices.get(tracker_entity.device_id)
                    if device and device.id not in result["linked_devices"]:
                        result["linked_devices"].append(device.id)

                        # Get all entities for this device
                        device_entities = [
                            e for e in self._entity_registry.get_all()
                            if e.device_id == device.id
                        ]
                        for entity in device_entities:
                            entity_info = {
                                "entity_id": entity.entity_id,
                                "domain": entity.domain,
                                "friendly_name": entity.friendly_name,
                                "state": entity.state.state if entity.state else None,
                            }
                            if entity_info not in result["linked_entities"]:
                                result["linked_entities"].append(entity_info)

            # Always try to get home address from zone (regardless of person's current location)
            # This allows answering "where is [person]" even when they're away
            home_zone = await self.get_state("zone.home")
            if home_zone and home_zone.attributes:
                result["address"] = {
                    "latitude": home_zone.attributes.get("latitude"),
                    "longitude": home_zone.attributes.get("longitude"),
                    "radius": home_zone.attributes.get("radius"),
                    "name": home_zone.attributes.get("friendly_name") or "Home",
                }
                # Try to get formatted address if available in zone attributes
                if "address" in home_zone.attributes:
                    result["address"]["formatted"] = home_zone.attributes.get("address")

            return result
        except Exception as e:
            logger.warning(f"Failed to get person entity details for {person_entity_id}: {e}")
            return None

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

        Uses just-in-time loading: EntityRegistry is populated with metadata (no states)
        by HAContextService. State is loaded just-in-time when entity is accessed.

        Args:
            name: Friendly name or entity_id to resolve
            domain: Optional domain hint to narrow search

        Returns:
            Matching Entity or None.
        """
        # EntityRegistry is populated by HAContextService with metadata (no states)
        # This allows fast resolution without loading all states upfront
        entity = self._entity_registry.find_by_name(name, domain)

        # If entity found but state is placeholder, state will be loaded just-in-time when needed
        # For now, return entity (state can be loaded via load_entity_state() if needed)
        return entity

    async def resolve_entity_async(self, name: str, domain: str | None = None) -> Entity | None:
        """Resolve a friendly name to an entity (async version with metadata refresh).

        Ensures entity metadata is refreshed before attempting resolution.
        This is important for timer actions and other background operations where
        the entity registry might be empty or stale.

        Args:
            name: Friendly name or entity_id to resolve
            domain: Optional domain hint to narrow search

        Returns:
            Matching Entity or None.
        """
        # First try with existing registry
        entity = self._entity_registry.find_by_name(name, domain)
        if entity:
            return entity

        # If not found, refresh metadata to ensure we have the latest entity list
        # This addresses the performance optimization issue where entity registry
        # might be empty or stale, preventing proper entity resolution
        # Always refresh if entity not found - the registry might be stale even if it has entities
        try:
            from barnabeenet.services.homeassistant.context import get_ha_context_service

            context_service = await get_ha_context_service(self)
            entities_before = len(context_service._entity_metadata)
            registry_size = len(self._entity_registry.all())
            
            # Force refresh to get latest entities from HA
            await context_service.refresh_metadata(force=True)
            entities_after = len(context_service._entity_metadata)
            
            logger.info(
                "Refreshed entity metadata for resolution: %d -> %d entities (registry had %d, searching for '%s')",
                entities_before,
                entities_after,
                registry_size,
                name
            )
        except Exception as e:
            logger.warning("Could not refresh metadata for entity resolution: %s", e)

        # Try again after refresh
        entity = self._entity_registry.find_by_name(name, domain)
        if entity:
            logger.debug("Resolved '%s' to %s after metadata refresh", name, entity.entity_id)
        else:
            logger.debug("Could not resolve '%s' (domain: %s) even after metadata refresh", name, domain)
        return entity

    async def load_entity_state(self, entity_id: str) -> EntityState | None:
        """Load entity state just-in-time.

        Args:
            entity_id: Entity ID to load state for

        Returns:
            EntityState or None if not found
        """
        if not self._client:
            return None

        try:
            response = await self._client.get(f"/api/states/{entity_id}")
            if response.status_code == 200:
                state_data = response.json()
                from barnabeenet.services.homeassistant.entities import EntityState
                return EntityState(
                    state=state_data.get("state", "unknown"),
                    attributes=state_data.get("attributes", {}),
                    last_changed=state_data.get("last_changed"),
                    last_updated=state_data.get("last_updated"),
                )
        except Exception as e:
            logger.debug("Failed to load state for %s: %s", entity_id, e)

        return None

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

    # =========================================================================
    # Event Subscription (WebSocket)
    # =========================================================================

    async def subscribe_to_events(self) -> None:
        """Start subscribing to Home Assistant state change events via WebSocket.

        Creates a background task that maintains a persistent WebSocket connection
        and receives real-time state change notifications.
        """
        if self._event_task is not None:
            logger.debug("Already subscribed to events")
            return

        self._event_task = asyncio.create_task(self._event_subscription_loop())
        logger.info("Started Home Assistant event subscription")

    async def unsubscribe_from_events(self) -> None:
        """Stop subscribing to Home Assistant events."""
        if self._event_task is not None:
            self._event_task.cancel()
            try:
                await self._event_task
            except asyncio.CancelledError:
                pass
            self._event_task = None
            self._ws_connected = False
            logger.info("Stopped Home Assistant event subscription")

    def update_token(self, new_token: str) -> None:
        """Update the access token (used when token is refreshed via dashboard)."""
        self._token = new_token
        logger.info("HA access token updated")

    async def reconnect_events(self) -> None:
        """Reconnect event subscription (call after updating token)."""
        await self.unsubscribe_from_events()
        await self.subscribe_to_events()

    async def _event_subscription_loop(self) -> None:
        """Background task that maintains WebSocket connection for events."""
        reconnect_delay = 5  # seconds between reconnection attempts
        max_reconnect_delay = 60
        auth_failures = 0
        max_auth_failures = 3  # Stop after this many consecutive auth failures

        while True:
            try:
                await self._run_event_subscription()
                # Reset auth failures on successful connection
                auth_failures = 0
                reconnect_delay = 5
            except asyncio.CancelledError:
                logger.info("Event subscription cancelled")
                break
            except HAAuthenticationError as e:
                auth_failures += 1
                logger.error(
                    "HA WebSocket auth failed (%d/%d): %s - token may be invalid or expired",
                    auth_failures,
                    max_auth_failures,
                    e,
                )
                self._ws_connected = False
                if auth_failures >= max_auth_failures:
                    logger.error(
                        "HA WebSocket auth failed %d times - stopping reconnection. "
                        "Please update the HA token in Configuration.",
                        auth_failures,
                    )
                    break
            except Exception as e:
                logger.error("Event subscription error: %s", e)
                self._ws_connected = False

            # Exponential backoff on reconnect
            logger.info("Reconnecting to HA WebSocket in %d seconds...", reconnect_delay)
            await asyncio.sleep(reconnect_delay)
            reconnect_delay = min(reconnect_delay * 2, max_reconnect_delay)

    async def _run_event_subscription(self) -> None:
        """Run the WebSocket event subscription."""
        # Build WebSocket URL
        ws_url = self._url.replace("http://", "ws://").replace("https://", "wss://")
        ws_url = f"{ws_url}/api/websocket"

        logger.debug("Connecting to HA WebSocket at %s", ws_url)

        async with websockets.connect(ws_url) as ws:
            # Step 1: Receive auth_required
            msg = json.loads(await ws.recv())
            if msg.get("type") != "auth_required":
                raise RuntimeError(f"Expected auth_required, got: {msg.get('type')}")

            # Step 2: Send auth
            await ws.send(json.dumps({"type": "auth", "access_token": self._token}))

            # Step 3: Receive auth result
            msg = json.loads(await ws.recv())
            if msg.get("type") == "auth_invalid":
                raise HAAuthenticationError(msg.get("message", "Invalid access token"))
            if msg.get("type") != "auth_ok":
                raise RuntimeError(f"Auth failed: {msg}")

            logger.info("WebSocket authenticated with Home Assistant")

            # Step 4: Subscribe to state_changed events
            await ws.send(
                json.dumps({"id": 1, "type": "subscribe_events", "event_type": "state_changed"})
            )

            # Step 5: Receive subscription confirmation
            msg = json.loads(await ws.recv())
            if not msg.get("success"):
                raise RuntimeError(f"Failed to subscribe to events: {msg}")

            logger.info("Subscribed to Home Assistant state_changed events")
            self._ws_connected = True

            # Step 6: Listen for events
            async for raw_msg in ws:
                try:
                    msg = json.loads(raw_msg)
                    if msg.get("type") == "event":
                        event_data = msg.get("event", {})
                        if event_data.get("event_type") == "state_changed":
                            await self._handle_state_change(event_data.get("data", {}))
                except json.JSONDecodeError:
                    logger.warning("Invalid JSON from WebSocket: %s", raw_msg[:100])
                except Exception as e:
                    logger.warning("Error processing event: %s", e)

    async def _handle_state_change(self, data: dict[str, Any]) -> None:
        """Process a state_changed event from Home Assistant."""
        from barnabeenet.services.activity_log import ActivityType, log_activity

        entity_id = data.get("entity_id", "")
        old_state = data.get("old_state") or {}
        new_state = data.get("new_state") or {}

        # Skip unavailable/unknown transitions that aren't meaningful
        old_value = old_state.get("state")
        new_value = new_state.get("state")

        # Create state change event
        event = StateChangeEvent(
            entity_id=entity_id,
            old_state=old_value,
            new_state=new_value,
            timestamp=datetime.now(),
            old_attributes=old_state.get("attributes", {}),
            new_attributes=new_state.get("attributes", {}),
        )

        # Add to rolling buffer
        self._state_changes.appendleft(event)

        # Update entity state in registry if we have it
        entity = self._entity_registry.get(entity_id)
        if entity and new_state:
            entity.state = EntityState(
                state=new_value or "unknown",
                attributes=new_state.get("attributes", {}),
                last_changed=new_state.get("last_changed"),
                last_updated=new_state.get("last_updated"),
            )

        # Notify callbacks
        for callback in self._event_callbacks:
            try:
                callback(event)
            except Exception as e:
                logger.warning("State change callback error: %s", e)

        # Log significant changes to activity log (not sensor updates every second)
        if old_value != new_value and new_value not in (None, "unavailable"):
            domain = entity_id.split(".")[0] if "." in entity_id else "unknown"

            # Only log state changes for user-relevant domains
            if domain in (
                "light",
                "switch",
                "climate",
                "lock",
                "cover",
                "media_player",
                "binary_sensor",
                "alarm_control_panel",
                "fan",
                "vacuum",
            ):
                friendly_name = new_state.get("attributes", {}).get("friendly_name", entity_id)

                domain_icons = {
                    "light": "💡",
                    "switch": "🔌",
                    "sensor": "📊",
                    "binary_sensor": "🔔",
                    "climate": "🌡️",
                    "lock": "🔒",
                    "cover": "🚪",
                    "media_player": "🎵",
                    "fan": "🌀",
                    "vacuum": "🧹",
                    "alarm_control_panel": "🚨",
                }
                icon = domain_icons.get(domain, "🔄")

                await log_activity(
                    type=ActivityType.HA_STATE_CHANGE,
                    source="homeassistant",
                    title=f"{icon} {friendly_name}: {old_value} → {new_value}",
                    entity_id=entity_id,
                    domain=domain,
                    old_state=old_value,
                    new_state=new_value,
                )

                logger.info("State change: %s: %s → %s", entity_id, old_value, new_value)
