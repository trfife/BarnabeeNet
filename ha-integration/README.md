# BarnabeeNet Home Assistant Integration

This custom integration adds BarnabeeNet as a conversation agent in Home Assistant.

## Features

- **Native Assist Integration** - Use BarnabeeNet with HA's built-in Assist feature
- **Automatic User Detection** - Speaker name is automatically detected from the logged-in HA user
- **Room Context** - If using a device in a specific area, that context is passed to BarnabeeNet
- **Conversation Memory** - Maintains conversation context across messages

## Installation

### HACS (Recommended)

1. Add this repository as a custom repository in HACS
2. Search for "BarnabeeNet" and install
3. Restart Home Assistant

### Manual Installation

1. Copy the `custom_components/barnabeenet` folder to your HA `config/custom_components/` directory:

```bash
# From your HA config directory
mkdir -p custom_components
cp -r /path/to/barnabeenet/ha-integration/custom_components/barnabeenet custom_components/
```

2. Restart Home Assistant

## Configuration

1. Go to **Settings** → **Devices & Services**
2. Click **Add Integration**
3. Search for "BarnabeeNet"
4. Enter your BarnabeeNet server URL (e.g., `http://192.168.86.51:8000`)
5. Click **Submit**

## Usage

### Set as Default Conversation Agent

1. Go to **Settings** → **Voice assistants**
2. Click on your voice assistant (or create one)
3. Under **Conversation agent**, select **BarnabeeNet**

### Use with Phones

1. Open the Home Assistant app on your phone
2. Tap the Assist button (microphone icon)
3. Speak your command
4. HA Cloud does STT, sends text to BarnabeeNet, speaks the response

### Use with Satellites

Assign BarnabeeNet to specific Wyoming satellites or ESPHome voice devices in the Voice assistants settings.

## How It Works

```
User speaks → HA STT (Cloud/Local) → BarnabeeNet conversation agent
                                          ↓
                                    POST /api/v1/chat
                                    {
                                      "text": "turn on kitchen lights",
                                      "speaker": "thom",  ← auto-detected from HA user
                                      "room": "living_room"  ← auto-detected from device area
                                    }
                                          ↓
                                    Response spoken via TTS
```

## Troubleshooting

### "Cannot connect to BarnabeeNet"

- Ensure BarnabeeNet is running: `curl http://192.168.86.51:8000/api/v1/health`
- Check that the URL is accessible from your HA instance
- Make sure there's no firewall blocking the connection

### Speaker not detected

- Ensure the HA user has a linked "Person" entity
- Check that the person entity has the correct `user_id` attribute

### Logs

Enable debug logging by adding to `configuration.yaml`:

```yaml
logger:
  logs:
    custom_components.barnabeenet: debug
```
