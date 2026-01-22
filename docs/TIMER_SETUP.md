# Timer Setup Guide for BarnabeeNet

## Overview

BarnabeeNet uses Home Assistant timer helper entities to manage timers. You need to create timer helpers in Home Assistant before using timer functionality.

## Prerequisites

- Home Assistant installed and running
- BarnabeeNet connected to Home Assistant
- Access to Home Assistant UI or YAML configuration

## Creating Timer Helpers

### Option 1: Via Home Assistant UI

1. Go to **Settings** → **Devices & Services** → **Helpers**
2. Click **+ CREATE HELPER** (bottom right)
3. Select **Timer**
4. Create 5-10 timer helpers with these names:
   - `barnabee_1`
   - `barnabee_2`
   - `barnabee_3`
   - `barnabee_4`
   - `barnabee_5`
   - `barnabee_6`
   - `barnabee_7`
   - `barnabee_8`
   - `barnabee_9`
   - `barnabee_10`

5. For each timer:
   - **Name**: `barnabee_1` (through `barnabee_10`)
   - **Icon**: ⏱️ (optional)
   - **Duration**: Leave default (will be set by BarnabeeNet)

### Option 2: Via YAML Configuration

Add to your `configuration.yaml`:

```yaml
timer:
  barnabee_1:
    name: Barnabee Timer 1
    icon: mdi:timer
  barnabee_2:
    name: Barnabee Timer 2
    icon: mdi:timer
  barnabee_3:
    name: Barnabee Timer 3
    icon: mdi:timer
  barnabee_4:
    name: Barnabee Timer 4
    icon: mdi:timer
  barnabee_5:
    name: Barnabee Timer 5
    icon: mdi:timer
  barnabee_6:
    name: Barnabee Timer 6
    icon: mdi:timer
  barnabee_7:
    name: Barnabee Timer 7
    icon: mdi:timer
  barnabee_8:
    name: Barnabee Timer 8
    icon: mdi:timer
  barnabee_9:
    name: Barnabee Timer 9
    icon: mdi:timer
  barnabee_10:
    name: Barnabee Timer 10
    icon: mdi:timer
```

After adding to YAML:
1. Restart Home Assistant
2. Verify timers appear in **Developer Tools** → **States** (search for `timer.barnabee_*`)

## Verification

After creating the timers, verify they're accessible:

1. In Home Assistant, go to **Developer Tools** → **States**
2. Search for `timer.barnabee`
3. You should see `timer.barnabee_1` through `timer.barnabee_10`

BarnabeeNet will automatically discover these timers on startup.

## Timer Features

Once set up, you can use timers with commands like:

### Basic Timers
- "Set a timer for 5 minutes"
- "Set a lasagna timer for 20 minutes"
- "Start a timer for 10 minutes"

### Timer Queries
- "How long on lasagna?"
- "How much time left on pizza?"
- "Time left on lasagna"

### Timer Control
- "Pause the lasagna timer"
- "Resume the lasagna timer"
- "Cancel the lasagna timer"
- "Stop the lasagna timer"

### Device Duration Timers
- "Turn on the office fan for 10 minutes"
- "Turn on the office light for 5 minutes"

### Delayed Actions
- "In 60 seconds turn off the office light"
- "Wait 3 minutes turn on the office fan"
- "Turn off the office fan in 30 seconds"

### Chained Actions
- "Wait 3 minutes turn on the office fan and then in 30 seconds turn it off again"
- "In 60 seconds turn off the office light and then in 10 seconds turn it back on"

## Testing

Use the office fan and light for testing (safe entities):
- Office fan: `fan.office_fan` (or your actual entity ID)
- Office light: `light.office_light` (or your actual entity ID)

Example test commands:
1. "Turn on the office fan for 2 minutes"
2. "In 30 seconds turn off the office light"
3. "Wait 1 minute turn on the office fan and then in 20 seconds turn it off again"

## Troubleshooting

### No Timer Entities Found

If you see a warning: "No timer entities found matching pattern timer.barnabee_*"

1. Verify timers exist in Home Assistant:
   - Go to **Developer Tools** → **States**
   - Search for `timer.barnabee`
2. Check entity IDs match exactly: `timer.barnabee_1`, `timer.barnabee_2`, etc.
3. Restart BarnabeeNet after creating timers
4. Check BarnabeeNet logs for timer discovery messages

### Timer Not Starting

1. Check Home Assistant connection in BarnabeeNet Configuration
2. Verify timer entity is not already in use
3. Check BarnabeeNet logs for errors

### Chained Actions Not Working

1. Ensure entity IDs are correctly resolved
2. Check that actions are parsed correctly (use dashboard to see action details)
3. Verify Home Assistant service calls are working

## Notes

- Timer pool size: Default is 10 timers. You can create more if needed.
- Timer entities are pooled and reused automatically
- Timers persist across BarnabeeNet restarts (managed by Home Assistant)
- Paused timers resume from where they left off
