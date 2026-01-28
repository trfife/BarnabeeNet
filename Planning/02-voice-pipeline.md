# Area 02: Voice Pipeline

**Version:** 1.0  
**Status:** Implementation Ready  
**Dependencies:** Area 01 (Core Data Layer)  
**Phase:** Infrastructure  

---

## 1. Overview

### 1.1 Purpose

The Voice Pipeline handles all audio I/O: wake word detection, speech-to-text, text-to-speech, and real-time audio transport. This is the most latency-critical component—every millisecond here is felt by users.

### 1.2 V1 Problems Solved

| V1 Problem | V2 Solution |
|------------|-------------|
| 300-500ms STT hop to HA/Mentra | Local Parakeet STT (<50ms) |
| 200-400ms TTS hop to HA/Mentra | Local Kokoro TTS (<200ms) |
| No barge-in support | Pipecat full-duplex with interrupt handling |
| Sequential processing | Parallel STT + filler injection |
| No acoustic echo cancellation | WebRTC built-in AEC |

### 1.3 Design Principles

1. **Local-first:** STT and TTS run on RTX 4070 Ti. Cloud is fallback only.
2. **Full-duplex:** User can interrupt Barnabee mid-response.
3. **Streaming:** Don't wait for complete utterance—stream STT results.
4. **Filler injection:** Mask latency with contextual acknowledgments.
5. **Device-agnostic:** Same pipeline serves phones, tablets, glasses, desktop.

### 1.4 Latency Budget

| Component | Budget | Notes |
|-----------|--------|-------|
| Wake word detection | 50ms | openWakeWord on GPU |
| VAD + AEC | 30ms | Silero VAD |
| STT (streaming) | 100ms | Parakeet, first partial |
| SmartTurn detection | 50ms | Semantic end-of-turn |
| **Total input latency** | **230ms** | Wake to text ready |
| TTS generation | 150ms | Kokoro, first chunk |
| Audio delivery | 50ms | WebRTC/WebSocket |
| **Total output latency** | **200ms** | Text to first audio |

**End-to-end target:** <500ms from end of user speech to first audio response (for cached/fast-path commands).

---

## 2. Technology Stack

| Component | Technology | Version | Rationale |
|-----------|------------|---------|-----------|
| Orchestration | Pipecat | 0.0.40+ | Production-tested, handles full-duplex complexity |
| Transport (primary) | WebRTC | - | Built-in AEC, DTLS encryption, NAT traversal |
| Transport (fallback) | WebSocket | - | For devices that can't do WebRTC |
| Wake word | openWakeWord | 0.6+ | Trainable, open source, HA-integrated |
| VAD | Silero VAD | 4.0+ | Fast, accurate, MIT licensed |
| STT | NVIDIA Parakeet | 1.0b | <50ms latency, 95%+ accuracy |
| TTS | Kokoro | 0.8+ | Custom voice training, low latency |
| Audio processing | PyAudio / sounddevice | - | Low-level audio I/O |

### 2.1 Why Pipecat

Per Pipecat documentation and Daily.co benchmarks:
- Handles VAD, interruption, streaming STT/TTS out of the box
- Supports WebRTC via Daily.co or self-hosted
- Async Python, integrates with FastAPI
- Used in production by voice AI companies (Daily, Cartesia)

Building this from scratch would take months and introduce subtle bugs (race conditions in duplex audio are notoriously hard).

### 2.2 Why Not Whisper

| Model | Latency | Accuracy | GPU Memory |
|-------|---------|----------|------------|
| Whisper large-v3 | 800-1200ms | 97% | 10GB |
| Whisper medium | 400-600ms | 94% | 5GB |
| Parakeet-TDT-1.1B | 45-80ms | 95% | 4GB |

Per NVIDIA benchmarks, Parakeet achieves near-Whisper accuracy at 10-15x lower latency. This is critical for conversational feel.

---

## 3. Architecture

### 3.1 High-Level Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           VOICE PIPELINE                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  DEVICE LAYER                                                                │
│  ════════════                                                                │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐                    │
│  │  Phone   │  │  Tablet  │  │ Glasses  │  │ Desktop  │                    │
│  │ (Native) │  │ (WebRTC) │  │  (BLE)   │  │ (WebRTC) │                    │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘                    │
│       │             │             │             │                           │
│       └─────────────┴──────┬──────┴─────────────┘                           │
│                            │                                                 │
│  TRANSPORT LAYER           ▼                                                 │
│  ═══════════════  ┌────────────────┐                                        │
│                   │ WebRTC Server  │◄─── STUN/TURN for NAT traversal       │
│                   │ (Daily.co SDK  │                                        │
│                   │  or Pipecat)   │                                        │
│                   └───────┬────────┘                                        │
│                           │                                                 │
│  PROCESSING LAYER         ▼                                                 │
│  ════════════════ ┌───────────────────────────────────────────────────┐    │
│                   │              PIPECAT PIPELINE                      │    │
│                   │                                                    │    │
│                   │  ┌─────────┐    ┌─────────┐    ┌─────────┐       │    │
│                   │  │   AEC   │───▶│   VAD   │───▶│  Wake   │       │    │
│                   │  │ (WebRTC)│    │(Silero) │    │  Word   │       │    │
│                   │  └─────────┘    └─────────┘    └────┬────┘       │    │
│                   │                                     │            │    │
│                   │                    ┌────────────────┘            │    │
│                   │                    ▼                             │    │
│                   │  ┌─────────────────────────────────────────┐    │    │
│                   │  │         STREAMING STT (Parakeet)        │    │    │
│                   │  │                                         │    │    │
│                   │  │  Audio chunks ──▶ Partial transcripts   │    │    │
│                   │  │                   ──▶ Final transcript  │    │    │
│                   │  └─────────────────────┬───────────────────┘    │    │
│                   │                        │                        │    │
│                   │                        ▼                        │    │
│                   │  ┌─────────────────────────────────────────┐    │    │
│                   │  │         SMART TURN DETECTION            │    │    │
│                   │  │                                         │    │    │
│                   │  │  Silence + Semantic completion check    │    │    │
│                   │  └─────────────────────┬───────────────────┘    │    │
│                   │                        │                        │    │
│                   └────────────────────────┼────────────────────────┘    │
│                                            │                             │
│                                            ▼                             │
│                              ┌─────────────────────────┐                 │
│                              │    TO INTENT ROUTER     │                 │
│                              │    (Area 03)            │                 │
│                              └─────────────────────────┘                 │
│                                                                          │
│  OUTPUT PATH                                                             │
│  ═══════════                                                             │
│                              ┌─────────────────────────┐                 │
│                              │   FROM RESPONSE GEN     │                 │
│                              │   (Area 06)             │                 │
│                              └───────────┬─────────────┘                 │
│                                          │                               │
│                   ┌──────────────────────┼──────────────────────┐       │
│                   │                      ▼                      │       │
│                   │  ┌─────────────────────────────────────┐   │       │
│                   │  │         STREAMING TTS (Kokoro)      │   │       │
│                   │  │                                     │   │       │
│                   │  │  Text chunks ──▶ Audio chunks       │   │       │
│                   │  │  (stream as generated)              │   │       │
│                   │  └─────────────────────┬───────────────┘   │       │
│                   │                        │                   │       │
│                   │                        ▼                   │       │
│                   │  ┌─────────────────────────────────────┐   │       │
│                   │  │         BARGE-IN DETECTOR           │   │       │
│                   │  │                                     │   │       │
│                   │  │  Monitor input while outputting     │   │       │
│                   │  │  If speech detected: cancel TTS     │   │       │
│                   │  └─────────────────────────────────────┘   │       │
│                   │                                            │       │
│                   └────────────────────────┼───────────────────┘       │
│                                            │                           │
│                                            ▼                           │
│                              ┌─────────────────────────┐               │
│                              │   TO DEVICE VIA WebRTC  │               │
│                              └─────────────────────────┘               │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Pipeline States

```
                    ┌──────────────┐
                    │    IDLE      │
                    │  (listening  │
                    │  for wake)   │
                    └──────┬───────┘
                           │ Wake word detected
                           ▼
                    ┌──────────────┐
                    │   LISTENING  │
                    │  (STT active)│
                    └──────┬───────┘
                           │ End of turn detected
                           ▼
                    ┌──────────────┐
                    │  PROCESSING  │◄─── Filler plays here
                    │  (waiting    │
                    │   for LLM)   │
                    └──────┬───────┘
                           │ Response ready
                           ▼
                    ┌──────────────┐
         ┌─────────│   SPEAKING   │
         │         │  (TTS output)│
         │         └──────┬───────┘
         │                │ Utterance complete
         │ Barge-in       ▼
         │         ┌──────────────┐
         └────────▶│   LISTENING  │ (if conversation mode)
                   │   or IDLE    │ (if command mode)
                   └──────────────┘
```

---

## 4. Component Specifications

### 4.1 Wake Word Detection (openWakeWord)

**Model:** Custom-trained "Barnabee" model

**Training requirements:**
- 3000+ synthetic samples via Piper TTS (multiple voices, speeds, pitches)
- 100+ real recordings from family members
- Negative samples from common household audio

**Configuration:**
```python
WAKE_WORD_CONFIG = {
    "model_path": "/models/barnabee_wake.onnx",
    "threshold": 0.7,              # Trigger threshold
    "trigger_level": 3,            # Consecutive frames needed
    "vad_threshold": 0.5,          # Pre-filter with VAD
    "refractory_period_ms": 2000,  # Cooldown after trigger
}
```

**Performance targets:**
- False positive rate: <0.5/hour
- False negative rate: <2%
- Latency: <50ms from utterance end to detection

**Training script location:** `/scripts/train_wake_word.py`

### 4.2 Voice Activity Detection (Silero VAD)

**Purpose:** Detect speech vs. silence to control STT activation and end-of-turn detection.

**Configuration:**
```python
VAD_CONFIG = {
    "model": "silero_vad",
    "threshold": 0.5,
    "min_speech_duration_ms": 250,
    "min_silence_duration_ms": 300,  # End-of-utterance silence
    "speech_pad_ms": 30,
    "window_size_samples": 512,      # 32ms at 16kHz
}
```

**Integration with SmartTurn:**
- VAD provides raw speech/silence signals
- SmartTurn adds semantic completion detection
- Combined: don't cut off "I want to..." just because of brief pause

### 4.3 SmartTurn Detection

**Problem:** Silence-based turn detection fails on:
- Thinking pauses ("I want to... hmm... turn on the light")
- List enumeration ("Turn on the kitchen, living room, and... bedroom lights")
- Natural speech disfluencies

**Solution:** Combine silence detection with semantic completion scoring.

**Algorithm:**
```python
async def detect_end_of_turn(transcript: str, silence_ms: int) -> bool:
    # Fast path: long silence always ends turn
    if silence_ms > 1500:
        return True
    
    # Fast path: short silence never ends turn
    if silence_ms < 300:
        return False
    
    # Medium silence: check semantic completion
    if 300 <= silence_ms <= 1500:
        completion_score = await score_semantic_completion(transcript)
        
        # Higher silence = lower completion threshold needed
        threshold = 0.9 - (silence_ms - 300) / 2400  # 0.9 at 300ms, 0.4 at 1500ms
        
        return completion_score > threshold
    
    return False


async def score_semantic_completion(text: str) -> float:
    """
    Score how semantically complete an utterance is.
    Uses lightweight local model or heuristics.
    
    Returns: 0.0 (incomplete) to 1.0 (complete)
    """
    # Heuristic fast path for common patterns
    text_lower = text.lower().strip()
    
    # Clearly complete
    if text_lower.endswith(('please', 'thanks', 'now', '?', '!')):
        return 0.95
    
    # Clearly incomplete
    incomplete_patterns = [
        'and', 'or', 'but', 'the', 'a', 'an', 'to', 'in', 'on',
        'i want to', 'can you', 'please turn', 'set the'
    ]
    for pattern in incomplete_patterns:
        if text_lower.endswith(pattern):
            return 0.2
    
    # Ambiguous: use lightweight classifier
    # This could be a small fine-tuned model or LLM call
    return await classifier.score_completion(text)
```

**Performance target:** <50ms for heuristic path, <150ms with classifier fallback

### 4.4 Speech-to-Text (Parakeet)

**Model:** NVIDIA Parakeet-TDT-1.1B

**Why Parakeet:**
- Streaming (emits partial results)
- <50ms latency to first partial
- 95%+ accuracy (comparable to Whisper medium)
- Runs efficiently on RTX 4070 Ti (4GB VRAM)

**Configuration:**
```python
STT_CONFIG = {
    "model": "nvidia/parakeet-tdt-1.1b",
    "device": "cuda",
    "compute_type": "float16",
    "beam_size": 1,                    # Greedy for speed
    "language": "en",
    "chunk_length_s": 0.5,             # Process 500ms chunks
    "stream_chunk_s": 0.1,             # Emit partials every 100ms
    "vad_filter": True,
    "word_timestamps": False,          # Disable for speed (enable for meetings)
}
```

**Streaming integration:**
```python
class StreamingSTT:
    def __init__(self, config: dict):
        self.model = load_parakeet(config)
        self.buffer = AudioBuffer()
        self.transcript = ""
    
    async def process_chunk(self, audio_chunk: bytes) -> Optional[str]:
        """Process audio chunk, return partial transcript if available."""
        self.buffer.append(audio_chunk)
        
        if self.buffer.duration_ms >= 100:  # Process every 100ms
            partial = await self.model.transcribe_streaming(
                self.buffer.get_audio(),
                is_final=False
            )
            
            if partial and partial != self.transcript:
                self.transcript = partial
                return partial
        
        return None
    
    async def finalize(self) -> str:
        """Finalize transcription when turn ends."""
        final = await self.model.transcribe_streaming(
            self.buffer.get_audio(),
            is_final=True
        )
        self.buffer.clear()
        result = final or self.transcript
        self.transcript = ""
        return result
```

### 4.5 Text-to-Speech (Kokoro)

**Model:** Kokoro with custom Barnabee voice

**Why Kokoro:**
- Open source (Apache 2.0)
- Custom voice training supported
- Streaming output
- Low latency (<200ms to first audio)
- Natural prosody

**Voice training:**
1. Record 30+ minutes of target voice samples
2. Transcribe samples
3. Fine-tune Kokoro on voice + transcripts
4. Export ONNX model for inference

**Configuration:**
```python
TTS_CONFIG = {
    "model": "/models/kokoro_barnabee.onnx",
    "voice": "barnabee_v1",
    "device": "cuda",
    "sample_rate": 24000,
    "streaming": True,
    "chunk_size": 1024,                # Samples per chunk
    "speed": 1.0,
    "pitch": 1.0,
}
```

**Streaming implementation:**
```python
class StreamingTTS:
    def __init__(self, config: dict):
        self.model = load_kokoro(config)
        self.audio_queue = asyncio.Queue()
        self.is_speaking = False
        self.cancelled = False
    
    async def speak(self, text: str) -> AsyncIterator[bytes]:
        """Stream audio chunks as they're generated."""
        self.is_speaking = True
        self.cancelled = False
        
        async for audio_chunk in self.model.synthesize_streaming(text):
            if self.cancelled:
                break
            yield audio_chunk
        
        self.is_speaking = False
    
    def cancel(self):
        """Cancel current speech (for barge-in)."""
        self.cancelled = True
```

### 4.6 Barge-In Handling

**Problem:** User starts speaking while Barnabee is responding. Must:
1. Detect user speech during TTS output
2. Cancel TTS immediately
3. Switch to listening mode
4. Not trigger on echo of Barnabee's own voice (AEC handles this)

**Implementation:**
```python
class BargeInDetector:
    def __init__(self, vad: SileroVAD, tts: StreamingTTS):
        self.vad = vad
        self.tts = tts
        self.barge_in_threshold = 0.7
        self.min_speech_duration_ms = 150  # Avoid false triggers
        self.speech_start_time = None
    
    async def monitor(self, audio_chunk: bytes) -> bool:
        """
        Monitor input audio during TTS output.
        Returns True if barge-in detected.
        """
        if not self.tts.is_speaking:
            return False
        
        # VAD on input (AEC should have removed TTS echo)
        is_speech = await self.vad.is_speech(audio_chunk)
        
        if is_speech:
            if self.speech_start_time is None:
                self.speech_start_time = time.monotonic()
            
            speech_duration_ms = (time.monotonic() - self.speech_start_time) * 1000
            
            if speech_duration_ms >= self.min_speech_duration_ms:
                # Confirmed barge-in
                self.tts.cancel()
                self.speech_start_time = None
                return True
        else:
            self.speech_start_time = None
        
        return False
```

### 4.7 Filler Audio Injection

**Purpose:** Mask processing latency with contextual acknowledgments.

**Pre-generated fillers:**
```python
FILLERS = {
    "acknowledgment_short": [
        "mm-hmm",
        "okay", 
        "got it",
        "sure",
    ],
    "acknowledgment_thinking": [
        "let me check",
        "one moment",
        "checking now",
    ],
    "acknowledgment_searching": [
        "searching for that",
        "looking that up",
        "let me find that",
    ],
    "error_soft": [
        "hmm, having trouble with that",
        "let me try again",
    ],
}
```

**Pre-generation script:**
```python
async def generate_fillers(tts: StreamingTTS, output_dir: Path):
    """Pre-generate all filler audio files."""
    for category, phrases in FILLERS.items():
        category_dir = output_dir / category
        category_dir.mkdir(exist_ok=True)
        
        for i, phrase in enumerate(phrases):
            audio = await tts.synthesize(phrase)
            audio_path = category_dir / f"{i}.wav"
            save_audio(audio, audio_path)
```

**Injection logic:**
```python
class FillerInjector:
    def __init__(self, filler_dir: Path):
        self.fillers = self._load_fillers(filler_dir)
        self.last_filler_time = 0
        self.min_filler_gap_ms = 2000  # Don't spam fillers
    
    async def maybe_inject(
        self, 
        processing_time_ms: int,
        context: str = "general"
    ) -> Optional[bytes]:
        """
        Return filler audio if appropriate given processing time.
        """
        now = time.monotonic() * 1000
        
        if now - self.last_filler_time < self.min_filler_gap_ms:
            return None
        
        if processing_time_ms < 100:
            return None  # Too fast, no filler needed
        
        if processing_time_ms < 500:
            category = "acknowledgment_short"
        elif processing_time_ms < 1500:
            category = "acknowledgment_thinking"
        else:
            category = "acknowledgment_searching"
        
        # Select random filler from category
        filler = random.choice(self.fillers[category])
        self.last_filler_time = now
        
        return filler
```

---

## 5. Pipecat Integration

### 5.1 Pipeline Definition

```python
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineTask
from pipecat.processors.aggregators.sentence import SentenceAggregator
from pipecat.services.openai import OpenAILLMService
from pipecat.transports.services.daily import DailyTransport

class BarnabeeVoicePipeline:
    def __init__(self, config: PipelineConfig):
        self.config = config
        self.transport = None
        self.pipeline = None
    
    async def create_pipeline(self, room_url: str, token: str) -> Pipeline:
        """Create the full voice pipeline."""
        
        # Transport (WebRTC via Daily)
        self.transport = DailyTransport(
            room_url=room_url,
            token=token,
            bot_name="Barnabee",
            params=DailyParams(
                audio_in_enabled=True,
                audio_out_enabled=True,
                vad_enabled=True,
                vad_analyzer=SileroVADAnalyzer(),
            )
        )
        
        # STT
        stt = ParakeetSTTService(
            model=self.config.stt_model,
            device="cuda",
        )
        
        # TTS
        tts = KokoroTTSService(
            model=self.config.tts_model,
            voice=self.config.voice,
            device="cuda",
        )
        
        # Wake word
        wake_word = OpenWakeWordService(
            model_path=self.config.wake_word_model,
            threshold=0.7,
        )
        
        # Intent processor (bridges to Area 03)
        intent_processor = BarnabeeIntentProcessor(
            classifier=self.config.intent_classifier,
            ha_client=self.config.ha_client,
            memory_store=self.config.memory_store,
        )
        
        # Filler injector
        filler = FillerInjector(self.config.filler_dir)
        
        # Build pipeline
        self.pipeline = Pipeline([
            self.transport.input(),       # Audio in
            wake_word,                     # Wake word detection
            stt,                           # Speech to text
            SmartTurnDetector(),           # End-of-turn detection
            intent_processor,              # Intent + response generation
            filler,                        # Filler injection
            SentenceAggregator(),          # Buffer for natural TTS
            tts,                           # Text to speech
            self.transport.output(),       # Audio out
        ])
        
        return self.pipeline
    
    async def run(self, room_url: str, token: str):
        """Run the voice pipeline."""
        pipeline = await self.create_pipeline(room_url, token)
        runner = PipelineRunner()
        
        task = PipelineTask(
            pipeline,
            params=PipelineParams(
                allow_interruptions=True,
                enable_metrics=True,
            )
        )
        
        await runner.run(task)
```

### 5.2 Custom Processors

```python
from pipecat.processors.frame_processor import FrameProcessor
from pipecat.frames.frames import (
    Frame, TextFrame, AudioRawFrame, 
    UserStartedSpeakingFrame, UserStoppedSpeakingFrame
)

class SmartTurnDetector(FrameProcessor):
    """
    Combines VAD silence detection with semantic completion.
    """
    
    def __init__(self):
        super().__init__()
        self.transcript_buffer = ""
        self.silence_start = None
        self.completion_scorer = CompletionScorer()
    
    async def process_frame(self, frame: Frame, direction):
        await super().process_frame(frame, direction)
        
        if isinstance(frame, TextFrame):
            # Accumulate transcript
            self.transcript_buffer += frame.text
        
        elif isinstance(frame, UserStoppedSpeakingFrame):
            # User stopped speaking, start silence timer
            self.silence_start = time.monotonic()
        
        elif isinstance(frame, UserStartedSpeakingFrame):
            # User resumed, reset
            self.silence_start = None
        
        # Check for end of turn
        if self.silence_start:
            silence_ms = (time.monotonic() - self.silence_start) * 1000
            
            if await self._is_turn_complete(silence_ms):
                # Emit end-of-turn signal
                await self.push_frame(EndOfTurnFrame(
                    transcript=self.transcript_buffer
                ))
                self.transcript_buffer = ""
                self.silence_start = None
                return
        
        await self.push_frame(frame, direction)
    
    async def _is_turn_complete(self, silence_ms: int) -> bool:
        if silence_ms > 1500:
            return True
        if silence_ms < 300:
            return False
        
        score = await self.completion_scorer.score(self.transcript_buffer)
        threshold = 0.9 - (silence_ms - 300) / 2400
        return score > threshold


class FillerInjector(FrameProcessor):
    """
    Injects filler audio during processing delays.
    """
    
    def __init__(self, filler_dir: Path):
        super().__init__()
        self.fillers = load_fillers(filler_dir)
        self.processing_start = None
    
    async def process_frame(self, frame: Frame, direction):
        await super().process_frame(frame, direction)
        
        if isinstance(frame, EndOfTurnFrame):
            # User finished speaking, start timer
            self.processing_start = time.monotonic()
        
        elif isinstance(frame, TextFrame) and self.processing_start:
            # Response starting, check if filler needed
            processing_ms = (time.monotonic() - self.processing_start) * 1000
            
            if processing_ms > 300:
                filler = self._select_filler(processing_ms)
                if filler:
                    await self.push_frame(AudioRawFrame(
                        audio=filler,
                        sample_rate=24000,
                        num_channels=1
                    ))
            
            self.processing_start = None
        
        await self.push_frame(frame, direction)
    
    def _select_filler(self, processing_ms: int) -> Optional[bytes]:
        if processing_ms < 500:
            category = "acknowledgment_short"
        elif processing_ms < 1500:
            category = "acknowledgment_thinking"
        else:
            category = "acknowledgment_searching"
        
        return random.choice(self.fillers[category])
```

---

## 6. WebRTC Transport

### 6.1 Self-Hosted vs. Daily.co

| Option | Pros | Cons |
|--------|------|------|
| Daily.co | Managed TURN/STUN, global edge, easy setup | Cost ($), external dependency |
| Self-hosted (mediasoup) | Free, full control | Complex setup, TURN server needed |
| Self-hosted (Janus) | Mature, many features | Complex, resource heavy |

**Recommendation:** Start with Daily.co free tier (10k minutes/month). Migrate to self-hosted mediasoup if cost becomes issue.

### 6.2 Connection Flow

```
Device                     Server                      Daily.co
   │                          │                            │
   │  1. Request room token   │                            │
   │─────────────────────────▶│                            │
   │                          │  2. Create room + token    │
   │                          │───────────────────────────▶│
   │                          │◀───────────────────────────│
   │◀─────────────────────────│                            │
   │  3. Join room (WebRTC)   │                            │
   │──────────────────────────┼───────────────────────────▶│
   │                          │  4. Bot joins same room    │
   │                          │───────────────────────────▶│
   │◀─────────────────────────┼────────────────────────────│
   │  5. Peer connection      │                            │
   │  6. Audio streams        │                            │
```

### 6.3 Room Management

```python
from daily import Daily, CallClient

class RoomManager:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.active_rooms: Dict[str, Room] = {}
    
    async def create_room_for_device(self, device_id: str) -> RoomInfo:
        """Create or get existing room for device."""
        
        if device_id in self.active_rooms:
            room = self.active_rooms[device_id]
            if room.is_active:
                return room.info
        
        # Create new room
        room_config = {
            "properties": {
                "exp": int(time.time()) + 3600,  # 1 hour
                "enable_chat": False,
                "enable_screenshare": False,
                "max_participants": 2,
            }
        }
        
        response = await self._create_room(room_config)
        
        room = Room(
            room_url=response["url"],
            token=response["token"],
            device_id=device_id,
        )
        
        self.active_rooms[device_id] = room
        
        return room.info
    
    async def close_room(self, device_id: str):
        """Close room when device disconnects."""
        if device_id in self.active_rooms:
            room = self.active_rooms.pop(device_id)
            await room.close()
```

---

## 7. Device-Specific Handling

### 7.1 Device Capabilities Matrix

| Device | Transport | Wake Word | Input | Output |
|--------|-----------|-----------|-------|--------|
| Android Phone | WebRTC (native) | Local | Mic | Speaker/Earpiece |
| Lenovo Tablet | WebRTC (browser) | Server-side | Mic | Speaker |
| Even Glasses | BLE → Bridge | Server-side | Mic | Bone conduction |
| Desktop | WebRTC (browser) | Server-side | Mic | Speaker |

### 7.2 Phone Native App

**Requirements:**
- Local wake word detection (battery efficiency)
- Push-to-talk fallback option
- Background listening mode
- Proximity sensor to switch earpiece/speaker

**Architecture:**
```
┌─────────────────────────────────────────┐
│           ANDROID APP                    │
│                                          │
│  ┌──────────────────────────────────┐   │
│  │  Local Wake Word (openWakeWord)  │   │
│  │  Always listening (low power)    │   │
│  └────────────────┬─────────────────┘   │
│                   │ Wake detected        │
│                   ▼                      │
│  ┌──────────────────────────────────┐   │
│  │  WebRTC Connection to Server     │   │
│  │  Stream audio bi-directionally   │   │
│  └──────────────────────────────────┘   │
│                                          │
└─────────────────────────────────────────┘
```

### 7.3 Even Realities Glasses

**Constraint:** BLE audio only, limited bandwidth

**Architecture:**
```
Glasses ──BLE──▶ Phone App ──WebRTC──▶ Server
                    │
                    └─▶ Local wake word
```

**Special handling:**
- Whisper TTS mode (lower volume, conversational tone)
- HUD text fallback for noisy environments
- Shorter response preference

### 7.4 Lenovo Smart Displays (ViewAssist)

**Architecture:**
- Custom web app with WebRTC
- Server-side wake word (device always connected)
- Visual feedback on display

```javascript
// ViewAssist web app (simplified)
class BarnabeeClient {
    constructor(serverUrl) {
        this.serverUrl = serverUrl;
        this.peerConnection = null;
        this.audioContext = null;
    }
    
    async connect() {
        // Get room info
        const room = await fetch(`${this.serverUrl}/room`, {
            method: 'POST',
            body: JSON.stringify({ device_id: this.deviceId })
        }).then(r => r.json());
        
        // Join Daily room
        this.callClient = Daily.createCallObject();
        await this.callClient.join({ url: room.url, token: room.token });
        
        // Set up audio tracks
        this.callClient.on('track-started', this.handleTrack.bind(this));
    }
    
    handleTrack(event) {
        if (event.track.kind === 'audio' && !event.participant.local) {
            // Barnabee's audio output
            const audio = new Audio();
            audio.srcObject = new MediaStream([event.track]);
            audio.play();
        }
    }
}
```

---

## 8. Audio Processing Details

### 8.1 Audio Format Standards

| Stage | Format | Sample Rate | Channels | Bit Depth |
|-------|--------|-------------|----------|-----------|
| WebRTC input | Opus | 48kHz | 1 (mono) | 16-bit |
| After decode | PCM | 16kHz | 1 | 16-bit |
| STT input | PCM | 16kHz | 1 | 16-bit |
| TTS output | PCM | 24kHz | 1 | 16-bit |
| WebRTC output | Opus | 48kHz | 1 | 16-bit |

### 8.2 Resampling

```python
import librosa
import numpy as np

def resample_audio(audio: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
    """Resample audio to target sample rate."""
    if orig_sr == target_sr:
        return audio
    return librosa.resample(audio, orig_sr=orig_sr, target_sr=target_sr)

# WebRTC (48kHz) → STT (16kHz)
stt_audio = resample_audio(webrtc_audio, 48000, 16000)

# TTS (24kHz) → WebRTC (48kHz)
webrtc_audio = resample_audio(tts_audio, 24000, 48000)
```

### 8.3 Acoustic Echo Cancellation

WebRTC handles AEC automatically when:
1. Both input and output use same audio device
2. Audio tracks are properly associated in peer connection

**Fallback for non-WebRTC paths:**
```python
# Use speexdsp for software AEC
from speexdsp import EchoCanceller

aec = EchoCanceller.create(
    frame_size=256,       # 16ms at 16kHz
    filter_length=2048,   # 128ms echo tail
    sample_rate=16000
)

def process_with_aec(mic_audio: bytes, speaker_audio: bytes) -> bytes:
    """Remove speaker echo from mic audio."""
    return aec.process(mic_audio, speaker_audio)
```

---

## 9. Error Handling & Fallbacks

### 9.1 Failure Modes

| Failure | Detection | Fallback |
|---------|-----------|----------|
| STT timeout | >2s no result | Retry once, then "I didn't catch that" |
| STT confidence low | <0.5 confidence | Ask for clarification |
| TTS failure | Exception | Pre-recorded error message |
| WebRTC disconnect | ICE failure | Reconnect, notify user |
| Wake word false positive | User doesn't speak after | Auto-cancel after 5s silence |
| GPU overload | CUDA OOM | Queue requests, notify if backlog |

### 9.2 Graceful Degradation

```python
class VoicePipelineWithFallback:
    def __init__(self):
        self.primary_stt = ParakeetSTT()
        self.fallback_stt = WhisperSTT()  # Slower but more robust
        self.stt_failures = 0
    
    async def transcribe(self, audio: bytes) -> str:
        try:
            result = await asyncio.wait_for(
                self.primary_stt.transcribe(audio),
                timeout=2.0
            )
            self.stt_failures = 0
            return result
        
        except (asyncio.TimeoutError, STTError) as e:
            self.stt_failures += 1
            logger.warning(f"Primary STT failed: {e}")
            
            if self.stt_failures >= 3:
                logger.error("Primary STT repeated failures, using fallback")
                return await self.fallback_stt.transcribe(audio)
            
            # Single failure: retry primary
            return await self.primary_stt.transcribe(audio)
```

### 9.3 Health Monitoring

```python
@dataclass
class VoicePipelineHealth:
    stt_latency_p50_ms: float
    stt_latency_p95_ms: float
    tts_latency_p50_ms: float
    tts_latency_p95_ms: float
    wake_word_false_positives_per_hour: float
    wake_word_false_negatives_percent: float
    barge_in_success_rate: float
    webrtc_connection_success_rate: float

async def check_health() -> VoicePipelineHealth:
    # Collect metrics from last hour
    metrics = await get_pipeline_metrics(hours=1)
    
    return VoicePipelineHealth(
        stt_latency_p50_ms=np.percentile(metrics.stt_latencies, 50),
        stt_latency_p95_ms=np.percentile(metrics.stt_latencies, 95),
        # ... etc
    )
```

---

## 10. File Structure

```
barnabeenet-v2/
├── src/
│   └── barnabee/
│       └── voice/
│           ├── __init__.py
│           ├── config.py              # PipelineConfig dataclass
│           ├── pipeline.py            # BarnabeeVoicePipeline
│           ├── processors/
│           │   ├── __init__.py
│           │   ├── smart_turn.py      # SmartTurnDetector
│           │   ├── filler.py          # FillerInjector
│           │   ├── barge_in.py        # BargeInDetector
│           │   └── wake_word.py       # Wake word processor
│           ├── services/
│           │   ├── __init__.py
│           │   ├── stt.py             # ParakeetSTTService
│           │   ├── tts.py             # KokoroTTSService
│           │   └── vad.py             # SileroVADService
│           ├── transport/
│           │   ├── __init__.py
│           │   ├── webrtc.py          # Daily/WebRTC handling
│           │   ├── websocket.py       # WebSocket fallback
│           │   └── room_manager.py    # Room lifecycle
│           └── audio/
│               ├── __init__.py
│               ├── resampling.py      # Audio format conversion
│               └── aec.py             # Echo cancellation fallback
├── models/
│   ├── barnabee_wake.onnx             # Wake word model
│   └── kokoro_barnabee.onnx           # TTS voice model
├── fillers/
│   ├── acknowledgment_short/
│   ├── acknowledgment_thinking/
│   └── acknowledgment_searching/
└── scripts/
    ├── train_wake_word.py
    ├── train_tts_voice.py
    └── generate_fillers.py
```

---

## 11. Implementation Checklist

### Core Pipeline

- [ ] Pipecat integration and basic pipeline
- [ ] Daily.co WebRTC transport
- [ ] WebSocket fallback transport
- [ ] Room management (create, join, close)

### Wake Word

- [ ] openWakeWord integration
- [ ] Training data collection (synthetic + real)
- [ ] Model training pipeline
- [ ] False positive/negative tuning

### STT

- [ ] Parakeet model setup on GPU
- [ ] Streaming transcription
- [ ] Confidence scoring
- [ ] Fallback to Whisper

### TTS

- [ ] Kokoro model setup on GPU
- [ ] Custom voice training
- [ ] Streaming synthesis
- [ ] Filler audio generation

### Turn Detection

- [ ] Silero VAD integration
- [ ] SmartTurn semantic completion
- [ ] Completion scorer (heuristics + model)

### Barge-In

- [ ] Barge-in detection during TTS
- [ ] TTS cancellation
- [ ] AEC verification

### Device Support

- [ ] Android native app WebRTC
- [ ] Lenovo web app WebRTC
- [ ] Even glasses BLE bridge
- [ ] Desktop browser WebRTC

### Validation

- [ ] Latency benchmarks (<500ms end-to-end)
- [ ] Wake word accuracy (FP <0.5/hr, FN <2%)
- [ ] STT accuracy (>95%)
- [ ] Barge-in success rate (>90%)

### Acceptance Criteria

1. **End-to-end latency <500ms** for fast-path commands
2. **Wake word false positive <0.5/hour** in typical home environment
3. **STT accuracy >95%** on family member speech
4. **Barge-in works reliably** without echo false triggers
5. **All device types connected** and streaming audio

---

## 12. Handoff Notes for Implementation Agent

### Critical Points

1. **Pipecat is the foundation.** Don't reinvent the wheel. Use their frame processing model.

2. **WebRTC AEC is essential.** Without it, barge-in will constantly false-trigger on Barnabee's own voice.

3. **Parakeet requires CUDA.** Verify GPU memory before loading. It needs ~4GB.

4. **Streaming is non-negotiable.** Batch STT/TTS adds 500ms+ latency. Always stream.

5. **Filler injection timing is tricky.** Too early sounds robotic. Too late is useless. Target 300ms.

6. **Test with real noise.** Kitchen sounds, TV, kids yelling. Lab silence is not reality.

### Common Pitfalls

- Forgetting to resample between WebRTC (48kHz) and STT (16kHz)
- Not handling WebRTC ICE failures (network changes)
- Blocking the audio processing thread with sync operations
- Wake word triggering on TV/radio saying "Barnabee" (add speaker verification later)
- TTS sounding robotic at sentence boundaries (use Pipecat's SentenceAggregator)

### Performance Tuning

- Use CUDA streams for parallel STT/TTS on GPU
- Pre-warm models on startup (first inference is slow)
- Keep WebRTC connections alive (reconnection is expensive)
- Buffer 100ms of audio before STT to avoid cutting off starts

---

**End of Area 02: Voice Pipeline**
