# Area 04: Home Assistant Integration

**Version:** 1.0  
**Status:** Implementation Ready  
**Dependencies:** Area 01 (Core Data Layer), Area 03 (Intent Classification)  
**Phase:** Backbone  

---

## 1. Overview

### 1.1 Purpose

Home Assistant Integration connects BarnabeeNet to the smart home. This layer caches entity state, resolves natural language to entities, injects relevant context into LLM prompts, and executes commands.

### 1.2 V1 Problems Solved

| V1 Problem | V2 Solution |
|------------|-------------|
| "I don't track locations" (but HA has person.thom) | Smart context injection from HA state |
| No entity state awareness | Real-time WebSocket subscription + cache |
| Generic responses ignoring home state | Relevant entity context in every prompt |
| Can't answer "is anyone home?" | Person entity tracking |
| 2,291 entities can't fit in prompt | Semantic filtering injects only relevant entities |

### 1.3 Design Principles

1. **Real-time state:** WebSocket subscription means we know entity state within milliseconds of change.
2. **Smart context injection:** Don't inject 2,291 entities. Inject the 5-10 relevant to this query.
3. **Speculative execution:** For high-confidence commands, start HA action while generating response.
4. **Semantic entity understanding:** "The lights" in office context = office lights, not all 200 lights.
5. **Graceful degradation:** If HA is down, acknowledge limitation but don't crash.

### 1.4 Entity Scale

| Domain | Count | Context Injection Strategy |
|--------|-------|---------------------------|
| Lights | ~200 | By area, by recent use |
| Switches | ~150 | By area, by device class |
| Sensors | ~800 | Temperature/humidity for rooms mentioned |
| Binary Sensors | ~300 | Security-relevant only when asked |
| Climate | ~10 | Always for climate queries |
| Covers | ~20 | By area |
| Locks | ~10 | Always for security queries |
| Media Players | ~30 | By area, by recent use |
| Cameras | ~15 | Never inject (privacy) |
| Person | 6 | Always for location queries |
| Other | ~750 | Rarely injected |

---

## 2. Technology Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| HA Connection | websocket-client (async) | Real-time state subscription |
| HTTP Fallback | httpx | Service calls, REST API |
| Entity Cache | SQLite (Area 01) + In-memory LRU | Fast lookup, persistence |
| State Pub/Sub | Redis (Area 01) | Broadcast state changes to workers |
| Entity Enhancement | Custom semantic layer | Keywords, aliases, relationships |

---

## 3. Architecture

### 3.1 Data Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    HOME ASSISTANT INTEGRATION                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │                     HOME ASSISTANT INSTANCE                         │     │
│  │                     (http://homeassistant.local:8123)              │     │
│  └───────────────────────────┬────────────────────────────────────────┘     │
│                              │                                               │
│              ┌───────────────┼───────────────┐                              │
│              │               │               │                              │
│              ▼               ▼               ▼                              │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐                   │
│  │  WebSocket    │  │  REST API     │  │  Events API   │                   │
│  │  (state sub)  │  │  (services)   │  │  (history)    │                   │
│  └───────┬───────┘  └───────┬───────┘  └───────┬───────┘                   │
│          │                  │                  │                            │
│          └──────────────────┼──────────────────┘                            │
│                             │                                               │
│                             ▼                                               │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                      HA CONNECTION MANAGER                            │  │
│  │                                                                       │  │
│  │  • Maintains WebSocket connection with auto-reconnect                │  │
│  │  • Authenticates with long-lived access token                        │  │
│  │  • Routes state changes to cache                                     │  │
│  │  • Queues service calls                                              │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                             │                                               │
│              ┌──────────────┼──────────────┐                               │
│              │              │              │                               │
│              ▼              ▼              ▼                               │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐                  │
│  │ ENTITY CACHE  │  │ AREA CACHE    │  │ SERVICE CACHE │                  │
│  │               │  │               │  │               │                  │
│  │ SQLite +      │  │ In-memory     │  │ In-memory     │                  │
│  │ In-memory LRU │  │               │  │               │                  │
│  └───────────────┘  └───────────────┘  └───────────────┘                  │
│          │                                                                 │
│          ▼                                                                 │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                    SEMANTIC ENHANCEMENT LAYER                         │  │
│  │                                                                       │  │
│  │  For each entity:                                                    │  │
│  │  • Extract keywords from name, area, device class                    │  │
│  │  • Generate aliases (common names, abbreviations)                    │  │
│  │  • Map relationships (device → entities, area → entities)            │  │
│  │  • Compute access patterns (frequently used together)                │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│          │                                                                 │
│          ▼                                                                 │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                    CONTEXT INJECTION ENGINE                           │  │
│  │                                                                       │  │
│  │  Given: intent, entities, speaker, location                          │  │
│  │  Output: Relevant HA context for LLM prompt (max 500 tokens)         │  │
│  │                                                                       │  │
│  │  Strategies:                                                         │  │
│  │  • Intent-based: light_control → light entities in relevant areas    │  │
│  │  • Location-based: speaker's current area + mentioned areas          │  │
│  │  • Recency-based: recently controlled entities                       │  │
│  │  • Query-specific: "is anyone home" → person entities only           │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│          │                                                                 │
│          ▼                                                                 │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                    COMMAND EXECUTOR                                   │  │
│  │                                                                       │  │
│  │  • Validates entity IDs exist                                        │  │
│  │  • Maps intent + entities → HA service call                          │  │
│  │  • Handles speculative execution for high-confidence commands        │  │
│  │  • Returns confirmation or error                                     │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 State Synchronization Flow

```
HA State Change
      │
      ▼
WebSocket Message
      │
      ▼
┌─────────────────┐
│ Parse & Validate│
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
┌───────┐ ┌─────────┐
│SQLite │ │In-Memory│
│Persist│ │ Cache   │
└───────┘ └────┬────┘
               │
               ▼
        ┌────────────┐
        │Redis Pub   │
        │(broadcast) │
        └────────────┘
               │
               ▼
        ┌────────────┐
        │All Workers │
        │Updated     │
        └────────────┘
```

---

## 4. HA Connection Manager

### 4.1 WebSocket Client

```python
import asyncio
import json
from typing import Callable, Optional
import websockets
from websockets.exceptions import ConnectionClosed

class HAWebSocketClient:
    def __init__(
        self,
        url: str,
        token: str,
        on_state_change: Callable,
        on_connect: Optional[Callable] = None,
        on_disconnect: Optional[Callable] = None,
    ):
        self.url = url.replace("http", "ws") + "/api/websocket"
        self.token = token
        self.on_state_change = on_state_change
        self.on_connect = on_connect
        self.on_disconnect = on_disconnect
        
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.message_id = 0
        self.pending_requests: dict = {}
        self._running = False
        self._reconnect_delay = 1  # Exponential backoff
    
    async def connect(self):
        """Connect to HA WebSocket and subscribe to state changes."""
        self._running = True
        
        while self._running:
            try:
                async with websockets.connect(self.url) as ws:
                    self.ws = ws
                    self._reconnect_delay = 1  # Reset backoff
                    
                    # Authenticate
                    auth_msg = await ws.recv()
                    auth_data = json.loads(auth_msg)
                    
                    if auth_data["type"] == "auth_required":
                        await ws.send(json.dumps({
                            "type": "auth",
                            "access_token": self.token
                        }))
                        
                        auth_result = await ws.recv()
                        if json.loads(auth_result)["type"] != "auth_ok":
                            raise Exception("Authentication failed")
                    
                    # Subscribe to state changes
                    await self._subscribe_state_changes()
                    
                    if self.on_connect:
                        await self.on_connect()
                    
                    # Message loop
                    await self._message_loop()
                    
            except ConnectionClosed:
                if self.on_disconnect:
                    await self.on_disconnect()
                
                if self._running:
                    await asyncio.sleep(self._reconnect_delay)
                    self._reconnect_delay = min(self._reconnect_delay * 2, 60)
            
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                await asyncio.sleep(self._reconnect_delay)
                self._reconnect_delay = min(self._reconnect_delay * 2, 60)
    
    async def _subscribe_state_changes(self):
        """Subscribe to all state change events."""
        self.message_id += 1
        await self.ws.send(json.dumps({
            "id": self.message_id,
            "type": "subscribe_events",
            "event_type": "state_changed"
        }))
    
    async def _message_loop(self):
        """Process incoming WebSocket messages."""
        async for message in self.ws:
            data = json.loads(message)
            
            if data["type"] == "event":
                event = data.get("event", {})
                if event.get("event_type") == "state_changed":
                    await self.on_state_change(event["data"])
            
            elif data["type"] == "result":
                msg_id = data.get("id")
                if msg_id in self.pending_requests:
                    self.pending_requests[msg_id].set_result(data)
    
    async def call_service(
        self,
        domain: str,
        service: str,
        entity_id: Optional[str] = None,
        data: Optional[dict] = None,
        timeout: float = 10.0
    ) -> dict:
        """Call an HA service."""
        self.message_id += 1
        msg_id = self.message_id
        
        service_data = data or {}
        if entity_id:
            service_data["entity_id"] = entity_id
        
        request = {
            "id": msg_id,
            "type": "call_service",
            "domain": domain,
            "service": service,
            "service_data": service_data
        }
        
        # Create future for response
        future = asyncio.Future()
        self.pending_requests[msg_id] = future
        
        try:
            await self.ws.send(json.dumps(request))
            result = await asyncio.wait_for(future, timeout=timeout)
            return result
        finally:
            self.pending_requests.pop(msg_id, None)
    
    async def get_states(self) -> list:
        """Get all current states."""
        self.message_id += 1
        msg_id = self.message_id
        
        future = asyncio.Future()
        self.pending_requests[msg_id] = future
        
        await self.ws.send(json.dumps({
            "id": msg_id,
            "type": "get_states"
        }))
        
        result = await asyncio.wait_for(future, timeout=30.0)
        return result.get("result", [])
    
    def stop(self):
        """Stop the WebSocket client."""
        self._running = False
        if self.ws:
            asyncio.create_task(self.ws.close())
```

### 4.2 Connection Manager

```python
class HAConnectionManager:
    def __init__(
        self,
        ha_url: str,
        ha_token: str,
        entity_cache: 'EntityCache',
        redis: 'Redis',
    ):
        self.ha_url = ha_url
        self.ha_token = ha_token
        self.entity_cache = entity_cache
        self.redis = redis
        
        self.ws_client: Optional[HAWebSocketClient] = None
        self.http_client = httpx.AsyncClient(
            base_url=ha_url,
            headers={"Authorization": f"Bearer {ha_token}"},
            timeout=30.0
        )
        
        self.connected = False
        self.last_full_sync = None
    
    async def start(self):
        """Start HA connection and initial sync."""
        # Initial full state sync via REST (faster than WebSocket)
        await self._full_state_sync()
        
        # Start WebSocket for real-time updates
        self.ws_client = HAWebSocketClient(
            url=self.ha_url,
            token=self.ha_token,
            on_state_change=self._handle_state_change,
            on_connect=self._on_ws_connect,
            on_disconnect=self._on_ws_disconnect,
        )
        
        asyncio.create_task(self.ws_client.connect())
    
    async def _full_state_sync(self):
        """Sync all states from HA."""
        response = await self.http_client.get("/api/states")
        response.raise_for_status()
        states = response.json()
        
        # Batch update cache
        await self.entity_cache.bulk_update(states)
        
        # Load areas
        areas_response = await self.http_client.get("/api/config")
        config = areas_response.json()
        # Areas come from registry, need different endpoint
        
        self.last_full_sync = datetime.utcnow()
        logger.info(f"Synced {len(states)} entities from HA")
    
    async def _handle_state_change(self, event_data: dict):
        """Handle a state change event."""
        entity_id = event_data.get("entity_id")
        new_state = event_data.get("new_state")
        
        if not entity_id or not new_state:
            return
        
        # Update cache
        await self.entity_cache.update_entity(entity_id, new_state)
        
        # Broadcast via Redis
        await self.redis.publish("ha:state_changed", json.dumps({
            "entity_id": entity_id,
            "state": new_state["state"],
            "attributes": new_state.get("attributes", {}),
            "last_changed": new_state.get("last_changed"),
        }))
    
    async def _on_ws_connect(self):
        self.connected = True
        logger.info("Connected to Home Assistant WebSocket")
    
    async def _on_ws_disconnect(self):
        self.connected = False
        logger.warning("Disconnected from Home Assistant WebSocket")
    
    async def call_service(
        self,
        domain: str,
        service: str,
        entity_id: Optional[str] = None,
        data: Optional[dict] = None,
    ) -> dict:
        """Call an HA service via WebSocket (preferred) or REST (fallback)."""
        if self.ws_client and self.connected:
            return await self.ws_client.call_service(domain, service, entity_id, data)
        else:
            # REST fallback
            payload = {"entity_id": entity_id, **(data or {})}
            response = await self.http_client.post(
                f"/api/services/{domain}/{service}",
                json=payload
            )
            response.raise_for_status()
            return response.json()
```

---

## 5. Entity Cache

### 5.1 Cache Structure

```python
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime

@dataclass
class CachedEntity:
    entity_id: str
    domain: str
    state: str
    attributes: Dict[str, Any]
    friendly_name: Optional[str]
    device_class: Optional[str]
    area: Optional[str]
    
    # Semantic enhancement
    keywords: List[str] = field(default_factory=list)
    aliases: List[str] = field(default_factory=list)
    
    # Metadata
    last_changed: Optional[datetime] = None
    last_accessed: Optional[datetime] = None
    access_count: int = 0
    
    @property
    def is_on(self) -> bool:
        return self.state.lower() in ("on", "true", "open", "unlocked", "home", "playing")
    
    @property
    def is_available(self) -> bool:
        return self.state.lower() != "unavailable"


class EntityCache:
    def __init__(self, db: Database, memory_cache: DataCache):
        self.db = db
        self.memory_cache = memory_cache
        self._area_cache: Dict[str, str] = {}  # entity_id → area
        self._domain_entities: Dict[str, List[str]] = {}  # domain → [entity_ids]
        self._area_entities: Dict[str, List[str]] = {}  # area → [entity_ids]
    
    async def bulk_update(self, states: List[dict]):
        """Bulk update cache from full state sync."""
        async with self.db.transaction():
            for state in states:
                entity_id = state["entity_id"]
                domain = entity_id.split(".")[0]
                
                # Extract and enhance
                friendly_name = state.get("attributes", {}).get("friendly_name")
                device_class = state.get("attributes", {}).get("device_class")
                area = await self._get_entity_area(entity_id)
                
                keywords = self._extract_keywords(friendly_name, area, device_class)
                aliases = self._generate_aliases(friendly_name, entity_id)
                
                # Persist to SQLite
                await self.db.execute(
                    """
                    INSERT OR REPLACE INTO ha_entity_cache 
                    (entity_id, domain, state, attributes, friendly_name, 
                     device_class, area, keywords, aliases, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                    """,
                    [
                        entity_id, domain, state["state"],
                        json.dumps(state.get("attributes", {})),
                        friendly_name, device_class, area,
                        json.dumps(keywords), json.dumps(aliases)
                    ]
                )
                
                # Update in-memory indexes
                if domain not in self._domain_entities:
                    self._domain_entities[domain] = []
                if entity_id not in self._domain_entities[domain]:
                    self._domain_entities[domain].append(entity_id)
                
                if area:
                    if area not in self._area_entities:
                        self._area_entities[area] = []
                    if entity_id not in self._area_entities[area]:
                        self._area_entities[area].append(entity_id)
    
    async def update_entity(self, entity_id: str, new_state: dict):
        """Update single entity from state change event."""
        # Update SQLite
        await self.db.execute(
            """
            UPDATE ha_entity_cache
            SET state = ?, attributes = ?, updated_at = datetime('now')
            WHERE entity_id = ?
            """,
            [new_state["state"], json.dumps(new_state.get("attributes", {})), entity_id]
        )
        
        # Invalidate memory cache
        self.memory_cache.delete(f"ha:{entity_id}")
    
    async def get_entity(self, entity_id: str) -> Optional[CachedEntity]:
        """Get entity by ID."""
        # Check memory cache
        cached = self.memory_cache.get(f"ha:{entity_id}")
        if cached:
            return cached
        
        # Query SQLite
        row = await self.db.fetchone(
            "SELECT * FROM ha_entity_cache WHERE entity_id = ?",
            [entity_id]
        )
        
        if not row:
            return None
        
        entity = self._row_to_entity(row)
        
        # Cache in memory
        self.memory_cache.set(f"ha:{entity_id}", entity)
        
        # Update access tracking
        await self.db.execute(
            """
            UPDATE ha_entity_cache 
            SET last_accessed = datetime('now'), access_count = access_count + 1
            WHERE entity_id = ?
            """,
            [entity_id]
        )
        
        return entity
    
    async def get_entities_by_domain(self, domain: str) -> List[CachedEntity]:
        """Get all entities for a domain."""
        rows = await self.db.fetchall(
            "SELECT * FROM ha_entity_cache WHERE domain = ?",
            [domain]
        )
        return [self._row_to_entity(r) for r in rows]
    
    async def get_entities_by_area(self, area: str) -> List[CachedEntity]:
        """Get all entities in an area."""
        rows = await self.db.fetchall(
            "SELECT * FROM ha_entity_cache WHERE area = ?",
            [area]
        )
        return [self._row_to_entity(r) for r in rows]
    
    async def get_entities_by_domain_and_area(
        self, 
        domain: str, 
        area: str
    ) -> List[CachedEntity]:
        """Get entities matching domain AND area."""
        rows = await self.db.fetchall(
            "SELECT * FROM ha_entity_cache WHERE domain = ? AND area = ?",
            [domain, area]
        )
        return [self._row_to_entity(r) for r in rows]
    
    async def search_entities(
        self,
        query: str,
        domain: Optional[str] = None,
        area: Optional[str] = None,
        limit: int = 10
    ) -> List[CachedEntity]:
        """Search entities by keyword/alias."""
        conditions = ["1=1"]
        params = []
        
        if domain:
            conditions.append("domain = ?")
            params.append(domain)
        
        if area:
            conditions.append("area = ?")
            params.append(area)
        
        # Search in keywords and aliases (JSON arrays)
        conditions.append(
            "(keywords LIKE ? OR aliases LIKE ? OR friendly_name LIKE ?)"
        )
        search_pattern = f"%{query}%"
        params.extend([search_pattern, search_pattern, search_pattern])
        
        rows = await self.db.fetchall(
            f"""
            SELECT * FROM ha_entity_cache 
            WHERE {' AND '.join(conditions)}
            LIMIT ?
            """,
            params + [limit]
        )
        
        return [self._row_to_entity(r) for r in rows]
    
    async def get_person_entities(self) -> List[CachedEntity]:
        """Get all person entities (for location queries)."""
        return await self.get_entities_by_domain("person")
    
    async def get_areas(self) -> List[str]:
        """Get all unique areas."""
        rows = await self.db.fetchall(
            "SELECT DISTINCT area FROM ha_entity_cache WHERE area IS NOT NULL"
        )
        return [r[0] for r in rows]
    
    def _extract_keywords(
        self,
        friendly_name: Optional[str],
        area: Optional[str],
        device_class: Optional[str]
    ) -> List[str]:
        """Extract searchable keywords from entity metadata."""
        keywords = []
        
        if friendly_name:
            # Split on common separators
            words = re.split(r'[\s_\-]+', friendly_name.lower())
            keywords.extend(words)
        
        if area:
            keywords.append(area.lower())
        
        if device_class:
            keywords.append(device_class.lower())
        
        return list(set(keywords))
    
    def _generate_aliases(
        self,
        friendly_name: Optional[str],
        entity_id: str
    ) -> List[str]:
        """Generate common aliases for an entity."""
        aliases = []
        
        if friendly_name:
            # Original name
            aliases.append(friendly_name.lower())
            
            # Without common suffixes
            for suffix in [" light", " lights", " switch", " sensor", " lock"]:
                if friendly_name.lower().endswith(suffix):
                    aliases.append(friendly_name.lower().replace(suffix, ""))
            
            # Common abbreviations
            abbreviations = {
                "living room": ["living", "lr"],
                "bedroom": ["bed"],
                "bathroom": ["bath"],
                "kitchen": ["kit"],
            }
            for full, abbrevs in abbreviations.items():
                if full in friendly_name.lower():
                    for abbrev in abbrevs:
                        aliases.append(
                            friendly_name.lower().replace(full, abbrev)
                        )
        
        return list(set(aliases))
    
    def _row_to_entity(self, row) -> CachedEntity:
        """Convert database row to CachedEntity."""
        return CachedEntity(
            entity_id=row["entity_id"],
            domain=row["domain"],
            state=row["state"],
            attributes=json.loads(row["attributes"]),
            friendly_name=row["friendly_name"],
            device_class=row["device_class"],
            area=row["area"],
            keywords=json.loads(row["keywords"]) if row["keywords"] else [],
            aliases=json.loads(row["aliases"]) if row["aliases"] else [],
            last_accessed=row["last_accessed"],
            access_count=row["access_count"],
        )
```

---

## 6. Context Injection Engine

### 6.1 Strategy Selection

Different intents need different context:

| Intent | Context Strategy | Max Entities |
|--------|------------------|--------------|
| light_control | Lights in mentioned/current area | 10 |
| climate_control | All climate entities | 10 |
| lock_control | All locks + door sensors | 10 |
| location_query | All person entities | 6 |
| weather_query | Weather entity only | 1 |
| media_control | Media players in area | 5 |
| general_query | Minimal (speaker location only) | 2 |
| timer_set | None (no HA context needed) | 0 |

### 6.2 Context Builder

```python
@dataclass
class HAContext:
    """Home Assistant context for LLM prompt injection."""
    entities: List[CachedEntity]
    speaker_location: Optional[str]
    relevant_areas: List[str]
    token_count: int  # Approximate token usage
    
    def to_prompt_text(self) -> str:
        """Format context for LLM prompt."""
        lines = []
        
        if self.speaker_location:
            lines.append(f"Speaker is currently in: {self.speaker_location}")
        
        if self.entities:
            lines.append("\nRelevant home devices:")
            for entity in self.entities:
                state_desc = self._describe_state(entity)
                lines.append(f"- {entity.friendly_name or entity.entity_id}: {state_desc}")
        
        return "\n".join(lines)
    
    def _describe_state(self, entity: CachedEntity) -> str:
        """Generate human-readable state description."""
        state = entity.state
        attrs = entity.attributes
        
        if entity.domain == "light":
            if state == "on":
                brightness = attrs.get("brightness", 255)
                pct = round(brightness / 255 * 100)
                return f"on ({pct}% brightness)"
            return "off"
        
        elif entity.domain == "climate":
            current = attrs.get("current_temperature")
            target = attrs.get("temperature")
            mode = attrs.get("hvac_mode", state)
            if current and target:
                return f"{mode}, currently {current}°, target {target}°"
            return mode
        
        elif entity.domain == "person":
            return state  # "home" or "not_home" or zone name
        
        elif entity.domain == "lock":
            return "locked" if state == "locked" else "unlocked"
        
        elif entity.domain == "cover":
            position = attrs.get("current_position")
            if position is not None:
                return f"{state} ({position}% open)"
            return state
        
        elif entity.domain == "sensor":
            unit = attrs.get("unit_of_measurement", "")
            return f"{state}{unit}"
        
        return state


class ContextInjectionEngine:
    def __init__(self, entity_cache: EntityCache):
        self.entity_cache = entity_cache
        self.MAX_TOKENS = 500  # Token budget for HA context
    
    async def build_context(
        self,
        intent: str,
        extracted_entities: dict,
        speaker_id: Optional[str],
        device_id: Optional[str],
    ) -> HAContext:
        """Build HA context for LLM prompt injection."""
        
        # Determine speaker location
        speaker_location = await self._get_speaker_location(speaker_id)
        
        # Determine relevant areas
        relevant_areas = self._determine_relevant_areas(
            extracted_entities.get("locations", []),
            speaker_location
        )
        
        # Select strategy based on intent
        strategy = self._select_strategy(intent)
        
        # Gather entities using strategy
        entities = await strategy(
            intent=intent,
            extracted_entities=extracted_entities,
            areas=relevant_areas,
        )
        
        # Trim to token budget
        entities = self._trim_to_budget(entities)
        
        context = HAContext(
            entities=entities,
            speaker_location=speaker_location,
            relevant_areas=relevant_areas,
            token_count=self._estimate_tokens(entities),
        )
        
        return context
    
    async def _get_speaker_location(self, speaker_id: Optional[str]) -> Optional[str]:
        """Get speaker's current location from person entity."""
        if not speaker_id:
            return None
        
        person_entity = await self.entity_cache.get_entity(f"person.{speaker_id}")
        if person_entity:
            state = person_entity.state
            if state == "home":
                # Try to get more specific location from device tracker
                # For now, just return "home"
                return "home"
            elif state != "not_home":
                return state  # Zone name
        
        return None
    
    def _determine_relevant_areas(
        self,
        mentioned_areas: List[str],
        speaker_location: Optional[str]
    ) -> List[str]:
        """Determine which areas are relevant to this query."""
        areas = list(mentioned_areas)
        
        # Add speaker's area if home
        if speaker_location and speaker_location != "not_home":
            if speaker_location not in areas:
                areas.append(speaker_location)
        
        return areas
    
    def _select_strategy(self, intent: str) -> Callable:
        """Select context gathering strategy based on intent."""
        strategies = {
            "light_control": self._strategy_light_control,
            "climate_control": self._strategy_climate,
            "lock_control": self._strategy_security,
            "cover_control": self._strategy_covers,
            "media_control": self._strategy_media,
            "location_query": self._strategy_location,
            "weather_query": self._strategy_weather,
            "calendar_query": self._strategy_minimal,
            "timer_set": self._strategy_none,
            "timer_query": self._strategy_none,
            "time_query": self._strategy_none,
            "memory_query": self._strategy_minimal,
        }
        
        return strategies.get(intent, self._strategy_minimal)
    
    async def _strategy_light_control(
        self,
        intent: str,
        extracted_entities: dict,
        areas: List[str],
    ) -> List[CachedEntity]:
        """Context strategy for light control."""
        entities = []
        
        # If specific devices extracted, get those
        device_ids = extracted_entities.get("devices", [])
        for device_id in device_ids:
            entity = await self.entity_cache.get_entity(device_id)
            if entity:
                entities.append(entity)
        
        # If areas specified, get lights in those areas
        if not entities and areas:
            for area in areas:
                area_lights = await self.entity_cache.get_entities_by_domain_and_area(
                    "light", area
                )
                entities.extend(area_lights)
        
        # If still nothing, get recently used lights
        if not entities:
            all_lights = await self.entity_cache.get_entities_by_domain("light")
            # Sort by access count and take top 10
            entities = sorted(
                all_lights, 
                key=lambda e: e.access_count, 
                reverse=True
            )[:10]
        
        return entities[:10]
    
    async def _strategy_climate(
        self,
        intent: str,
        extracted_entities: dict,
        areas: List[str],
    ) -> List[CachedEntity]:
        """Context strategy for climate control."""
        # Always return all climate entities (usually few)
        return await self.entity_cache.get_entities_by_domain("climate")
    
    async def _strategy_security(
        self,
        intent: str,
        extracted_entities: dict,
        areas: List[str],
    ) -> List[CachedEntity]:
        """Context strategy for lock/security queries."""
        entities = []
        
        # All locks
        locks = await self.entity_cache.get_entities_by_domain("lock")
        entities.extend(locks)
        
        # Door/window sensors
        binary_sensors = await self.entity_cache.get_entities_by_domain("binary_sensor")
        door_window = [
            e for e in binary_sensors 
            if e.device_class in ("door", "window", "garage_door")
        ]
        entities.extend(door_window)
        
        return entities[:10]
    
    async def _strategy_location(
        self,
        intent: str,
        extracted_entities: dict,
        areas: List[str],
    ) -> List[CachedEntity]:
        """Context strategy for location queries (where is X)."""
        return await self.entity_cache.get_person_entities()
    
    async def _strategy_media(
        self,
        intent: str,
        extracted_entities: dict,
        areas: List[str],
    ) -> List[CachedEntity]:
        """Context strategy for media control."""
        if areas:
            entities = []
            for area in areas:
                media = await self.entity_cache.get_entities_by_domain_and_area(
                    "media_player", area
                )
                entities.extend(media)
            return entities[:5]
        
        # All media players
        return (await self.entity_cache.get_entities_by_domain("media_player"))[:5]
    
    async def _strategy_weather(
        self,
        intent: str,
        extracted_entities: dict,
        areas: List[str],
    ) -> List[CachedEntity]:
        """Context strategy for weather queries."""
        weather = await self.entity_cache.get_entities_by_domain("weather")
        return weather[:1]
    
    async def _strategy_covers(
        self,
        intent: str,
        extracted_entities: dict,
        areas: List[str],
    ) -> List[CachedEntity]:
        """Context strategy for cover (blinds, garage) control."""
        if areas:
            entities = []
            for area in areas:
                covers = await self.entity_cache.get_entities_by_domain_and_area(
                    "cover", area
                )
                entities.extend(covers)
            return entities[:10]
        
        return (await self.entity_cache.get_entities_by_domain("cover"))[:10]
    
    async def _strategy_minimal(
        self,
        intent: str,
        extracted_entities: dict,
        areas: List[str],
    ) -> List[CachedEntity]:
        """Minimal context - just person entities."""
        return await self.entity_cache.get_person_entities()
    
    async def _strategy_none(
        self,
        intent: str,
        extracted_entities: dict,
        areas: List[str],
    ) -> List[CachedEntity]:
        """No HA context needed."""
        return []
    
    def _trim_to_budget(self, entities: List[CachedEntity]) -> List[CachedEntity]:
        """Trim entities to fit within token budget."""
        result = []
        token_count = 0
        
        for entity in entities:
            # Estimate tokens for this entity (rough: 20 tokens per entity)
            entity_tokens = 20
            if token_count + entity_tokens > self.MAX_TOKENS:
                break
            result.append(entity)
            token_count += entity_tokens
        
        return result
    
    def _estimate_tokens(self, entities: List[CachedEntity]) -> int:
        """Estimate token count for entities."""
        return len(entities) * 20  # Rough estimate
```

---

## 7. Command Executor

### 7.1 Service Mapping

```python
INTENT_TO_SERVICE = {
    "light_control": {
        "on": ("light", "turn_on"),
        "off": ("light", "turn_off"),
        "toggle": ("light", "toggle"),
        "brightness": ("light", "turn_on"),  # with brightness_pct
        "color": ("light", "turn_on"),       # with rgb_color or color_temp
    },
    "climate_control": {
        "set_temperature": ("climate", "set_temperature"),
        "set_mode": ("climate", "set_hvac_mode"),
        "turn_off": ("climate", "turn_off"),
    },
    "lock_control": {
        "lock": ("lock", "lock"),
        "unlock": ("lock", "unlock"),
    },
    "cover_control": {
        "open": ("cover", "open_cover"),
        "close": ("cover", "close_cover"),
        "stop": ("cover", "stop_cover"),
        "position": ("cover", "set_cover_position"),
    },
    "media_control": {
        "play": ("media_player", "media_play"),
        "pause": ("media_player", "media_pause"),
        "stop": ("media_player", "media_stop"),
        "next": ("media_player", "media_next_track"),
        "previous": ("media_player", "media_previous_track"),
        "volume": ("media_player", "volume_set"),
    },
    "scene_activation": {
        "activate": ("scene", "turn_on"),
    },
}
```

### 7.2 Executor Implementation

```python
@dataclass
class CommandResult:
    success: bool
    entity_ids: List[str]
    action: str
    error: Optional[str] = None
    execution_time_ms: float = 0


class CommandExecutor:
    def __init__(self, ha_manager: HAConnectionManager, entity_cache: EntityCache):
        self.ha = ha_manager
        self.entity_cache = entity_cache
    
    async def execute(
        self,
        intent: str,
        entities: dict,
        action: Optional[str] = None,
    ) -> CommandResult:
        """Execute a command based on classified intent."""
        start_time = time.perf_counter()
        
        # Get entity IDs
        entity_ids = entities.get("devices", [])
        if not entity_ids:
            return CommandResult(
                success=False,
                entity_ids=[],
                action=action or "unknown",
                error="No devices identified for command"
            )
        
        # Validate entities exist
        valid_entities = []
        for eid in entity_ids:
            entity = await self.entity_cache.get_entity(eid)
            if entity and entity.is_available:
                valid_entities.append(eid)
        
        if not valid_entities:
            return CommandResult(
                success=False,
                entity_ids=entity_ids,
                action=action or "unknown",
                error="No available devices found"
            )
        
        # Determine action from intent and entities
        action = action or self._infer_action(intent, entities)
        
        # Get service mapping
        service_map = INTENT_TO_SERVICE.get(intent, {})
        service_info = service_map.get(action)
        
        if not service_info:
            return CommandResult(
                success=False,
                entity_ids=valid_entities,
                action=action,
                error=f"Unknown action '{action}' for intent '{intent}'"
            )
        
        domain, service = service_info
        
        # Build service data
        service_data = self._build_service_data(entities)
        
        # Execute for each entity
        errors = []
        for eid in valid_entities:
            try:
                await self.ha.call_service(
                    domain=domain,
                    service=service,
                    entity_id=eid,
                    data=service_data
                )
            except Exception as e:
                errors.append(f"{eid}: {str(e)}")
        
        execution_time = (time.perf_counter() - start_time) * 1000
        
        if errors:
            return CommandResult(
                success=False,
                entity_ids=valid_entities,
                action=action,
                error="; ".join(errors),
                execution_time_ms=execution_time
            )
        
        return CommandResult(
            success=True,
            entity_ids=valid_entities,
            action=action,
            execution_time_ms=execution_time
        )
    
    def _infer_action(self, intent: str, entities: dict) -> str:
        """Infer action from intent and entity data."""
        # Check for explicit action indicators
        raw_slots = entities.get("raw_slots", {})
        
        if "brightness" in raw_slots:
            return "brightness"
        if "color" in raw_slots:
            return "color"
        if "temperature" in raw_slots:
            return "set_temperature"
        
        # Default actions by intent
        default_actions = {
            "light_control": "toggle",
            "climate_control": "set_temperature",
            "lock_control": "lock",
            "cover_control": "toggle",
            "media_control": "toggle",
        }
        
        return default_actions.get(intent, "on")
    
    def _build_service_data(self, entities: dict) -> dict:
        """Build service call data from extracted entities."""
        data = {}
        raw_slots = entities.get("raw_slots", {})
        
        if "brightness" in raw_slots:
            data["brightness_pct"] = raw_slots["brightness"]
        
        if "color" in raw_slots:
            color = raw_slots["color"]
            if isinstance(color, dict) and "color_temp" in color:
                data["color_temp_kelvin"] = color["color_temp"]
            elif isinstance(color, str):
                data["color_name"] = color
        
        if "temperature" in raw_slots:
            data["temperature"] = raw_slots["temperature"]
        
        if "volume" in raw_slots:
            data["volume_level"] = raw_slots["volume"] / 100
        
        if "position" in raw_slots:
            data["position"] = raw_slots["position"]
        
        return data
```

### 7.3 Speculative Execution

```python
class SpeculativeExecutor:
    """
    For high-confidence commands, execute before response generation.
    
    Safe for speculation:
    - light_control (reversible)
    - climate_control (reversible)
    - media_control (reversible)
    - cover_control (reversible)
    - time_query (no side effects)
    - weather_query (no side effects)
    
    NOT safe for speculation:
    - lock_control (security-sensitive)
    - scene_activation (may be complex/irreversible)
    - memory_create (explicit user action)
    """
    
    SAFE_INTENTS = {
        "light_control",
        "climate_control", 
        "media_control",
        "cover_control",
        "time_query",
        "weather_query",
    }
    
    CONFIDENCE_THRESHOLD = 0.98
    
    def __init__(self, executor: CommandExecutor):
        self.executor = executor
        self.pending_executions: Dict[str, asyncio.Task] = {}
    
    async def maybe_execute_speculatively(
        self,
        request_id: str,
        intent: str,
        confidence: float,
        entities: dict,
    ) -> Optional[CommandResult]:
        """
        Start speculative execution if conditions are met.
        
        Returns result immediately if execution completes before response generation.
        """
        if intent not in self.SAFE_INTENTS:
            return None
        
        if confidence < self.CONFIDENCE_THRESHOLD:
            return None
        
        # Start execution in background
        task = asyncio.create_task(
            self.executor.execute(intent, entities)
        )
        self.pending_executions[request_id] = task
        
        # Give it a short time to complete
        try:
            result = await asyncio.wait_for(
                asyncio.shield(task),
                timeout=0.1  # 100ms head start
            )
            return result
        except asyncio.TimeoutError:
            # Still running, will complete in background
            return None
    
    async def get_result(self, request_id: str) -> Optional[CommandResult]:
        """Get result of speculative execution."""
        task = self.pending_executions.pop(request_id, None)
        if task:
            return await task
        return None
    
    def cancel(self, request_id: str):
        """Cancel speculative execution (e.g., if classification was wrong)."""
        task = self.pending_executions.pop(request_id, None)
        if task and not task.done():
            task.cancel()
```

---

## 8. Graceful Degradation

### 8.1 HA Unavailable Handling

```python
class HAHealthChecker:
    def __init__(self, ha_manager: HAConnectionManager):
        self.ha = ha_manager
        self.last_check = None
        self.is_healthy = True
        self.consecutive_failures = 0
    
    async def check_health(self) -> bool:
        """Check if HA is responsive."""
        try:
            # Simple ping via REST API
            response = await self.ha.http_client.get("/api/", timeout=5.0)
            if response.status_code == 200:
                self.is_healthy = True
                self.consecutive_failures = 0
                return True
        except Exception:
            pass
        
        self.consecutive_failures += 1
        if self.consecutive_failures >= 3:
            self.is_healthy = False
        
        return False
    
    def get_degraded_response(self, intent: str) -> str:
        """Get appropriate response when HA is unavailable."""
        responses = {
            "light_control": "I'm having trouble connecting to the home system right now. I'll try again in a moment.",
            "climate_control": "I can't reach the thermostat at the moment. Please try again shortly.",
            "location_query": "I'm unable to check locations right now. The home system seems to be offline.",
            "lock_control": "I can't access the locks right now for safety reasons. Please check manually.",
        }
        
        return responses.get(
            intent,
            "I'm having trouble connecting to the home system. Please try again in a moment."
        )
```

---

## 9. File Structure

```
barnabeenet-v2/
├── src/
│   └── barnabee/
│       └── ha/
│           ├── __init__.py
│           ├── config.py               # HA connection settings
│           ├── connection.py           # HAConnectionManager, WebSocket client
│           ├── cache.py                # EntityCache
│           ├── context.py              # ContextInjectionEngine
│           ├── executor.py             # CommandExecutor, SpeculativeExecutor
│           ├── health.py               # HAHealthChecker
│           └── models.py               # CachedEntity, CommandResult, HAContext
└── tests/
    └── ha/
        ├── test_cache.py
        ├── test_context.py
        ├── test_executor.py
        └── test_connection.py
```

---

## 10. Implementation Checklist

### Connection Layer

- [ ] WebSocket client with auto-reconnect
- [ ] Authentication handling
- [ ] State change subscription
- [ ] Service call via WebSocket
- [ ] HTTP fallback for service calls

### Entity Cache

- [ ] Bulk state sync from REST API
- [ ] Real-time updates from WebSocket
- [ ] SQLite persistence
- [ ] In-memory LRU caching
- [ ] Keyword extraction
- [ ] Alias generation
- [ ] Domain/area indexing

### Context Injection

- [ ] Strategy selection by intent
- [ ] Light control strategy
- [ ] Climate strategy
- [ ] Security strategy
- [ ] Location strategy
- [ ] Token budget management
- [ ] Prompt text formatting

### Command Execution

- [ ] Service mapping for all intents
- [ ] Entity validation
- [ ] Service data building
- [ ] Error handling
- [ ] Speculative execution

### Resilience

- [ ] Health checking
- [ ] Degraded mode responses
- [ ] Connection recovery
- [ ] Redis state broadcast

### Validation

- [ ] WebSocket reconnects within 5 seconds
- [ ] Entity cache query <10ms
- [ ] Context injection <20ms
- [ ] Service call <500ms
- [ ] "Where is Thom?" returns correct location

### Acceptance Criteria

1. **Real-time state updates** within 100ms of HA change
2. **Entity resolution >98% accuracy** for common device names
3. **Context injection <500 tokens** per request
4. **Graceful degradation** when HA is offline
5. **Speculative execution** saves 200-300ms on high-confidence commands

---

## 11. Handoff Notes for Implementation Agent

### Critical Points

1. **WebSocket is primary, REST is fallback.** WebSocket gives real-time updates; REST is for initial sync and degraded mode.

2. **Entity cache must stay warm.** Cold cache queries hit SQLite. Warm cache is in-memory LRU.

3. **Context injection is the key to smart responses.** Without it, LLM doesn't know home state.

4. **Speculative execution is aggressive.** Only for reversible, high-confidence actions.

5. **Never cache camera states in prompt context.** Privacy concern.

### Common Pitfalls

- Forgetting to handle WebSocket disconnection (HA restarts, network blips)
- Not invalidating memory cache on state change
- Injecting too much context (token budget overflow)
- Not validating entity exists before service call
- Blocking on service calls (always use async with timeout)

### Performance Tuning

- Pre-load all entities at startup (bulk sync)
- Index frequently-queried combinations (domain+area)
- Cache entity resolution results (same text → same result)
- Batch service calls when possible (multiple lights = one call with list)

---

**End of Area 04: Home Assistant Integration**
