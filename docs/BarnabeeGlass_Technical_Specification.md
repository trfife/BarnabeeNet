# BarnabeeGlass: Custom Smart Glasses AI System
## Technical Specification for Building a MentraOS-Style Platform Connected to BarnabeeNet

**Version:** 1.0  
**Author:** Thom Fife  
**Date:** January 2026  
**Purpose:** Fork reference document for building custom smart glasses AI integration with Barnabee

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [System Architecture Overview](#2-system-architecture-overview)
3. [Hardware: Even Realities G1 Glasses](#3-hardware-even-realities-g1-glasses)
4. [Bluetooth Connectivity & Protocol](#4-bluetooth-connectivity--protocol)
5. [Audio Capture Pipeline](#5-audio-capture-pipeline)
6. [Real-Time Transcription Services](#6-real-time-transcription-services)
7. [Display System & Layouts](#7-display-system--layouts)
8. [Mobile App Architecture](#8-mobile-app-architecture)
9. [Cloud Backend Architecture](#9-cloud-backend-architecture)
10. [SDK & App Development](#10-sdk--app-development)
11. [Barnabee Integration Points](#11-barnabee-integration-points)
12. [Key Open Source Resources](#12-key-open-source-resources)
13. [Implementation Roadmap](#13-implementation-roadmap)
14. [Environment Configuration Reference](#14-environment-configuration-reference)

---

## 1. Executive Summary

This document provides complete technical specifications for building a custom smart glasses AI system (codename: **BarnabeeGlass**) that replicates and extends the functionality of MentraOS, connected exclusively to your Barnabee AI assistant and BarnabeeNet infrastructure.

### What MentraOS Is

MentraOS (formerly AugmentOS) is an open-source operating system for smart glasses that provides:
- Cross-device compatibility (Even Realities G1, Vuzix Z100, Mentra Live)
- Real-time audio capture and transcription
- AI assistant integration
- Text display on glasses
- App ecosystem with SDK

### Your Custom Version (BarnabeeGlass)

Your fork will:
- Connect exclusively to your Azure OpenAI instance via Barnabee
- Use Azure Speech Services for transcription (consistent with your existing stack)
- Integrate with BarnabeeNet's Node-RED infrastructure
- Support G1 glasses and phone microphone input
- Leverage your existing sub-2ms response architecture

---

## 2. System Architecture Overview

### MentraOS Architecture (Reference)

```
┌─────────────────┐     BLE      ┌──────────────────┐   WebSocket    ┌────────────────┐
│  Smart Glasses  │◄────────────►│   Mobile App     │◄──────────────►│  Cloud Backend │
│  (G1/Mentra)    │              │  (React Native)  │                │  (Node.js)     │
└─────────────────┘              └──────────────────┘                └────────┬───────┘
                                                                              │
                                                                     WebSocket│
                                                                              ▼
                                                                    ┌────────────────┐
                                                                    │  Third-Party   │
                                                                    │  Apps (SDK)    │
                                                                    └────────────────┘
```

### BarnabeeGlass Architecture (Your Version)

```
┌─────────────────┐     BLE      ┌──────────────────┐   WebSocket    ┌────────────────┐
│  G1 Glasses     │◄────────────►│   BarnabeeGlass  │◄──────────────►│  BarnabeeNet   │
│                 │              │   Mobile App     │                │  (Node-RED)    │
│ • Microphone    │   LC3 Audio  │                  │                │                │
│ • MicroLED      │   ─────────► │ • BLE Manager    │  Audio Stream  │ • Azure Speech │
│ • TouchBars     │              │ • LC3 Decoder    │  ─────────────►│   (STT)        │
│                 │   Text/BMP   │ • Display Format │                │                │
│                 │   ◄───────── │                  │  Text Response │ • Azure OpenAI │
└─────────────────┘              └──────────────────┘  ◄─────────────│   (Barnabee)   │
                                                                     └────────────────┘
```

### Data Flow Summary

1. **User speaks** → G1 glasses microphone captures audio
2. **Audio streams** → LC3 codec over BLE to mobile app
3. **Mobile app** → Streams audio via WebSocket to BarnabeeNet
4. **BarnabeeNet** → Sends to Azure Speech Services for transcription
5. **Transcription** → Passes to Azure OpenAI (your GPT-4 deployment)
6. **AI Response** → Returns through WebSocket to mobile app
7. **Display** → Mobile app formats and sends text to glasses via BLE

---

## 3. Hardware: Even Realities G1 Glasses

### Display Specifications

| Specification | Value |
|---------------|-------|
| **Display Type** | JBD 0.13" green monochrome MicroLED |
| **Native Resolution** | 640×480 pixels |
| **Effective Resolution** | 640×200 pixels (active area) |
| **AI Text Width** | 488 pixels maximum |
| **Field of View** | 25° horizontal |
| **Transparency** | 98% (diffractive waveguide) |
| **Brightness** | 1,000 nits (auto-adjusting) |
| **Refresh Rate** | 20Hz |
| **Perceived Distance** | 1-5 meters in front of user |

### Image Format Requirements

- **Dimensions:** 576×136 pixels
- **Format:** 1-bit BMP
- **Color:** Only lit pixels illuminate (black = off)

### Audio Specifications

| Specification | Value |
|---------------|-------|
| **Microphones** | 2 MEMS (temple tips) |
| **Active Microphone** | Right side for recording |
| **Audio Codec** | LC3 (Low Complexity Communication Codec) |
| **Max Recording** | 30 seconds per session |
| **Typical Sample Rate** | 16-48kHz (LC3 standard) |
| **Bit Depth** | 16-bit |

### Battery & Physical

| Specification | Value |
|---------------|-------|
| **Glasses Battery** | 160mAh (~1.5 days typical) |
| **Case Battery** | 2,000mAh |
| **Weight** | 44 grams |
| **Bluetooth** | BLE 5.2 |

---

## 4. Bluetooth Connectivity & Protocol

### Critical: Dual BLE Connection Architecture

The G1 uses a unique **dual BLE connection** system—each temple arm maintains a separate Bluetooth connection. This is essential for your implementation.

**Device Naming Pattern:**
- Left arm: `G1_X_L`, `G1_XX_L`, or `G1_XXX_L`
- Right arm: `G1_X_R`, `G1_XX_R`, or `G1_XXX_R`

**Command Sequence Rule:**  
Commands must be sent to the **left arm first**, wait for acknowledgment, then send to the **right arm**.

### Core BLE Commands

```javascript
// Command Reference from EvenDemoApp
const COMMANDS = {
  // Microphone Control
  ENABLE_MIC: [0x0E, 0x01],           // Enable right-side microphone
  AUDIO_DATA: 0xF1,                    // Receive audio stream
  
  // Display Commands
  SEND_TEXT: 0x4E,                     // Send AI text with pagination
  SEND_BMP: 0x15,                      // Send BMP image (194 bytes/packet)
  END_TRANSMISSION: [0x20, 0x0D, 0x0E], // Signal end of data
  CRC_VALIDATE: 0x16,                  // CRC32 validation
  
  // TouchBar Events (Received)
  TOUCHBAR_EVENT: 0xF5,                // TouchBar interaction prefix
};

// TouchBar Event Types (second byte after 0xF5)
const TOUCHBAR_EVENTS = {
  SINGLE_TAP: 0x01,        // Page navigation
  DOUBLE_TAP: 0x00,        // Close/exit
  TRIPLE_TAP_LEFT: 0x04,   // Toggle silent mode
  TRIPLE_TAP_RIGHT: 0x05,  // Toggle silent mode
  AI_ACTIVATED: 0x17,      // Long-press left (start AI)
  AI_STOPPED: 0x18,        // Stop AI recording
};
```

### Text Display Command Structure (0x4E)

```javascript
// Packet format for sending text to glasses
const textPacket = [
  seq,              // Sequence number (0-255)
  total_packages,   // Total packets in this transmission
  current_package,  // Current packet number
  newscreen_status, // Display status byte
  current_page,     // Current page number
  max_page,         // Maximum pages
  ...data           // Text data bytes
];

// Status byte values
const DISPLAY_STATUS = {
  AI_DISPLAYING: 0x30,    // Auto-scroll mode
  AI_COMPLETE: 0x40,      // Display complete
  NETWORK_ERROR: 0x60,    // Error state
};
```

### Audio Stream Format

```javascript
// Audio packet format (0xF1 command)
const audioPacket = [
  sequence_number,  // 0-255, cycles for packet ordering
  ...audio_data     // LC3 encoded audio bytes
];
```

---

## 5. Audio Capture Pipeline

### Pipeline Flow

```
┌──────────────┐    ┌───────────────┐    ┌──────────────┐    ┌─────────────┐
│ G1 Mic       │───►│ LC3 Encoder   │───►│ BLE Stream   │───►│ Mobile App  │
│ (Right side) │    │ (On glasses)  │    │ (0xF1 cmd)   │    │             │
└──────────────┘    └───────────────┘    └──────────────┘    └──────┬──────┘
                                                                    │
                                                                    ▼
┌──────────────┐    ┌───────────────┐    ┌──────────────┐    ┌─────────────┐
│ Display      │◄───│ Response      │◄───│ Azure OpenAI │◄───│ Azure STT   │
│ (0x4E cmd)   │    │ Formatting    │    │ (Barnabee)   │    │ WebSocket   │
└──────────────┘    └───────────────┘    └──────────────┘    └─────────────┘
```

### LC3 Codec Details

LC3 (Low Complexity Communication Codec) is Bluetooth LE Audio's standard codec:
- **Compression:** High efficiency, low latency
- **Frame Duration:** 7.5ms or 10ms
- **Bit Rate:** 16-320 kbps
- **Sample Rates:** 8/16/24/32/44.1/48 kHz

**Decoding Libraries:**
- **liblc3** (official reference): https://github.com/google/liblc3
- **lc3-codec** (npm): For JavaScript/Node.js
- **pylc3** (pip): Python bindings

### Alternative: Phone Microphone

For situations where G1 glasses aren't available:

```javascript
// Web Audio API for phone mic capture
const audioContext = new AudioContext({ sampleRate: 16000 });
const stream = await navigator.mediaDevices.getUserMedia({ 
  audio: { 
    sampleRate: 16000,
    channelCount: 1,
    echoCancellation: true,
    noiseSuppression: true
  } 
});

const source = audioContext.createMediaStreamSource(stream);
const processor = audioContext.createScriptProcessor(4096, 1, 1);

processor.onaudioprocess = (e) => {
  const audioData = e.inputBuffer.getChannelData(0);
  // Convert to 16-bit PCM
  const pcmData = float32ToPCM16(audioData);
  // Send to BarnabeeNet
  websocket.send(pcmData);
};
```

---

## 6. Real-Time Transcription Services

### MentraOS Transcription Options

MentraOS supports two primary transcription services:

1. **Azure Speech Services** (Recommended for your stack)
2. **Soniox** (Alternative)

### Azure Speech Services Integration

Since you're already using Azure, this is the natural choice for BarnabeeGlass.

**Configuration Variables:**
```bash
AZURE_SPEECH_REGION=eastus  # or your preferred region
AZURE_SPEECH_KEY=your-speech-services-key
```

**WebSocket Streaming Implementation:**

```javascript
// Azure Speech SDK real-time transcription
import * as speechsdk from 'microsoft-cognitiveservices-speech-sdk';

class AzureTranscriptionService {
  constructor(subscriptionKey, region) {
    this.speechConfig = speechsdk.SpeechConfig.fromSubscription(
      subscriptionKey, 
      region
    );
    this.speechConfig.speechRecognitionLanguage = 'en-US';
    
    // Enable real-time streaming
    this.audioConfig = speechsdk.AudioConfig.fromStreamInput(
      this.pushStream
    );
  }

  startStreaming(onInterim, onFinal) {
    this.recognizer = new speechsdk.SpeechRecognizer(
      this.speechConfig, 
      this.audioConfig
    );

    // Interim results (partial transcription)
    this.recognizer.recognizing = (s, e) => {
      onInterim(e.result.text);
    };

    // Final results
    this.recognizer.recognized = (s, e) => {
      if (e.result.reason === speechsdk.ResultReason.RecognizedSpeech) {
        onFinal(e.result.text);
      }
    };

    this.recognizer.startContinuousRecognitionAsync();
  }

  pushAudioChunk(audioBuffer) {
    // Push decoded LC3 audio (PCM format)
    this.pushStream.write(audioBuffer);
  }

  stop() {
    this.recognizer.stopContinuousRecognitionAsync();
  }
}
```

**Audio Format Requirements for Azure:**
- Format: Raw PCM (16-bit linear)
- Sample Rate: 16kHz or 8kHz
- Channels: Mono
- Container: None (raw bytes) or WAV header

### Alternative: Deepgram (Lower Latency)

If you need sub-300ms latency:

```javascript
// Deepgram WebSocket streaming
const deepgram = new Deepgram(DEEPGRAM_API_KEY);

const connection = deepgram.transcription.live({
  punctuate: true,
  interim_results: true,
  language: 'en-US',
  model: 'nova-2',  // Latest model
});

connection.on('transcriptReceived', (data) => {
  const transcript = data.channel.alternatives[0].transcript;
  const isFinal = data.is_final;
  // Process transcript
});

// Send audio chunks
connection.send(audioBuffer);
```

### Transcription Latency Comparison

| Service | Typical Latency | Streaming | Best For |
|---------|----------------|-----------|----------|
| Azure Speech | ~200-400ms | WebSocket | Azure ecosystem integration |
| Deepgram Nova-2 | ~150-300ms | Native WS | Lowest latency |
| OpenAI Whisper API | ~500ms+ | Batch | Accuracy, multilingual |
| AssemblyAI | ~300-500ms | Yes | Speaker diarization |

---

## 7. Display System & Layouts

### Layout Types

MentraOS provides four primary layout types:

```typescript
// Layout Type Definitions
interface TextWall {
  layoutType: 'TEXT_WALL';
  text: string;
}

interface DoubleTextWall {
  layoutType: 'DOUBLE_TEXT_WALL';
  topText: string;
  bottomText: string;
}

interface ReferenceCard {
  layoutType: 'REFERENCE_CARD';
  title: string;
  text: string;
}

interface DashboardCard {
  layoutType: 'DASHBOARD_CARD';
  leftText: string;
  rightText: string;
}
```

### Display Constraints

| Constraint | Value |
|------------|-------|
| Max Width | 488 pixels (for AI text) |
| Recommended Font Size | 21 |
| Visible Lines | ~5 per screen |
| Character Limit | ~25-30 chars per line |

### Pagination System

For responses longer than one screen:

```javascript
// Pagination structure
const paginatedResponse = {
  currentPage: 1,
  maxPages: 3,
  content: [
    "First screen of text...",
    "Second screen of text...",
    "Third screen of text..."
  ]
};

// Send paginated content
async function sendPaginatedText(session, pages) {
  for (let i = 0; i < pages.length; i++) {
    await sendTextPacket({
      text: pages[i],
      currentPage: i + 1,
      maxPage: pages.length,
      status: i === pages.length - 1 ? 0x40 : 0x30  // Complete on last
    });
  }
}
```

### BMP Image Display

For custom graphics (icons, diagrams):

```javascript
// BMP format requirements
const bmpConfig = {
  width: 576,
  height: 136,
  bitsPerPixel: 1,  // Monochrome
  packetSize: 194   // Bytes per BLE packet
};

// Send BMP in chunks
async function sendBitmap(imageBuffer) {
  const packets = chunkBuffer(imageBuffer, 194);
  for (const packet of packets) {
    await sendBLECommand(0x15, packet);
  }
  await sendBLECommand([0x20, 0x0D, 0x0E]);  // End transmission
}
```

---

## 8. Mobile App Architecture

### MentraOS Mobile Structure

```
mobile/
├── src/
│   ├── services/
│   │   ├── BLEManager.ts         # Bluetooth connection handling
│   │   ├── GlassesProtocol.ts    # G1 command protocol
│   │   ├── AudioProcessor.ts     # LC3 decoding
│   │   └── WebSocketClient.ts    # Cloud connection
│   ├── screens/
│   │   ├── HomeScreen.tsx        # Main interface
│   │   ├── SettingsScreen.tsx    # Configuration
│   │   └── DevModeScreen.tsx     # Developer options
│   └── stores/
│       ├── GlassesStore.ts       # Glasses state
│       └── SessionStore.ts       # User session
├── android/                       # Native Android code
├── ios/                           # Native iOS code
└── app.config.ts                  # Expo configuration
```

### BarnabeeGlass Mobile Simplification

Your version can be significantly simpler:

```
barnabee-glass-app/
├── src/
│   ├── services/
│   │   ├── G1Connection.ts       # G1 BLE handling
│   │   ├── LC3Decoder.ts         # Audio decoding
│   │   └── BarnabeeClient.ts     # BarnabeeNet WebSocket
│   ├── screens/
│   │   ├── MainScreen.tsx        # Single main screen
│   │   └── SettingsScreen.tsx    # Connection config
│   └── App.tsx
└── package.json
```

### Key BLE Manager Implementation

```typescript
// G1Connection.ts
import { BleManager, Device, Characteristic } from 'react-native-ble-plx';

class G1Connection {
  private manager: BleManager;
  private leftDevice: Device | null = null;
  private rightDevice: Device | null = null;

  async connect() {
    // Scan for G1 devices
    this.manager.startDeviceScan(null, null, (error, device) => {
      if (device?.name?.includes('G1_') && device.name.includes('_L')) {
        this.connectLeft(device);
      }
      if (device?.name?.includes('G1_') && device.name.includes('_R')) {
        this.connectRight(device);
      }
    });
  }

  async sendCommand(command: number[], data?: Uint8Array) {
    // Always send to left first, then right
    await this.leftDevice?.writeCharacteristic(
      SERVICE_UUID,
      CHAR_UUID,
      Buffer.from([...command, ...(data || [])]).toString('base64')
    );
    await this.rightDevice?.writeCharacteristic(
      SERVICE_UUID,
      CHAR_UUID,
      Buffer.from([...command, ...(data || [])]).toString('base64')
    );
  }

  subscribeToAudio(onAudioData: (data: Uint8Array) => void) {
    // Subscribe to 0xF1 notifications
    this.rightDevice?.monitorCharacteristicForDevice(
      SERVICE_UUID,
      AUDIO_CHAR_UUID,
      (error, characteristic) => {
        if (characteristic?.value) {
          const data = Buffer.from(characteristic.value, 'base64');
          onAudioData(new Uint8Array(data));
        }
      }
    );
  }
}
```

---

## 9. Cloud Backend Architecture

### MentraOS Cloud Structure

```
cloud/packages/
├── cloud/                    # Main backend service
│   ├── src/
│   │   ├── services/
│   │   │   ├── WebSocketService.ts
│   │   │   ├── TranscriptionService.ts
│   │   │   ├── SessionManager.ts
│   │   │   └── DisplayManager.ts
│   │   ├── managers/
│   │   │   ├── AudioManager.ts
│   │   │   ├── CameraManager.ts
│   │   │   └── LocationManager.ts
│   │   └── index.ts
├── sdk/                      # TypeScript SDK for apps
├── store/                    # App store frontend
└── tests/                    # Integration tests
```

### BarnabeeNet Integration Architecture

Your backend integrates with existing BarnabeeNet:

```
BarnabeeNet (Node-RED)
├── flows/
│   ├── glasses-websocket.json    # WebSocket endpoint
│   ├── audio-processing.json     # LC3 decode + STT
│   ├── barnabee-ai.json          # Azure OpenAI calls
│   └── display-formatting.json   # Response formatting
└── subflows/
    ├── azure-stt.json            # Azure Speech wrapper
    └── azure-openai.json         # Existing Barnabee logic
```

### Node-RED Flow: Glasses WebSocket Handler

```json
{
  "id": "glasses-ws-handler",
  "type": "websocket in",
  "name": "Glasses WebSocket",
  "server": "glasses-ws-server",
  "wires": [["audio-processor"]]
}
```

### Session Management

```typescript
// UserSession equivalent for BarnabeeGlass
interface GlassesSession {
  sessionId: string;
  userId: string;
  connectedAt: Date;
  glassesConnected: boolean;
  
  // Capabilities
  capabilities: {
    hasDisplay: boolean;
    hasMicrophone: boolean;
    hasCamera: boolean;
  };
  
  // Current state
  state: {
    isRecording: boolean;
    currentPage: number;
    lastTranscription: string;
    pendingResponse: string | null;
  };
}
```

---

## 10. SDK & App Development

### MentraOS SDK Overview

The `@mentraos/sdk` package provides:

```typescript
import { 
  AppServer,
  AppSession,
  TranscriptionData,
  ButtonPress,
  PhotoData,
  LocationUpdate
} from '@mentraos/sdk';

// Create app server
class MyApp extends AppServer {
  async onSession(session: AppSession) {
    // Handle new session
    session.events.onTranscription((data: TranscriptionData) => {
      console.log(`User said: ${data.text}`);
    });
    
    session.events.onButtonPress((data: ButtonPress) => {
      console.log(`Button: ${data.buttonId}, Type: ${data.pressType}`);
    });
  }
}
```

### Key SDK Methods

```typescript
// Display methods
session.layouts.showTextWall("Hello World!");
session.layouts.showDoubleTextWall("Title", "Content");
session.layouts.showReferenceCard({ title: "Card", text: "Details" });
session.layouts.showDashboardCard({ left: "Label", right: "Value" });
session.layouts.clearView();

// Audio methods
session.audio.play('https://example.com/sound.mp3');
session.audio.speak('Hello world', { language: 'en-US' });
session.audio.stop();

// Camera methods (if available)
const photo = await session.camera.requestPhoto();

// Dashboard
session.dashboard.write({ text: "Status update" });
```

### Event Types

```typescript
// Transcription event
interface TranscriptionData {
  text: string;
  transcribeLanguage: string;
  isFinal: boolean;
  timestamp: number;
}

// Button press event
interface ButtonPress {
  buttonId: 'main' | 'side';
  pressType: 'single' | 'double' | 'long';
  timestamp: number;
}

// Head position event
interface HeadPosition {
  position: 'up' | 'down' | 'center';
  timestamp: number;
}
```

### For BarnabeeGlass: Simplified Direct Integration

Since you're not building an app ecosystem, you can skip the SDK layer:

```typescript
// Direct BarnabeeNet integration
class BarnabeeGlassService {
  private ws: WebSocket;
  private azureSpeech: AzureTranscriptionService;
  private azureOpenAI: AzureOpenAIClient;

  async handleAudioStream(audioBuffer: Uint8Array) {
    // Decode LC3 to PCM
    const pcm = await this.decodeLC3(audioBuffer);
    
    // Stream to Azure Speech
    this.azureSpeech.pushAudioChunk(pcm);
  }

  async handleTranscription(text: string, isFinal: boolean) {
    if (isFinal && text.length > 0) {
      // Send to Barnabee (Azure OpenAI)
      const response = await this.azureOpenAI.chat([
        { role: 'system', content: 'You are Barnabee...' },
        { role: 'user', content: text }
      ]);
      
      // Format and display
      const formatted = this.formatForGlasses(response);
      await this.displayOnGlasses(formatted);
    }
  }

  private formatForGlasses(text: string): string[] {
    // Split into pages (~25 chars × 5 lines = 125 chars per page)
    const maxCharsPerPage = 120;
    const pages: string[] = [];
    
    for (let i = 0; i < text.length; i += maxCharsPerPage) {
      pages.push(text.slice(i, i + maxCharsPerPage));
    }
    
    return pages;
  }
}
```

---

## 11. Barnabee Integration Points

### Existing BarnabeeNet Architecture

Based on your existing system:

```
BarnabeeNet
├── Node-RED (orchestration)
├── Azure OpenAI (GPT-4)
├── Home Assistant (device control)
├── Whisper (optional local STT)
└── WebSocket bridge (sub-2ms latency)
```

### Integration Strategy

**Option A: Node-RED Native Integration**

Add glasses handling directly to Node-RED:

```
[Glasses WS In] → [LC3 Decode] → [Azure STT] → [Barnabee AI] → [Format] → [Glasses WS Out]
```

**Option B: Dedicated Microservice**

Separate glasses handling service that calls BarnabeeNet:

```
Mobile App ──► Glasses Service ──► BarnabeeNet API ──► Azure OpenAI
                     │
                     └──► Azure Speech (direct)
```

### Recommended: Hybrid Approach

Given your sub-2ms architecture goals:

```javascript
// glasses-service.ts
class GlassesService {
  private barnabeeWS: WebSocket;  // Existing Barnabee WebSocket
  private azureSpeech: SpeechRecognizer;
  
  constructor() {
    // Connect to existing BarnabeeNet WebSocket
    this.barnabeeWS = new WebSocket('ws://barnabee.local:1880/ws/chat');
    
    // Direct Azure Speech connection (bypass Node-RED for latency)
    this.azureSpeech = new SpeechRecognizer(/* config */);
  }

  async processVoiceCommand(audioBuffer: Uint8Array) {
    // 1. Direct STT (lowest latency path)
    const transcription = await this.transcribe(audioBuffer);
    
    // 2. Send to Barnabee via existing WebSocket
    this.barnabeeWS.send(JSON.stringify({
      type: 'glasses_command',
      text: transcription,
      context: 'voice_assistant'
    }));
  }

  onBarnabeeResponse(response: string) {
    // Format and display on glasses
    this.displayResponse(response);
  }
}
```

### Context Injection

Enhance Barnabee with glasses context:

```javascript
const systemPrompt = `You are Barnabee, Thom's AI assistant. 
You are currently responding via smart glasses display.

DISPLAY CONSTRAINTS:
- Keep responses under 200 characters for comfortable reading
- Use short, clear sentences
- Avoid markdown formatting
- For longer responses, indicate continuation

CURRENT CONTEXT:
- User is wearing Even Realities G1 glasses
- Display is green monochrome MicroLED
- User can page through responses with touchbar

CAPABILITIES:
- Voice responses (via glasses speakers)
- Text display (5 lines visible)
- Home automation commands available`;
```

---

## 12. Key Open Source Resources

### Primary Repository

**MentraOS (Main):**  
https://github.com/Mentra-Community/MentraOS

- MIT License
- 1,500+ stars
- Complete source code
- Active development

### Official Even Realities Resources

**EvenDemoApp:**  
https://github.com/even-realities/EvenDemoApp
- BSD-2-Clause license
- Complete BLE protocol documentation
- Flutter reference implementation

**Official GitHub:**  
https://github.com/even-realities

### Community Libraries

**Python SDK:**
```bash
pip install even_glasses
```
- GitHub: github.com/emingenc/g1-python
- GPL-3.0 license
- BLE control, text display

**Android Library:**
- GitHub: github.com/rodrigofalvarez/g1-basis-android
- Kotlin, coroutines/Flow
- Modular architecture

**Gadgetbridge Support:**
- https://gadgetbridge.org/gadgets/others/even_realities/
- Open source Android app
- Reverse-engineered protocol details

### Documentation

**MentraOS Cloud Docs:**
- https://cloud-docs.mentra.glass
- SDK integration guides
- API reference

**MentraOS App Docs:**
- https://docs.mentra.glass
- App development tutorials
- Layout reference

### Example Apps

**MentraOS Example App:**  
https://github.com/Mentra-Community/MentraOS-Cloud-Example-App

**React Example:**  
https://github.com/Mentra-Community/MentraOS-React-Example-App

**Live Captions:**  
https://github.com/Mentra-Community/LiveCaptionsOnSmartGlasses

### Community Resources

**Discord Communities:**
- G1 Community: discord.com/invite/gKjXY9M (~4,000 members)
- MentraOS: mentra.glass/discord
- Even Hub: discord.gg/GsuDkKDXDe

**Curated List:**  
https://github.com/galfaroth/awesome-even-realities-g1

---

## 13. Implementation Roadmap

### Phase 1: Foundation (Week 1-2)

1. **Clone MentraOS repository**
   ```bash
   git clone https://github.com/Mentra-Community/MentraOS.git
   cd MentraOS
   ```

2. **Study G1 protocol**
   - Review `mobile/src/services/` for BLE handling
   - Understand command structure from EvenDemoApp

3. **Set up development environment**
   - Install Bun, Docker, ngrok
   - Configure environment variables

### Phase 2: BLE Integration (Week 3-4)

1. **Create simplified mobile app**
   - React Native or native Android
   - G1 BLE connection only (no app ecosystem)

2. **Implement core commands**
   - Microphone enable/disable
   - Audio stream reception
   - Text display

3. **Test with physical G1 glasses**

### Phase 3: Audio Pipeline (Week 5-6)

1. **LC3 decoding**
   - Integrate liblc3 or JavaScript decoder
   - Test audio quality

2. **Azure Speech integration**
   - WebSocket streaming setup
   - Real-time transcription testing

3. **Latency optimization**
   - Target <500ms end-to-end

### Phase 4: Barnabee Integration (Week 7-8)

1. **Connect to BarnabeeNet**
   - WebSocket bridge setup
   - Context injection

2. **Response formatting**
   - Pagination logic
   - Display optimization

3. **End-to-end testing**
   - Voice command flow
   - Response display

### Phase 5: Enhancement (Week 9+)

1. **Additional features**
   - Head position detection
   - Dashboard integration
   - Notification forwarding

2. **Performance tuning**
   - Latency reduction
   - Battery optimization

3. **Documentation**
   - Usage guide
   - Maintenance procedures

---

## 14. Environment Configuration Reference

### BarnabeeGlass Environment Variables

```bash
# ===========================================
# BarnabeeGlass Configuration
# ===========================================

# Server Configuration
NODE_ENV=development
PORT=8002
CLOUD_VERSION=1.0.0

# MongoDB (for session storage)
MONGO_URL=mongodb://localhost:27017/barnabeeglass

# JWT Authentication
AUTH_JWT_SECRET=your-secure-jwt-secret
JWT_PRIVATE_KEY=-----BEGIN PRIVATE KEY-----
your-rsa-private-key
-----END PRIVATE KEY-----

# ===========================================
# Azure Speech Services (Transcription)
# ===========================================
AZURE_SPEECH_REGION=eastus
AZURE_SPEECH_KEY=your-azure-speech-key

# ===========================================
# Azure OpenAI (Barnabee)
# ===========================================
AZURE_OPENAI_API_KEY=your-azure-openai-key
AZURE_OPENAI_API_INSTANCE_NAME=your-instance-name
AZURE_OPENAI_API_DEPLOYMENT_NAME=gpt-4
AZURE_OPENAI_API_VERSION=2024-08-01-preview

# ===========================================
# BarnabeeNet Connection
# ===========================================
BARNABEE_WS_URL=ws://barnabee.local:1880/ws/glasses
BARNABEE_API_URL=http://barnabee.local:1880/api

# ===========================================
# Optional: Text-to-Speech
# ===========================================
AZURE_TTS_KEY=your-azure-tts-key
AZURE_TTS_REGION=eastus
DEFAULT_VOICE=en-US-JennyNeural

# ===========================================
# Development
# ===========================================
LOG_LEVEL=debug
ENABLE_DEV_MODE=true
```

### Docker Compose Template

```yaml
# docker-compose.yml
version: '3.8'

services:
  barnabeeglass:
    build: .
    ports:
      - "8002:80"
    environment:
      - NODE_ENV=development
    volumes:
      - .:/app
      - /app/node_modules
    depends_on:
      - mongodb

  mongodb:
    image: mongo:7.0
    ports:
      - "127.0.0.1:27017:27017"
    volumes:
      - mongo_data:/data/db

volumes:
  mongo_data:
```

---

## Appendix A: G1 BLE Service/Characteristic UUIDs

These need to be reverse-engineered or obtained from EvenDemoApp:

```javascript
// Placeholder - extract from EvenDemoApp source
const BLE_CONFIG = {
  SERVICE_UUID: 'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx',
  COMMAND_CHAR_UUID: 'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx',
  AUDIO_CHAR_UUID: 'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx',
  NOTIFY_CHAR_UUID: 'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx',
};
```

---

## Appendix B: Message Type Reference

### Mobile → Cloud Messages

| Type | Description |
|------|-------------|
| `AUDIO_CHUNK` | LC3 audio data from glasses |
| `BUTTON_PRESS` | TouchBar interaction |
| `HEAD_POSITION` | User looked up/down |
| `CONNECTION_STATUS` | Glasses connect/disconnect |

### Cloud → Mobile Messages

| Type | Description |
|------|-------------|
| `DISPLAY_TEXT` | Text to show on glasses |
| `DISPLAY_IMAGE` | BMP image data |
| `PLAY_AUDIO` | Audio URL or TTS |
| `CLEAR_DISPLAY` | Clear glasses screen |

---

## Appendix C: Error Codes

| Code | Meaning | Resolution |
|------|---------|------------|
| `BLE_001` | Glasses not found | Check pairing, restart glasses |
| `BLE_002` | Connection lost | Automatic reconnect |
| `STT_001` | Transcription failed | Check Azure credentials |
| `AI_001` | OpenAI timeout | Retry with backoff |
| `DISPLAY_001` | Text too long | Auto-pagination triggered |

---

**Document Version History:**
- v1.0 (Jan 2026): Initial comprehensive specification

**Next Steps:**
1. Fork MentraOS repository
2. Set up development environment
3. Begin Phase 1 implementation
4. Join MentraOS Discord for community support
