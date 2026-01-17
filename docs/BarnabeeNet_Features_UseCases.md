# BarnabeeNet Features & Use Cases

**Document Version:** 1.0  
**Last Updated:** January 16, 2026  
**Author:** Thom Fife  
**Purpose:** Comprehensive catalog of BarnabeeNet capabilities, features, and practical use cases

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Core Feature Categories](#core-feature-categories)
3. [Interaction Modes](#interaction-modes)
4. [Agent Capabilities](#agent-capabilities)
5. [Privacy & Security Features](#privacy--security-features)
6. [Use Case Categories](#use-case-categories)
7. [Family & Household Use Cases](#family--household-use-cases)
8. [Personal Productivity Use Cases](#personal-productivity-use-cases)
9. [Wellness & Health Use Cases](#wellness--health-use-cases)
10. [Proactive Intelligence Use Cases](#proactive-intelligence-use-cases)
11. [Proxy Mode Use Cases](#proxy-mode-use-cases)
12. [Guest & Hospitality Use Cases](#guest--hospitality-use-cases)
13. [Advanced "Superhuman" Use Cases](#advanced-superhuman-use-cases)
14. [Example Interaction Flows](#example-interaction-flows)
15. [Feature Comparison Matrix](#feature-comparison-matrix)

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
│  [Speaker ID] ◄───────────────────────────── [Transcription]    │
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
6. Set timer with break reminders

**Voice Commands**:
```
"Hey Barnabee, activate deep work for 2 hours"
"No interruptions unless it's urgent"
"Play brown noise"
"How much focus time do I have left?"
"I'm done focusing" (restores normal mode)
```

### UC-P02: Meeting Preparation

**Scenario**: Prepare environment for video calls

**Trigger**: 5 minutes before calendar meeting

**Flow**:
1. Proactive notification: "Your meeting with [name] starts in 5 minutes"
2. Adjust lighting for video (front-lit, reduced background)
3. Close blinds if backlit
4. Silence household audio
5. Display meeting agenda on AR glasses or dashboard

**Voice Commands**:
```
"Hey Barnabee, I have a meeting in 5 minutes"
"Set up for video call"
"What's this meeting about?" (retrieves calendar details)
"Mute the house"
```

### UC-P03: Task Capture & Management

**Scenario**: Capture ideas and tasks hands-free

**Features**:
- Voice-to-task capture
- Integration with task management systems
- Context tagging (project, priority, due date)
- Review and summary

**Voice Commands**:
```
"Hey Barnabee, remind me to review the proposal tomorrow at 10 AM"
"Add 'buy birthday gift for Mom' to my shopping list"
"What tasks do I have for today?"
"What did I ask you to remind me about this week?"
```

### UC-P04: Daily Review & Planning

**Scenario**: Morning and evening reflection routines

**Trigger**: Voice command or schedule

**Morning Review**:
```
"Hey Barnabee, what's my day look like?"
  → Weather, calendar summary, priority tasks, overnight notifications
```

**Evening Review**:
```
"Hey Barnabee, let's review today"
  → Completed tasks, open items, tomorrow preview
  → "Anything you want to capture before tomorrow?"
```

### UC-P05: Context Switching

**Scenario**: Transition between work modes efficiently

**Voice Commands**:
```
"Hey Barnabee, I'm switching to emails"
  → Pause focus music, restore notifications, adjust lighting
  
"Hey Barnabee, lunch break"
  → Warm lighting, entertainment available, break reminder in 30 min
  
"Hey Barnabee, back to work"
  → Restore work mode settings
```

---

## Wellness & Health Use Cases

### UC-W01: Habit Tracking

**Scenario**: Build and maintain healthy habits

**Features**:
- Voice-logged habit completion
- Streak tracking with encouragement
- Gentle reminders without nagging
- Weekly progress summaries

**Voice Commands**:
```
"Hey Barnabee, I did my meditation"
"How many days in a row have I exercised?"
"Remind me to take vitamins at 9 AM"
"How am I doing on my habits this week?"
```

### UC-W02: Hydration & Movement Reminders

**Scenario**: Encourage healthy behaviors during work

**Trigger**: Polling-based (configurable intervals)

**Flow**:
1. Every 90 minutes during work hours, gentle reminder
2. Watch haptic notification: "Time to stretch!"
3. Voice optional: "You've been at your desk for a while. How about a quick stretch?"
4. Track compliance patterns, adjust timing

**Configuration**:
```yaml
wellness_reminders:
  hydration:
    interval: 60  # minutes
    delivery: [watch_haptic, voice_optional]
  movement:
    interval: 90  # minutes
    delivery: [watch_haptic, ar_glasses]
  eye_break:
    interval: 20  # 20-20-20 rule
    delivery: [ar_glasses]
```

### UC-W03: Sleep Support

**Scenario**: Improve sleep quality through environment

**Trigger**: "Hey Barnabee, I'm going to bed" or schedule

**Flow**:
1. Dim all lights to 10%
2. Set bedroom to sleep temperature (67°F)
3. Activate white noise or sleep sounds
4. Enable "Do Not Disturb" except emergencies
5. Morning: Gradual sunrise lighting 30 min before alarm

**Voice Commands**:
```
"Hey Barnabee, set sleep sounds for 30 minutes"
"Wake me up at 6:30 with gentle sunrise"
"How did I sleep last night?" (integrates with wearable data)
```

### UC-W04: Mood & Energy Check-ins

**Scenario**: Track emotional wellbeing over time

**Features**:
- Optional periodic check-ins
- Voice sentiment detection
- Pattern identification
- Supportive responses (not therapy replacement)

**Voice Commands**:
```
"Hey Barnabee, I'm feeling stressed"
  → "I hear you. Would you like me to dim the lights and play
     calming music? Or would you prefer some quiet time?"
     
"Log my mood as 7 out of 10"
"How has my energy been this week?"
```

### UC-W05: Mindfulness & Breathing

**Scenario**: Guided micro-meditation during busy day

**Trigger**: Voice command or stress detection

**Voice Commands**:
```
"Hey Barnabee, I need a minute"
  → Dims lights, offers: "Would you like a 2-minute breathing exercise?"
  
"Guide me through box breathing"
  → Step-by-step audio guidance with timing
```

---

## Proactive Intelligence Use Cases

### UC-PR01: Safety Alerts

**Scenario**: Detect and alert on safety concerns

| Trigger | Alert | Action Options |
|---------|-------|----------------|
| Door open > 10 min at night | "Front door has been open for 10 minutes" | Close/Lock, Ignore, Check camera |
| Smoke detector activation | Urgent alarm + "Smoke detected in kitchen" | Call 911, Silence (if false) |
| Water leak sensor | "Water detected in basement" | Show camera, Call plumber |
| Unusual motion at night | "Motion detected in backyard at 2 AM" | Show camera, Arm alarm |

### UC-PR02: Convenience Notifications

**Scenario**: Helpful unprompted information

| Trigger | Notification | Delivery |
|---------|-------------|----------|
| Package detected (camera AI) | "Package delivered at front door" | Watch, AR, voice |
| Weather change | "Rain expected in 2 hours. Windows are open." | Voice (if home) |
| Calendar approaching | "Your 3 PM meeting starts in 10 minutes" | Watch, voice |
| Appliance complete | "Washing machine cycle complete" | Watch haptic |

### UC-PR03: Energy Optimization

**Scenario**: Detect and reduce energy waste

| Pattern | Notification | Suggestion |
|---------|-------------|------------|
| Lights on in empty room | "Living room lights on, no motion for 30 min" | Turn off? |
| HVAC running, windows open | "AC running but office window is open" | Close window? |
| High energy during peak | "Peak rate period starting in 30 min" | Delay dishwasher? |
| Unused device drawing power | "Guest room TV in standby for 48 hours" | Cut power? |

### UC-PR04: Automation Suggestions

**Scenario**: Learn patterns and propose automations

**Detection**:
- "You turn on the office lights at 6:30 AM every weekday"
- "You lower the thermostat when leaving for work"
- "Kids' hallway light always goes on at 7 PM"

**Proposal**:
```
Barnabee: "I've noticed you turn on the office lights around 6:30 AM
           on weekdays. Would you like me to do this automatically?"
           
User: "Yes, but only if I'm home"

Barnabee: "Got it. I'll turn on office lights at 6:30 AM on weekdays
           when you're detected at home. You can say 'undo automation'
           if this doesn't work out."
```

---

## Proxy Mode Use Cases

### UC-PX01: Meeting Attendance

**Scenario**: Barnabee joins Teams call when user is unavailable

**Trigger**: Calendar meeting + user opt-in

**Capabilities**:
- Join as bot participant
- Real-time transcription
- Key topic extraction
- Action item identification
- Post-meeting summary

**Flow**:
```
User: "Hey Barnabee, cover my 2 PM standup"

Barnabee: "I'll join the 2 PM Engineering Standup and take notes.
           Should I mention you're unavailable, or stay silent?"
           
User: "Mention I had a conflict but I'll review the notes"

[After meeting]

Barnabee: "Your standup ended. Key points:
           - Sprint demo moved to Friday
           - You have an action item: Review PR #234
           - Sarah asked about your timeline on the API project
           Would you like me to send a follow-up message?"
```

### UC-PX02: Voice Presence (Advanced)

**Scenario**: Barnabee responds in user's cloned voice for simple queries

**Safety Constraints**:
- Explicit opt-in required each session
- Only answers from verified semantic memory
- Never improvises or speculates
- Identifies as proxy when uncertain

**Example**:
```
[In Teams meeting, user is driving]

Colleague: "Thom, do we have budget approval for the Beelink upgrade?"

Barnabee (in Thom's voice): "Yes, that was approved last week.
           I can send you the details after this call."
           
[Question Barnabee can't answer]

Colleague: "What do you think about the new API design?"

Barnabee (in Thom's voice): "I'd want to review the details before
           commenting. Can you send that to me for follow-up?"
```

### UC-PX03: Call Summarization

**Scenario**: Summarize missed portions of calls

**Trigger**: "Hey Barnabee, catch me up on the last 10 minutes"

**Features**:
- Real-time transcription buffer
- Key point extraction
- Speaker attribution
- Sentiment analysis

**Output**:
```
Barnabee: "In the last 10 minutes:
           
           1. Budget discussion concluded - Q2 approved as proposed
           2. Sarah raised concerns about timeline on Project X
           3. Decision: Move demo to Friday
           4. You were mentioned: John asked if you'll lead the
              architecture review
              
           Want me to provide more detail on any of these?"
```

---

## Guest & Hospitality Use Cases

### UC-G01: Guest Mode Activation

**Scenario**: Visitors coming over, simplify smart home

**Trigger**: Voice command or calendar event

**Flow**:
1. Disable complex automations (motion lights, auto-shades)
2. Enable simple switch control
3. Create guest WiFi credentials
4. Set up simplified dashboard on tablet
5. Relax permission restrictions for common areas

**Voice Commands**:
```
"Hey Barnabee, we have guests coming"
  → "Guest mode activated. Complex automations paused.
     Guest WiFi password is 'Welcome2024'.
     Should I set any specific rooms for guest access?"
     
"Guests are leaving"
  → "Restoring normal automations. Rotating guest WiFi password."
```

### UC-G02: Overnight Guest Setup

**Scenario**: Preparing guest room for overnight visitors

**Trigger**: Voice command

**Flow**:
1. Set guest room temperature to comfortable (70°F)
2. Turn on guest room lights to welcoming level
3. Enable bedside lamp control
4. Place tablet with simplified controls
5. Brief guest on basic commands

**Voice Commands**:
```
"Hey Barnabee, prepare the guest room for Mom"
"Set guest room to her preferred temperature" (retrieves from memory)
"What commands can guests use?"
```

### UC-G03: Guest Temporary Access

**Scenario**: Babysitter, contractor, or service worker access

**Features**:
- Time-limited door codes
- Restricted device access
- Activity logging
- Automatic expiration

**Voice Commands**:
```
"Hey Barnabee, the babysitter is coming at 5 PM"
  → Creates 4-hour door code, enables limited controls
  
"Give the plumber a door code for tomorrow 9 AM to 12 PM"
  → Creates temporary code, logs all activity
```

### UC-G04: Party Mode

**Scenario**: Hosting a gathering with optimal ambiance

**Trigger**: Voice command

**Flow**:
1. Set lighting to party preset (colorful, dynamic)
2. Enable multi-room audio
3. Simplify controls for guests
4. Disable motion-triggered lights
5. Set temperature slightly cooler (accounting for body heat)

**Voice Commands**:
```
"Hey Barnabee, party mode"
"Play upbeat music in the living room and kitchen"
"End party mode" → Gradually returns to normal settings
```

---

## Advanced "Superhuman" Use Cases

### UC-A01: Idea Incubation

**Scenario**: Capture and develop ideas over time

**Features**:
- Voice capture of raw ideas
- Periodic prompts to develop further
- Connection to related ideas
- Synthesis suggestions

**Voice Commands**:
```
"Hey Barnabee, new idea: What if we used solar to power the garden lights?"

[Two days later, Barnabee proactively:]
"I've been thinking about your solar garden lights idea.
 Would you like me to research compatible solar controllers?"
 
"Show me all my home improvement ideas"
"Connect this to my energy efficiency project"
```

### UC-A02: Relationship Nurturing

**Scenario**: Maintain connections with loved ones

**Features**:
- Birthday and anniversary reminders
- "Haven't called in a while" nudges
- Gift suggestion based on interests
- Relationship health tracking

**Voice Commands**:
```
"Hey Barnabee, when is Dad's birthday?"
"Remind me to call Sarah next week"
"What might Mom like for her birthday?" → Suggests based on memory
"Who haven't I talked to in a while?"
```

### UC-A03: Memory Replay

**Scenario**: Recall and relive past moments

**Features**:
- Search conversations by topic/time
- Surface "this day last year" moments
- Fact verification against memory
- Nostalgic recalls

**Voice Commands**:
```
"Hey Barnabee, what did we talk about last Christmas?"
"When did I mention wanting to visit Japan?"
"What was that restaurant Elizabeth recommended?"
"What happened this day last year?"
```

### UC-A04: Eco-Advising

**Scenario**: Optimize home for environmental impact

**Features**:
- Real-time energy monitoring
- Carbon footprint tracking
- Optimization suggestions
- Solar/battery integration

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
| **Interaction** | | | | |
| Voice | ✅ | ✅ | ✅ | ✅ |
| AR glasses | ✅ | ❌ | ❌ | Vision Pro |
| Wearable gestures | ✅ | ❌ | ❌ | Apple Watch |
| Multi-turn dialogue | ✅ | Limited | ✅ | Limited |
| **Intelligence** | | | | |
| Proactive suggestions | ✅ | Basic | ✅ | Basic |
| Automation proposals | ✅ | ❌ | ✅ | ❌ |
| Context awareness | ✅ | Basic | ✅ | Basic |
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
| Episodic memory | | | ✅ | ✅ | ✅ |
| Semantic memory | | | ✅ | ✅ | ✅ |
| Proactive alerts | | | | ✅ | ✅ |
| AR glasses | | | ✅ | ✅ | ✅ |
| Wearable gestures | | | | ✅ | ✅ |
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

---

## Document Revision History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-01-16 | Initial features and use cases document |

---

*This document catalogs BarnabeeNet features and use cases. For theoretical foundations, see BarnabeeNet_Theory_Research.md. For hardware specifications, see BarnabeeNet_Hardware_Specifications.md.*
