# Area 20: Native Mobile Applications

**Version:** 2.0  
**Status:** Implementation Ready  
**Dependencies:** Areas 02, 14, 15, 17 (Voice Pipeline, Multi-Device, API Contracts, Security)  
**Phase:** Extended Functionality  

---

## 1. Overview

### 1.1 Purpose

This specification defines **two distinct Android applications** for BarnabeeNet V2:

1. **Barnabee Phone App** - Replaces Google Assistant on phones, tracks notifications
2. **Barnabee Display App** - Launcher for Lenovo Smart Displays running custom Android

Plus an iOS app with limited functionality due to Apple restrictions.

### 1.2 Application Summary

| App | Platform | Purpose | Key Features |
|-----|----------|---------|--------------|
| **Barnabee Phone** | Android phones | Default assistant replacement | Wake word, voice commands, notification tracking |
| **Barnabee Display** | Lenovo View (Android) | Smart display launcher | Camera/mic, motion detection, HA dashboards, slideshow |
| **Barnabee iOS** | iPhone/iPad | Voice assistant (limited) | Push-to-talk, Siri Shortcuts, widgets |

### 1.3 Platform Capabilities

| Feature | Android Phone | Lenovo Display | iOS |
|---------|---------------|----------------|-----|
| Default assistant replacement | Yes | N/A (is launcher) | No |
| Always-on wake word | Yes | Yes | No |
| Camera/video capture | No | Yes | No |
| Motion detection | No | Yes | No |
| HA dashboard display | No | Yes | No |
| Slideshow/ambient mode | No | Yes | No |
| Notification tracking | Yes | Yes | Limited |
| Push-to-talk | Yes | Yes | Yes |
| Widget | Yes | N/A | Yes |

### 1.4 Design Principles

1. **Two distinct Android apps:** Phone app and Display app have different purposes - don't conflate them
2. **Display is a launcher:** Barnabee Display replaces the home screen entirely
3. **Motion-aware:** Display shows HA dashboards when someone approaches, slideshow when idle
4. **Always listening:** Both Android apps support always-on wake word
5. **Consistent protocol:** Same WebSocket API for all platforms
6. **Battery conscious:** Phone app optimizes for battery; Display app is always plugged in

---

## 2. Android Application

### 2.1 Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       ANDROID APPLICATION                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    PRESENTATION LAYER                                │   │
│  │                                                                      │   │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐     │   │
│  │  │  Main Activity  │  │  Voice Overlay  │  │     Widget      │     │   │
│  │  │  (Jetpack       │  │  (Transparent   │  │  (Quick launch) │     │   │
│  │  │   Compose)      │  │   Activity)     │  │                 │     │   │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────┘     │   │
│  │                                                                      │   │
│  │  ┌─────────────────┐  ┌─────────────────┐                          │   │
│  │  │  Quick Settings │  │  Notification   │                          │   │
│  │  │     Tile        │  │   Handler       │                          │   │
│  │  └─────────────────┘  └─────────────────┘                          │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                   │                                          │
│                                   ▼                                          │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    SERVICE LAYER                                     │   │
│  │                                                                      │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │              VoiceInteractionService                         │   │   │
│  │  │   (Registers as default assistant - replaces Google)        │   │   │
│  │  └─────────────────────────────────────────────────────────────┘   │   │
│  │                                                                      │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │              WakeWordService (Foreground)                    │   │   │
│  │  │   • openWakeWord detection                                  │   │   │
│  │  │   • VAD for efficient audio processing                      │   │   │
│  │  │   • Persistent notification for always-on                   │   │   │
│  │  └─────────────────────────────────────────────────────────────┘   │   │
│  │                                                                      │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │              AudioCaptureService                             │   │   │
│  │  │   • Microphone capture                                      │   │   │
│  │  │   • Audio preprocessing                                     │   │   │
│  │  │   • WebSocket streaming                                     │   │   │
│  │  └─────────────────────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                   │                                          │
│                                   ▼                                          │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    DATA LAYER                                        │   │
│  │                                                                      │   │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐     │   │
│  │  │  WebSocket      │  │  Auth Manager   │  │  Preferences    │     │   │
│  │  │  Client         │  │  (Keystore)     │  │  DataStore      │     │   │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────┘     │   │
│  │                                                                      │   │
│  │  ┌─────────────────┐  ┌─────────────────┐                          │   │
│  │  │  Device         │  │  Model Cache    │                          │   │
│  │  │  Registration   │  │  (Wake Word)    │                          │   │
│  │  └─────────────────┘  └─────────────────┘                          │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Technology Stack

| Component | Technology | Notes |
|-----------|------------|-------|
| Language | Kotlin | Modern, concise, coroutines support |
| UI Framework | Jetpack Compose | Declarative, modern Android UI |
| Architecture | MVVM + Clean Architecture | Testable, maintainable |
| Dependency Injection | Hilt | Standard Android DI |
| Networking | OkHttp + WebSocket | Reliable, well-tested |
| Audio | Android AudioRecord | Low-level audio capture |
| Wake Word | openWakeWord (TFLite) | On-device detection |
| Local Storage | DataStore (Preferences) | Encrypted preferences |
| Secure Storage | Android Keystore | For auth tokens |
| Background Work | WorkManager | Reliable background tasks |

### 2.3 VoiceInteractionService Implementation

```kotlin
// VoiceInteractionService - Registers as default assistant
package com.barnabee.assistant

import android.service.voice.VoiceInteractionService
import android.service.voice.VoiceInteractionSession
import android.service.voice.VoiceInteractionSessionService

class BarnabeeVoiceService : VoiceInteractionService() {
    
    override fun onReady() {
        super.onReady()
        // Service is ready to handle voice interactions
    }
}

class BarnabeeSessionService : VoiceInteractionSessionService() {
    
    override fun onNewSession(args: Bundle?): VoiceInteractionSession {
        return BarnabeeVoiceSession(this)
    }
}

class BarnabeeVoiceSession(context: Context) : VoiceInteractionSession(context) {
    
    private val voiceClient = BarnabeeVoiceClient()
    
    override fun onShow(args: Bundle?, showFlags: Int) {
        super.onShow(args, showFlags)
        
        // Show voice UI overlay
        setUiEnabled(true)
        
        // Start listening
        startVoiceCapture()
    }
    
    override fun onHide() {
        super.onHide()
        stopVoiceCapture()
    }
    
    private fun startVoiceCapture() {
        // Start audio capture and stream to backend
        voiceClient.startSession()
    }
    
    private fun stopVoiceCapture() {
        voiceClient.endSession()
    }
}
```

### 2.4 Wake Word Service

```kotlin
// WakeWordService - Always-on wake word detection
package com.barnabee.assistant

import android.app.Notification
import android.app.Service
import android.content.Intent
import android.os.IBinder
import kotlinx.coroutines.*

class WakeWordService : Service() {
    
    private val scope = CoroutineScope(Dispatchers.Default + SupervisorJob())
    private lateinit var wakeWordDetector: WakeWordDetector
    private lateinit var vadDetector: VadDetector
    private lateinit var audioCapture: AudioCapture
    
    override fun onCreate() {
        super.onCreate()
        
        // Initialize models
        wakeWordDetector = WakeWordDetector(assets)
        vadDetector = VadDetector(assets)
        audioCapture = AudioCapture()
    }
    
    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        // Start as foreground service with notification
        val notification = createNotification()
        startForeground(NOTIFICATION_ID, notification)
        
        // Start listening
        startListening()
        
        return START_STICKY
    }
    
    private fun startListening() {
        scope.launch {
            audioCapture.start()
            
            audioCapture.audioFlow.collect { audioChunk ->
                // First check VAD (voice activity)
                if (vadDetector.hasVoiceActivity(audioChunk)) {
                    // Then check for wake word
                    val wakeWordResult = wakeWordDetector.detect(audioChunk)
                    
                    if (wakeWordResult.detected && wakeWordResult.confidence > WAKE_WORD_THRESHOLD) {
                        onWakeWordDetected()
                    }
                }
            }
        }
    }
    
    private fun onWakeWordDetected() {
        // Vibrate feedback
        vibrateShort()
        
        // Launch voice session
        val intent = Intent(this, VoiceActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK
            putExtra("trigger", "wake_word")
        }
        startActivity(intent)
    }
    
    private fun createNotification(): Notification {
        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("Barnabee")
            .setContentText("Listening for 'Hey Barnabee'")
            .setSmallIcon(R.drawable.ic_barnabee)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .setOngoing(true)
            .addAction(
                R.drawable.ic_stop,
                "Stop",
                createStopPendingIntent()
            )
            .build()
    }
    
    override fun onDestroy() {
        scope.cancel()
        audioCapture.stop()
        super.onDestroy()
    }
    
    override fun onBind(intent: Intent?): IBinder? = null
    
    companion object {
        private const val NOTIFICATION_ID = 1001
        private const val CHANNEL_ID = "barnabee_wakeword"
        private const val WAKE_WORD_THRESHOLD = 0.7f
    }
}
```

### 2.5 WebSocket Voice Client

```kotlin
// BarnabeeVoiceClient - WebSocket communication with backend
package com.barnabee.assistant

import kotlinx.coroutines.flow.*
import okhttp3.*
import okio.ByteString.Companion.toByteString

class BarnabeeVoiceClient(
    private val authManager: AuthManager,
    private val config: AppConfig,
) {
    private var webSocket: WebSocket? = null
    private val client = OkHttpClient.Builder()
        .pingInterval(30, TimeUnit.SECONDS)
        .build()
    
    private val _state = MutableStateFlow<VoiceState>(VoiceState.Idle)
    val state: StateFlow<VoiceState> = _state.asStateFlow()
    
    private val _transcripts = MutableSharedFlow<Transcript>()
    val transcripts: SharedFlow<Transcript> = _transcripts.asSharedFlow()
    
    private val _responses = MutableSharedFlow<BarnabeeResponse>()
    val responses: SharedFlow<BarnabeeResponse> = _responses.asSharedFlow()
    
    suspend fun connect(): Boolean {
        val token = authManager.getSessionToken() ?: return false
        
        val request = Request.Builder()
            .url("${config.wsBaseUrl}/v2/voice/stream?token=$token")
            .build()
        
        return suspendCancellableCoroutine { continuation ->
            webSocket = client.newWebSocket(request, object : WebSocketListener() {
                override fun onOpen(webSocket: WebSocket, response: Response) {
                    _state.value = VoiceState.Connected
                    continuation.resume(true)
                }
                
                override fun onMessage(webSocket: WebSocket, text: String) {
                    handleTextMessage(text)
                }
                
                override fun onMessage(webSocket: WebSocket, bytes: ByteString) {
                    handleAudioMessage(bytes)
                }
                
                override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                    _state.value = VoiceState.Error(t.message ?: "Connection failed")
                    if (continuation.isActive) {
                        continuation.resume(false)
                    }
                }
                
                override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                    _state.value = VoiceState.Disconnected
                }
            })
            
            continuation.invokeOnCancellation {
                webSocket?.cancel()
            }
        }
    }
    
    fun startSession() {
        _state.value = VoiceState.Listening
        
        webSocket?.send(Json.encodeToString(
            VoiceMessage.SessionStart(
                deviceId = config.deviceId,
                clientTimestamp = System.currentTimeMillis()
            )
        ))
    }
    
    fun sendAudio(audioData: ByteArray) {
        if (_state.value == VoiceState.Listening) {
            webSocket?.send(audioData.toByteString())
        }
    }
    
    fun endSession() {
        _state.value = VoiceState.Processing
        
        webSocket?.send(Json.encodeToString(
            VoiceMessage.SessionEnd(
                clientTimestamp = System.currentTimeMillis()
            )
        ))
    }
    
    fun disconnect() {
        webSocket?.close(1000, "Client disconnect")
        webSocket = null
        _state.value = VoiceState.Disconnected
    }
    
    private fun handleTextMessage(text: String) {
        val message = Json.decodeFromString<ServerMessage>(text)
        
        when (message) {
            is ServerMessage.TranscriptPartial -> {
                _transcripts.tryEmit(Transcript.Partial(message.text))
            }
            is ServerMessage.TranscriptFinal -> {
                _transcripts.tryEmit(Transcript.Final(message.text))
            }
            is ServerMessage.ResponseStart -> {
                _state.value = VoiceState.Speaking
            }
            is ServerMessage.ResponseText -> {
                _responses.tryEmit(BarnabeeResponse.Text(message.text))
            }
            is ServerMessage.ResponseEnd -> {
                _state.value = VoiceState.Idle
            }
            is ServerMessage.Error -> {
                _state.value = VoiceState.Error(message.message)
            }
        }
    }
    
    private fun handleAudioMessage(bytes: ByteString) {
        // Audio response from TTS
        _responses.tryEmit(BarnabeeResponse.Audio(bytes.toByteArray()))
    }
}

sealed class VoiceState {
    object Idle : VoiceState()
    object Connected : VoiceState()
    object Listening : VoiceState()
    object Processing : VoiceState()
    object Speaking : VoiceState()
    object Disconnected : VoiceState()
    data class Error(val message: String) : VoiceState()
}
```

### 2.6 Device Registration Flow

```kotlin
// DeviceRegistration - First-time setup
package com.barnabee.assistant

import android.content.Context
import android.provider.Settings
import androidx.security.crypto.EncryptedSharedPreferences

class DeviceRegistration(
    private val context: Context,
    private val apiClient: BarnabeeApiClient,
) {
    private val prefs = EncryptedSharedPreferences.create(
        "barnabee_device",
        "barnabee_master_key",
        context,
        EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
        EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
    )
    
    val isRegistered: Boolean
        get() = prefs.contains("device_id") && prefs.contains("device_secret")
    
    val deviceId: String?
        get() = prefs.getString("device_id", null)
    
    suspend fun register(userId: String): Result<DeviceCredentials> {
        val deviceName = "${Build.MANUFACTURER} ${Build.MODEL}"
        val deviceType = "android_phone"
        
        return try {
            val response = apiClient.registerDevice(
                deviceName = deviceName,
                deviceType = deviceType,
                userId = userId,
            )
            
            // Store credentials securely
            prefs.edit()
                .putString("device_id", response.deviceId)
                .putString("device_secret", response.deviceSecret)
                .apply()
            
            Result.success(response)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
    
    suspend fun authenticate(): Result<String> {
        val deviceId = prefs.getString("device_id", null)
            ?: return Result.failure(Exception("Not registered"))
        val deviceSecret = prefs.getString("device_secret", null)
            ?: return Result.failure(Exception("Not registered"))
        
        return try {
            val response = apiClient.authenticateDevice(deviceId, deviceSecret)
            Result.success(response.sessionToken)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
    
    fun registerViaQrCode(qrData: String): Boolean {
        // QR code contains: barnabee://register?server=...&token=...
        val uri = Uri.parse(qrData)
        
        if (uri.scheme != "barnabee" || uri.host != "register") {
            return false
        }
        
        val serverUrl = uri.getQueryParameter("server") ?: return false
        val setupToken = uri.getQueryParameter("token") ?: return false
        
        // Store server URL and use setup token for registration
        prefs.edit()
            .putString("server_url", serverUrl)
            .putString("setup_token", setupToken)
            .apply()
        
        return true
    }
}
```

### 2.7 Android Manifest Configuration

```xml
<!-- AndroidManifest.xml -->
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    package="com.barnabee.assistant">

    <!-- Permissions -->
    <uses-permission android:name="android.permission.RECORD_AUDIO" />
    <uses-permission android:name="android.permission.INTERNET" />
    <uses-permission android:name="android.permission.FOREGROUND_SERVICE" />
    <uses-permission android:name="android.permission.FOREGROUND_SERVICE_MICROPHONE" />
    <uses-permission android:name="android.permission.VIBRATE" />
    <uses-permission android:name="android.permission.RECEIVE_BOOT_COMPLETED" />
    <uses-permission android:name="android.permission.POST_NOTIFICATIONS" />
    <uses-permission android:name="android.permission.CAMERA" />  <!-- For QR scanning -->

    <application
        android:name=".BarnabeeApplication"
        android:icon="@mipmap/ic_launcher"
        android:label="@string/app_name"
        android:theme="@style/Theme.Barnabee">

        <!-- Main Activity -->
        <activity
            android:name=".MainActivity"
            android:exported="true">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>

        <!-- Voice Overlay Activity -->
        <activity
            android:name=".VoiceActivity"
            android:exported="true"
            android:theme="@style/Theme.Barnabee.Transparent"
            android:launchMode="singleTask"
            android:excludeFromRecents="true">
        </activity>

        <!-- Voice Interaction Service (Default Assistant) -->
        <service
            android:name=".BarnabeeVoiceService"
            android:permission="android.permission.BIND_VOICE_INTERACTION"
            android:exported="true">
            <meta-data
                android:name="android.voice_interaction"
                android:resource="@xml/voice_interaction_service" />
            <intent-filter>
                <action android:name="android.service.voice.VoiceInteractionService" />
            </intent-filter>
        </service>

        <!-- Session Service -->
        <service
            android:name=".BarnabeeSessionService"
            android:permission="android.permission.BIND_VOICE_INTERACTION"
            android:exported="true">
        </service>

        <!-- Wake Word Foreground Service -->
        <service
            android:name=".WakeWordService"
            android:foregroundServiceType="microphone"
            android:exported="false">
        </service>

        <!-- Widget -->
        <receiver
            android:name=".widget.BarnabeeWidget"
            android:exported="true">
            <intent-filter>
                <action android:name="android.appwidget.action.APPWIDGET_UPDATE" />
            </intent-filter>
            <meta-data
                android:name="android.appwidget.provider"
                android:resource="@xml/barnabee_widget_info" />
        </receiver>

        <!-- Quick Settings Tile -->
        <service
            android:name=".tile.BarnabeeTileService"
            android:icon="@drawable/ic_barnabee"
            android:label="@string/app_name"
            android:permission="android.permission.BIND_QUICK_SETTINGS_TILE"
            android:exported="true">
            <intent-filter>
                <action android:name="android.service.quicksettings.action.QS_TILE" />
            </intent-filter>
        </service>

        <!-- Boot Receiver -->
        <receiver
            android:name=".BootReceiver"
            android:exported="true">
            <intent-filter>
                <action android:name="android.intent.action.BOOT_COMPLETED" />
            </intent-filter>
        </receiver>

    </application>

</manifest>
```

---

## 3. Barnabee Display App (Lenovo View Launcher)

### 3.1 Purpose

The Barnabee Display app is a **custom Android launcher** designed for Lenovo Smart Display devices (and similar Android-based smart displays). It replaces the default home screen and provides:

- **Voice assistant** with wake word detection
- **HA dashboard display** when motion is detected
- **Photo slideshow** when idle (no motion)
- **Video/audio capture** for voice commands and visual context
- **Always-on operation** (display is always plugged in)

### 3.2 Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    BARNABEE DISPLAY LAUNCHER                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    DISPLAY MODES                                     │   │
│  │                                                                      │   │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐     │   │
│  │  │   IDLE MODE     │  │  ACTIVE MODE    │  │   VOICE MODE    │     │   │
│  │  │                 │  │                 │  │                 │     │   │
│  │  │  • Photo        │  │  • HA Dashboard │  │  • Voice UI     │     │   │
│  │  │    slideshow    │  │  • Clock/weather│  │  • Waveform     │     │   │
│  │  │  • Clock        │  │  • Quick actions│  │  • Transcript   │     │   │
│  │  │  • Low bright   │  │  • Full bright  │  │  • Response     │     │   │
│  │  │                 │  │                 │  │                 │     │   │
│  │  │  No motion for  │  │  Motion         │  │  Wake word or   │     │   │
│  │  │  5+ minutes     │  │  detected       │  │  touch trigger  │     │   │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────┘     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                   │                                          │
│                                   ▼                                          │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    SERVICES                                          │   │
│  │                                                                      │   │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐     │   │
│  │  │MotionDetection  │  │  WakeWordService│  │  AudioCapture   │     │   │
│  │  │Service          │  │                 │  │  Service        │     │   │
│  │  │                 │  │  • openWakeWord │  │                 │     │   │
│  │  │  • Camera feed  │  │  • VAD          │  │  • Mic capture  │     │   │
│  │  │  • Frame diff   │  │  • Always on    │  │  • WebSocket    │     │   │
│  │  │  • Presence     │  │                 │  │    streaming    │     │   │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────┘     │   │
│  │                                                                      │   │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐     │   │
│  │  │  HAWebView      │  │  PhotoSlideshow │  │  WebSocket      │     │   │
│  │  │  Service        │  │  Service        │  │  Client         │     │   │
│  │  │                 │  │                 │  │                 │     │   │
│  │  │  • Dashboard    │  │  • Google Photos│  │  • Voice API    │     │   │
│  │  │    rendering    │  │  • Local photos │  │  • HA events    │     │   │
│  │  │  • Auto-refresh │  │  • Transitions  │  │                 │     │   │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────┘     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.3 Display Modes State Machine

```
                    ┌──────────────────┐
                    │                  │
        ┌───────────│   IDLE MODE      │◄──────────────┐
        │           │   (Slideshow)    │               │
        │           └────────┬─────────┘               │
        │                    │                         │
        │            Motion  │                         │ No motion
        │           detected │                         │ for 5 min
        │                    ▼                         │
        │           ┌──────────────────┐               │
        │           │                  │               │
        │           │  ACTIVE MODE     │───────────────┘
        │           │  (HA Dashboard)  │
        │           └────────┬─────────┘
        │                    │
        │  Wake word         │ Wake word
        │  detected          │ detected
        │                    ▼
        │           ┌──────────────────┐
        │           │                  │
        └───────────│   VOICE MODE     │
                    │  (Listening/     │
                    │   Responding)    │
                    └──────────────────┘
                             │
                             │ Response complete
                             │ (returns to previous mode)
                             ▼
```

### 3.4 Launcher Activity Implementation

```kotlin
// BarnabeeDisplayLauncher.kt - Main launcher activity
package com.barnabee.display

import android.app.Activity
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.runtime.*
import kotlinx.coroutines.flow.*

class BarnabeeDisplayLauncher : ComponentActivity() {
    
    private val motionDetector by lazy { MotionDetectionService(this) }
    private val wakeWordService by lazy { WakeWordService(this) }
    private val slideshowService by lazy { PhotoSlideshowService(this) }
    private val haWebViewService by lazy { HAWebViewService(this) }
    
    private val _displayMode = MutableStateFlow<DisplayMode>(DisplayMode.Idle)
    
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        
        // Register as default launcher
        setDefaultLauncher()
        
        // Start services
        startServices()
        
        setContent {
            BarnabeeDisplayTheme {
                val mode by _displayMode.collectAsState()
                
                DisplayScreen(
                    mode = mode,
                    onModeChange = { _displayMode.value = it }
                )
            }
        }
    }
    
    private fun startServices() {
        // Start motion detection
        motionDetector.start { hasMotion ->
            handleMotionChange(hasMotion)
        }
        
        // Start wake word detection
        wakeWordService.start { detected ->
            if (detected) {
                _displayMode.value = DisplayMode.Voice
            }
        }
    }
    
    private fun handleMotionChange(hasMotion: Boolean) {
        when {
            hasMotion && _displayMode.value == DisplayMode.Idle -> {
                _displayMode.value = DisplayMode.Active
            }
            !hasMotion && _displayMode.value == DisplayMode.Active -> {
                // Start idle timer
                startIdleTimer()
            }
        }
    }
    
    private fun startIdleTimer() {
        // After 5 minutes of no motion, switch to idle
        lifecycleScope.launch {
            delay(5 * 60 * 1000) // 5 minutes
            if (_displayMode.value == DisplayMode.Active) {
                _displayMode.value = DisplayMode.Idle
            }
        }
    }
    
    private fun setDefaultLauncher() {
        // This activity is declared as launcher in manifest
        // User selects it as default home app on first run
    }
}

sealed class DisplayMode {
    object Idle : DisplayMode()      // Slideshow + clock
    object Active : DisplayMode()    // HA Dashboard
    object Voice : DisplayMode()     // Voice interaction
}
```

### 3.5 Motion Detection Service

```kotlin
// MotionDetectionService.kt - Camera-based motion detection
package com.barnabee.display

import android.content.Context
import android.graphics.Bitmap
import android.graphics.ImageFormat
import android.hardware.camera2.*
import android.media.ImageReader
import kotlinx.coroutines.*
import kotlin.math.abs

class MotionDetectionService(private val context: Context) {
    
    private var cameraDevice: CameraDevice? = null
    private var imageReader: ImageReader? = null
    private var previousFrame: IntArray? = null
    private var motionCallback: ((Boolean) -> Unit)? = null
    
    private val scope = CoroutineScope(Dispatchers.Default + SupervisorJob())
    
    // Motion detection parameters
    private val motionThreshold = 0.05f  // 5% pixel change = motion
    private val checkIntervalMs = 500L   // Check every 500ms
    
    private var lastMotionTime = System.currentTimeMillis()
    private val noMotionTimeoutMs = 30_000L  // 30 seconds of no motion = idle
    
    fun start(callback: (Boolean) -> Unit) {
        motionCallback = callback
        openCamera()
    }
    
    private fun openCamera() {
        val cameraManager = context.getSystemService(Context.CAMERA_SERVICE) as CameraManager
        
        // Find front-facing camera (for detecting people in room)
        val cameraId = cameraManager.cameraIdList.find { id ->
            val characteristics = cameraManager.getCameraCharacteristics(id)
            characteristics.get(CameraCharacteristics.LENS_FACING) == 
                CameraCharacteristics.LENS_FACING_FRONT
        } ?: cameraManager.cameraIdList.first()
        
        // Low resolution for motion detection (saves power)
        imageReader = ImageReader.newInstance(320, 240, ImageFormat.YUV_420_888, 2)
        imageReader?.setOnImageAvailableListener({ reader ->
            processFrame(reader)
        }, null)
        
        cameraManager.openCamera(cameraId, object : CameraDevice.StateCallback() {
            override fun onOpened(camera: CameraDevice) {
                cameraDevice = camera
                startCapture()
            }
            
            override fun onDisconnected(camera: CameraDevice) {
                camera.close()
            }
            
            override fun onError(camera: CameraDevice, error: Int) {
                camera.close()
            }
        }, null)
    }
    
    private fun startCapture() {
        val captureRequest = cameraDevice?.createCaptureRequest(
            CameraDevice.TEMPLATE_PREVIEW
        )?.apply {
            addTarget(imageReader!!.surface)
            // Low frame rate to save power
            set(CaptureRequest.CONTROL_AE_TARGET_FPS_RANGE, Range(5, 10))
        }?.build()
        
        cameraDevice?.createCaptureSession(
            listOf(imageReader!!.surface),
            object : CameraCaptureSession.StateCallback() {
                override fun onConfigured(session: CameraCaptureSession) {
                    session.setRepeatingRequest(captureRequest!!, null, null)
                }
                
                override fun onConfigureFailed(session: CameraCaptureSession) {}
            },
            null
        )
    }
    
    private fun processFrame(reader: ImageReader) {
        val image = reader.acquireLatestImage() ?: return
        
        try {
            val currentFrame = extractLuminance(image)
            val hasMotion = detectMotion(currentFrame)
            
            if (hasMotion) {
                lastMotionTime = System.currentTimeMillis()
                motionCallback?.invoke(true)
            } else if (System.currentTimeMillis() - lastMotionTime > noMotionTimeoutMs) {
                motionCallback?.invoke(false)
            }
            
            previousFrame = currentFrame
        } finally {
            image.close()
        }
    }
    
    private fun extractLuminance(image: Image): IntArray {
        val plane = image.planes[0]  // Y plane
        val buffer = plane.buffer
        val luminance = IntArray(buffer.remaining())
        
        for (i in luminance.indices) {
            luminance[i] = buffer.get().toInt() and 0xFF
        }
        
        return luminance
    }
    
    private fun detectMotion(currentFrame: IntArray): Boolean {
        val previous = previousFrame ?: return false
        
        if (previous.size != currentFrame.size) return false
        
        var changedPixels = 0
        val threshold = 30  // Pixel value change threshold
        
        for (i in currentFrame.indices) {
            if (abs(currentFrame[i] - previous[i]) > threshold) {
                changedPixels++
            }
        }
        
        val changeRatio = changedPixels.toFloat() / currentFrame.size
        return changeRatio > motionThreshold
    }
    
    fun stop() {
        scope.cancel()
        cameraDevice?.close()
        imageReader?.close()
    }
}
```

### 3.6 Photo Slideshow Service

```kotlin
// PhotoSlideshowService.kt - Ambient photo display
package com.barnabee.display

import android.content.Context
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*

class PhotoSlideshowService(private val context: Context) {
    
    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())
    
    private val _currentPhoto = MutableStateFlow<PhotoItem?>(null)
    val currentPhoto: StateFlow<PhotoItem?> = _currentPhoto.asStateFlow()
    
    // Slideshow settings
    private var intervalSeconds = 30
    private var transitionDuration = 1000L  // 1 second crossfade
    
    private var photoSources: List<PhotoSource> = emptyList()
    private var photoIndex = 0
    private var photos: List<PhotoItem> = emptyList()
    
    fun configure(
        sources: List<PhotoSource>,
        intervalSeconds: Int = 30,
    ) {
        this.photoSources = sources
        this.intervalSeconds = intervalSeconds
        
        scope.launch {
            loadPhotos()
        }
    }
    
    private suspend fun loadPhotos() {
        photos = photoSources.flatMap { source ->
            when (source) {
                is PhotoSource.GooglePhotos -> loadGooglePhotos(source.albumId)
                is PhotoSource.LocalFolder -> loadLocalPhotos(source.path)
                is PhotoSource.HAMediaSource -> loadHAPhotos(source.entityId)
            }
        }.shuffled()
    }
    
    fun start() {
        scope.launch {
            while (isActive) {
                if (photos.isNotEmpty()) {
                    _currentPhoto.value = photos[photoIndex % photos.size]
                    photoIndex++
                }
                delay(intervalSeconds * 1000L)
            }
        }
    }
    
    fun stop() {
        scope.coroutineContext.cancelChildren()
    }
    
    private suspend fun loadGooglePhotos(albumId: String): List<PhotoItem> {
        // TODO: Implement Google Photos API integration
        // Uses Google Photos Library API with OAuth
        return emptyList()
    }
    
    private suspend fun loadLocalPhotos(path: String): List<PhotoItem> {
        val folder = java.io.File(path)
        return folder.listFiles()
            ?.filter { it.extension in listOf("jpg", "jpeg", "png", "webp") }
            ?.map { PhotoItem.Local(it.absolutePath) }
            ?: emptyList()
    }
    
    private suspend fun loadHAPhotos(entityId: String): List<PhotoItem> {
        // Load from Home Assistant media source
        return emptyList()
    }
}

sealed class PhotoItem {
    data class Local(val path: String) : PhotoItem()
    data class Remote(val url: String) : PhotoItem()
}

sealed class PhotoSource {
    data class GooglePhotos(val albumId: String) : PhotoSource()
    data class LocalFolder(val path: String) : PhotoSource()
    data class HAMediaSource(val entityId: String) : PhotoSource()
}
```

### 3.7 HA Dashboard WebView

```kotlin
// HADashboardView.kt - Home Assistant dashboard display
package com.barnabee.display

import android.annotation.SuppressLint
import android.content.Context
import android.webkit.*
import androidx.compose.runtime.*
import androidx.compose.ui.viewinterop.AndroidView

@SuppressLint("SetJavaScriptEnabled")
@Composable
fun HADashboardView(
    dashboardUrl: String,
    authToken: String,
    modifier: Modifier = Modifier,
) {
    var webView by remember { mutableStateOf<WebView?>(null) }
    
    AndroidView(
        factory = { context ->
            WebView(context).apply {
                settings.apply {
                    javaScriptEnabled = true
                    domStorageEnabled = true
                    cacheMode = WebSettings.LOAD_DEFAULT
                    // Allow mixed content for local HA
                    mixedContentMode = WebSettings.MIXED_CONTENT_ALWAYS_ALLOW
                }
                
                webViewClient = object : WebViewClient() {
                    override fun onPageFinished(view: WebView?, url: String?) {
                        // Inject auth token
                        view?.evaluateJavascript("""
                            localStorage.setItem('hassTokens', JSON.stringify({
                                access_token: '$authToken',
                                token_type: 'Bearer'
                            }));
                        """.trimIndent(), null)
                    }
                    
                    override fun shouldOverrideUrlLoading(
                        view: WebView?,
                        request: WebResourceRequest?
                    ): Boolean {
                        // Keep all navigation within HA
                        return false
                    }
                }
                
                // Load dashboard
                loadUrl(dashboardUrl)
                webView = this
            }
        },
        modifier = modifier,
        update = { view ->
            // Refresh dashboard periodically
            if (view.url != dashboardUrl) {
                view.loadUrl(dashboardUrl)
            }
        }
    )
    
    // Auto-refresh every 5 minutes
    LaunchedEffect(dashboardUrl) {
        while (true) {
            delay(5 * 60 * 1000)
            webView?.reload()
        }
    }
}
```

### 3.8 Display Composable Screens

```kotlin
// DisplayScreen.kt - Main display UI
package com.barnabee.display

import androidx.compose.animation.*
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier

@Composable
fun DisplayScreen(
    mode: DisplayMode,
    onModeChange: (DisplayMode) -> Unit,
) {
    Box(modifier = Modifier.fillMaxSize()) {
        // Background layer - always showing something
        Crossfade(
            targetState = mode,
            animationSpec = tween(durationMillis = 500)
        ) { currentMode ->
            when (currentMode) {
                DisplayMode.Idle -> IdleModeScreen()
                DisplayMode.Active -> ActiveModeScreen()
                DisplayMode.Voice -> VoiceModeScreen(
                    onComplete = { 
                        // Return to previous mode after voice interaction
                        onModeChange(DisplayMode.Active)
                    }
                )
            }
        }
        
        // Always-visible clock overlay (except in voice mode)
        if (mode != DisplayMode.Voice) {
            ClockOverlay(
                modifier = Modifier.align(Alignment.TopEnd)
            )
        }
        
        // Touch anywhere to trigger voice (if not already in voice mode)
        if (mode != DisplayMode.Voice) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .clickable { onModeChange(DisplayMode.Voice) }
            )
        }
    }
}

@Composable
fun IdleModeScreen() {
    val slideshowService = LocalSlideshowService.current
    val currentPhoto by slideshowService.currentPhoto.collectAsState()
    
    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(Color.Black)
    ) {
        // Photo slideshow
        currentPhoto?.let { photo ->
            AsyncImage(
                model = when (photo) {
                    is PhotoItem.Local -> photo.path
                    is PhotoItem.Remote -> photo.url
                },
                contentDescription = null,
                modifier = Modifier.fillMaxSize(),
                contentScale = ContentScale.Crop,
            )
        }
        
        // Dim overlay
        Box(
            modifier = Modifier
                .fillMaxSize()
                .background(Color.Black.copy(alpha = 0.3f))
        )
        
        // Large clock
        Text(
            text = remember { 
                SimpleDateFormat("h:mm", Locale.getDefault()).format(Date())
            },
            style = MaterialTheme.typography.displayLarge.copy(
                fontSize = 120.sp,
                fontWeight = FontWeight.Light,
            ),
            color = Color.White,
            modifier = Modifier.align(Alignment.Center)
        )
    }
}

@Composable
fun ActiveModeScreen() {
    val config = LocalDisplayConfig.current
    
    HADashboardView(
        dashboardUrl = config.haDashboardUrl,
        authToken = config.haToken,
        modifier = Modifier.fillMaxSize()
    )
}

@Composable
fun VoiceModeScreen(onComplete: () -> Unit) {
    val voiceSession = LocalVoiceSession.current
    val state by voiceSession.state.collectAsState()
    val transcript by voiceSession.transcript.collectAsState()
    val response by voiceSession.response.collectAsState()
    
    // Auto-start voice session
    LaunchedEffect(Unit) {
        voiceSession.startSession()
    }
    
    // Return to previous mode when complete
    LaunchedEffect(state) {
        if (state == VoiceState.Idle && response.isNotEmpty()) {
            delay(2000) // Show response for 2 seconds
            onComplete()
        }
    }
    
    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(Color.Black.copy(alpha = 0.9f)),
        contentAlignment = Alignment.Center
    ) {
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(24.dp)
        ) {
            // Animated waveform/orb
            VoiceAnimationOrb(
                state = state,
                modifier = Modifier.size(200.dp)
            )
            
            // Transcript
            if (transcript.isNotEmpty()) {
                Text(
                    text = transcript,
                    style = MaterialTheme.typography.headlineMedium,
                    color = Color.White,
                    textAlign = TextAlign.Center,
                    modifier = Modifier.padding(horizontal = 48.dp)
                )
            }
            
            // Response
            if (response.isNotEmpty()) {
                Text(
                    text = response,
                    style = MaterialTheme.typography.titleLarge,
                    color = Color.White.copy(alpha = 0.8f),
                    textAlign = TextAlign.Center,
                    modifier = Modifier.padding(horizontal = 48.dp)
                )
            }
            
            // State indicator
            Text(
                text = when (state) {
                    VoiceState.Listening -> "Listening..."
                    VoiceState.Processing -> "Thinking..."
                    VoiceState.Speaking -> "Speaking..."
                    else -> ""
                },
                style = MaterialTheme.typography.bodyLarge,
                color = Color.White.copy(alpha = 0.6f)
            )
        }
    }
}
```

### 3.9 Android Manifest for Launcher

```xml
<!-- AndroidManifest.xml for Display App -->
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    package="com.barnabee.display">

    <!-- Permissions -->
    <uses-permission android:name="android.permission.RECORD_AUDIO" />
    <uses-permission android:name="android.permission.CAMERA" />
    <uses-permission android:name="android.permission.INTERNET" />
    <uses-permission android:name="android.permission.FOREGROUND_SERVICE" />
    <uses-permission android:name="android.permission.FOREGROUND_SERVICE_CAMERA" />
    <uses-permission android:name="android.permission.FOREGROUND_SERVICE_MICROPHONE" />
    <uses-permission android:name="android.permission.RECEIVE_BOOT_COMPLETED" />
    <uses-permission android:name="android.permission.WAKE_LOCK" />
    <uses-permission android:name="android.permission.READ_EXTERNAL_STORAGE" />

    <!-- Required for launcher -->
    <uses-feature android:name="android.hardware.camera" android:required="true" />
    <uses-feature android:name="android.hardware.camera.front" android:required="true" />

    <application
        android:name=".BarnabeeDisplayApplication"
        android:icon="@mipmap/ic_launcher"
        android:label="@string/app_name"
        android:theme="@style/Theme.BarnabeeDisplay"
        android:keepScreenOn="true">

        <!-- Main Launcher Activity -->
        <activity
            android:name=".BarnabeeDisplayLauncher"
            android:exported="true"
            android:launchMode="singleTask"
            android:screenOrientation="landscape"
            android:configChanges="orientation|screenSize"
            android:excludeFromRecents="true">
            
            <!-- Register as a home/launcher app -->
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.HOME" />
                <category android:name="android.intent.category.DEFAULT" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>

        <!-- Motion Detection Service -->
        <service
            android:name=".services.MotionDetectionService"
            android:foregroundServiceType="camera"
            android:exported="false">
        </service>

        <!-- Wake Word Service -->
        <service
            android:name=".services.WakeWordService"
            android:foregroundServiceType="microphone"
            android:exported="false">
        </service>

        <!-- Boot Receiver - Auto-start on device boot -->
        <receiver
            android:name=".BootReceiver"
            android:exported="true"
            android:directBootAware="true">
            <intent-filter>
                <action android:name="android.intent.action.BOOT_COMPLETED" />
                <action android:name="android.intent.action.LOCKED_BOOT_COMPLETED" />
            </intent-filter>
        </receiver>

    </application>

</manifest>
```

### 3.10 Display App Configuration

```kotlin
// DisplayConfig.kt - Configuration for display app
package com.barnabee.display

data class DisplayConfig(
    // Barnabee backend
    val barnabeeUrl: String = "https://barnabee.local",
    val wsUrl: String = "wss://barnabee.local/v2/voice/stream",
    
    // Home Assistant
    val haDashboardUrl: String = "http://homeassistant.local:8123/lovelace/display",
    val haToken: String = "",
    
    // Slideshow
    val slideshowSources: List<PhotoSource> = emptyList(),
    val slideshowIntervalSeconds: Int = 30,
    
    // Motion detection
    val motionSensitivity: Float = 0.05f,  // 5% pixel change
    val idleTimeoutMinutes: Int = 5,
    
    // Display
    val idleBrightness: Float = 0.3f,  // 30% brightness when idle
    val activeBrightness: Float = 1.0f,
    
    // Device
    val deviceId: String = "",
    val deviceLocation: String = "",  // e.g., "kitchen", "living_room"
)
```

---

## 4. iOS Application

### 3.1 Platform Limitations

Apple does not allow third-party apps to:
- Replace Siri as the default assistant
- Continuously listen for wake words in the background
- Process audio when the app is not in foreground

**Practical implications:**
- No always-on wake word detection
- Must use push-to-talk or Siri Shortcuts
- Limited to foreground audio capture
- Home Assistant becomes the primary fallback for hands-free

### 3.2 iOS App Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       iOS APPLICATION                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    UI LAYER (SwiftUI)                                │   │
│  │                                                                      │   │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐     │   │
│  │  │   Main View     │  │  Voice Sheet    │  │    Widget       │     │   │
│  │  │  (Push-to-talk) │  │  (Full screen   │  │  (WidgetKit)    │     │   │
│  │  │                 │  │   voice UI)     │  │                 │     │   │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────┘     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                   │                                          │
│                                   ▼                                          │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    SERVICE LAYER                                     │   │
│  │                                                                      │   │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐     │   │
│  │  │  AudioEngine    │  │  WebSocket      │  │  Siri Shortcut  │     │   │
│  │  │  (AVFoundation) │  │  Client         │  │  Handler        │     │   │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────┘     │   │
│  │                                                                      │   │
│  │  ┌─────────────────┐  ┌─────────────────┐                          │   │
│  │  │  Auth Manager   │  │  Notification   │                          │   │
│  │  │  (Keychain)     │  │  Handler        │                          │   │
│  │  └─────────────────┘  └─────────────────┘                          │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.3 Technology Stack

| Component | Technology | Notes |
|-----------|------------|-------|
| Language | Swift | Native iOS development |
| UI Framework | SwiftUI | Modern declarative UI |
| Architecture | MVVM | Clean separation |
| Networking | URLSession WebSocket | Native WebSocket support |
| Audio | AVFoundation | Audio capture and playback |
| Secure Storage | Keychain | For auth tokens |
| Widget | WidgetKit | Home screen widget |
| Shortcuts | App Intents | Siri Shortcuts support |

### 3.4 Push-to-Talk Implementation

```swift
// VoiceSession.swift - Main voice interaction handler
import AVFoundation
import Combine

class VoiceSession: ObservableObject {
    @Published var state: VoiceState = .idle
    @Published var transcript: String = ""
    @Published var response: String = ""
    
    private var audioEngine: AVAudioEngine?
    private var webSocket: URLSessionWebSocketTask?
    private let authManager: AuthManager
    private let config: AppConfig
    
    init(authManager: AuthManager, config: AppConfig) {
        self.authManager = authManager
        self.config = config
    }
    
    func startSession() async throws {
        // Request microphone permission
        guard await requestMicrophonePermission() else {
            throw VoiceError.permissionDenied
        }
        
        // Connect WebSocket
        try await connectWebSocket()
        
        // Start audio capture
        try startAudioCapture()
        
        state = .listening
    }
    
    func endSession() {
        stopAudioCapture()
        sendEndMessage()
        state = .processing
    }
    
    private func connectWebSocket() async throws {
        guard let token = authManager.sessionToken else {
            throw VoiceError.notAuthenticated
        }
        
        var urlComponents = URLComponents(string: "\(config.wsBaseUrl)/v2/voice/stream")!
        urlComponents.queryItems = [URLQueryItem(name: "token", value: token)]
        
        guard let url = urlComponents.url else {
            throw VoiceError.invalidURL
        }
        
        let session = URLSession(configuration: .default)
        webSocket = session.webSocketTask(with: url)
        webSocket?.resume()
        
        // Start receiving messages
        receiveMessages()
    }
    
    private func startAudioCapture() throws {
        audioEngine = AVAudioEngine()
        
        let inputNode = audioEngine!.inputNode
        let format = inputNode.outputFormat(forBus: 0)
        
        // Install tap for audio data
        inputNode.installTap(onBus: 0, bufferSize: 4096, format: format) { [weak self] buffer, time in
            self?.sendAudioBuffer(buffer)
        }
        
        try audioEngine!.start()
    }
    
    private func stopAudioCapture() {
        audioEngine?.inputNode.removeTap(onBus: 0)
        audioEngine?.stop()
        audioEngine = nil
    }
    
    private func sendAudioBuffer(_ buffer: AVAudioPCMBuffer) {
        guard let channelData = buffer.floatChannelData else { return }
        
        let frameLength = Int(buffer.frameLength)
        var audioData = Data()
        
        for i in 0..<frameLength {
            var sample = channelData.pointee[i]
            audioData.append(Data(bytes: &sample, count: MemoryLayout<Float>.size))
        }
        
        let message = URLSessionWebSocketTask.Message.data(audioData)
        webSocket?.send(message) { _ in }
    }
    
    private func receiveMessages() {
        webSocket?.receive { [weak self] result in
            switch result {
            case .success(let message):
                self?.handleMessage(message)
                self?.receiveMessages() // Continue receiving
            case .failure(let error):
                self?.handleError(error)
            }
        }
    }
    
    private func handleMessage(_ message: URLSessionWebSocketTask.Message) {
        switch message {
        case .string(let text):
            handleTextMessage(text)
        case .data(let data):
            handleAudioData(data)
        @unknown default:
            break
        }
    }
    
    private func handleTextMessage(_ text: String) {
        guard let data = text.data(using: .utf8),
              let message = try? JSONDecoder().decode(ServerMessage.self, from: data) else {
            return
        }
        
        DispatchQueue.main.async { [weak self] in
            switch message {
            case .transcriptPartial(let text):
                self?.transcript = text
            case .transcriptFinal(let text):
                self?.transcript = text
            case .responseStart:
                self?.state = .speaking
            case .responseText(let text):
                self?.response = text
            case .responseEnd:
                self?.state = .idle
            case .error(let msg):
                self?.state = .error(msg)
            }
        }
    }
    
    private func handleAudioData(_ data: Data) {
        // Play TTS audio response
        AudioPlayer.shared.play(data)
    }
}
```

### 3.5 Siri Shortcuts Integration

```swift
// BarnabeeIntents.swift - Siri Shortcuts support
import AppIntents

struct AskBarnabeeIntent: AppIntent {
    static var title: LocalizedStringResource = "Ask Barnabee"
    static var description = IntentDescription("Ask Barnabee a question")
    
    @Parameter(title: "Question")
    var question: String?
    
    static var parameterSummary: some ParameterSummary {
        Summary("Ask Barnabee \(\.$question)")
    }
    
    func perform() async throws -> some IntentResult & ProvidesDialog {
        let client = BarnabeeTextClient()
        
        guard let question = question, !question.isEmpty else {
            return .result(dialog: "What would you like to ask?")
        }
        
        do {
            let response = try await client.askText(question)
            return .result(dialog: IntentDialog(response))
        } catch {
            return .result(dialog: "Sorry, I couldn't connect to Barnabee.")
        }
    }
}

struct ControlLightsIntent: AppIntent {
    static var title: LocalizedStringResource = "Control Lights"
    static var description = IntentDescription("Turn lights on or off via Barnabee")
    
    @Parameter(title: "Action")
    var action: LightAction
    
    @Parameter(title: "Room")
    var room: String?
    
    enum LightAction: String, AppEnum {
        case on, off, toggle
        
        static var typeDisplayRepresentation: TypeDisplayRepresentation = "Light Action"
        static var caseDisplayRepresentations: [LightAction: DisplayRepresentation] = [
            .on: "Turn On",
            .off: "Turn Off",
            .toggle: "Toggle",
        ]
    }
    
    func perform() async throws -> some IntentResult & ProvidesDialog {
        let client = BarnabeeTextClient()
        
        let command = room != nil
            ? "Turn \(action.rawValue) the \(room!) lights"
            : "Turn \(action.rawValue) the lights"
        
        do {
            let response = try await client.askText(command)
            return .result(dialog: IntentDialog(response))
        } catch {
            return .result(dialog: "Sorry, I couldn't control the lights.")
        }
    }
}

// App Shortcuts provider
struct BarnabeeShortcuts: AppShortcutsProvider {
    static var appShortcuts: [AppShortcut] {
        AppShortcut(
            intent: AskBarnabeeIntent(),
            phrases: [
                "Ask \(.applicationName) \(\.$question)",
                "Hey \(.applicationName) \(\.$question)",
            ],
            shortTitle: "Ask Barnabee",
            systemImageName: "bubble.left.fill"
        )
        
        AppShortcut(
            intent: ControlLightsIntent(),
            phrases: [
                "Turn \(\.$action) the lights with \(.applicationName)",
                "\(.applicationName) lights \(\.$action)",
            ],
            shortTitle: "Control Lights",
            systemImageName: "lightbulb.fill"
        )
    }
}
```

### 3.6 Home Screen Widget

```swift
// BarnabeeWidget.swift - WidgetKit implementation
import WidgetKit
import SwiftUI

struct BarnabeeWidgetEntry: TimelineEntry {
    let date: Date
    let lastInteraction: String?
}

struct BarnabeeWidgetProvider: TimelineProvider {
    func placeholder(in context: Context) -> BarnabeeWidgetEntry {
        BarnabeeWidgetEntry(date: Date(), lastInteraction: nil)
    }
    
    func getSnapshot(in context: Context, completion: @escaping (BarnabeeWidgetEntry) -> Void) {
        let entry = BarnabeeWidgetEntry(date: Date(), lastInteraction: "Tap to talk")
        completion(entry)
    }
    
    func getTimeline(in context: Context, completion: @escaping (Timeline<BarnabeeWidgetEntry>) -> Void) {
        let entry = BarnabeeWidgetEntry(date: Date(), lastInteraction: "Tap to talk")
        let timeline = Timeline(entries: [entry], policy: .never)
        completion(timeline)
    }
}

struct BarnabeeWidgetView: View {
    var entry: BarnabeeWidgetEntry
    
    var body: some View {
        ZStack {
            Color.blue.opacity(0.1)
            
            VStack(spacing: 8) {
                Image(systemName: "waveform.circle.fill")
                    .font(.system(size: 40))
                    .foregroundColor(.blue)
                
                Text("Barnabee")
                    .font(.headline)
                
                if let lastInteraction = entry.lastInteraction {
                    Text(lastInteraction)
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }
        }
        .widgetURL(URL(string: "barnabee://voice"))
    }
}

@main
struct BarnabeeWidget: Widget {
    let kind: String = "BarnabeeWidget"
    
    var body: some WidgetConfiguration {
        StaticConfiguration(kind: kind, provider: BarnabeeWidgetProvider()) { entry in
            BarnabeeWidgetView(entry: entry)
        }
        .configurationDisplayName("Barnabee")
        .description("Quick access to Barnabee voice assistant")
        .supportedFamilies([.systemSmall])
    }
}
```

---

## 4. Home Assistant Assist Integration (iOS Fallback)

### 4.1 Configuration Guide

For iOS users who need hands-free access, Home Assistant's Assist feature provides a reliable fallback.

**Prerequisites:**
- Home Assistant 2023.5+ with Assist configured
- HA Companion app installed on iOS device
- Barnabee backend accessible from HA

### 4.2 HA Custom Conversation Agent

```yaml
# configuration.yaml
conversation:
  intents:
    BarnabeeProxy:
      - ".*"  # Match everything

intent_script:
  BarnabeeProxy:
    async_action: true
    action:
      - service: rest_command.barnabee_query
        data:
          query: "{{ trigger.sentence }}"
          speaker: "{{ context.user_id }}"
        response_variable: barnabee_response
      - stop: "{{ barnabee_response.content.response }}"

rest_command:
  barnabee_query:
    url: "http://barnabee.local:8000/v2/text/query"
    method: POST
    headers:
      Authorization: "Bearer {{ states('input_text.barnabee_token') }}"
      Content-Type: "application/json"
    payload: '{"query": "{{ query }}", "speaker_id": "{{ speaker }}"}'
```

### 4.3 HA Companion App Setup Instructions

```markdown
## Setting Up Barnabee via Home Assistant on iOS

1. **Open Home Assistant Companion App**
   - Go to Settings → Companion App → Assist

2. **Configure Assist Pipeline**
   - Select "Barnabee" as the conversation agent
   - Enable "Use with Siri"

3. **Siri Integration**
   - Say "Hey Siri, ask Home Assistant..."
   - Your query will be routed to Barnabee

4. **Apple Watch**
   - The HA Companion app supports voice on Apple Watch
   - Tap the Assist complication to talk to Barnabee

**Note:** This method requires HA to be accessible. For local-only 
access, ensure your iOS device is on the home network.
```

---

## 5. Build and Distribution

### 5.1 Android Distribution

| Method | Audience | Update Mechanism |
|--------|----------|------------------|
| APK Direct | Family | Manual download from dashboard |
| F-Droid (optional) | Privacy-conscious users | F-Droid client updates |
| Internal Testing | Development | ADB install |

```yaml
# .github/workflows/android-build.yml
name: Android Build

on:
  push:
    tags:
      - 'v*'
  workflow_dispatch:

jobs:
  build:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up JDK
        uses: actions/setup-java@v4
        with:
          java-version: '17'
          distribution: 'temurin'
      
      - name: Build Release APK
        run: ./gradlew assembleRelease
        working-directory: mobile/android
      
      - name: Sign APK
        uses: r0adkll/sign-android-release@v1
        with:
          releaseDirectory: mobile/android/app/build/outputs/apk/release
          signingKeyBase64: ${{ secrets.SIGNING_KEY }}
          alias: ${{ secrets.ALIAS }}
          keyStorePassword: ${{ secrets.KEY_STORE_PASSWORD }}
          keyPassword: ${{ secrets.KEY_PASSWORD }}
      
      - name: Upload APK
        uses: actions/upload-artifact@v4
        with:
          name: barnabee-release
          path: mobile/android/app/build/outputs/apk/release/*.apk
```

### 5.2 iOS Distribution

| Method | Audience | Limit |
|--------|----------|-------|
| TestFlight | Family members | 10,000 users |
| Ad Hoc | Development | 100 devices |

```yaml
# .github/workflows/ios-build.yml
name: iOS Build

on:
  push:
    tags:
      - 'v*'
  workflow_dispatch:

jobs:
  build:
    runs-on: macos-latest
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Install certificates
        uses: apple-actions/import-codesign-certs@v2
        with:
          p12-file-base64: ${{ secrets.CERTIFICATES_P12 }}
          p12-password: ${{ secrets.CERTIFICATES_PASSWORD }}
      
      - name: Install provisioning profile
        uses: apple-actions/download-provisioning-profiles@v1
        with:
          bundle-id: com.barnabee.assistant
          issuer-id: ${{ secrets.APPSTORE_ISSUER_ID }}
          api-key-id: ${{ secrets.APPSTORE_KEY_ID }}
          api-private-key: ${{ secrets.APPSTORE_PRIVATE_KEY }}
      
      - name: Build iOS app
        run: |
          xcodebuild -workspace Barnabee.xcworkspace \
            -scheme Barnabee \
            -configuration Release \
            -archivePath build/Barnabee.xcarchive \
            archive
        working-directory: mobile/ios
      
      - name: Export IPA
        run: |
          xcodebuild -exportArchive \
            -archivePath build/Barnabee.xcarchive \
            -exportPath build/export \
            -exportOptionsPlist ExportOptions.plist
        working-directory: mobile/ios
      
      - name: Upload to TestFlight
        uses: apple-actions/upload-testflight-build@v1
        with:
          app-path: mobile/ios/build/export/Barnabee.ipa
          issuer-id: ${{ secrets.APPSTORE_ISSUER_ID }}
          api-key-id: ${{ secrets.APPSTORE_KEY_ID }}
          api-private-key: ${{ secrets.APPSTORE_PRIVATE_KEY }}
```

---

## 6. Implementation Checklist

### Android Phone App
- [ ] Project setup (Kotlin, Jetpack Compose, Hilt)
- [ ] VoiceInteractionService implementation
- [ ] Wake word service with openWakeWord
- [ ] Audio capture and WebSocket streaming
- [ ] Device registration flow
- [ ] Main UI with voice overlay
- [ ] Widget implementation
- [ ] Quick settings tile
- [ ] Notification tracking and forwarding
- [ ] Boot receiver for auto-start
- [ ] Battery optimization handling

### Android Display App (Lenovo View)
- [ ] Project setup (Kotlin, Jetpack Compose)
- [ ] Launcher activity with HOME intent filter
- [ ] Motion detection service (camera-based)
- [ ] Wake word service (always listening)
- [ ] Display mode state machine (Idle/Active/Voice)
- [ ] Photo slideshow (Google Photos, local, HA media)
- [ ] HA Dashboard WebView integration
- [ ] Voice UI overlay
- [ ] Auto-brightness based on mode
- [ ] Boot receiver for auto-start
- [ ] Screen always-on handling

### iOS App
- [ ] Project setup (Swift, SwiftUI)
- [ ] Push-to-talk voice session
- [ ] WebSocket client
- [ ] Device registration
- [ ] Siri Shortcuts (App Intents)
- [ ] Home screen widget
- [ ] Keychain auth storage

### Home Assistant Integration
- [ ] Custom conversation agent configuration
- [ ] REST command for Barnabee proxy
- [ ] Display-specific dashboard (lovelace/display)
- [ ] Setup documentation for users

### CI/CD
- [ ] Android Phone app build workflow
- [ ] Android Display app build workflow
- [ ] iOS build workflow
- [ ] Artifact storage
- [ ] Version management

---

## 7. Acceptance Criteria

### Android Phone App
1. **Default assistant works:** Long-press home launches Barnabee instead of Google Assistant
2. **Wake word works:** "Hey Barnabee" triggers voice UI from background
3. **Voice commands work:** Full round-trip voice → STT → intent → response → TTS
4. **Widget works:** Tap widget launches voice session
5. **Notification tracking:** App sees and can report on notifications
6. **Battery acceptable:** <5% daily battery drain with wake word enabled

### Android Display App (Lenovo View)
1. **Launcher works:** App is set as default home, survives reboots
2. **Motion detection works:** Screen shows HA dashboard when person approaches
3. **Slideshow works:** Photos cycle when no motion detected for 5 minutes
4. **Wake word works:** "Hey Barnabee" triggers voice mode from any display mode
5. **HA Dashboard works:** WebView shows configured dashboard with auto-refresh
6. **Touch-to-talk works:** Tapping screen triggers voice mode
7. **Always-on:** Display never sleeps (device is plugged in)

### iOS App
1. **Push-to-talk works:** App foreground voice session completes successfully
2. **Siri Shortcuts work:** "Hey Siri, ask Barnabee" routes query and speaks response
3. **Widget works:** Tap widget opens app to voice mode
4. **HA fallback works:** Assist via HA Companion routes to Barnabee

---

## 8. Handoff Notes for Implementation Agent

### Critical Points

1. **Two separate Android apps.** Don't try to combine phone and display into one app—they have completely different purposes and lifecycles.

2. **Phone app: VoiceInteractionService is key.** This is what makes Barnabee the default assistant. Get this right first.

3. **Display app: Launcher mode is key.** The app must register as a launcher and handle HOME intent. It replaces the entire home screen.

4. **Wake word runs locally on both.** Don't stream audio to backend until wake word is detected. Privacy and efficiency.

5. **Display app is always-on.** No battery optimization needed—device is plugged in. Screen should never sleep.

6. **Motion detection is presence detection.** Use front camera with low resolution (320x240) and low frame rate (5-10fps) to detect if someone is in the room.

7. **iOS Siri Shortcuts are the main iOS voice interface.** Push-to-talk requires app open. Siri Shortcuts work hands-free.

### Common Pitfalls

- Forgetting to handle Android battery optimization on phone app (gets killed)
- Display app: Not keeping screen awake (use FLAG_KEEP_SCREEN_ON)
- Display app: Camera permissions denied on first run
- Not requesting permissions correctly (audio, camera, notifications)
- WebSocket reconnection not robust enough
- iOS background audio restrictions (can't capture in background)
- Display app: WebView not injecting HA auth token correctly

### Platform-Specific Notes

**Android Phone:**
- Target SDK 34+ for latest assistant APIs
- Handle Doze mode and app standby
- Test on multiple manufacturers (Samsung, Pixel, etc.)

**Android Display (Lenovo View):**
- Test launcher behavior on the specific device
- Ensure direct boot aware (starts before unlock)
- Handle screen brightness programmatically
- Test camera-based motion detection lighting conditions

**iOS:**
- iOS 17+ for latest App Intents
- Test Shortcuts in different Siri languages
- Widget refresh is limited by iOS

---

**End of Area 20: Native Mobile Applications**
