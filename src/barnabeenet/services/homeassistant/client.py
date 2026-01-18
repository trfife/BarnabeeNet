"""Home Assistant API client.

Async client for communicating with Home Assistant's REST API.
Handles:
- Authentication via long-lived access token
- Service calls (turn_on, turn_off, etc.)
- State retrieval
- Entity discovery
- Event subscriptions (via WebSocket in future)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx

from barnabeenet.services.homeassistant.entities import Entity, EntityRegistry, EntityState

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
            return len(self._entity_registry)

        except httpx.RequestError as e:
            logger.error("Failed to refresh entities: %s", e)
            return 0

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
