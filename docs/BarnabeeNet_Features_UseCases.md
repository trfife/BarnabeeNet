# BarnabeeNet Features & Use Cases

**Document Version:** 1.1  
**Last Updated:** January 17, 2026  
**Author:** Thom Fife  
**Purpose:** Comprehensive catalog of BarnabeeNet capabilities, features, and practical use cases

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Core Feature Categories](#core-feature-categories)
3. [Spatial Awareness System](#spatial-awareness-system)
4. [Interaction Modes](#interaction-modes)
5. [Agent Capabilities](#agent-capabilities)
6. [Privacy & Security Features](#privacy--security-features)
7. [Per-Listener Response Adaptation](#per-listener-response-adaptation)
8. [Use Case Categories](#use-case-categories)
9. [Family & Household Use Cases](#family--household-use-cases)
10. [Personal Productivity Use Cases](#personal-productivity-use-cases)
11. [Wellness & Health Use Cases](#wellness--health-use-cases)
12. [Proactive Intelligence Use Cases](#proactive-intelligence-use-cases)
13. [Proxy Mode Use Cases](#proxy-mode-use-cases)
14. [Guest & Hospitality Use Cases](#guest--hospitality-use-cases)
15. [Advanced "Superhuman" Use Cases](#advanced-superhuman-use-cases)
16. [Example Interaction Flows](#example-interaction-flows)
17. [Feature Comparison Matrix](#feature-comparison-matrix)

---

## Executive Summary

BarnabeeNet transforms home automation from reactive device control into proactive, personalized assistance. Unlike commercial assistants (Alexa, Google Home, Siri), BarnabeeNet is designed for:

| Dimension | Commercial Assistants | BarnabeeNet |
|-----------|----------------------|-------------|
| **Privacy** | Cloud-dependent, data harvested | Local-first, data sovereignty |
| **Personalization** | Generic profiles | Per-person speaker recognition |
| **Proactivity** | Limited notifications | Context-aware anticipation |
| **Memory** | Session-based | Long-term episodic/semantic |
| **Modality** | Voice + screen | Voice + AR + wearable + gesture |
| **Intelligence** | Command-response | Multi-turn conversation + reasoning |
| **Evolution** | Vendor-controlled | Self-improving via Evolver Agent |
| **Spatial Awareness** | Room-agnostic | Room graph with context routing |
| **Response Adaptation** | One-size-fits-all | Per-listener vocabulary and tone |

### Feature Highlights

```
┌─────────────────────────────────────────────────────────────────┐
│                    BARNABEENET CAPABILITIES                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  🎯 CORE                    🧠 INTELLIGENCE                      │
│  ├─ <500ms voice response   ├─ Speaker recognition              │
│  ├─ Multi-room audio        ├─ Intent understanding             │
│  ├─ Device control          ├─ Context awareness                │
│  └─ Scene activation        └─ Long-term memory                 │
│                                                                  │
│  👁️ MULTI-MODAL              🔮 PROACTIVE                        │
│  ├─ AR glasses overlay      ├─ Safety alerts                    │
│  ├─ Wearable gestures       ├─ Convenience reminders            │
│  ├─ Touch dashboards        ├─ Pattern detection                │
│  └─ Bluetooth headset       └─ Automation suggestions           │
│                                                                  │
│  🛡️ PRIVACY                  📈 SELF-IMPROVING                   │
│  ├─ Local processing        ├─ Prompt optimization              │
│  ├─ Privacy zones           ├─ Model benchmarking               │
│  ├─ Per-user permissions    ├─ Code enhancement                 │
│  └─ Audit trail             └─ Pattern learning                 │
│                                                                  │
│  👥 FAMILY                   🎭 PROXY MODE                       │
│  ├─ Kid-safe controls       ├─ Meeting attendance               │
│  ├─ Guest mode              ├─ Voice presence                   │
│  ├─ Conflict resolution     ├─ Summarization                    │
│  └─ Shared calendars        └─ Action items                     │
│                                                                  │
│  📍 SPATIAL AWARENESS        🎚️ ADAPTIVE RESPONSES               │
│  ├─ Room graph model        ├─ Age-appropriate vocabulary       │
│  ├─ Context-aware routing   ├─ Expertise-level matching         │
│  ├─ Multi-room continuity   ├─ Guest mode simplification        │
│  └─ Privacy zone respect    └─ Multi-listener detection         │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Core Feature Categories

### 1. Voice Control & Understanding

| Feature | Description | Latency Target |
|---------|-------------|----------------|
| **Wake Word Detection** | "Hey Barnabee" or custom phrase | 0ms (always listening) |
| **Speech-to-Text** | Local transcription via Faster-Whisper | <150ms |
| **Intent Classification** | Understand command purpose | <20ms |
| **Multi-Turn Dialogue** | Maintain conversation context | N/A |
| **Clarification** | Ask follow-up questions | N/A |
| **Confirmation** | Verify high-risk actions | N/A |

**Example Commands**:
```
"Hey Barnabee, turn on the living room lights"
"Set them to 50%"
"Actually, make them warmer"
"What's the temperature in here?"
"Turn on the fireplace if it's below 68"
```

### 2. Device Control

| Capability | Supported Devices | Example |
|------------|------------------|---------|
| **Lighting** | Hue, LIFX, Z-Wave, Zigbee | "Dim the kitchen to 30%" |
| **Climate** | Nest, Ecobee, Z-Wave thermostats | "Set temperature to 72" |
| **Locks** | August, Schlage, Yale | "Is the front door locked?" |
| **Garage** | MyQ, Chamberlain | "Close the garage" |
| **Media** | Sonos, Chromecast, Apple TV | "Play jazz in the office" |
| **Shades** | Lutron, IKEA, Hunter Douglas | "Open the bedroom blinds" |
| **Appliances** | Smart plugs, switches | "Turn off the coffee maker" |
| **Security** | Ring, Wyze, Ubiquiti | "Show me the front door camera" |

### 3. Information Retrieval

| Query Type | Source | Example |
|------------|--------|---------|
| **Time/Date** | Local | "What time is it?" |
| **Weather** | External API | "Will it rain today?" |
| **Calendar** | Personal calendar integration | "What's on my schedule?" |
| **Home State** | Home Assistant | "Are any windows open?" |
| **Personal Facts** | Semantic memory | "When is Mom's birthday?" |
| **General Knowledge** | LLM | "How do I remove a wine stain?" |

### 4. Routine & Scene Activation

| Routine Type | Trigger | Actions |
|--------------|---------|---------|
| **Good Morning** | Voice / Schedule / Motion | Lights on, blinds open, news brief, coffee |
| **Leaving Home** | Voice / Geofence | Lights off, thermostat eco, doors locked |
| **Movie Time** | Voice | Lights dim, shades close, TV on |
| **Bedtime** | Voice / Schedule | Lights off, doors locked, alarm set |
| **Deep Work** | Voice | DND, lights optimal, music focus |
| **Guest Mode** | Voice / Calendar | Simplified automations, guest WiFi |

---

## Spatial Awareness System

BarnabeeNet maintains a real-time **Room Graph**—a spatial model of your home that tracks occupancy, adjacency relationships, acoustic reach, and privacy boundaries. This enables context-aware decisions about where and when to interact.

### Room Graph Model

```
┌─────────────────────────────────────────────────────────────────┐
│                       ROOM GRAPH TOPOLOGY                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐      │
│  │ GARAGE  │────│ KITCHEN │────│ LIVING  │────│ OFFICE  │      │
│  │ (common)│    │ (common)│    │ (common)│    │ (common)│      │
│  └────┬────┘    └────┬────┘    └────┬────┘    └─────────┘      │
│       │              │              │                           │
│       │         ┌────┴────┐        │                           │
│       │         │ HALLWAY │────────┘                           │
│       │         └────┬────┘                                    │
│       │              │                                          │
│  ┌────┴────┐    ┌────┴────────────────────────┐                │
│  │ MASTER  │    │     KIDS' HALLWAY           │                │
│  │ BEDROOM │    └──┬─────┬─────┬─────┬───────┘                │
│  │ (private)│      │     │     │     │                         │
│  └─────────┘    ┌──┴──┐┌─┴──┐┌─┴──┐┌─┴──┐                     │
│                 │PENNY││XAND││ZACH││VIOL│  (privacy zones)     │
│                 └─────┘└────┘└────┘└────┘                      │
│                                                                  │
│  Legend: ─── = adjacent, (zone) = privacy level                 │
└─────────────────────────────────────────────────────────────────┘
```

| Attribute | Description | Example |
|-----------|-------------|---------|
| **Adjacency** | Physical proximity relationships | Kitchen → Living Room → Office |
| **Acoustic Reach** | Whether audio output in one room is audible in another | Office speaker audible in hallway |
| **Occupancy State** | Who is currently in each room (via presence sensors) | Thom in office, kids in living room |
| **Activity Context** | Inferred current activity | "Working" (office, weekday, 9am-5pm) |
| **Privacy Level** | Zone classification | Common area vs. private room |

### Room-Aware Notification Routing

BarnabeeNet evaluates multiple factors before delivering any proactive notification:

| Factor | Weight | Description |
|--------|--------|-------------|
| **Relevance Distance** | High | Is the notification relevant to the room where the target user is located? |
| **Acoustic Isolation** | Medium | Will the notification disturb others in adjacent rooms? |
| **Activity Disruption** | High | Is the user in a focus-sensitive context (work, sleep, conversation)? |
| **Urgency Override** | Critical | Safety alerts bypass all filters |

**Routing Decision Tree:**

1. **Safety/Security alerts**: Always deliver immediately to nearest speaker + wearables
2. **User-relevant convenience**: Deliver to user's current room only
3. **Household-wide info**: Deliver to common areas when occupied
4. **Low-priority reminders**: Queue for opportunistic delivery or wearable-only

### Privacy-Aware Context Behavior

| Context | Location Inference | Barnabee Behavior |
|---------|-------------------|-------------------|
| **Work Hours (9-5) + Office** | User is working | No non-urgent proactive audio; route to watch/AR only |
| **Evening + Living Room** | Family time | Household-relevant notifications OK |
| **Bedroom + Late Night** | Sleeping/winding down | Quiet hours enforced; emergencies only |
| **Bathroom** | Private moment | No audio output ever; presence-only tracking |
| **Kitchen + Mealtime** | Cooking/eating | Timer and cooking-related notifications only |

**Example: Work Hour Privacy**
- When Thom is in the office during calendar-marked work hours:
  - Kitchen reminders ("Oven preheated") → Queued until he leaves office OR sent to watch only
  - Package delivery → Watch haptic + AR notification (no audio)
  - Calendar meeting in 5 min → Audio announcement allowed (work-relevant)

### Multi-Room Conversation Continuity

BarnabeeNet tracks conversation state across rooms, enabling seamless transitions:

**Handoff Triggers:**
- Motion detected in new room + no motion in previous room for 30s
- Explicit: "Hey Barnabee, I'm moving to the kitchen"
- Wearable location inference (if enabled)

**State Preserved:**
- Conversation context (last 5 turns)
- Pending actions/confirmations
- Active timers and reminders
- Temporary session preferences

**Example Flow:**
```
[Office]
Thom: "Hey Barnabee, what's for dinner?"
Barnabee: "You have chicken thawing. Want me to suggest recipes?"
Thom: "Yes"

[Thom walks to kitchen - motion detected]

[Kitchen - 30 seconds later]
Barnabee: "Welcome to the kitchen. I found three recipes for your 
          chicken—lemon herb, stir fry, or parmesan. Which sounds good?"
```

**Privacy Boundary:** Conversation does NOT follow into privacy zones (bathrooms, children's rooms)

### Spatial Awareness Scenarios

**Scenario 1: Kitchen Timer, Office Worker**
- Elizabeth sets a 20-minute oven timer from the kitchen
- Elizabeth goes to the office to work
- At 5 minutes remaining: Watch haptic only (no office audio disruption)
- At 1 minute remaining: Watch haptic + brief office announcement if not in a meeting

**Scenario 2: Kid's Bedtime, Parent in Living Room**
- 8:00 PM bedtime routine triggers
- Announcement plays in kids' hallway and common areas
- NO announcement in Thom's office (working) or master bedroom
- Parents receive watch notification: "Bedtime routine started"

**Scenario 3: Guest Arrives, Family Distributed**
- Doorbell rings, guest detected
- Thom (office): Watch notification + AR popup
- Elizabeth (kitchen): Audio announcement "Someone's at the door"
- Kids (bedrooms): No notification (privacy zone)

---

## Interaction Modes

### Voice Interaction

**Primary Interface**: Natural language voice commands

```
┌─────────────────────────────────────────────────────────────────┐
│                      VOICE INTERACTION FLOW                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  User: "Hey Barnabee"                                           │
│         │                                                        │
│         ▼                                                        │
│  [Wake Word Detection] ──► [Audio Capture] ──► [STT]            │
│                                                   │              │
│                                                   ▼              │
│  [Speaker ID] ◄───────────────────────────────── [Transcription]│
│       │                                           │              │
│       ▼                                           ▼              │
│  [User Context]                              [Meta Agent]        │
│       │                                           │              │
│       └──────────────► [Specialized Agent] ◄─────┘              │
│                               │                                  │
│                               ▼                                  │
│                        [Response Generation]                     │
│                               │                                  │
│                               ▼                                  │
│                        [TTS] ──► [Audio Output]                 │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Voice Features**:
- **Speaker Recognition**: Identifies who is speaking (8 family members)
- **Multi-Room**: Responds on nearest speaker or follows user
- **Private Mode**: Routes to Bluetooth headset for confidential responses
- **Emotional Detection**: Adjusts tone based on detected stress/mood
- **Streaming TTS**: Begins speaking before full response is generated

### AR Glasses Interaction (Even Realities G1)

**Use Cases**:
- Ambient notifications without screen dependency
- Real-time translation overlays
- Navigation/wayfinding in home
- Device status at a glance
- Teleprompter for Proxy Mode

**Interaction Patterns**:

| Trigger | Display | Duration |
|---------|---------|----------|
| Proactive alert | Icon + short text | 5 seconds |
| Voice response | Scrolling text | Until dismissed |
| Navigation | Arrow overlay | Continuous |
| Device status | Icon grid | On request |

**Example AR Overlays**:
```
┌────────────────────────────────────────┐
│  🚪 Front door unlocked                │
│  └─ Tap to lock                        │
└────────────────────────────────────────┘

┌────────────────────────────────────────┐
│  📦 Package detected at front door     │
│  └─ UPS • 2:34 PM                      │
└────────────────────────────────────────┘

┌────────────────────────────────────────┐
│  🌡️ Office: 72°F                       │
│  💡 Lights: 80%                        │
│  🔊 Music: Lo-Fi Beats                 │
└────────────────────────────────────────┘
```

### Wearable Interaction (Amazfit Cheetah Pro)

**Input Methods**:

| Input | Detection | Use Case |
|-------|-----------|----------|
| **Crown Twist** | Rotation sensor | Select Yes/No, adjust values |
| **Button Click** | Physical press | Confirm, dismiss, trigger action |
| **Double-Tap** | Accelerometer | Quick toggle (lights, music) |
| **Shake** | Accelerometer | Dismiss notification, cancel |
| **Long Press** | Button hold | Emergency/panic, undo last |

**Output Methods**:

| Output | Type | Use Case |
|--------|------|----------|
| **Haptic Pulse** | Vibration pattern | Silent alert |
| **Screen Notification** | Visual | Choice prompt, status |
| **LED Flash** | Light | Urgent alert |

**Choice Prompts**:
```
┌─────────────────────────┐
│  🚪 Garage door open    │
│     10 minutes          │
│                         │
│  [Close]    [Ignore]    │
│   Twist←      Twist→    │
└─────────────────────────┘

┌─────────────────────────┐
│  🌡️ Lower temperature?  │
│     Currently 74°F      │
│                         │
│  Crown: Select temp     │
│  Button: Confirm        │
└─────────────────────────┘
```

### Touch Dashboard Interaction (ThinkSmart Views)

**Dashboard Locations**:

| Location | Primary Function | Key Widgets |
|----------|-----------------|-------------|
| Kitchen | Family hub | Calendar, timers, recipes, intercom |
| Office | Work control | Meeting status, focus mode, device quick-access |
| Bedroom | Ambient display | Clock, weather, gentle wake controls |
| Living Room | Entertainment | Media controls, lighting scenes |

**Dashboard Features**:
- Voice-activated (satellite mode)
- Touch controls for common actions
- Camera for video calls/intercom
- Proximity-aware display dimming
- Guest-accessible simplified view

---

## Agent Capabilities

### Instant Response Agent

**Purpose**: Sub-5ms responses for predictable queries

| Pattern | Response | Example |
|---------|----------|---------|
| Time queries | `datetime.now()` | "It's 3:45 PM" |
| Date queries | `datetime.today()` | "Today is Friday, January 16th" |
| Greetings | Contextual + name | "Good afternoon, Thom" |
| Simple math | `safe_eval()` | "15 times 23 is 345" |
| Status check | Random friendly | "I'm doing great, thanks for asking!" |

### Action Agent

**Purpose**: Execute device control commands

**Capabilities**:
- Single device commands: "Turn on the lamp"
- Multi-device commands: "Turn off all the lights"
- Conditional execution: "If the door is unlocked, lock it"
- Relative adjustments: "Make it warmer" / "Dim the lights"
- Scene activation: "Activate movie mode"
- Scheduled actions: "Turn off the porch light at midnight"

**Output Schema**:
```json
{
  "action": "call_service",
  "domain": "light",
  "service": "turn_on",
  "target": {
    "entity_id": ["light.living_room", "light.kitchen"]
  },
  "data": {
    "brightness_pct": 80,
    "color_temp_kelvin": 3000
  },
  "confirmation": "Turning on living room and kitchen lights to 80%"
}
```

### Interaction Agent

**Purpose**: Complex conversations and reasoning

**Capabilities**:
- Multi-turn dialogue with context retention
- Personal knowledge retrieval from memory
- Complex reasoning and analysis
- Creative responses (stories, jokes, explanations)
- Emotional awareness and adaptive tone
- Web search integration (when enabled)

**Example Complex Interaction**:
```
User: "I'm planning a dinner party for Saturday"
Barnabee: "That sounds fun! How many guests are you expecting?"
User: "About 8 people"
Barnabee: "Got it. I can help you prepare. Would you like me to:
           - Add it to the family calendar?
           - Set up a 'dinner party' lighting scene?
           - Remind you to clean on Friday?"
User: "All of that, and remind me to buy flowers"
Barnabee: "Done! I've created a Saturday dinner party event,
           set up warm lighting at 6 PM, and added reminders
           for cleaning Friday and flowers Saturday morning."
```

### Memory Agent

**Purpose**: Store and retrieve personal knowledge

**Memory Types**:

| Type | Retention | Example |
|------|-----------|---------|
| **Working** | 10 min session | Current conversation context |
| **Episodic** | 30 days | "Last week you asked about flights to Denver" |
| **Semantic** | Indefinite | "Thom prefers 68°F when working" |
| **Procedural** | Indefinite | "Kids' bedtime routine starts at 8 PM" |

**Memory Operations**:
- **Store**: Automatically extract facts from conversations
- **Retrieve**: Query by semantic similarity
- **Consolidate**: Nightly batch processing for pattern detection
- **Forget**: Explicit deletion on request

### Proactive Agent

**Purpose**: Unsolicited helpful notifications

**Trigger Categories**:

| Category | Examples | Urgency |
|----------|----------|---------|
| **Safety** | Door open at night, smoke detected, water leak | High |
| **Security** | Unusual motion, unknown person, failed lock | High |
| **Convenience** | Package arrived, calendar reminder, weather change | Medium |
| **Efficiency** | Energy waste detected, automation suggestion | Low |
| **Wellness** | Hydration reminder, break suggestion, sleep time | Low |

**Rate Limiting**:
- Maximum 3 non-urgent notifications per hour
- No proactive audio in children's rooms
- Quiet hours respect (10 PM - 7 AM default)
- User can snooze categories

### Evolver Agent

**Purpose**: System self-improvement

**Capabilities**:
- **Prompt Refinement**: A/B test prompt variants
- **Model Benchmarking**: Compare LLM performance via Azure ML
- **Code Enhancement**: Propose PRs for agent improvements
- **Pattern Learning**: Discover behavioral patterns for automations

**Boundaries**:
- Changes require user approval
- No external API modifications
- Scoped to internal optimization only
- All proposals logged for audit

---

## Privacy & Security Features

### Privacy Zones

| Zone | Constraints | Rooms |
|------|-------------|-------|
| **Children's Rooms** | No audio, no memory, no proactive | Penelope, Xander, Zachary, Viola bedrooms |
| **Bathrooms** | No audio, presence-only sensors | Master bath, kids' bath |
| **Common Areas** | Full features enabled | Living room, kitchen, office, garage |

### Permission System

| User Type | Capabilities |
|-----------|-------------|
| **Admin** (Thom, Elizabeth) | All commands, configuration, security |
| **Adult** | Device control, personal queries, scenes |
| **Teen** | Limited device control, no security commands |
| **Child** | Information queries, entertainment only |
| **Guest** | Pre-approved commands only |

**Permission Examples**:
```yaml
thom:
  permissions:
    - all_devices
    - security_controls
    - configuration
    - memory_access

penelope:  # Teen
  permissions:
    - bedroom_devices
    - common_area_lights
    - entertainment
  restrictions:
    - no_door_locks
    - no_thermostat_override
    - no_security_cameras

guest:
  permissions:
    - guest_room_lights
    - common_area_lights
    - entertainment
  restrictions:
    - no_door_locks
    - no_security
    - no_memory_storage
```

### Data Flow Controls

| Data Type | Local | Cloud (Optional) |
|-----------|-------|------------------|
| Raw audio | ✅ Processed only | ❌ Never |
| Transcription | ✅ Stored | ✅ For complex queries |
| Speaker embeddings | ✅ Only | ❌ Never |
| Device commands | ✅ Executed | ❌ Never |
| Personal facts | ✅ Stored | ❌ Never |
| Children's data | ✅ Never stored | ❌ Never |

### Audit Trail

Every interaction logged with:
- Timestamp
- Speaker identification + confidence
- Transcription
- Intent classification
- Agent invoked
- Actions executed
- Cloud API usage (if any)
- Privacy zone

---

## Per-Listener Response Adaptation

BarnabeeNet tailors every response based on who is listening. This goes beyond permissions to include vocabulary, complexity, emotional tone, and content filtering.

### Listener Profile Attributes

| Attribute | Values | Effect on Response |
|-----------|--------|-------------------|
| **Age Category** | Adult, Teen, Child (5-12), Young Child (<5) | Vocabulary complexity, content filtering |
| **Expertise Level** | Technical, Standard, Simplified | Explanation depth for home automation |
| **Communication Style** | Direct, Conversational, Playful | Tone and personality expression |
| **Notification Preference** | Audio, Visual, Haptic, Combined | Delivery method selection |
| **Content Restrictions** | None, Moderate, Strict | Filtering of news, media recommendations |

### Response Differentiation Examples

**Query: "What's the weather like today?"**

| Listener | Response |
|----------|----------|
| **Thom (Adult/Technical)** | "Currently 42°F with 60% humidity. High of 55°F, low of 38°F. 30% chance of rain after 3 PM. Winds from the northwest at 12 mph." |
| **Elizabeth (Adult/Conversational)** | "It's a bit chilly this morning at 42 degrees. It should warm up to the mid-fifties later. You might want a light jacket, and there's a small chance of rain this afternoon." |
| **Penelope (Teen)** | "It's 42 degrees now, getting up to 55. Might rain later—maybe grab a jacket?" |
| **Xander (Child, 8)** | "It's cold outside! You'll need a warm coat. It might rain after school." |
| **Viola (Young Child, 5)** | "Brrr, it's chilly! Wear your warm coat today, sweetie!" |

**Query: "Turn on the living room lights"**

| Listener | Response |
|----------|----------|
| **Adult** | "Done." (minimal confirmation) |
| **Child** | "I turned on the lights for you!" (encouraging tone) |
| **Guest** | "The living room lights are now on." (polite, clear) |

**Query: "Why is it so hot in here?"**

| Listener | Response |
|----------|----------|
| **Thom (Technical)** | "The thermostat is set to 74°F, and the HVAC has been running in heat mode for 20 minutes. Current temperature is 73°F. Would you like me to lower the setpoint?" |
| **Elizabeth (Conversational)** | "It does feel warm! The heat's been running and it's up to 73. Want me to turn it down a bit?" |
| **Child** | "It is pretty warm! Do you want me to make it cooler?" |

### Guest Mode Behavior

Guests receive a simplified, privacy-respecting experience:

| Capability | Guest Access | Reason |
|------------|--------------|--------|
| **Basic device control** | ✅ Guest room + common areas | Hospitality convenience |
| **Information queries** | ✅ General only | No access to family data |
| **Memory storage** | ❌ | Privacy protection |
| **Personal preferences** | ❌ | Session-only, no persistence |
| **Security commands** | ❌ | Safety restriction |
| **Family calendar** | ❌ | Privacy protection |
| **Proactive suggestions** | ❌ | Minimal interruption |

**Guest Response Style:**
- Always polite and slightly formal
- Never assumes familiarity or prior context
- Offers help proactively upon arrival
- No family-specific information disclosed

**Example:**
```
[Unknown speaker detected]
Barnabee: "Hello! I'm Barnabee, the home assistant. I can help with 
          lights, temperature, and entertainment in common areas. 
          Just say 'Hey Barnabee' if you need anything."
```

**Temporary Guest Registration:**
- Household admin can say: "Hey Barnabee, we have a guest named Marcus staying for the weekend"
- Guest receives temporary profile with limited permissions
- Automatic expiration after specified duration

### Age-Appropriate Content Filtering

| Content Type | Adult | Teen | Child | Young Child |
|--------------|-------|------|-------|-------------|
| News headlines | Full | Filtered for violence | Weather/sports only | None |
| Music recommendations | All | Age-appropriate | Kid-friendly | Children's music |
| Movie suggestions | All | PG-13 and below | G/PG only | G only |
| Definitions/explanations | Full | Full | Simplified | Very simple |
| Health information | Detailed | General | Redirect to parent | Redirect to parent |

**Dynamic Filtering:**
- When multiple listeners present, apply most restrictive profile
- "Hey Barnabee, what's on the news?" with child present → "There's some weather news and sports scores. Would you like to hear those?"

### Multi-Listener Detection

When multiple people are in the same room, BarnabeeNet:
1. Identifies the primary speaker (who asked the question)
2. Detects other occupants via presence sensors
3. Applies the most appropriate content restrictions
4. Maintains age-appropriate vocabulary for youngest present

**Example:**
```
[Living Room - Xander (8) and Viola (5) present]

Xander: "Hey Barnabee, how do volcanoes work?"

LISTENER ANALYSIS:
├─ Primary Speaker: Xander (speaker ID match)
├─ Age Category: Child (8)
├─ Others Present: Viola (5), via room occupancy
├─ Content Level: YOUNGEST_PRESENT = 5 years old
└─ Response Style: Very simple, engaging

Barnabee: "Great question! A volcano is like a big mountain with 
          a hole in the top. Deep underground, it's super hot—so hot 
          that rocks melt into gooey stuff called lava. Sometimes the 
          lava pushes up and comes out the top like a soda bottle that 
          got shaken up! Whoosh!"
```

---

## Use Case Categories

BarnabeeNet supports use cases across multiple life domains:

```
┌─────────────────────────────────────────────────────────────────┐
│                    USE CASE TAXONOMY                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │   FAMILY    │  │ PRODUCTIVITY│  │  WELLNESS   │              │
│  ├─────────────┤  ├─────────────┤  ├─────────────┤              │
│  │ Coordination│  │ Focus modes │  │ Habit track │              │
│  │ Kid safety  │  │ Meetings    │  │ Reminders   │              │
│  │ Chores      │  │ Task manage │  │ Mood support│              │
│  │ Scheduling  │  │ Time boxing │  │ Sleep       │              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
│                                                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │  PROACTIVE  │  │   PROXY     │  │    GUEST    │              │
│  ├─────────────┤  ├─────────────┤  ├─────────────┤              │
│  │ Safety alert│  │ Call attend │  │ Temp access │              │
│  │ Convenience │  │ Summarize   │  │ Simple mode │              │
│  │ Suggestions │  │ Voice clone │  │ Hospitality │              │
│  │ Patterns    │  │ Action items│  │ Check-out   │              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
│                                                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │  ADVANCED   │  │    ECO      │  │ RELATIONSHIP│              │
│  ├─────────────┤  ├─────────────┤  ├─────────────┤              │
│  │ Idea incub  │  │ Energy opt  │  │ Date remind │              │
│  │ Dream interp│  │ Carbon track│  │ Gift suggest│              │
│  │ Ethics audit│  │ Waste alert │  │ Connection  │              │
│  │ Memory play │  │ Solar manage│  │ Conflict res│              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Family & Household Use Cases

### UC-F01: Morning Routine Coordination

**Scenario**: Weekday morning with 4 kids getting ready for school

**Trigger**: 6:30 AM weekday schedule

**Flow**:
1. Gradually brighten master bedroom lights over 10 minutes
2. Start coffee maker
3. After motion detected in kitchen, play weather and calendar brief
4. At 7:00 AM, announce "15 minutes until bus" in kids' common areas
5. At 7:10 AM, announce "5 minutes until bus"
6. If front door hasn't opened by 7:20, alert parents

**Voice Commands**:
```
"Hey Barnabee, what's on the kids' schedule today?"
"Remind Penelope about her soccer gear"
"Is everyone's lunch packed?" (triggers checklist)
```

### UC-F02: Homework Time Management

**Scenario**: After-school homework period for multiple children

**Trigger**: 4:00 PM weekday or voice command

**Flow**:
1. Activate "Homework Mode" scene: TV off, focused lighting, no entertainment
2. Set 25-minute Pomodoro timer per child
3. Provide break notifications with stretch suggestions
4. Track time spent per subject (optional voice logging)
5. Notify parents when homework time complete

**Voice Commands**:
```
"Hey Barnabee, start homework time"
"Set a timer for 20 minutes for Xander's math"
"How much homework time has Zachary done?"
"Homework time is over" (restores entertainment access)
```

### UC-F03: Bedtime Routine

**Scenario**: Structured bedtime for children of different ages

**Trigger**: Voice command or schedule (tiered by child age)

**Flow**:
1. 7:30 PM: "Bedtime in 30 minutes" announcement for younger kids
2. 7:45 PM: Dim common area lights to 30%
3. 8:00 PM: Turn off entertainment, activate nightlights
4. 8:15 PM: "Lights out in 5 minutes" in kids' hallway
5. 8:20 PM: All kids' room lights off, sound machines on
6. Older kids get extended timeline (9:00/9:30 PM)

**Voice Commands**:
```
"Hey Barnabee, start bedtime for the little ones"
"Penelope can stay up until 9:30 tonight"
"Is everyone in bed?" (checks motion sensors)
```

### UC-F04: Chore Tracking & Gamification

**Scenario**: Encourage kids to complete household chores

**Trigger**: Voice command or schedule

**Features**:
- Voice-logged chore completion
- Point system tracked in memory
- Weekly rewards announced
- Fair rotation tracking

**Voice Commands**:
```
"Hey Barnabee, Viola finished setting the table" → +5 points
"Whose turn is it to take out the trash?"
"How many chore points does Xander have?"
"What chores are left for today?"
```

### UC-F05: Family Calendar Coordination

**Scenario**: Managing complex schedules for 6 family members

**Features**:
- Conflict detection across calendars
- Transportation coordination
- Reminder distribution to relevant family members
- "What's happening" summaries

**Voice Commands**:
```
"Hey Barnabee, what's happening this weekend?"
"Does anyone have a conflict with Sunday at 3?"
"Add Zachary's birthday party to Saturday at 2"
"Remind Elizabeth about Penelope's recital tomorrow"
```

### UC-F06: Thermostat Negotiation

**Scenario**: Family members prefer different temperatures

**Trigger**: Conflicting temperature requests

**Flow**:
1. Detect who is present in each zone via presence sensors
2. Apply preference weighting (adults > kids, majority rule)
3. If conflict persists, suggest compromise
4. Learn patterns over time for proactive adjustment

**Voice Commands**:
```
"Hey Barnabee, it's too cold in here"
  → Barnabee: "I see Elizabeth prefers it warmer. The office is currently
     68°F, which Thom set earlier. Should I raise it to 70°F as a compromise?"
```

### UC-F07: Work-From-Home Boundary Management

**Scenario**: Thom works from home and needs protection from household interruptions

**Spatial Awareness Features Used**:
- Office presence detection
- Calendar work hour integration
- Kitchen/laundry event suppression

**Flow**:
1. Thom enters office during calendar work block
2. BarnabeeNet sets office to "focus mode" automatically
3. Kitchen events (oven timer, dishwasher done) → Watch only, no audio
4. Kids' requests for non-urgent help → "Dad's working, try again later or ask Mom"
5. Urgent events (safety, security, family emergency) → Always delivered

**Voice Commands**:
```
"Hey Barnabee, I need to focus for the next 2 hours"
  → Extends focus mode beyond calendar, suppresses all non-urgent notifications

"Hey Barnabee, I'm available now"
  → Ends focus mode, delivers queued notifications: "While you were working: 
     dishwasher finished, you got a package, and Elizabeth asked about dinner plans"
```

**Spatial Awareness Example**:
- Oven timer set in kitchen goes off
- System checks: Who set the timer? Elizabeth. Where is Elizabeth? Living room.
- Announcement plays in living room, NOT in Thom's office
- If Elizabeth had gone to the office, announcement would play on her watch only

### UC-F08: Kid-Friendly Homework Helper

**Scenario**: Children ask BarnabeeNet for homework help

**Per-Listener Adaptation**:
- Age-appropriate vocabulary
- Encouraging tone
- Step-by-step explanations
- Parental content boundaries

**Flow Examples**:

**Xander (8 years old) - Math Help:**
```
Xander: "Hey Barnabee, what's 7 times 8?"
Barnabee: "7 times 8 is 56! Great question. Here's a trick: 
          7 times 8 is like counting 7 groups of 8 things. 
          Want me to help with more math?"
```

**Penelope (Teen) - Research Help:**
```
Penelope: "Hey Barnabee, when was the French Revolution?"
Barnabee: "The French Revolution began in 1789 and lasted until 
          1799. It started with the storming of the Bastille on 
          July 14, 1789. Would you like more details about specific 
          events or causes?"
```

**Same Question, Different Listener:**

| Question | Xander (8) | Penelope (14) | Thom (Adult) |
|----------|------------|---------------|--------------|
| "What's DNA?" | "DNA is like a recipe book inside your body that tells it how to grow!" | "DNA is a molecule that contains genetic instructions for development. It's shaped like a twisted ladder called a double helix." | "Deoxyribonucleic acid—the molecular structure encoding genetic information. Do you want the technical explanation or general overview?" |

---

## Personal Productivity Use Cases

### UC-P01: Deep Work Mode

**Scenario**: Uninterrupted focus time for knowledge work

**Trigger**: "Hey Barnabee, I need to focus" or calendar block

**Flow**:
1. Set office lights to optimal focus settings (cool, bright)
2. Enable Do Not Disturb on all devices
3. Suppress non-urgent notifications
4. Play focus music (optional)
5. Block entertainment commands
6. Track focus time for productivity insights

**Voice Commands**:
```
"Hey Barnabee, I need to focus for 2 hours"
"Start a Pomodoro"
"How long have I been in deep work?"
"I'm done focusing" (restores normal mode)
```

### UC-P02: Meeting Management

**Scenario**: Managing work meetings from home office

**Features**:
- Calendar integration for meeting reminders
- "Meeting mode" scene (lighting, DND, camera-ready)
- Automatic transcript capture (optional)
- Post-meeting summary generation

**Voice Commands**:
```
"Hey Barnabee, when's my next meeting?"
"Set up for my video call"
"I'm going into a meeting" (activates meeting mode)
"Meeting's over" (restores normal, asks for notes)
```

### UC-P03: Task Capture

**Scenario**: Quick capture of ideas and tasks during the day

**Features**:
- Voice-to-task conversion
- Integration with task managers (Todoist, Things, etc.)
- Context tagging (work, personal, home)
- Reminder setting

**Voice Commands**:
```
"Hey Barnabee, remind me to call the dentist tomorrow at 10"
"Add 'buy birthday present for Mom' to my shopping list"
"Note to self: research standing desks"
"What's on my task list for today?"
```

### UC-P04: Email/Communication Triage

**Scenario**: Voice-based email management

**Features**:
- Read email summaries aloud
- Quick reply via voice
- Priority filtering
- Snooze and scheduling

**Voice Commands**:
```
"Hey Barnabee, do I have any important emails?"
"Read the email from Sarah"
"Reply: Sounds good, let's meet at 3"
"Snooze that until tomorrow morning"
```

### UC-P05: Woodworking Project Memory

**Scenario**: Thom has an ongoing woodworking project; BarnabeeNet maintains context

**Profile-Based Features**:
- Project memory per user
- Material tracking
- Progress state
- Contextual suggestions

**Example Interactions**:
```
[Week 1]
Thom: "Hey Barnabee, I'm starting a new bookshelf project"
Barnabee: "I'll remember that. What kind of wood are you using?"
Thom: "Red oak, and I ordered pocket screws from Amazon"
Barnabee: "Got it—red oak bookshelf with pocket screws. 
          I'll let you know when the screws arrive."

[3 days later - package notification]
Barnabee: "Your pocket screws arrived. Ready for the bookshelf?"

[Week 2]
Thom: "Hey Barnabee, how's my project going?"
Barnabee: "Your red oak bookshelf project: you have the pocket screws.
          Last week you mentioned cutting the shelves. 
          Have you finished that step?"
Thom: "Yes, I'm ready for assembly"
Barnabee: "Nice progress! For pocket screw assembly, remember to 
          pre-drill and use clamps for alignment. Want me to play 
          your workshop playlist?"

[Context awareness]
Thom: [In garage] "What glue should I use?"
Barnabee: "For your red oak bookshelf, Titebond III is great for 
          furniture—it's waterproof and sands well. You might have 
          some in the cabinet from the table project last year."
```

**Profile Data Stored**:
- Active projects with status
- Preferred materials/brands
- Past project history
- Skill level (intermediate woodworker)

---

## Wellness & Health Use Cases

### UC-W01: Hydration Reminders

**Scenario**: Gentle reminders to drink water throughout the day

**Features**:
- Personalized timing based on activity
- Non-intrusive delivery (watch haptic)
- Tracking of consumption (optional)
- Weather-aware adjustment

**Voice Commands**:
```
"Hey Barnabee, I just had a glass of water"
"How much water have I had today?"
"Pause water reminders for an hour"
```

### UC-W02: Movement Breaks

**Scenario**: Encourage regular movement during sedentary work

**Features**:
- Sitting duration tracking via presence sensors
- Stretch suggestions
- Standing desk reminders
- Walk prompts

**Flow Example**:
```
[After 90 minutes seated in office]
Barnabee: [Watch haptic] "You've been sitting for a while. 
          Time for a quick stretch?"
          
[Options: Yes / Later / Skip]
```

### UC-W03: Sleep Optimization

**Scenario**: Support healthy sleep habits

**Features**:
- Wind-down routine automation
- Blue light reduction scheduling
- Sleep environment optimization
- Wake-up time suggestions based on sleep cycles

**Voice Commands**:
```
"Hey Barnabee, I'm going to bed"
  → Triggers wind-down: lights dim, temperature drops, locks confirmed

"What time should I wake up to feel rested?"
"Track my sleep" (if wearable integrated)
```

### UC-W04: Medication Reminders

**Scenario**: Ensure medications are taken on schedule

**Features**:
- Customizable schedule per medication
- Confirmation tracking
- Refill reminders
- Interaction with pharmacy APIs (future)

**Voice Commands**:
```
"Hey Barnabee, I took my morning vitamins"
"When is my next medication due?"
"Remind me to refill my prescription"
```

### UC-W05: Stress Detection & Support

**Scenario**: Recognize stress patterns and offer support

**Features**:
- Voice pattern analysis for stress indicators
- Proactive calming suggestions
- Environment adjustments (lighting, music)
- Breathing exercise guidance

**Flow Example**:
```
[Voice analysis detects elevated stress]
Barnabee: "You sound a bit stressed. Would you like me to 
          dim the lights and play some calm music? Or I could 
          guide you through a quick breathing exercise."
```

---

## Proactive Intelligence Use Cases

### UC-PI01: Safety Monitoring

**Scenario**: Continuous monitoring for safety issues

**Triggers**:
- Door open at night
- Smoke/CO detection
- Water leak sensors
- Unusual temperature

**Response Pattern**:
1. Immediate alert via all available channels
2. Contextual information provided
3. Suggested actions offered
4. Escalation if no response

### UC-PI02: Energy Optimization

**Scenario**: Reduce energy waste automatically

**Features**:
- Occupancy-based light/HVAC control
- Solar production optimization
- Time-of-use rate awareness
- Energy usage insights

**Voice Commands**:
```
"Hey Barnabee, what's our energy usage today?"
"How can I reduce our carbon footprint?"
"When is the best time to run the dishwasher?"
```

### UC-PI03: Pattern Learning

**Scenario**: Discover and suggest automations

**Features**:
- Behavioral pattern detection
- Automation suggestions
- A/B testing of suggestions
- Feedback loop for improvement

**Example**:
```
Barnabee: "I've noticed you turn on the porch light every evening 
          around sunset. Would you like me to do this automatically?"
```

### UC-PI04: Predictive Maintenance

**Scenario**: Anticipate home maintenance needs

**Features**:
- Filter replacement reminders
- Unusual device behavior detection
- Seasonal maintenance prompts
- Integration with service providers (future)

---

## Proxy Mode Use Cases

### UC-PM01: Meeting Attendance

**Scenario**: Barnabee attends a meeting on your behalf

**Features**:
- Voice synthesis matching your voice (with consent)
- Real-time transcription and summarization
- Intelligent question answering based on your knowledge
- Action item extraction

**Voice Commands**:
```
"Hey Barnabee, attend my 2 PM meeting for me"
"Brief me on what happened in the team meeting"
"What action items do I have from today's meetings?"
```

### UC-PM02: Phone Call Handling

**Scenario**: Screen and handle phone calls

**Features**:
- Caller identification
- Contextual call screening
- Message taking
- Urgent call escalation

**Flow Example**:
```
[Incoming call from unknown number]
Barnabee: [To caller] "Hello, you've reached Thom's phone. 
          He's currently unavailable. May I take a message?"

[After call]
Barnabee: [To Thom] "You had a call from a solar panel company. 
          They wanted to schedule an estimate. I told them you'd 
          call back if interested. The callback number is saved."
```

---

## Guest & Hospitality Use Cases

### UC-G01: Guest Arrival

**Scenario**: Welcoming guests to your home

**Features**:
- Simplified interface activation
- Guest WiFi auto-share
- House tour guidance
- Temporary permissions

**Flow**:
```
[Guest detected at front door]
Barnabee: [To owners] "Your guest has arrived."
          [After door opens, to guest] "Welcome! I'm Barnabee. 
          I can help with lights, temperature, and entertainment. 
          The WiFi password has been sent to your phone."
```

### UC-G02: Guest Room Setup

**Scenario**: Preparing for overnight guests

**Features**:
- Climate preferences for guest room
- Wake-up routine customization
- Privacy mode for guest areas
- Check-out reminders

**Voice Commands**:
```
"Hey Barnabee, set up the guest room for Mom's visit"
"Guest prefers it warmer—set guest room to 72"
"Remind our guest about checkout at 11 AM"
```

---

## Advanced "Superhuman" Use Cases

### UC-A01: Idea Incubator

**Scenario**: Capture and develop ideas over time

**Features**:
- Voice journaling of ideas
- Semantic linking between related ideas
- Periodic "what about this idea?" prompts
- Connection suggestions

### UC-A02: Relationship Maintenance

**Scenario**: Stay connected with important people

**Features**:
- Contact frequency tracking
- Birthday/anniversary reminders
- Conversation starters based on shared interests
- Gift suggestions

### UC-A03: Personal Knowledge Management

**Scenario**: Build a personal knowledge base

**Features**:
- Automatic fact extraction from conversations
- Semantic search across all interactions
- "What do I know about X?" queries
- Knowledge gap identification

### UC-A04: Environmental Sustainability

**Scenario**: Minimize household environmental impact

**Features**:
- Carbon footprint tracking
- Sustainable alternatives suggestions
- Energy/water usage optimization
- Waste reduction reminders

**Voice Commands**:
```
"Hey Barnabee, what's our energy usage today?"
"How can I reduce our carbon footprint?"
"When is the best time to run the dishwasher?" (based on solar/rates)
"Compare this month's energy to last month"
```

### UC-A05: Ethical Auditing

**Scenario**: Review system decisions for fairness

**Features**:
- Transparency logs for all proactive actions
- "Why did you do that?" explanations
- Bias detection in suggestions
- User override tracking

**Voice Commands**:
```
"Hey Barnabee, why did you suggest lowering the temperature?"
  → "I noticed you usually lower it at this time on weekdays,
     and current usage is above average for the household."
     
"Show me all proactive notifications from this week"
"Have you been treating all family members fairly?"
```

### UC-A06: Dream Interpretation (Experimental)

**Scenario**: Process and reflect on dreams

**Features**:
- Voice journal dreams upon waking
- Pattern identification over time
- Symbolic interpretation (user-controlled)
- Connection to waking concerns

**Voice Commands**:
```
"Hey Barnabee, I want to record a dream"
  → Opens recording mode, transcribes dream narrative
  
"What patterns have you noticed in my dreams?"
"Do any of my dreams connect to what I've been stressed about?"
```

### UC-A07: Multi-Room Conversation Continuity

**Scenario**: Complex conversation continues across multiple rooms

**Spatial Awareness Features**:
- Conversation state persistence (30-minute timeout)
- Seamless room-to-room handoff
- Privacy boundary respect

**Flow**:
```
[Living Room]
Thom: "Hey Barnabee, help me plan this weekend"
Barnabee: "Sure! You have Penelope's soccer game Saturday at 10 AM 
          and a dinner reservation Sunday at 6. What else?"
Thom: "I need to finish the garage organization project"
Barnabee: "I'll block out time. Saturday afternoon after soccer?"

[Thom walks to kitchen]
[Motion detected, conversation context transfers]

[Kitchen - 30 seconds later]
Thom: "What about Sunday morning?"
Barnabee: [Continues without re-explaining context] 
          "Sunday morning is free until 4 PM when you'd want to 
          start getting ready for dinner. That's about 5 hours—
          enough for significant garage progress."
Thom: "Perfect. Remind me about both"
Barnabee: "Done. I'll remind you Saturday at 1 PM and Sunday at 9 AM.
          Also, you mentioned needing storage bins—should I add that 
          to the shopping list?"

[Later - Thom in office]
Thom: "Hey Barnabee, what did we decide about this weekend?"
Barnabee: "Here's your weekend plan: Soccer Saturday 10 AM, garage 
          Saturday afternoon and Sunday morning, dinner Sunday 6 PM.
          You have reminders set for the garage sessions."
```

**Technical Behavior**:
- Conversation context persists for 30 minutes of inactivity
- Room transitions detected via presence sensors
- Context is NOT transferred to privacy zones
- Explicit close: "Hey Barnabee, we're done planning"

---

## Example Interaction Flows

### Flow 1: Complete Morning Routine

```
[6:30 AM - Scheduled trigger]
Barnabee: [Gradually brightens bedroom lights]

[6:45 AM - Motion detected in bedroom]
Barnabee: "Good morning, Thom. It's 45 degrees and cloudy.
           You have 3 meetings today, starting at 9 AM.
           Coffee is ready in the kitchen."

Thom: "Thanks. What's first on my calendar?"

Barnabee: "Your first meeting is '1:1 with Sarah' at 9 AM,
           then 'Sprint Planning' at 10:30, and 'Architecture Review'
           at 2 PM. Would you like me to set up your office?"

Thom: "Yes, and remind me about the architecture doc"

Barnabee: "Office lights set to morning mode. I'll remind you
           about the architecture document at 8:30."

[8:30 AM - Reminder]
Barnabee: "Quick reminder: You wanted to review the architecture
           document before your 2 PM meeting."
```

### Flow 2: Managing Unexpected Situation

```
[10:30 PM - Sensor trigger]
Barnabee: [Watch haptic buzz + AR notification]
          "The garage door has been open for 10 minutes."

[AR glasses display]
┌──────────────────────────────┐
│  🚗 Garage door open         │
│     10 minutes               │
│                              │
│  [Close]       [Ignore]      │
│   Twist←        Twist→       │
└──────────────────────────────┘

[User twists crown left]
Barnabee: [Watch confirms] "Garage door closing."

[If no response in 2 minutes]
Barnabee: [Voice, gentle volume]
          "The garage door is still open. Would you like me to close it?"
```

### Flow 3: Complex Multi-Turn Conversation

```
Thom: "Hey Barnabee, I'm planning Elizabeth's birthday"

Barnabee: "Elizabeth's birthday is on March 15th, that's in 8 weeks.
           Would you like help planning something?"

Thom: "Yes, I want to do a surprise dinner"

Barnabee: "A surprise dinner sounds lovely. I remember she enjoyed
           the Italian place downtown last year. Shall I look into
           reservations, or are you thinking of cooking at home?"

Thom: "Let's do home. Can you help coordinate with the kids?"

Barnabee: "Of course. I can:
           1. Add a private calendar event visible only to you and the kids
           2. Help plan a menu based on Elizabeth's favorites
           3. Set reminders for shopping and prep
           4. Coordinate 'keep Mom busy' tasks on the day
           
           Where would you like to start?"

Thom: "All of it. And remember, she loves chocolate cake"

Barnabee: "Got it. I've noted chocolate cake as a must-have.
           I'll create the plan and share it with the kids tomorrow
           when Elizabeth is at work. Anything else to add?"

Thom: "That's perfect, thanks"

Barnabee: "You're welcome. This is going to be great.
           I'll check in next week with progress updates."
```

### Flow 4: Wellness Support

```
[3:00 PM - Watch haptic pulse]

Barnabee: [Watch display]
          "You've been at your desk for 2 hours.
           Time for a stretch?"
           
          [Yes] [Later]

[User taps "Later"]

[3:30 PM - Another pulse]
Barnabee: "Still at it! Here's a 30-second stretch you can
           do right at your desk."
           
[If user seems stressed - detected via voice pattern later]

Thom: "Hey Barnabee, I can't find that file anywhere"
      [Voice analysis: elevated stress, fast speech]

Barnabee: "I hear you're frustrated. Let me help search.
           What was the file about? Also, would you like me
           to dim the lights a bit? Sometimes that helps."
```

### Flow 5: Deferred Proactive Notification

This flow demonstrates how BarnabeeNet evaluates and defers non-urgent notifications based on spatial and activity context.

```
[2:30 PM - Dishwasher cycle completes]
Proactive Agent: Evaluates notification

EVALUATION:
├─ Event: dishwasher.complete
├─ Urgency: LOW (convenience)
├─ Relevant Users: Elizabeth (started cycle)
├─ Elizabeth Location: OFFICE (presence sensor)
├─ Elizabeth Activity: WORK_HOURS (calendar integration)
└─ Decision: DEFER (user in focus context)

[Notification queued with 30-minute expiry]

[2:35 PM - Elizabeth leaves office for kitchen]
Room Graph: MOVEMENT_DETECTED
├─ From: office
├─ To: kitchen
├─ User: Elizabeth (speaker ID on "hey barnabee" at 2:34)
└─ Trigger: DELIVER_QUEUED_NOTIFICATIONS

Barnabee: "By the way, the dishwasher finished about 5 minutes ago."
Elizabeth: "Thanks!"

[Alternative: If 30 minutes pass without good delivery opportunity]
Barnabee: [Watch haptic only - subtle reminder that dishwasher is done]
```

### Flow 6: Room Graph Event Propagation

Shows how events propagate through the spatial model to reach appropriate listeners.

```
[7:00 PM - Front door opens, Thom enters]
Event: PRESENCE.ARRIVED
├─ User: Thom (geofence + door sensor correlation)
├─ Entry Point: front_door
└─ Propagate: YES

ROOM GRAPH STATE:
┌─────────────────────────────────────────────────────┐
│ Kitchen: Elizabeth (cooking)                         │
│ Living Room: Xander, Viola (playing)                │
│ Office: EMPTY                                        │
│ Master Bedroom: EMPTY                                │
│ Penelope's Room: Penelope (privacy zone - no notify)│
└─────────────────────────────────────────────────────┘

PROPAGATION DECISION:
├─ Announcement Type: "Thom is home"
├─ Kitchen (Elizabeth): ANNOUNCE (relevant, cooking dinner)
├─ Living Room (kids): ANNOUNCE (dad's home = relevant)
├─ Penelope's Room: SUPPRESS (privacy zone)
└─ Output Devices: kitchen_speaker, living_room_speaker

Barnabee: [Kitchen] "Thom just got home."
Barnabee: [Living Room] "Hey kids, Dad's home!"

[Personalized greeting in entryway]
Barnabee: [Entryway] "Welcome home, Thom. Dinner's almost ready, 
          and the kids have been waiting to show you something."
```

### Flow 7: Conflict Resolution with Overrides

Demonstrates how BarnabeeNet handles conflicting preferences and explicit overrides.

```
[Scenario: Thermostat conflict during family gathering]

STATE:
├─ Living Room Occupants: Thom, Elizabeth, 3 kids
├─ Stored Preferences:
│   ├─ Thom: 68°F
│   ├─ Elizabeth: 72°F  
│   ├─ Kids: No strong preference
│   └─ Current Setting: 70°F (auto-compromised)
└─ System Suggestion: MAINTAIN 70°F (majority comfortable)

Elizabeth: "Hey Barnabee, I'm cold. Turn up the heat."

OVERRIDE EVALUATION:
├─ Requester: Elizabeth (adult, full permissions)
├─ Current Setting: 70°F
├─ Requested Change: Warmer (implicit)
├─ Conflict Detection: Thom prefers cooler
└─ Resolution: CONFIRM_WITH_CONTEXT

Barnabee: "I can raise it to 72. That's warmer than Thom usually 
          prefers—should I go ahead?"

Elizabeth: "Yes, just for tonight"

Barnabee: "Done, raising to 72. I'll return to the usual 70 
          tomorrow morning."

[System records temporary override with expiry]
OVERRIDE_RECORD:
├─ User: Elizabeth
├─ Action: thermostat → 72
├─ Scope: TEMPORARY (tonight)
├─ Expires: 6:00 AM tomorrow
└─ Previous Setting: Restore to 70

[Next morning at 6:00 AM]
Barnabee: [Silent action - restores to 70°F]
[Log entry for audit trail]
```

### Flow 8: Multi-Listener Response Selection

Shows real-time response adaptation based on detected listeners.

```
[Living Room - Xander (8) and Viola (5) present]

Xander: "Hey Barnabee, how do volcanoes work?"

LISTENER ANALYSIS:
├─ Primary Speaker: Xander (speaker ID match)
├─ Age Category: Child (8)
├─ Others Present: Viola (5), via room occupancy
├─ Content Level: YOUNGEST_PRESENT = 5 years old
└─ Response Style: Very simple, engaging

Barnabee: "Great question! A volcano is like a big mountain with 
          a hole in the top. Deep underground, it's super hot—so hot 
          that rocks melt into gooey stuff called lava. Sometimes the 
          lava pushes up and comes out the top like a soda bottle that 
          got shaken up! Whoosh!"

[If Thom enters mid-response]
LISTENER_CHANGE: Adult joined
[No response modification - already delivered]
[Future responses will account for adult presence but maintain 
 child-appropriate content when children are primary audience]

[Later - Thom alone in office]

Thom: "Hey Barnabee, explain how volcanoes work"

LISTENER ANALYSIS:
├─ Primary Speaker: Thom (speaker ID match)
├─ Age Category: Adult
├─ Others Present: None
├─ Content Level: ADULT
├─ Expertise: Standard (Thom's profile)
└─ Response Style: Technical but accessible

Barnabee: "Volcanoes form at tectonic plate boundaries or hotspots 
          where magma from the mantle reaches the surface. The eruption 
          style depends on magma viscosity and gas content—low-viscosity 
          basaltic magma produces effusive eruptions like Hawaii, while 
          high-viscosity rhyolitic magma causes explosive eruptions like 
          Mount St. Helens. Want me to go deeper into plate tectonics 
          or eruption mechanics?"
```

---

## Feature Comparison Matrix

### BarnabeeNet vs. Commercial Assistants

| Feature | BarnabeeNet | Alexa | Google Home | Siri |
|---------|-------------|-------|-------------|------|
| **Privacy** | | | | |
| Local voice processing | ✅ | ❌ | ❌ | Partial |
| No cloud data storage | ✅ | ❌ | ❌ | ❌ |
| Per-room privacy zones | ✅ | ❌ | ❌ | ❌ |
| Audit trail | ✅ | Limited | Limited | Limited |
| **Personalization** | | | | |
| Speaker recognition | ✅ (8 users) | ✅ (6 users) | ✅ (6 users) | ✅ (6 users) |
| Per-user permissions | ✅ Granular | Basic | Basic | Basic |
| Long-term memory | ✅ | ❌ | Limited | ❌ |
| Preference learning | ✅ | Limited | Limited | Limited |
| Per-listener response adaptation | ✅ | ❌ | ❌ | ❌ |
| **Interaction** | | | | |
| Voice | ✅ | ✅ | ✅ | ✅ |
| AR glasses | ✅ | ❌ | ❌ | Vision Pro |
| Wearable gestures | ✅ | ❌ | ❌ | Apple Watch |
| Multi-turn dialogue | ✅ | Limited | ✅ | Limited |
| Multi-room continuity | ✅ | ❌ | ❌ | ❌ |
| **Intelligence** | | | | |
| Proactive suggestions | ✅ | Basic | ✅ | Basic |
| Automation proposals | ✅ | ❌ | ✅ | ❌ |
| Context awareness | ✅ | Basic | ✅ | Basic |
| Spatial awareness | ✅ | ❌ | ❌ | ❌ |
| Emotional detection | ✅ | ❌ | ❌ | ❌ |
| **Advanced** | | | | |
| Proxy Mode | ✅ | ❌ | ❌ | ❌ |
| Self-improvement | ✅ | ❌ | ❌ | ❌ |
| Guest hospitality | ✅ | Basic | Basic | Basic |
| Family coordination | ✅ | Basic | ✅ | Basic |

### Feature Availability by Phase

| Feature | Phase 1 | Phase 2 | Phase 3 | Phase 4 | Phase 5 |
|---------|---------|---------|---------|---------|---------|
| Voice control | ✅ | ✅ | ✅ | ✅ | ✅ |
| Device actions | ✅ | ✅ | ✅ | ✅ | ✅ |
| Speaker recognition | | ✅ | ✅ | ✅ | ✅ |
| Per-user permissions | | ✅ | ✅ | ✅ | ✅ |
| Per-listener adaptation | | ✅ | ✅ | ✅ | ✅ |
| Episodic memory | | | ✅ | ✅ | ✅ |
| Semantic memory | | | ✅ | ✅ | ✅ |
| Spatial awareness | | | ✅ | ✅ | ✅ |
| Proactive alerts | | | | ✅ | ✅ |
| AR glasses | | | ✅ | ✅ | ✅ |
| Wearable gestures | | | | ✅ | ✅ |
| Multi-room continuity | | | | ✅ | ✅ |
| Proxy Mode | | | | ✅ | ✅ |
| Evolver Agent | | | | ✅ | ✅ |
| All optimizations | | | | | ✅ |

---

## Appendix A: Voice Command Quick Reference

### Device Control
```
"Turn on/off [device/room]"
"Set [device] to [value]"
"Dim/Brighten [lights] to [percent]"
"Set temperature to [degrees]"
"Lock/Unlock [door]"
"Open/Close [garage/blinds/shades]"
"Play [music/media] in [room]"
```

### Information
```
"What time/date is it?"
"What's the weather?"
"What's on my calendar?"
"What's the temperature in [room]?"
"Are any [doors/windows] open?"
"Who is home?"
```

### Routines
```
"Good morning/night"
"I'm leaving/home"
"Movie/Party/Guest mode"
"Activate [scene name]"
"Start bedtime for [person]"
"Deep work mode for [duration]"
```

### Memory
```
"Remember that [fact]"
"What do you know about [topic]?"
"When did I mention [thing]?"
"Forget [thing]"
```

### Proactive Management
```
"Pause/Resume proactive notifications"
"Why did you [action]?"
"Don't do that again"
"That was helpful, keep doing it"
```

### Spatial Awareness
```
"I'm moving to the [room]"
"Follow me" (continue conversation across rooms)
"Don't disturb me in the office"
"I'm available now" (end focus mode, deliver queued notifications)
```

---

## Appendix B: Trigger Phrases by Mode

### Discreet Triggers (Watch/Gesture)
| Gesture | Action |
|---------|--------|
| Double-tap crown | Toggle last light |
| Long-press button | "I need help" (non-emergency) |
| Shake dismiss | Cancel current action |
| Crown twist on notification | Select response |

### Voice Triggers
| Phrase | Mode |
|--------|------|
| "Hey Barnabee" | Standard activation |
| "Barnabee, urgent" | Priority mode (interrupts) |
| "Barnabee, whisper" | Quiet response mode |
| "Barnabee, private" | Route to headset |

### Context-Aware Triggers
| Context | Automatic Behavior |
|---------|-------------------|
| Headset connected | Routes TTS to headset |
| AR glasses worn | Adds visual notifications |
| Guest mode active | Simplified responses |
| Deep work active | Only urgent interrupts |
| User in privacy zone | No proactive audio |
| Multiple listeners | Age-appropriate filtering |

---

## Document Revision History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-01-16 | Initial features and use cases document |
| 1.1 | 2026-01-17 | Added Spatial Awareness System section with room graph model, notification routing, multi-room conversation continuity. Added Per-Listener Response Adaptation section with age-appropriate responses, guest mode behavior, content filtering. Added new use cases: UC-F07 (Work-From-Home Boundaries), UC-F08 (Kid-Friendly Homework Helper), UC-P05 (Woodworking Project Memory), UC-A07 (Multi-Room Conversation Continuity). Added interaction flows: Deferred Proactive Notification, Room Graph Event Propagation, Conflict Resolution with Overrides, Multi-Listener Response Selection. Updated Feature Comparison Matrix with spatial awareness and per-listener adaptation rows. |

---

*This document catalogs BarnabeeNet features and use cases. For theoretical foundations, see BarnabeeNet_Theory_Research.md. For hardware specifications, see BarnabeeNet_Hardware_Specifications.md. For technical architecture details including Room Graph implementation, see BarnabeeNet_Technical_Architecture.md.*
