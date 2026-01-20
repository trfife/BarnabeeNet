# BarnabeeNet Integration Guide

Connect Home Assistant, ViewAssist, or any system to BarnabeeNet's AI brain.

## Quick Start

**Simplest possible request:**
```bash
curl "http://192.168.86.51:8000/api/v1/chat?text=what+time+is+it"
```

**Response:**
```json
{"response": "It's 3:45 PM.", "intent": "instant", "agent": "instant"}
```

That's it! BarnabeeNet handles intent classification, memory, device control, and everything else.

---

## API Endpoints

### 1. Simple Chat (Recommended)

**POST /api/v1/chat** - Send JSON body, get response

```bash
curl -X POST "http://192.168.86.51:8000/api/v1/chat" \
  -H "Content-Type: application/json" \
  -d '{"text": "turn on the kitchen lights", "speaker": "thom", "room": "kitchen"}'
```

**Response:**
```json
{
  "response": "Done! I've turned on the kitchen lights.",
  "intent": "action",
  "agent": "action",
  "conversation_id": "abc123"
}
```

**Body Fields:**
| Field | Required | Description |
|-----------|----------|-------------|
| text | ✅ | The command or question |
| speaker | ❌ | Who's speaking (for personalization) |
| room | ❌ | Which room (for context) |
| conversation_id | ❌ | Continue a conversation |

### 2. GET Chat (for testing)

**GET /api/v1/chat?text=...** - Same as POST, but GET for easy browser testing

```
http://192.168.86.51:8000/api/v1/chat?text=what%20time%20is%20it&speaker=thom
```

### 3. Full Process (with detailed trace)

**POST /api/v1/voice/process** - Returns full pipeline details

```bash
curl -X POST "http://192.168.86.51:8000/api/v1/voice/process" \
  -H "Content-Type: application/json" \
  -d '{"text": "turn on the lights", "speaker": "thom"}'
```

Returns: trace_id, latency breakdown, memory stats, LLM details, etc.

---

## Home Assistant Integration

### Option 1: REST Command (Recommended)

Add to `configuration.yaml`:

```yaml
rest_command:
  barnabee:
    url: "http://192.168.86.51:8000/api/v1/chat"
    method: POST
    content_type: "application/json"
    payload: '{"text": "{{ text }}", "speaker": "{{ speaker | default(''ha'') }}", "room": "{{ room | default('''') }}"}'
```

Use in automations:
```yaml
action:
  - service: rest_command.barnabee
    data:
      text: "Good morning! Time to wake up."
      speaker: "alexa"
      room: "bedroom"
```

### Option 2: Shell Command

```yaml
shell_command:
  barnabee: 'curl -s "http://192.168.86.51:8000/api/v1/chat?text={{ text | urlencode }}"'
```

### Option 3: Custom Conversation Agent (Recommended)

Install the BarnabeeNet custom component to use BarnabeeNet as a native HA conversation agent.
This is the best integration method - it automatically detects speaker from HA user and room from device area.

1. Copy `ha-integration/custom_components/barnabeenet/` to your HA `custom_components/` directory
2. Restart Home Assistant
3. Add BarnabeeNet integration: **Settings** → **Devices & Services** → **Add Integration** → "BarnabeeNet"
4. Enter URL: `http://192.168.86.51:8000`
5. Create an Assist Pipeline using BarnabeeNet as the conversation agent

---

## ViewAssist Integration

**For complete ViewAssist setup, see [VIEWASSIST_INTEGRATION.md](VIEWASSIST_INTEGRATION.md)**

ViewAssist tablets work with BarnabeeNet through Home Assistant's Assist pipeline:

1. Install BarnabeeNet HA custom component (see above)
2. Create an Assist Pipeline with BarnabeeNet as conversation agent
3. Install ViewAssist Companion App (VACA) on your tablet
4. Configure VACA to use the BarnabeeNet Assist Pipeline

**Direct API access** (for advanced use):

Text mode:
```
POST http://192.168.86.51:8000/api/v1/chat
{"text": "turn on the lights", "speaker": "thom", "room": "living_room"}
```

Audio mode (with transcription):
```
POST http://192.168.86.51:8000/api/v1/input/audio
Content-Type: multipart/form-data
audio: <file>
```

Returns transcription + AI response.

---

## Response Format

All endpoints return JSON with at minimum:

```json
{
  "response": "The AI's response text",
  "intent": "instant|action|interaction|memory",
  "agent": "which agent handled it"
}
```

**Intent types:**
- `instant` - Quick responses (time, date, math, greetings)
- `action` - Device control (lights, switches, covers, etc.)
- `interaction` - Conversations, questions, advice
- `memory` - Store/recall personal information

---

## Examples

### Device Control
```
text: "turn off all the lights downstairs"
→ response: "Done! I've turned off the lights on the first floor."
```

### Questions
```
text: "what's the weather like?"
→ response: "It's 72°F and sunny outside. Perfect day for a walk!"
```

### Memory
```
text: "remember that my favorite color is blue"
→ response: "Got it! I'll remember that your favorite color is blue."

text: "what's my favorite color?"
→ response: "Your favorite color is blue!"
```

### Conversation Context
Pass `conversation_id` to maintain context:
```
text: "who wrote Romeo and Juliet?"
→ response: "William Shakespeare wrote Romeo and Juliet."
   conversation_id: "conv_123"

text: "when was he born?"  (with conversation_id: "conv_123")
→ response: "Shakespeare was born in 1564."
```

---

## Health Check

```bash
curl http://192.168.86.51:8000/api/v1/health
```

```json
{"status": "healthy", "version": "0.1.0"}
```

---

## WebSocket (Real-time)

For streaming audio transcription:
```
ws://192.168.86.51:8000/api/v1/ws/transcribe
```

For dashboard activity feed:
```
ws://192.168.86.51:8000/ws/dashboard
```
