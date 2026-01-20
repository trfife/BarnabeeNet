# BarnabeeNet Phone Finder & Battery Alert Feature

**Document Version:** 1.0  
**Created:** January 2026  
**Status:** Planning  
**Priority:** Medium-High (Quality of Life)

---

## Executive Summary

This feature addresses a common family pain point: kids leaving phones around the house, letting them die, and then being unable to find them. BarnabeeNet will provide:

1. **Proactive battery warnings** - Spoken alerts when battery drops below thresholds
2. **Remote phone finder** - Voice-activated alarm to locate lost phones
3. **Parent notifications** - Escalation when kids ignore warnings
4. **Dashboard visibility** - Battery status for all family devices

The implementation follows a phased approach, starting with Home Assistant Companion App integration (low effort, high value) before evaluating the need for a custom BarnabeeNet mobile app.

---

## Problem Statement

| Issue | Impact | Frequency |
|-------|--------|-----------|
| Kids leave phones on silent/dead | Can't reach them for safety | Daily |
| Phones lost in house | Time wasted searching | Weekly |
| Phones die unexpectedly | Miss important communications | Weekly |
| No visibility into device status | Parents unaware until too late | Constant |

### User Stories

1. **As a parent**, I want to say "Barnabee, find Penelope's phone" and have it make a loud noise so I can locate it quickly.

2. **As a parent**, I want BarnabeeNet to warn my kids when their phone battery is low, even if the phone is on silent.

3. **As a parent**, I want to see all family phone battery levels on the dashboard so I can remind kids to charge.

4. **As a kid**, I want a helpful reminder when my battery is low so my phone doesn't die unexpectedly.

5. **As a parent**, I want to be notified if a kid's phone reaches critical battery so I can intervene.

---

## Technical Approach

### Phase 1: Home Assistant Companion Integration (Recommended Start)

**Timeline:** 1-2 days  
**Effort:** Low  
**Value:** High (covers ~80% of use cases)

The Home Assistant Companion App already provides the core capabilities needed. This phase leverages existing infrastructure with minimal development.

#### Capabilities by Platform

| Feature | Android | iOS |
|---------|---------|-----|
| Battery level sensor | ✅ `sensor.{device}_battery_level` | ✅ `sensor.{device}_battery_level` |
| Remote TTS | ✅ `message: TTS` with `tts_text` | ❌ Not supported by iOS |
| Override silent mode | ✅ `media_stream: alarm_stream_max` | ⚠️ Critical Alerts only (sound, no TTS) |
| Location tracking | ✅ `device_tracker.{device}` | ✅ `device_tracker.{device}` |
| Custom notification sound | ✅ Notification Channels | ✅ With sound file in app bundle |
| Critical alerts | N/A (use alarm_stream) | ✅ Bypasses silent/DND |

#### Architecture (Phase 1)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     PHASE 1 ARCHITECTURE                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────────────┐  │
│  │ Kid's Phone  │    │    Home      │    │      BarnabeeNet         │  │
│  │              │◄───│  Assistant   │◄───│                          │  │
│  │ HA Companion │    │              │    │  ┌────────────────────┐  │  │
│  │    App       │    │ Automations  │    │  │ Action Agent       │  │  │
│  └──────────────┘    │ & Scripts    │    │  │ "find X's phone"   │  │  │
│        │             └──────────────┘    │  └────────────────────┘  │  │
│        │                    ▲            │                          │  │
│        │ Sensors:           │            │  ┌────────────────────┐  │  │
│        │ • battery_level    │            │  │ Proactive Agent    │  │  │
│        │ • battery_state    │            │  │ Battery monitoring │  │  │
│        │ • device_tracker   │            │  └────────────────────┘  │  │
│        │                    │            │                          │  │
│        └────────────────────┘            │  ┌────────────────────┐  │  │
│                                          │  │ Dashboard          │  │  │
│                                          │  │ Battery status     │  │  │
│                                          │  └────────────────────┘  │  │
│                                          └──────────────────────────┘  │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

#### Implementation Components

##### 1. Home Assistant Automations

**Low Battery Warning (Android - with TTS):**
```yaml
automation:
  - id: barnabeenet_battery_warning_android
    alias: "BarnabeeNet: Battery Warning (Android)"
    description: "Speak battery warning on Android devices"
    trigger:
      - platform: numeric_state
        entity_id:
          - sensor.xander_phone_battery_level
          - sensor.penelope_phone_battery_level
          - sensor.oliver_phone_battery_level
          - sensor.charlotte_phone_battery_level
        below: 20
    condition:
      - condition: template
        value_template: "{{ trigger.to_state.attributes.get('device_class', '') != 'ios' }}"
    action:
      - variables:
          device_name: "{{ trigger.to_state.name | replace(' Battery Level', '') }}"
          battery_level: "{{ trigger.to_state.state }}"
          notify_service: "notify.mobile_app_{{ trigger.entity_id | replace('sensor.', '') | replace('_battery_level', '') }}"
      - service: "{{ notify_service }}"
        data:
          message: "TTS"
          data:
            tts_text: "Hey! Your phone battery is at {{ battery_level }} percent. Please find a charger soon!"
            media_stream: "alarm_stream_max"
            channel: "battery_warning"
            importance: "high"

  - id: barnabeenet_battery_critical_android
    alias: "BarnabeeNet: Battery Critical (Android)"
    description: "Urgent spoken warning at critical battery"
    trigger:
      - platform: numeric_state
        entity_id:
          - sensor.xander_phone_battery_level
          - sensor.penelope_phone_battery_level
          - sensor.oliver_phone_battery_level
          - sensor.charlotte_phone_battery_level
        below: 10
    action:
      - variables:
          device_name: "{{ trigger.to_state.name | replace(' Battery Level', '') }}"
          battery_level: "{{ trigger.to_state.state }}"
          notify_service: "notify.mobile_app_{{ trigger.entity_id | replace('sensor.', '') | replace('_battery_level', '') }}"
      - service: "{{ notify_service }}"
        data:
          message: "TTS"
          data:
            tts_text: "Warning! Your phone is at {{ battery_level }} percent and about to die! Plug it in now!"
            media_stream: "alarm_stream_max"
            channel: "battery_critical"
            importance: "max"
      # Also notify parents
      - service: notify.mobile_app_thom_phone
        data:
          title: "🔋 {{ device_name }} Battery Critical"
          message: "Battery at {{ battery_level }}% - may die soon"
          data:
            channel: "family_alerts"
```

**Low Battery Warning (iOS - Critical Alert):**
```yaml
automation:
  - id: barnabeenet_battery_warning_ios
    alias: "BarnabeeNet: Battery Warning (iOS)"
    description: "Critical alert for iOS devices (no TTS available)"
    trigger:
      - platform: numeric_state
        entity_id:
          - sensor.penelope_iphone_battery_level
        below: 20
    action:
      - variables:
          device_name: "{{ trigger.to_state.name | replace(' Battery Level', '') }}"
          battery_level: "{{ trigger.to_state.state }}"
          notify_service: "notify.mobile_app_{{ trigger.entity_id | replace('sensor.', '') | replace('_battery_level', '') }}"
      - service: "{{ notify_service }}"
        data:
          title: "🔋 Battery Low!"
          message: "Your phone is at {{ battery_level }}%. Please charge it soon!"
          data:
            push:
              sound:
                name: "default"
                critical: 1
                volume: 0.8
```

**Find Phone Script:**
```yaml
script:
  barnabeenet_find_phone:
    alias: "BarnabeeNet: Find Phone"
    description: "Trigger loud alarm on target phone"
    fields:
      target_device:
        description: "Device ID to find"
        example: "xander_phone"
    sequence:
      - choose:
          # Android path - use TTS
          - conditions:
              - condition: template
                value_template: "{{ 'iphone' not in target_device }}"
            sequence:
              - service: "notify.mobile_app_{{ target_device }}"
                data:
                  message: "TTS"
                  data:
                    tts_text: "Hey! Someone is looking for this phone! Pick it up!"
                    media_stream: "alarm_stream_max"
                    channel: "find_phone"
                    importance: "max"
              - delay: "00:00:03"
              - repeat:
                  count: 3
                  sequence:
                    - service: "notify.mobile_app_{{ target_device }}"
                      data:
                        message: "TTS"
                        data:
                          tts_text: "This phone is being searched for!"
                          media_stream: "alarm_stream_max"
                    - delay: "00:00:02"
          # iOS path - critical alert with sound
          - conditions:
              - condition: template
                value_template: "{{ 'iphone' in target_device }}"
            sequence:
              - repeat:
                  count: 5
                  sequence:
                    - service: "notify.mobile_app_{{ target_device }}"
                      data:
                        title: "📱 FIND MY PHONE"
                        message: "Someone is looking for you!"
                        data:
                          push:
                            sound:
                              name: "default"
                              critical: 1
                              volume: 1.0
                    - delay: "00:00:02"
```

##### 2. BarnabeeNet Action Agent Patterns

Add to instant response patterns or Action Agent routing:

```yaml
# patterns/phone_finder.yaml
patterns:
  find_phone:
    - pattern: "find {name}'s phone"
      action: ha_script
      script: barnabeenet_find_phone
      parameters:
        target_device: "{name}_phone"
      response: "I'm pinging {name}'s phone now. Listen for the alarm!"
    
    - pattern: "where is {name}'s phone"
      action: ha_device_tracker
      entity: "device_tracker.{name}_phone"
      response_template: "{name}'s phone was last seen at {location} about {time_ago} ago."
    
    - pattern: "ping {name}"
      action: ha_script
      script: barnabeenet_find_phone
      parameters:
        target_device: "{name}_phone"
      response: "Pinging {name}'s phone!"
    
    - pattern: "is {name}'s phone charged"
      action: ha_sensor
      entity: "sensor.{name}_phone_battery_level"
      response_template: "{name}'s phone is at {state}% battery."
    
    - pattern: "what's the battery on {name}'s phone"
      action: ha_sensor
      entity: "sensor.{name}_phone_battery_level"
      response_template: "{name}'s phone has {state}% battery remaining."

  # Compound patterns
  find_all_phones:
    - pattern: "find all the phones"
      action: ha_script_multiple
      scripts:
        - barnabeenet_find_phone:
            target_device: xander_phone
        - barnabeenet_find_phone:
            target_device: penelope_phone
      response: "I'm pinging all the kids' phones now!"
    
    - pattern: "battery check"
      action: ha_sensor_multiple
      entities:
        - sensor.xander_phone_battery_level
        - sensor.penelope_phone_battery_level
        - sensor.oliver_phone_battery_level
        - sensor.charlotte_phone_battery_level
      response_template: "Phone batteries: {formatted_list}"
```

##### 3. Dashboard Integration

Add to Family page or create dedicated Phone Status section:

```javascript
// Phone status component for dashboard
async function loadPhoneStatus() {
    const phones = [
        { name: 'Xander', entity: 'sensor.xander_phone_battery_level', tracker: 'device_tracker.xander_phone' },
        { name: 'Penelope', entity: 'sensor.penelope_phone_battery_level', tracker: 'device_tracker.penelope_phone' },
        { name: 'Oliver', entity: 'sensor.oliver_phone_battery_level', tracker: 'device_tracker.oliver_phone' },
        { name: 'Charlotte', entity: 'sensor.charlotte_phone_battery_level', tracker: 'device_tracker.charlotte_phone' },
    ];
    
    const container = document.getElementById('phone-status-grid');
    
    for (const phone of phones) {
        const batteryResp = await fetch(`${API_BASE}/api/v1/homeassistant/state/${phone.entity}`);
        const trackerResp = await fetch(`${API_BASE}/api/v1/homeassistant/state/${phone.tracker}`);
        
        const battery = await batteryResp.json();
        const tracker = await trackerResp.json();
        
        const level = parseInt(battery.state) || 0;
        const location = tracker.state || 'unknown';
        
        container.innerHTML += `
            <div class="phone-card ${level < 20 ? 'low-battery' : ''}">
                <div class="phone-name">${phone.name}</div>
                <div class="phone-battery">
                    <div class="battery-icon">${getBatteryIcon(level)}</div>
                    <div class="battery-level">${level}%</div>
                </div>
                <div class="phone-location">📍 ${location}</div>
                <button class="btn btn-sm" onclick="findPhone('${phone.name.toLowerCase()}')">
                    🔔 Find
                </button>
            </div>
        `;
    }
}

function getBatteryIcon(level) {
    if (level > 80) return '🔋';
    if (level > 50) return '🔋';
    if (level > 20) return '🪫';
    return '⚠️';
}

async function findPhone(name) {
    await fetch(`${API_BASE}/api/v1/homeassistant/script/barnabeenet_find_phone`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target_device: `${name}_phone` })
    });
    showToast(`Pinging ${name}'s phone!`);
}
```

##### 4. Family Profile Integration

Add phone entity mappings to family profiles:

```yaml
# family_profiles addition
profiles:
  xander:
    devices:
      phone:
        entity_prefix: "xander_phone"
        battery_sensor: "sensor.xander_phone_battery_level"
        device_tracker: "device_tracker.xander_phone"
        notify_service: "notify.mobile_app_xander_phone"
        platform: "android"
        battery_thresholds:
          warning: 20
          critical: 10
          emergency: 5
    
  penelope:
    devices:
      phone:
        entity_prefix: "penelope_iphone"
        battery_sensor: "sensor.penelope_iphone_battery_level"
        device_tracker: "device_tracker.penelope_iphone"
        notify_service: "notify.mobile_app_penelope_iphone"
        platform: "ios"
        battery_thresholds:
          warning: 20
          critical: 10
          emergency: 5
```

---

### Phase 2: Evaluation Period

**Timeline:** 2-4 weeks after Phase 1 deployment  
**Effort:** None (monitoring only)

#### Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Battery warnings delivered | >95% | HA automation logs |
| Kids respond to warnings | >50% | Observed behavior |
| Find phone success rate | >90% | Manual testing |
| Silent mode bypass works | >80% | Per-device testing |
| Parent satisfaction | Positive | Family feedback |

#### Evaluation Questions

1. **Does `alarm_stream_max` work on all Android devices?**
   - Test on each kid's specific phone model
   - Document any that require different approach

2. **Do kids respond to TTS warnings?**
   - Are they effective or ignored?
   - Would a different voice/message work better?

3. **Is iOS Critical Alerts adequate?**
   - Sound-only vs TTS preference
   - Any kids ignoring visual-only alerts?

4. **What additional features are needed?**
   - Remote ringer mode change?
   - Charging reminders at specific times?
   - Automatic location sharing when battery critical?

---

### Phase 3: Custom App (If Needed)

**Timeline:** 4-8 weeks  
**Effort:** High  
**Decision Gate:** Only proceed if Phase 1 evaluation shows significant gaps

#### When to Build Custom App

| Indicator | Phase 1 Limitation | Custom App Solution |
|-----------|-------------------|---------------------|
| Kids ignore generic TTS | Android system voice | Kokoro/custom voice |
| Need branded experience | Generic HA notifications | BarnabeeNet UI |
| HA Companion unreliable | Background execution issues | Dedicated foreground service |
| Need additional features | HA limitations | Full control |
| Want remote microphone | Not available | Custom implementation |

#### Custom App Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     CUSTOM APP ARCHITECTURE                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                      BarnabeeNet Server                             │ │
│  │                                                                     │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌───────────┐ │ │
│  │  │ Device      │  │ FCM         │  │ Battery     │  │ Location  │ │ │
│  │  │ Registry    │  │ Provider    │  │ Monitor     │  │ Service   │ │ │
│  │  │             │  │             │  │ Service     │  │           │ │ │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └───────────┘ │ │
│  │         │                │                │               │        │ │
│  └─────────┼────────────────┼────────────────┼───────────────┼────────┘ │
│            │                │                │               │          │
│            │          FCM/APNs Push          │               │          │
│            │                │                │               │          │
│            ▼                ▼                ▼               ▼          │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                    BarnabeeNet Mobile App                          │ │
│  │                       (Flutter)                                    │ │
│  │                                                                     │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌───────────┐ │ │
│  │  │ Foreground  │  │ TTS Engine  │  │ FCM         │  │ Battery   │ │ │
│  │  │ Service     │  │ (Kokoro or  │  │ Receiver    │  │ Broadcast │ │ │
│  │  │             │  │  System)    │  │             │  │ Receiver  │ │ │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └───────────┘ │ │
│  │         │                │                │               │        │ │
│  │         └────────────────┴────────────────┴───────────────┘        │ │
│  │                                 │                                   │ │
│  │                    ┌────────────┴────────────┐                     │ │
│  │                    │    Audio Output         │                     │ │
│  │                    │    (STREAM_ALARM)       │                     │ │
│  │                    │    Bypasses silent mode │                     │ │
│  │                    └─────────────────────────┘                     │ │
│  │                                                                     │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

#### Technology Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| **Framework** | Flutter | Cross-platform, good native access, FCM integration |
| **Backend Communication** | REST + WebSocket | Existing BarnabeeNet API patterns |
| **Push Notifications** | Firebase Cloud Messaging | Industry standard, reliable |
| **Local TTS** | Android: System TTS / iOS: AVSpeechSynthesizer | Platform native, no licensing |
| **Optional: Custom Voice** | Kokoro model (on-device) | BarnabeeNet voice consistency |
| **Background Service** | Android: Foreground Service | Required for reliable monitoring |
| **State Management** | Riverpod | Flutter standard, reactive |

#### Core Features (MVP)

| Feature | Android | iOS | Priority |
|---------|---------|-----|----------|
| Battery monitoring | Local BroadcastReceiver | UIDevice + Background Refresh | P0 |
| Local TTS warnings | System TTS on STREAM_ALARM | AVSpeechSynthesizer (foreground only) | P0 |
| Remote find phone | FCM → TTS + alarm | FCM → Critical Alert | P0 |
| Status heartbeat | HTTP POST to BarnabeeNet | HTTP POST to BarnabeeNet | P0 |
| Location reporting | Fused Location Provider | Core Location | P1 |
| Remote ringer control | AudioManager API | Not possible on iOS | P2 |
| Custom Kokoro voice | On-device inference | On-device inference | P3 |

#### iOS Limitations & Workarounds

| Limitation | Impact | Workaround |
|------------|--------|------------|
| No background TTS | Can't speak when app closed | Critical Alert sound + visual |
| Critical Alerts require Apple approval | Weeks/months approval process | Use HA Companion's existing approval OR sound-only alerts |
| Background execution limited | Battery monitor may not run | Significant Location Changes + Push |
| No STREAM_ALARM equivalent | Can't bypass silent without Critical Alert | Apply for entitlement |

**Critical Alerts Entitlement Application:**
If building custom iOS app, apply to Apple via:
1. Developer account → Certificates, Identifiers & Profiles
2. Request Critical Alerts entitlement
3. Provide justification: "Family safety app for locating children's devices and battery emergency notifications"
4. Wait 2-8 weeks for approval

---

## API Additions

### BarnabeeNet API Endpoints

```yaml
# New endpoints for phone management
endpoints:
  # Get all registered phones
  GET /api/v1/phones:
    response:
      phones:
        - member_id: "xander"
          device_id: "xander_phone"
          platform: "android"
          battery_level: 45
          last_seen: "2026-01-20T10:30:00Z"
          location: "home"
          
  # Get specific phone status
  GET /api/v1/phones/{device_id}:
    response:
      device_id: "xander_phone"
      member_id: "xander"
      platform: "android"
      battery_level: 45
      battery_state: "discharging"
      last_seen: "2026-01-20T10:30:00Z"
      location: "home"
      location_accuracy: 10
      
  # Trigger find phone
  POST /api/v1/phones/{device_id}/find:
    request:
      message: "optional custom message"
      duration: 30  # seconds
    response:
      status: "triggered"
      
  # Update phone status (from custom app)
  POST /api/v1/phones/{device_id}/heartbeat:
    request:
      battery_level: 45
      battery_state: "discharging"
      location:
        lat: 35.123
        lon: -80.456
        accuracy: 10
    response:
      status: "ok"
      commands: []  # Any pending commands for device
```

### FCM Message Formats (Phase 3)

```json
// Find phone command
{
  "to": "<device_fcm_token>",
  "data": {
    "command": "find_phone",
    "message": "Someone is looking for your phone!",
    "duration": 30,
    "volume": 1.0
  },
  "android": {
    "priority": "high",
    "ttl": "60s"
  },
  "apns": {
    "headers": {
      "apns-priority": "10"
    },
    "payload": {
      "aps": {
        "sound": {
          "critical": 1,
          "name": "default",
          "volume": 1.0
        }
      }
    }
  }
}

// Battery warning (server-initiated)
{
  "to": "<device_fcm_token>",
  "data": {
    "command": "battery_warning",
    "message": "Your battery is at 15%! Please charge soon.",
    "level": 15
  }
}
```

---

## Dashboard UI Mockup

```
┌─────────────────────────────────────────────────────────────────────────┐
│  📱 Family Phones                                           [Refresh]   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐         │
│  │ 👦 Xander       │  │ 👧 Penelope     │  │ 👦 Oliver       │         │
│  │                 │  │                 │  │                 │         │
│  │   🔋 78%        │  │   ⚠️ 15%        │  │   🔋 92%        │         │
│  │   ████████░░    │  │   ██░░░░░░░░    │  │   █████████░    │         │
│  │                 │  │                 │  │                 │         │
│  │ 📍 Home         │  │ 📍 School       │  │ 📍 Home         │         │
│  │ 🕐 2 min ago    │  │ 🕐 5 min ago    │  │ 🕐 Just now     │         │
│  │                 │  │                 │  │                 │         │
│  │ [🔔 Find]       │  │ [🔔 Find]       │  │ [🔔 Find]       │         │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘         │
│                                                                          │
│  ┌─────────────────┐                                                    │
│  │ 👧 Charlotte    │     ┌────────────────────────────────────────┐    │
│  │                 │     │ Recent Alerts                          │    │
│  │   🔋 45%        │     │                                        │    │
│  │   █████░░░░░    │     │ 10:15 AM - Penelope battery at 20%    │    │
│  │                 │     │ 10:05 AM - Penelope battery at 25%    │    │
│  │ 📍 Home         │     │ 09:30 AM - Xander phone found         │    │
│  │ 🕐 1 min ago    │     │                                        │    │
│  │                 │     └────────────────────────────────────────┘    │
│  │ [🔔 Find]       │                                                    │
│  └─────────────────┘                                                    │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ Quick Actions                                                    │   │
│  │                                                                  │   │
│  │  [📱 Find All Phones]    [🔋 Battery Report]    [📍 Locations]  │   │
│  │                                                                  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Implementation Checklist

### Phase 1: HA Companion (Week 1)

- [ ] **Setup**
  - [ ] Install HA Companion on all kids' phones
  - [ ] Verify battery sensors appear in HA
  - [ ] Verify device trackers appear in HA
  - [ ] Test notification delivery to each device

- [ ] **Automations**
  - [ ] Create battery warning automation (20%)
  - [ ] Create battery critical automation (10%)
  - [ ] Create battery emergency automation (5%) with parent notification
  - [ ] Create find phone script
  - [ ] Test alarm_stream_max on each Android device
  - [ ] Test Critical Alerts on iOS devices

- [ ] **BarnabeeNet Integration**
  - [ ] Add phone finder patterns to Action Agent
  - [ ] Add battery query patterns
  - [ ] Test voice commands end-to-end
  - [ ] Add phone status to dashboard

- [ ] **Documentation**
  - [ ] Document per-device quirks
  - [ ] Create family quick reference card
  - [ ] Update operations runbook

### Phase 2: Evaluation (Weeks 2-5)

- [ ] **Monitoring**
  - [ ] Track automation trigger counts
  - [ ] Note devices where silent bypass fails
  - [ ] Gather family feedback
  - [ ] Document feature requests

- [ ] **Decision**
  - [ ] Evaluate success metrics
  - [ ] Decide on Phase 3 (custom app) necessity
  - [ ] Document Phase 3 requirements if proceeding

### Phase 3: Custom App (If Needed - Weeks 6-14)

- [ ] **Android App**
  - [ ] Flutter project setup
  - [ ] Foreground service implementation
  - [ ] Battery monitoring
  - [ ] FCM integration
  - [ ] TTS implementation
  - [ ] BarnabeeNet API integration
  - [ ] Testing on all family Android devices

- [ ] **iOS App**
  - [ ] Critical Alerts entitlement application
  - [ ] iOS-specific implementations
  - [ ] Testing on family iOS devices

- [ ] **Backend**
  - [ ] Phone registry endpoints
  - [ ] FCM provider integration
  - [ ] Heartbeat processing
  - [ ] Dashboard integration

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| alarm_stream_max doesn't work on some phones | Medium | Medium | Test each device; fallback to notification channel with custom sound |
| Kids disable HA Companion | Medium | High | Parent controls on phone; explain value proposition to kids |
| iOS TTS limitations frustrate users | Medium | Low | Set expectations; iOS kids get sound alerts |
| Battery drain from HA Companion | Low | Medium | Optimize sensor update intervals; monitor battery impact |
| Apple rejects Critical Alerts entitlement | Medium | Medium | Use HA Companion's existing approval; accept sound-only |
| Custom app development scope creep | Medium | High | Strict MVP; defer features to later phases |

---

## Success Criteria

### Phase 1 Success (Go/No-Go for Phase 3)

| Criteria | Target | Measurement |
|----------|--------|-------------|
| Battery warnings delivered successfully | >95% | HA logs |
| Find phone works on all devices | 100% | Manual testing |
| Kids respond to warnings (subjective) | Noticeable improvement | Family feedback |
| No significant battery drain from HA Companion | <5% additional drain | Battery stats |
| Voice commands work reliably | >90% | Testing |

### Overall Feature Success

| Criteria | Target | Measurement |
|----------|--------|-------------|
| Reduction in "where's my phone" requests | >50% | Family observation |
| Phones dying unexpectedly | <1x per week per kid | Family observation |
| Parent visibility into phone status | Always available | Dashboard |
| Family satisfaction | Positive | Feedback |

---

## Appendix A: Device Compatibility Notes

Document quirks for each family device after testing:

| Device | OS | alarm_stream_max | Critical Alerts | Notes |
|--------|----|--------------------|-----------------|-------|
| Xander's Phone | Android 14 | TBD | N/A | |
| Penelope's Phone | iOS 17 | N/A | TBD | |
| Oliver's Phone | Android 13 | TBD | N/A | |
| Charlotte's Phone | Android 12 | TBD | N/A | |

---

## Appendix B: Voice Command Reference

| Command | Action | Response |
|---------|--------|----------|
| "Find Xander's phone" | Triggers alarm on device | "I'm pinging Xander's phone now" |
| "Where is Penelope's phone" | Reports last known location | "Penelope's phone was last seen at home 5 minutes ago" |
| "Is Oliver's phone charged" | Reports battery level | "Oliver's phone is at 45% battery" |
| "Battery check" | Reports all phone batteries | "Phone batteries: Xander 78%, Penelope 15%..." |
| "Ping Charlotte" | Triggers alarm | "Pinging Charlotte's phone!" |
| "Find all the phones" | Triggers alarm on all kids' phones | "I'm pinging all the kids' phones now!" |

---

## Appendix C: Related Documentation

- [BarnabeeNet Action Agent Patterns](./BarnabeeNet_Action_Agent.md)
- [Home Assistant Integration](./BarnabeeNet_HA_Integration.md)
- [Family Profiles](./BarnabeeNet_Family_Profiles.md)
- [Dashboard Architecture](./BarnabeeNet_Dashboard_Signal_Architecture.md)
- [Operations Runbook](./BarnabeeNet_Operations_Runbook.md)

---

*Document maintained by: BarnabeeNet Development Team*  
*Last updated: January 2026*
