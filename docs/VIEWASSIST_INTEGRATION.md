# ViewAssist Integration Guide

Connect ViewAssist tablets to BarnabeeNet for AI-powered voice conversations.

## Overview

ViewAssist is a Home Assistant project that provides visual feedback on tablet dashboards for voice assistants. BarnabeeNet integrates with ViewAssist through Home Assistant's Assist pipeline.

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Tablet (ViewAssist)                          │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐            │
│  │ Wake Word   │───▶│ VACA App    │───▶│ HA Assist   │            │
│  │ Detection   │    │ (Audio)     │    │ Satellite   │            │
│  └─────────────┘    └─────────────┘    └─────────────┘            │
│                                               │                    │
└───────────────────────────────────────────────┼────────────────────┘
                                                │
                                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      Home Assistant                                  │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐            │
│  │ Assist      │───▶│ HA Cloud    │───▶│ BarnabeeNet │            │
│  │ Pipeline    │    │ STT         │    │ Agent       │            │
│  └─────────────┘    └─────────────┘    └─────────────┘            │
│                                               │                    │
└───────────────────────────────────────────────┼────────────────────┘
                                                │
                                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       BarnabeeNet Server                            │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐            │
│  │ MetaAgent   │───▶│ Agent       │───▶│ Response    │            │
│  │ (Classify)  │    │ Routing     │    │ + Actions   │            │
│  └─────────────┘    └─────────────┘    └─────────────┘            │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## Prerequisites

1. **BarnabeeNet server running** at `http://192.168.86.51:8000`
2. **Home Assistant** with voice assistant configured
3. **ViewAssist Companion App (VACA)** installed on tablet
4. **VACA HA Integration** installed via HACS

## Step 1: Install BarnabeeNet HA Custom Component

### Via HACS (Recommended)

1. Open HACS in Home Assistant
2. Go to **Integrations** → **Custom repositories**
3. Add repository: `https://github.com/trfife/BarnabeeNet`
4. Category: **Integration**
5. Click **Download**
6. Restart Home Assistant

### Manual Installation

1. Copy the `ha-integration/custom_components/barnabeenet/` folder to your HA `custom_components/` directory
2. Restart Home Assistant

### Configure the Integration

1. Go to **Settings** → **Devices & Services** → **Add Integration**
2. Search for "BarnabeeNet"
3. Enter BarnabeeNet URL: `http://192.168.86.51:8000`
4. Click **Submit**

The integration creates a conversation agent entity: `conversation.barnabeenet`

## Step 2: Create Assist Pipeline

1. Go to **Settings** → **Voice assistants**
2. Click **Add assistant**
3. Configure:
   - **Name**: Barnabee
   - **Language**: English
   - **Conversation agent**: BarnabeeNet
   - **Speech-to-text**: Home Assistant Cloud (or your preferred STT)
   - **Text-to-speech**: Home Assistant Cloud (or your preferred TTS)
4. Click **Create**

## Step 3: Install ViewAssist Companion App (VACA)

### On Your Tablet

1. Download VACA APK from [GitHub Releases](https://github.com/msp1974/ViewAssist_Companion_App/releases)
2. Install on your Android tablet
3. Open VACA and grant microphone permissions
4. Note the device ID shown in the app

### In Home Assistant

1. Install the **View Assist Companion App** integration via HACS
2. Go to **Settings** → **Devices & Services** → **Add Integration**
3. Search for "View Assist Companion App"
4. Enter your tablet's device ID
5. Click **Submit**

### Configure VACA to Use BarnabeeNet

1. Open VACA on your tablet
2. Go to **Settings** → **Voice Assistant**
3. Select **Barnabee** as the Assist Pipeline
4. Configure wake word (e.g., "Hey Barnabee")
5. Test by saying "Hey Barnabee, what time is it?"

## Step 4: Install ViewAssist Dashboard (Optional)

ViewAssist provides visual dashboards that show responses on your tablet.

1. Follow the [ViewAssist installation guide](https://dinki.github.io/View-Assist/docs/viewassist-setup/view-assist-integration)
2. Configure your satellite in View Assist settings
3. Set up visual responses for BarnabeeNet commands

## Alternative: Direct BarnabeeNet Integration

For advanced users who want to bypass HA's Assist pipeline:

### Direct Audio Input

Send audio directly to BarnabeeNet for STT + AI processing:

```bash
curl -X POST "http://192.168.86.51:8000/api/v1/input/audio" \
  -F "audio=@recording.wav" \
  -F "speaker=thom" \
  -F "room=living_room"
```

**Response:**
```json
{
  "transcription": "turn on the lights",
  "response": "Done! I've turned on the lights.",
  "intent": "action",
  "agent": "action"
}
```

### Direct Text Input

```bash
curl -X POST "http://192.168.86.51:8000/api/v1/chat" \
  -H "Content-Type: application/json" \
  -d '{"text": "what time is it", "speaker": "thom"}'
```

### WebSocket Streaming (Real-time)

For streaming audio transcription:

```
ws://192.168.86.51:8000/api/v1/voice/ws/transcribe
```

Send binary audio chunks, receive partial/final transcriptions as JSON.

## What Works

| Feature | Status | Notes |
|---------|--------|-------|
| Voice commands via VACA | ✅ | Through HA Assist pipeline |
| Device control | ✅ | "Turn on kitchen lights" |
| Conversations | ✅ | Complex questions, jokes, advice |
| Memory | ✅ | "Remember my favorite color is blue" |
| Multi-room | ✅ | Room detected from tablet location |
| Speaker ID | ✅ | From HA user login |
| Direct audio API | ✅ | `/api/v1/input/audio` |
| Direct text API | ✅ | `/api/v1/chat` |
| WebSocket streaming | ✅ | `/api/v1/voice/ws/transcribe` |

## Troubleshooting

### "BarnabeeNet is unavailable"

1. Check BarnabeeNet server is running: `curl http://192.168.86.51:8000/health`
2. Verify HA can reach the server (network/firewall)
3. Check HA logs for connection errors

### Slow Responses

1. Use HA Cloud STT (faster than local Whisper)
2. BarnabeeNet uses GPU STT when available (45ms vs 2400ms)
3. Check LLM model configuration in BarnabeeNet dashboard

### "I didn't understand that"

1. Check BarnabeeNet logs at `http://192.168.86.51:8000/`
2. Verify MetaAgent has a working LLM API key
3. Test directly: `curl "http://192.168.86.51:8000/api/v1/chat?text=hello"`

### Wake Word Not Working

1. Ensure VACA has microphone permissions
2. Try a different wake word
3. Check tablet audio settings (not muted)

## Example Commands

Once configured, try these with your ViewAssist tablet:

**Device Control:**
- "Hey Barnabee, turn on the living room lights"
- "Hey Barnabee, set the thermostat to 72 degrees"
- "Hey Barnabee, close all the blinds downstairs"

**Questions:**
- "Hey Barnabee, what time is it?"
- "Hey Barnabee, what's the weather like?"
- "Hey Barnabee, tell me a joke"

**Memory:**
- "Hey Barnabee, remember that my favorite color is blue"
- "Hey Barnabee, what's my favorite color?"

**Conversations:**
- "Hey Barnabee, who wrote Romeo and Juliet?"
- "When was he born?" (context maintained)

## Resources

- [ViewAssist Documentation](https://dinki.github.io/View-Assist/)
- [VACA GitHub](https://github.com/msp1974/ViewAssist_Companion_App)
- [BarnabeeNet Dashboard](http://192.168.86.51:8000/)
- [BarnabeeNet Integration Guide](INTEGRATION.md)
