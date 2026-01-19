# Mobile STT Client Architecture

> **Status**: Placeholder/Future Development
> **Target Platform**: Android (BT headset/glasses audio capture)

## Overview

This document outlines the architecture for a mobile Android client that captures audio from Bluetooth headsets or smart glasses and streams it to BarnabeeNet for real-time transcription.

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Android Mobile Client                      │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │ BT Audio    │───▶│ Silero VAD  │───▶│ Audio       │     │
│  │ Capture     │    │ (On-Device) │    │ Buffer      │     │
│  └─────────────┘    └─────────────┘    └─────────────┘     │
│                                               │              │
│                                               ▼              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │ Mode Switch │───▶│ WebSocket   │───▶│ Offline     │     │
│  │ (Voice/Btn) │    │ Client      │    │ Buffer      │     │
│  └─────────────┘    └─────────────┘    └─────────────┘     │
│                            │                 │              │
└────────────────────────────┼─────────────────┼──────────────┘
                             │                 │
                    (Connected)        (Disconnected)
                             │                 │
                             ▼                 ▼
                    ┌─────────────┐    ┌─────────────┐
                    │ BarnabeeNet │    │ Azure STT   │
                    │ Home Server │    │ (Fallback)  │
                    │ ws://...    │    │             │
                    └─────────────┘    └─────────────┘
```

## Key Components

### 1. Audio Capture

- **Primary**: Bluetooth SCO audio from headset/glasses
- **Fallback**: Device microphone
- **Format**: 16kHz PCM mono
- **Library**: Android AudioRecord API

### 2. Voice Activity Detection (VAD)

- **Model**: Silero VAD (ONNX, ~500KB)
- **Purpose**: Filter silence, reduce bandwidth
- **Threshold**: Configurable (default: 0.5)
- **On-device**: No network latency for VAD

### 3. WebSocket Streaming

- **Protocol**: WebSocket to BarnabeeNet `/api/v1/voice/ws/transcribe`
- **Format**: Binary audio chunks (100ms chunks)
- **Reconnection**: Exponential backoff with jitter

### 4. Mode Switching

Three operational modes:

| Mode | Trigger | Behavior |
|------|---------|----------|
| **Ambient** | Background service | Continuous capture, batch every 30-60s |
| **Real-time** | Hold button or voice command | Streaming with word-by-word results |
| **Command** | Wake word "Hey Barnabee" | Single utterance, wait for response |

### 5. Offline Handling

- Audio chunks buffered locally when disconnected
- Automatic sync when connection restored
- Fallback to Azure STT for critical commands

## Code Architecture

```kotlin
// Main entry point
class BarnabeeSTTClient(
    private val context: Context,
    private val serverUrl: String,
    private val azureKey: String? = null
) {
    // Components
    private val audioCapture = BluetoothAudioCapture(context)
    private val vad = SileroVAD(context)
    private val wsClient = BarnabeeWebSocketClient(serverUrl)
    private val offlineBuffer = OfflineAudioBuffer(context)
    private val modeController = STTModeController()

    // State
    private var currentMode: STTMode = STTMode.COMMAND
    private var isConnected: Boolean = false

    suspend fun start() {
        // Initialize components
        audioCapture.initialize()
        vad.initialize()
        wsClient.connect()

        // Start audio capture loop
        audioCapture.captureFlow
            .filter { vad.isSpeech(it) }
            .collect { chunk ->
                if (isConnected) {
                    wsClient.sendAudio(chunk)
                } else {
                    offlineBuffer.store(chunk)
                    // Try Azure fallback for commands
                    if (currentMode == STTMode.COMMAND) {
                        azureKey?.let { transcribeWithAzure(chunk) }
                    }
                }
            }
    }

    fun setMode(mode: STTMode) {
        currentMode = mode
        when (mode) {
            STTMode.AMBIENT -> wsClient.sendConfig(streaming = true, batchMode = true)
            STTMode.REALTIME -> wsClient.sendConfig(streaming = true, interim = true)
            STTMode.COMMAND -> wsClient.sendConfig(streaming = false, singleUtterance = true)
        }
    }
}
```

### Bluetooth Audio Capture

```kotlin
class BluetoothAudioCapture(private val context: Context) {
    private val audioManager = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager
    private var audioRecord: AudioRecord? = null

    val captureFlow: Flow<ByteArray> = flow {
        // Start Bluetooth SCO
        audioManager.startBluetoothSco()

        // Create AudioRecord
        val bufferSize = AudioRecord.getMinBufferSize(
            SAMPLE_RATE_HZ,
            AudioFormat.CHANNEL_IN_MONO,
            AudioFormat.ENCODING_PCM_16BIT
        )

        audioRecord = AudioRecord(
            MediaRecorder.AudioSource.VOICE_RECOGNITION,
            SAMPLE_RATE_HZ,
            AudioFormat.CHANNEL_IN_MONO,
            AudioFormat.ENCODING_PCM_16BIT,
            bufferSize
        )

        audioRecord?.startRecording()

        val buffer = ByteArray(CHUNK_SIZE_BYTES)
        while (true) {
            val bytesRead = audioRecord?.read(buffer, 0, buffer.size) ?: 0
            if (bytesRead > 0) {
                emit(buffer.copyOf(bytesRead))
            }
            delay(CHUNK_DURATION_MS)
        }
    }

    companion object {
        const val SAMPLE_RATE_HZ = 16000
        const val CHUNK_DURATION_MS = 100L
        const val CHUNK_SIZE_BYTES = (SAMPLE_RATE_HZ * 2 * CHUNK_DURATION_MS / 1000).toInt()
    }
}
```

### Silero VAD Integration

```kotlin
class SileroVAD(private val context: Context) {
    private var session: OrtSession? = null
    private var state: OnnxTensor? = null

    fun initialize() {
        val env = OrtEnvironment.getEnvironment()
        val modelBytes = context.assets.open("silero_vad.onnx").readBytes()
        session = env.createSession(modelBytes)
        // Initialize hidden state
        state = OnnxTensor.createTensor(env, FloatArray(128))
    }

    fun isSpeech(audioChunk: ByteArray, threshold: Float = 0.5f): Boolean {
        // Convert bytes to float samples
        val samples = audioChunk.toFloatArray()

        // Run VAD inference
        val inputs = mapOf(
            "input" to OnnxTensor.createTensor(env, arrayOf(samples)),
            "state" to state
        )

        val outputs = session?.run(inputs)
        val prob = (outputs?.get(0)?.value as FloatArray)[0]
        state = outputs?.get(1) as OnnxTensor

        return prob > threshold
    }
}
```

### WebSocket Client

```kotlin
class BarnabeeWebSocketClient(private val serverUrl: String) {
    private var webSocket: WebSocket? = null
    private val client = OkHttpClient.Builder()
        .readTimeout(0, TimeUnit.MILLISECONDS)
        .build()

    private val _transcriptions = MutableSharedFlow<TranscriptionResult>()
    val transcriptions: SharedFlow<TranscriptionResult> = _transcriptions

    fun connect() {
        val request = Request.Builder()
            .url("$serverUrl/api/v1/voice/ws/transcribe")
            .build()

        webSocket = client.newWebSocket(request, object : WebSocketListener() {
            override fun onMessage(webSocket: WebSocket, text: String) {
                val result = Json.decodeFromString<TranscriptionResult>(text)
                _transcriptions.tryEmit(result)
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                // Reconnect with exponential backoff
                scheduleReconnect()
            }
        })
    }

    fun sendAudio(chunk: ByteArray) {
        webSocket?.send(ByteString.of(*chunk))
    }

    fun sendConfig(streaming: Boolean, interim: Boolean = true, batchMode: Boolean = false) {
        val config = buildJsonObject {
            put("type", "config")
            put("streaming", streaming)
            put("interim_results", interim)
            put("batch_mode", batchMode)
        }
        webSocket?.send(config.toString())
    }
}
```

## Android Manifest Requirements

```xml
<manifest>
    <uses-permission android:name="android.permission.RECORD_AUDIO"/>
    <uses-permission android:name="android.permission.BLUETOOTH"/>
    <uses-permission android:name="android.permission.BLUETOOTH_CONNECT"/>
    <uses-permission android:name="android.permission.MODIFY_AUDIO_SETTINGS"/>
    <uses-permission android:name="android.permission.INTERNET"/>
    <uses-permission android:name="android.permission.FOREGROUND_SERVICE"/>
    <uses-permission android:name="android.permission.FOREGROUND_SERVICE_MICROPHONE"/>

    <application>
        <service
            android:name=".BarnabeeSTTService"
            android:foregroundServiceType="microphone"
            android:exported="false"/>
    </application>
</manifest>
```

## Dependencies

```kotlin
// build.gradle.kts
dependencies {
    // ONNX Runtime for Silero VAD
    implementation("com.microsoft.onnxruntime:onnxruntime-android:1.16.0")

    // WebSocket
    implementation("com.squareup.okhttp3:okhttp:4.12.0")

    // Coroutines
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.7.3")

    // JSON serialization
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.6.0")

    // Azure Speech SDK (optional fallback)
    implementation("com.microsoft.cognitiveservices.speech:client-sdk:1.32.0")
}
```

## Configuration

```kotlin
data class BarnabeeConfig(
    val serverUrl: String = "ws://192.168.86.51:8000",
    val azureSpeechKey: String? = null,
    val azureSpeechRegion: String = "eastus",
    val vadThreshold: Float = 0.5f,
    val reconnectDelayMs: Long = 1000,
    val maxReconnectDelayMs: Long = 30000,
    val defaultMode: STTMode = STTMode.COMMAND,
    val offlineBufferMaxMb: Int = 50
)
```

## Future Enhancements

1. **Wake Word Detection**: On-device "Hey Barnabee" detection using Porcupine
2. **Response Playback**: TTS responses through BT headset
3. **Wear OS Companion**: Smartwatch app for quick commands
4. **Glasses Integration**: Direct integration with smart glasses (Ray-Ban Meta, etc.)
5. **Privacy Mode**: Local-only processing option using on-device Whisper
6. **Multi-room Awareness**: Auto-detect room based on BT beacons

## Testing Checklist

- [ ] Audio capture from BT headset works
- [ ] VAD correctly filters silence
- [ ] WebSocket streaming connects and receives results
- [ ] Partial results appear in real-time
- [ ] Offline buffering works when disconnected
- [ ] Azure fallback works for critical commands
- [ ] Mode switching works via voice/button
- [ ] Battery usage is acceptable in ambient mode
- [ ] Reconnection works with exponential backoff

## Related Documentation

- [BarnabeeNet STT Router](../src/barnabeenet/services/stt/router.py)
- [WebSocket Streaming Endpoint](../src/barnabeenet/api/routes/voice.py)
- [Azure STT Integration](../src/barnabeenet/services/stt/azure_stt.py)
