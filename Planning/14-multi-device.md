# Area 14: Multi-Device Coordination

**Version:** 1.0  
**Status:** Implementation Ready  
**Dependencies:** Area 01 (Core Data Layer), Area 02 (Voice Pipeline), Area 04 (Home Assistant)  
**Phase:** Backbone  

---

## 1. Overview

### 1.1 Purpose

This specification defines how Barnabee handles multiple devices hearing the wake word simultaneously and how the system maintains availability when backend services are unreachable. With a household of 6 people and multiple voice-enabled devices (Lenovo tablets, phones, future smart glasses), this is critical for usable UX.

### 1.2 Problems Solved

| Problem | V2 Solution |
|---------|-------------|
| Multiple devices respond to "Hey Barnabee" | Proximity-based arbitration (closest device wins) |
| No device location awareness | HA-based location from Lenovo tablets + ESPresense |
| Backend unreachable = complete failure | Graceful degradation with local fallback |
| No feedback on service status | Device-level health indicators |

### 1.3 Design Principles

1. **Single responder:** Only one device speaks for any given wake word activation
2. **Closest wins:** Device nearest to speaker handles the interaction
3. **Location-aware:** Leverage HA device trackers and room sensors
4. **Fail gracefully:** Devices indicate degraded state, offer limited local functionality
5. **Fast arbitration:** Device selection must complete in <100ms to avoid perceptible delay

---

## 2. Architecture

### 2.1 Multi-Device Arbitration Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     MULTI-DEVICE WAKE WORD ARBITRATION                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  WAKE WORD DETECTED SIMULTANEOUSLY ON MULTIPLE DEVICES                       │
│                                                                              │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐              │
│  │ Kitchen  │    │ Living   │    │  Office  │    │ Bedroom  │              │
│  │ Lenovo   │    │  Room    │    │ Desktop  │    │  Tablet  │              │
│  │ Tablet   │    │ Lenovo   │    │          │    │          │              │
│  └────┬─────┘    └────┬─────┘    └────┬─────┘    └────┬─────┘              │
│       │               │               │               │                     │
│       │ Wake + meta   │ Wake + meta   │ Wake + meta   │ Wake + meta        │
│       │ (confidence,  │               │               │                     │
│       │  device_id,   │               │               │                     │
│       │  location)    │               │               │                     │
│       │               │               │               │                     │
│       └───────────────┴───────┬───────┴───────────────┘                     │
│                               │                                              │
│                               ▼                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                     ARBITRATION SERVICE                                 │ │
│  │                                                                         │ │
│  │  1. Collect wake events within 500ms window                            │ │
│  │  2. Identify speaker (voice ID if available)                           │ │
│  │  3. Get speaker's current location (HA person entity)                  │ │
│  │  4. Get device locations (HA device_tracker entities)                  │ │
│  │  5. Calculate proximity scores                                         │ │
│  │  6. Select winner (highest score)                                      │ │
│  │  7. Broadcast decision to all devices                                  │ │
│  │                                                                         │ │
│  │  Timeout: If no server response in 200ms, device self-arbitrates       │ │
│  │                                                                         │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                               │                                              │
│               ┌───────────────┼───────────────┐                             │
│               │               │               │                              │
│               ▼               ▼               ▼                              │
│         ┌──────────┐   ┌──────────┐   ┌──────────┐                         │
│         │  WINNER  │   │  LOSER   │   │  LOSER   │                         │
│         │          │   │          │   │          │                         │
│         │ Activate │   │ Suppress │   │ Suppress │                         │
│         │ pipeline │   │ Show dot │   │ Show dot │                         │
│         └──────────┘   └──────────┘   └──────────┘                         │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Arbitration Protocol

```python
# Message sent by device on wake word detection
@dataclass
class WakeWordEvent:
    event_id: str               # UUID for this wake event
    device_id: str              # e.g., "lenovo_kitchen"
    timestamp: float            # Unix timestamp (ms precision)
    wake_confidence: float      # 0.0-1.0 from openWakeWord
    audio_energy: float         # RMS of audio during wake word
    location: Optional[str]     # Room if known, e.g., "kitchen"
    speaker_embedding: Optional[bytes]  # For speaker identification

# Response from arbitration service
@dataclass  
class ArbitrationResult:
    event_id: str
    winner_device_id: str
    reason: str                 # "proximity", "confidence", "fallback"
    should_respond: bool        # True only for winner
```

### 2.3 Proximity Scoring Algorithm

```python
def calculate_proximity_score(
    device: DeviceInfo,
    speaker_location: Optional[str],
    wake_event: WakeWordEvent,
) -> float:
    """
    Calculate device's priority score for handling this wake event.
    Higher score = more likely to be selected.
    """
    score = 0.0
    
    # 1. Same room as speaker (if known) = +100 points
    if speaker_location and device.location == speaker_location:
        score += 100.0
    
    # 2. Adjacent room = +50 points (requires room adjacency map)
    elif speaker_location and is_adjacent(device.location, speaker_location):
        score += 50.0
    
    # 3. Audio energy (louder = closer) = +0-30 points
    # Normalize to 0-30 range based on typical values
    score += min(30.0, wake_event.audio_energy * 10)
    
    # 4. Wake word confidence = +0-20 points
    score += wake_event.wake_confidence * 20
    
    # 5. Device type preference (tablets > phones > desktop)
    device_priority = {
        "tablet": 10,
        "smart_display": 10,
        "phone": 5,
        "desktop": 0,
    }
    score += device_priority.get(device.device_type, 0)
    
    # 6. Recent interaction bonus (+5 if used in last 5 minutes)
    if device.last_interaction_at:
        minutes_ago = (time.time() - device.last_interaction_at) / 60
        if minutes_ago < 5:
            score += 5.0
    
    return score


# Room adjacency for Charlotte house
ROOM_ADJACENCY = {
    "kitchen": ["living_room", "dining_room"],
    "living_room": ["kitchen", "office", "front_entry"],
    "office": ["living_room"],
    "master_bedroom": ["master_bathroom"],
    # ... etc
}
```

---

## 3. Device Location Tracking

### 3.1 Location Sources

| Source | Accuracy | Latency | Current/Future |
|--------|----------|---------|----------------|
| HA device_tracker (Lenovo) | Room-level | <1s | Current (V2) |
| ESPresense (BLE) | ~1m | <3s | Future |
| WiFi AP association | Room-level | <5s | Future |
| Manual assignment | Room-level | N/A | Current (V2) |

### 3.2 Home Assistant Device Tracker Integration

```python
# src/barnabee/devices/location.py

# HA entity mapping for Lenovo tablets
DEVICE_HA_ENTITIES = {
    "lenovo_kitchen": "device_tracker.lenovo_kitchen_tablet",
    "lenovo_living_room": "device_tracker.lenovo_living_room_tablet",
    "lenovo_office": "device_tracker.lenovo_office_tablet",
    # Add as tablets are deployed
}

async def get_device_location(device_id: str) -> Optional[str]:
    """Get device's current room from HA."""
    entity_id = DEVICE_HA_ENTITIES.get(device_id)
    if not entity_id:
        return None
    
    state = await ha_client.get_state(entity_id)
    if state and state.state != "unavailable":
        # State is typically the room/zone name
        return state.state
    
    return None


async def get_speaker_location(user_id: str) -> Optional[str]:
    """Get user's current location from HA person entity."""
    entity_id = f"person.{user_id}"
    
    state = await ha_client.get_state(entity_id)
    if state:
        # Person state is typically "home" or a zone name
        if state.state == "home":
            # Check for more specific room location from device tracker
            return await get_user_room_from_devices(user_id)
        return state.state
    
    return None
```

### 3.3 Future ESPresense Integration

```yaml
# ESPresence config (for future implementation)
# Each room has a BLE beacon/ESP32 for trilateration

esppresence:
  rooms:
    - id: kitchen
      beacons:
        - mac: "AA:BB:CC:DD:EE:01"
    - id: living_room
      beacons:
        - mac: "AA:BB:CC:DD:EE:02"
    # ...

# Family members wear BLE tags (Apple Watch, Tile, etc.)
# ESPresence calculates room presence based on RSSI
```

---

## 4. Arbitration Service

### 4.1 Redis-Based Coordination

```python
# src/barnabee/devices/arbitration.py

ARBITRATION_WINDOW_MS = 500  # Collect events for 500ms
ARBITRATION_TIMEOUT_MS = 200  # Device self-arbitrates if no response

class ArbitrationService:
    def __init__(self, redis: Redis):
        self.redis = redis
    
    async def register_wake_event(self, event: WakeWordEvent) -> ArbitrationResult:
        """Register a wake event and get arbitration result."""
        
        # Store event in Redis with short TTL
        event_key = f"wake:{event.event_id}:{event.device_id}"
        await self.redis.setex(
            event_key,
            2,  # 2 second TTL
            json.dumps(asdict(event)),
        )
        
        # Add to time-windowed set for this event cluster
        cluster_key = f"wake_cluster:{int(event.timestamp / 1000)}"  # 1-second buckets
        await self.redis.zadd(cluster_key, {event.device_id: event.timestamp})
        await self.redis.expire(cluster_key, 5)
        
        # Wait for arbitration window
        await asyncio.sleep(ARBITRATION_WINDOW_MS / 1000)
        
        # Get all devices that detected this wake word
        devices = await self.redis.zrange(cluster_key, 0, -1)
        
        if len(devices) == 1:
            # Only one device - it wins by default
            return ArbitrationResult(
                event_id=event.event_id,
                winner_device_id=event.device_id,
                reason="only_device",
                should_respond=(event.device_id == devices[0]),
            )
        
        # Multiple devices - run proximity scoring
        winner = await self.select_winner(event.event_id, devices)
        
        return ArbitrationResult(
            event_id=event.event_id,
            winner_device_id=winner,
            reason="proximity",
            should_respond=(event.device_id == winner),
        )
    
    async def select_winner(self, event_id: str, devices: list[str]) -> str:
        """Select the winning device based on proximity scoring."""
        
        # Get speaker location if possible
        # For now, use None - will improve with speaker ID
        speaker_location = None
        
        scores = {}
        for device_id in devices:
            event_key = f"wake:{event_id}:{device_id}"
            event_data = await self.redis.get(event_key)
            if not event_data:
                continue
            
            event = WakeWordEvent(**json.loads(event_data))
            device_info = await get_device_info(device_id)
            
            scores[device_id] = calculate_proximity_score(
                device_info,
                speaker_location,
                event,
            )
        
        # Return highest scoring device
        return max(scores, key=scores.get)
```

### 4.2 Device-Side Arbitration (Fallback)

```python
# Client-side code on each device
# Used when server is unreachable

async def handle_wake_word_local(event: WakeWordEvent) -> bool:
    """Local arbitration when server is unavailable."""
    
    # Try server first
    try:
        result = await asyncio.wait_for(
            api_client.register_wake_event(event),
            timeout=ARBITRATION_TIMEOUT_MS / 1000,
        )
        return result.should_respond
    except (asyncio.TimeoutError, ConnectionError):
        pass
    
    # Server unavailable - self-arbitrate
    # Simple rule: highest confidence wins
    # Broadcast our confidence, wait for others
    
    await broadcast_local_wake(event)
    await asyncio.sleep(0.1)  # 100ms window
    
    other_events = await collect_local_broadcasts()
    
    if not other_events:
        return True  # No competition, we respond
    
    # Highest confidence wins
    max_confidence = max(e.wake_confidence for e in other_events)
    return event.wake_confidence >= max_confidence
```

---

## 5. Service Availability & Degradation

### 5.1 Health Check Hierarchy

```
                    ┌─────────────────────┐
                    │   Full Capability   │
                    │   (All services UP) │
                    └──────────┬──────────┘
                               │
                    ┌──────────┴──────────┐
                    │  ManOfWar (Beast)   │ ◄── Primary GPU server
                    │  reachable?         │
                    └──────────┬──────────┘
                          YES  │  NO
                    ┌──────────┴──────────┐
                    │                     │
                    ▼                     ▼
            ┌───────────────┐    ┌───────────────┐
            │ Full Voice    │    │ Check         │
            │ Pipeline      │    │ BattleServer  │
            └───────────────┘    └───────┬───────┘
                                    YES  │  NO
                                ┌────────┴────────┐
                                │                 │
                                ▼                 ▼
                        ┌───────────────┐ ┌───────────────┐
                        │ Degraded Mode │ │ Local Only    │
                        │ (No local GPU)│ │ (HA direct)   │
                        └───────────────┘ └───────────────┘
```

### 5.2 Degradation Levels

| Level | Condition | Capabilities | User Feedback |
|-------|-----------|--------------|---------------|
| **Full** | All services UP | Full voice AI | Normal operation |
| **Degraded** | GPU unavailable | HA commands only, no conversation | "I can only do simple commands right now" |
| **Minimal** | Only HA reachable | Basic HA control via HA voice | Indicator light changes color |
| **Offline** | Nothing reachable | Nothing | Red indicator, verbal alert |

### 5.3 Health Monitor

```python
# src/barnabee/health/monitor.py

class ServiceHealthMonitor:
    def __init__(self):
        self.check_interval = 10  # seconds
        self.services = {
            "manofwar": {"url": "http://manofwar:8000/health", "critical": True},
            "battleserver": {"url": "http://battleserver:8000/health", "critical": False},
            "gpu_services": {"url": "http://manofwar:8001/health", "critical": False},
            "home_assistant": {"url": "http://homeassistant:8123/api/", "critical": True},
            "redis": {"check": self.check_redis, "critical": True},
        }
        self.status: dict[str, ServiceStatus] = {}
    
    async def run(self):
        """Continuously monitor service health."""
        while True:
            await self.check_all()
            await asyncio.sleep(self.check_interval)
    
    async def check_all(self):
        """Check all services and update status."""
        for name, config in self.services.items():
            try:
                if "url" in config:
                    async with httpx.AsyncClient() as client:
                        resp = await client.get(config["url"], timeout=5)
                        healthy = resp.status_code == 200
                elif "check" in config:
                    healthy = await config["check"]()
                else:
                    healthy = False
                
                self.status[name] = ServiceStatus(
                    name=name,
                    healthy=healthy,
                    last_check=datetime.utcnow(),
                    critical=config["critical"],
                )
            except Exception as e:
                self.status[name] = ServiceStatus(
                    name=name,
                    healthy=False,
                    last_check=datetime.utcnow(),
                    critical=config["critical"],
                    error=str(e),
                )
        
        # Broadcast status to devices
        await self.broadcast_status()
    
    def get_degradation_level(self) -> str:
        """Determine current degradation level."""
        critical_down = any(
            not s.healthy for s in self.status.values() if s.critical
        )
        gpu_down = not self.status.get("gpu_services", ServiceStatus()).healthy
        
        if critical_down:
            if not self.status.get("home_assistant", ServiceStatus()).healthy:
                return "offline"
            return "minimal"
        elif gpu_down:
            return "degraded"
        return "full"
    
    async def broadcast_status(self):
        """Push status to all connected devices."""
        level = self.get_degradation_level()
        await self.redis.publish("barnabee:health", json.dumps({
            "level": level,
            "services": {k: v.healthy for k, v in self.status.items()},
            "timestamp": datetime.utcnow().isoformat(),
        }))
```

### 5.4 Device-Side Degradation Handling

```python
# On each Barnabee device

class DegradationHandler:
    def __init__(self):
        self.current_level = "full"
        self.ha_client = HAClient()  # Direct HA connection as fallback
    
    async def on_health_update(self, status: dict):
        """Handle health status broadcast from server."""
        new_level = status["level"]
        
        if new_level != self.current_level:
            await self.transition_to(new_level)
            self.current_level = new_level
    
    async def transition_to(self, level: str):
        """Update device state for new degradation level."""
        
        if level == "full":
            # Normal operation
            self.set_indicator_color("green")
        
        elif level == "degraded":
            # GPU unavailable - show warning, limit to simple commands
            self.set_indicator_color("yellow")
            await self.speak("Just so you know, I can only handle simple commands right now.")
        
        elif level == "minimal":
            # Only HA available - switch to direct HA control
            self.set_indicator_color("orange")
            await self.speak("I'm having trouble reaching my brain. I can still control your home, but not much else.")
        
        elif level == "offline":
            # Nothing works
            self.set_indicator_color("red")
            await self.speak("I've lost connection to all my services. Check the network.")
    
    async def handle_command_degraded(self, utterance: str):
        """Handle commands when in degraded/minimal mode."""
        
        if self.current_level == "minimal":
            # Try to execute via direct HA connection
            # Limited pattern matching for common commands
            if "turn on" in utterance.lower() or "turn off" in utterance.lower():
                await self.execute_simple_ha_command(utterance)
            else:
                await self.speak("Sorry, I can only do simple home commands right now.")
```

---

## 6. Fallback Chain

### 6.1 Complete Fallback Strategy

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          FALLBACK CHAIN                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  User says: "Turn on the kitchen lights"                                    │
│                                                                              │
│  1. TRY: Full pipeline (ManOfWar/Beast)                                     │
│     │    STT → Intent → HA command → Response generation → TTS              │
│     │                                                                        │
│     └─── Timeout/Error ──┐                                                  │
│                          │                                                   │
│  2. TRY: BattleServer (if ManOfWar down)                                    │
│     │    Cloud STT → Intent → HA command → Template response → Cloud TTS    │
│     │                                                                        │
│     └─── Timeout/Error ──┐                                                  │
│                          │                                                   │
│  3. TRY: Direct HA with local intent matching                               │
│     │    Local pattern match → HA service call → Pre-recorded response      │
│     │                                                                        │
│     └─── Timeout/Error ──┐                                                  │
│                          │                                                   │
│  4. FAIL: Apologize and suggest manual control                              │
│           Pre-recorded: "I can't reach my services. Try the app."           │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 6.2 Pre-Recorded Fallback Responses

Generate these in Barnabee's voice at deployment time:

```python
FALLBACK_RESPONSES = {
    "degraded_mode": "I'm running in limited mode right now. I can handle simple home commands.",
    "offline_mode": "I've lost connection to my services. Try using the app for now.",
    "ha_only_mode": "My brain is temporarily offline, but I can still control your home.",
    "action_complete": "Done.",
    "action_failed": "I couldn't do that. Something's not working right.",
    "not_understood": "I didn't catch that. Try again?",
}
```

---

## 7. Device Registration

### 7.1 Device Schema (Addition to Area 01)

```sql
-- =============================================================================
-- DEVICES
-- =============================================================================

CREATE TABLE devices (
    id TEXT PRIMARY KEY,                        -- e.g., "lenovo_kitchen"
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    
    -- Device info
    name TEXT NOT NULL,                         -- Human-readable name
    device_type TEXT NOT NULL,                  -- tablet, phone, desktop, smart_display
    
    -- Location
    location TEXT,                              -- Room assignment
    ha_entity_id TEXT,                          -- HA device_tracker entity
    
    -- Capabilities
    has_microphone INTEGER NOT NULL DEFAULT 1,
    has_speaker INTEGER NOT NULL DEFAULT 1,
    has_display INTEGER NOT NULL DEFAULT 1,
    
    -- Status
    status TEXT NOT NULL DEFAULT 'online',      -- online, offline, degraded
    last_seen TEXT,
    last_interaction_at TEXT,
    
    -- Wake word
    wake_word_sensitivity REAL NOT NULL DEFAULT 0.5,
    
    CHECK (device_type IN ('tablet', 'phone', 'desktop', 'smart_display', 'smart_speaker'))
);

CREATE INDEX idx_devices_location ON devices(location);
CREATE INDEX idx_devices_status ON devices(status);
```

### 7.2 Device Registration API

```python
@router.post("/devices/register")
async def register_device(device: DeviceRegistration) -> Device:
    """Register or update a device."""
    return await device_repo.upsert(device)

@router.post("/devices/{device_id}/heartbeat")
async def device_heartbeat(device_id: str) -> DeviceStatus:
    """Update device last_seen and get current status."""
    await device_repo.update_last_seen(device_id)
    return DeviceStatus(
        degradation_level=health_monitor.get_degradation_level(),
        services=health_monitor.status,
    )
```

---

## 8. Implementation Checklist

### Arbitration Service
- [ ] Redis-based event coordination
- [ ] Proximity scoring algorithm
- [ ] Winner broadcast mechanism
- [ ] Device-side fallback arbitration

### Location Tracking
- [ ] HA device_tracker integration
- [ ] Room adjacency map
- [ ] Person entity location lookup
- [ ] (Future) ESPresense integration stub

### Health Monitoring
- [ ] Service health checks
- [ ] Degradation level calculation
- [ ] Status broadcast to devices
- [ ] Device-side degradation handling

### Fallback Chain
- [ ] BattleServer fallback path
- [ ] Direct HA fallback
- [ ] Pre-recorded response generation
- [ ] Local pattern matching for simple commands

### Device Management
- [ ] Device registration API
- [ ] Heartbeat endpoint
- [ ] Device status dashboard

---

## 9. Acceptance Criteria

1. **Single responder:** Only one device speaks per wake word (observed)
2. **<100ms arbitration:** Winner selected within 100ms of wake word
3. **Correct proximity:** Device in same room as speaker wins 95%+ of the time
4. **Graceful degradation:** Visible indicator when in degraded mode
5. **HA fallback works:** Simple commands execute when GPU services down
6. **Offline detection:** Red indicator and verbal alert within 30 seconds of total outage

---

**End of Area 14: Multi-Device Coordination**
