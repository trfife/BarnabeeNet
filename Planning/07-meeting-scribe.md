# Area 07: Meeting/Scribe System

**Version:** 1.0  
**Status:** Implementation Ready  
**Dependencies:** Areas 01-02 (Data Layer, Voice Pipeline)  
**Phase:** Extended Functionality  

---

## 1. Overview

### 1.1 Purpose

The Meeting/Scribe System transforms Barnabee from a command-response assistant into a persistent listener that captures, transcribes, summarizes, and extracts actionable items from meetings and notes sessions.

### 1.2 Capabilities

| Mode | Trigger | Output |
|------|---------|--------|
| Meeting Notes | "Start taking notes" | Transcript + summary + action items |
| Journal | "Journal mode" | Personal reflection with prompts |
| Dictation | "Take a note" | Single memory entry |
| Voice Memo | "Record a voice memo" | Audio file + transcript |

### 1.3 Design Principles

1. **Privacy-first:** Meetings are explicitly started, never ambient.
2. **Speaker awareness:** Diarize who said what.
3. **Actionable output:** Don't just transcribe—extract decisions and todos.
4. **Searchable:** All content feeds into memory system.
5. **Non-intrusive:** Minimal interruptions during capture.

### 1.4 Not In Scope (V2)

- Real-time translation
- Video/screen recording
- External meeting platform integration (Zoom, Teams)
- Multi-room meeting bridging

---

## 2. Architecture

### 2.1 System Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        MEETING/SCRIBE SYSTEM                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  TRIGGER                                                                     │
│  ═══════                                                                     │
│  "Start taking notes" / "Journal mode" / "Record meeting"                   │
│                     │                                                        │
│                     ▼                                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    SESSION MANAGER                                   │   │
│  │                                                                      │   │
│  │  • Creates meeting/journal record                                   │   │
│  │  • Initializes speaker profiles                                     │   │
│  │  • Configures audio pipeline for continuous capture                 │   │
│  │  • Sets up segment buffer                                           │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                     │                                                        │
│                     ▼                                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    CONTINUOUS CAPTURE                                │   │
│  │                                                                      │   │
│  │  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐             │   │
│  │  │ Audio Input │───▶│     VAD     │───▶│  Chunking   │             │   │
│  │  │ (WebRTC)    │    │  (Silero)   │    │ (30s max)   │             │   │
│  │  └─────────────┘    └─────────────┘    └──────┬──────┘             │   │
│  │                                               │                     │   │
│  │                                               ▼                     │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │                    PROCESSING PIPELINE                       │   │   │
│  │  │                                                              │   │   │
│  │  │  Audio Chunk ──▶ STT ──▶ Diarization ──▶ Segment Storage    │   │   │
│  │  │                   │                          │               │   │   │
│  │  │                   └──────────────────────────┘               │   │   │
│  │  │                              │                               │   │   │
│  │  │                              ▼                               │   │   │
│  │  │              ┌─────────────────────────────────┐            │   │   │
│  │  │              │  transcript_segments table      │            │   │   │
│  │  │              │  meeting_id, speaker, text, ts  │            │   │   │
│  │  │              └─────────────────────────────────┘            │   │   │
│  │  └──────────────────────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                     │                                                        │
│                     │ "Stop notes" / Timeout                                │
│                     ▼                                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    POST-PROCESSING                                   │   │
│  │                                                                      │   │
│  │  1. Assemble full transcript from segments                          │   │
│  │  2. Generate summary (LLM)                                          │   │
│  │  3. Extract action items (LLM)                                      │   │
│  │  4. Extract decisions/facts (LLM)                                   │   │
│  │  5. Create memories from extractables                               │   │
│  │  6. Create todos from action items                                  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                     │                                                        │
│                     ▼                                                        │
│  OUTPUT                                                                      │
│  ══════                                                                      │
│  • Full transcript (searchable)                                             │
│  • Summary (3-5 sentences)                                                  │
│  • Action items → Todos                                                     │
│  • Key decisions → Memories                                                 │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Data Model

```
┌─────────────────┐       ┌──────────────────────┐
│    meetings     │       │  transcript_segments │
├─────────────────┤       ├──────────────────────┤
│ id              │──────▶│ meeting_id           │
│ title           │       │ segment_index        │
│ started_at      │       │ speaker_id           │
│ ended_at        │       │ speaker_label        │
│ status          │       │ text                 │
│ meeting_type    │       │ start_time           │
│ location        │       │ end_time             │
│ initiated_by    │       │ confidence           │
│ transcript_text │       │ audio_path           │
│ summary         │       └──────────────────────┘
│ metadata        │
└────────┬────────┘
         │
         │       ┌──────────────────────┐
         │       │   meeting_speakers   │
         ├──────▶├──────────────────────┤
         │       │ meeting_id           │
         │       │ speaker_label        │
         │       │ speaker_id (nullable)│
         │       │ voice_embedding      │
         │       │ segment_count        │
         │       └──────────────────────┘
         │
         │       ┌──────────────────────┐
         │       │    action_items      │
         └──────▶├──────────────────────┤
                 │ id                   │
                 │ meeting_id           │
                 │ description          │
                 │ assignee             │
                 │ due_date             │
                 │ todo_id (if created) │
                 │ status               │
                 └──────────────────────┘
```

---

## 3. Session Management

### 3.1 Session Types

```python
class MeetingType(Enum):
    MEETING = "meeting"      # Multi-speaker, formal
    NOTES = "notes"          # General note-taking
    JOURNAL = "journal"      # Personal reflection
    DICTATION = "dictation"  # Single note capture
    VOICE_MEMO = "voice_memo"  # Audio + transcript


@dataclass
class MeetingSession:
    id: str
    meeting_type: MeetingType
    title: Optional[str]
    started_at: datetime
    ended_at: Optional[datetime]
    status: str  # "active", "completed", "cancelled"
    initiated_by: str
    location: Optional[str]  # Room/area
    
    # Accumulated during session
    segments: List['TranscriptSegment'] = field(default_factory=list)
    speakers: Dict[str, 'SpeakerProfile'] = field(default_factory=dict)
    
    # Generated after session
    transcript_text: Optional[str] = None
    summary: Optional[str] = None
    action_items: List['ActionItem'] = field(default_factory=list)
    extracted_memories: List[str] = field(default_factory=list)
```

### 3.2 Session Manager

```python
class MeetingSessionManager:
    """Manage meeting/notes sessions."""
    
    def __init__(
        self,
        db: Database,
        capture_pipeline: 'ContinuousCapturePipeline',
        post_processor: 'MeetingPostProcessor',
    ):
        self.db = db
        self.capture = capture_pipeline
        self.post_processor = post_processor
        self.active_sessions: Dict[str, MeetingSession] = {}
    
    async def start_session(
        self,
        meeting_type: MeetingType,
        initiated_by: str,
        title: Optional[str] = None,
        location: Optional[str] = None,
    ) -> MeetingSession:
        """Start a new meeting/notes session."""
        
        # Check for existing active session
        existing = await self._get_active_session()
        if existing:
            raise SessionConflictError(
                f"Already recording: {existing.title or existing.meeting_type.value}"
            )
        
        # Create session
        session = MeetingSession(
            id=generate_uuid(),
            meeting_type=meeting_type,
            title=title or self._generate_title(meeting_type),
            started_at=datetime.utcnow(),
            ended_at=None,
            status="active",
            initiated_by=initiated_by,
            location=location,
        )
        
        # Persist
        await self._save_session(session)
        
        # Start capture pipeline
        await self.capture.start(
            session_id=session.id,
            on_segment=self._handle_segment,
        )
        
        self.active_sessions[session.id] = session
        
        return session
    
    async def end_session(
        self,
        session_id: Optional[str] = None,
    ) -> MeetingSession:
        """End the active session and trigger post-processing."""
        
        # Get session
        if session_id:
            session = self.active_sessions.get(session_id)
        else:
            session = await self._get_active_session()
        
        if not session:
            raise NoActiveSessionError("No active recording session")
        
        # Stop capture
        await self.capture.stop(session.id)
        
        # Update session
        session.ended_at = datetime.utcnow()
        session.status = "processing"
        await self._save_session(session)
        
        # Trigger post-processing
        asyncio.create_task(self._process_session(session))
        
        del self.active_sessions[session.id]
        
        return session
    
    async def _handle_segment(
        self,
        session_id: str,
        segment: 'TranscriptSegment',
    ):
        """Handle incoming transcript segment."""
        session = self.active_sessions.get(session_id)
        if not session:
            return
        
        # Add to session
        session.segments.append(segment)
        
        # Update speaker tracking
        if segment.speaker_label not in session.speakers:
            session.speakers[segment.speaker_label] = SpeakerProfile(
                label=segment.speaker_label,
                segment_count=0,
            )
        session.speakers[segment.speaker_label].segment_count += 1
        
        # Persist segment
        await self._save_segment(session_id, segment)
    
    async def _process_session(self, session: MeetingSession):
        """Run post-processing on completed session."""
        try:
            result = await self.post_processor.process(session)
            
            session.transcript_text = result.transcript
            session.summary = result.summary
            session.action_items = result.action_items
            session.extracted_memories = result.memory_ids
            session.status = "completed"
            
        except Exception as e:
            logger.error(f"Post-processing failed: {e}")
            session.status = "error"
        
        await self._save_session(session)
    
    def _generate_title(self, meeting_type: MeetingType) -> str:
        """Generate default title."""
        now = datetime.now()
        date_str = now.strftime("%B %d")
        time_str = now.strftime("%-I:%M %p")
        
        titles = {
            MeetingType.MEETING: f"Meeting - {date_str}",
            MeetingType.NOTES: f"Notes - {date_str} {time_str}",
            MeetingType.JOURNAL: f"Journal - {date_str}",
            MeetingType.DICTATION: f"Note - {date_str} {time_str}",
            MeetingType.VOICE_MEMO: f"Voice Memo - {date_str} {time_str}",
        }
        return titles.get(meeting_type, f"Recording - {date_str}")
```

---

## 4. Continuous Capture Pipeline

### 4.1 Audio Capture

```python
class ContinuousCapturePipeline:
    """Continuous audio capture with STT and diarization."""
    
    def __init__(
        self,
        stt_service: 'STTService',
        diarizer: 'SpeakerDiarizer',
        vad: 'VADService',
    ):
        self.stt = stt_service
        self.diarizer = diarizer
        self.vad = vad
        
        self.active_captures: Dict[str, 'CaptureState'] = {}
        
        # Configuration
        self.CHUNK_DURATION_S = 30  # Max segment duration
        self.MIN_CHUNK_DURATION_S = 2  # Min segment duration
        self.SILENCE_THRESHOLD_S = 1.5  # Split on silence
    
    async def start(
        self,
        session_id: str,
        on_segment: Callable,
    ):
        """Start continuous capture for a session."""
        state = CaptureState(
            session_id=session_id,
            on_segment=on_segment,
            audio_buffer=AudioBuffer(),
            segment_index=0,
            start_time=datetime.utcnow(),
        )
        
        self.active_captures[session_id] = state
        
        # Start processing loop
        asyncio.create_task(self._capture_loop(state))
    
    async def stop(self, session_id: str):
        """Stop capture and process remaining audio."""
        state = self.active_captures.get(session_id)
        if not state:
            return
        
        state.is_stopping = True
        
        # Process remaining audio
        if state.audio_buffer.duration_s > self.MIN_CHUNK_DURATION_S:
            await self._process_chunk(state, is_final=True)
        
        del self.active_captures[session_id]
    
    async def add_audio(self, session_id: str, audio: bytes):
        """Add audio data to capture buffer."""
        state = self.active_captures.get(session_id)
        if not state or state.is_stopping:
            return
        
        state.audio_buffer.append(audio)
    
    async def _capture_loop(self, state: 'CaptureState'):
        """Main capture processing loop."""
        while state.session_id in self.active_captures and not state.is_stopping:
            # Check for chunk boundary conditions
            should_process = (
                state.audio_buffer.duration_s >= self.CHUNK_DURATION_S or
                await self._detect_natural_break(state)
            )
            
            if should_process and state.audio_buffer.duration_s >= self.MIN_CHUNK_DURATION_S:
                await self._process_chunk(state)
            
            await asyncio.sleep(0.1)  # Check every 100ms
    
    async def _detect_natural_break(self, state: 'CaptureState') -> bool:
        """Detect natural speech break for chunking."""
        if state.audio_buffer.duration_s < self.MIN_CHUNK_DURATION_S:
            return False
        
        # Check for sustained silence at end of buffer
        recent_audio = state.audio_buffer.get_recent(self.SILENCE_THRESHOLD_S)
        is_silence = await self.vad.is_silence(recent_audio)
        
        return is_silence
    
    async def _process_chunk(self, state: 'CaptureState', is_final: bool = False):
        """Process an audio chunk into transcript segment."""
        # Get audio
        audio = state.audio_buffer.consume()
        
        if len(audio) == 0:
            return
        
        # Timestamps
        chunk_start = state.last_chunk_end or state.start_time
        chunk_end = datetime.utcnow()
        state.last_chunk_end = chunk_end
        
        # STT
        transcript = await self.stt.transcribe(audio)
        
        if not transcript or not transcript.strip():
            return
        
        # Diarization
        speaker_label = await self.diarizer.identify_speaker(
            audio=audio,
            session_id=state.session_id,
        )
        
        # Create segment
        segment = TranscriptSegment(
            segment_index=state.segment_index,
            speaker_label=speaker_label,
            text=transcript,
            start_time=chunk_start,
            end_time=chunk_end,
            confidence=0.9,  # From STT
        )
        
        state.segment_index += 1
        
        # Callback
        await state.on_segment(state.session_id, segment)


@dataclass
class CaptureState:
    session_id: str
    on_segment: Callable
    audio_buffer: 'AudioBuffer'
    segment_index: int
    start_time: datetime
    last_chunk_end: Optional[datetime] = None
    is_stopping: bool = False


@dataclass
class TranscriptSegment:
    segment_index: int
    speaker_label: str  # "Speaker 1", "Thom", etc.
    text: str
    start_time: datetime
    end_time: datetime
    confidence: float
    speaker_id: Optional[str] = None  # Resolved family member ID
```

---

## 5. Speaker Diarization

### 5.1 Diarization Strategy

```python
class SpeakerDiarizer:
    """
    Identify and track speakers in meeting audio.
    
    Strategy:
    1. Cluster audio segments by voice embedding similarity
    2. Match clusters to known family members (if enrolled)
    3. Label unknown speakers as "Speaker 1", "Speaker 2", etc.
    """
    
    def __init__(
        self,
        embedding_model: 'SpeakerEmbeddingModel',
        speaker_db: 'SpeakerDatabase',
    ):
        self.embedding_model = embedding_model
        self.speaker_db = speaker_db
        
        # Per-session speaker tracking
        self.session_speakers: Dict[str, Dict[str, np.ndarray]] = {}
        self.SIMILARITY_THRESHOLD = 0.75
    
    async def identify_speaker(
        self,
        audio: bytes,
        session_id: str,
    ) -> str:
        """Identify speaker from audio segment."""
        
        # Generate voice embedding
        embedding = await self.embedding_model.embed(audio)
        
        # Initialize session tracking
        if session_id not in self.session_speakers:
            self.session_speakers[session_id] = {}
        
        session = self.session_speakers[session_id]
        
        # Try to match known family member
        known_match = await self._match_known_speaker(embedding)
        if known_match:
            # Update session tracking with known speaker
            session[known_match] = self._update_embedding(
                session.get(known_match),
                embedding
            )
            return known_match
        
        # Try to match within session
        session_match = self._match_session_speaker(session, embedding)
        if session_match:
            session[session_match] = self._update_embedding(
                session[session_match],
                embedding
            )
            return session_match
        
        # New speaker
        speaker_num = len(session) + 1
        label = f"Speaker {speaker_num}"
        session[label] = embedding
        
        return label
    
    async def _match_known_speaker(
        self,
        embedding: np.ndarray,
    ) -> Optional[str]:
        """Match embedding against enrolled family members."""
        family_embeddings = await self.speaker_db.get_family_embeddings()
        
        best_match = None
        best_similarity = self.SIMILARITY_THRESHOLD
        
        for name, known_embedding in family_embeddings.items():
            similarity = self._cosine_similarity(embedding, known_embedding)
            if similarity > best_similarity:
                best_similarity = similarity
                best_match = name
        
        return best_match
    
    def _match_session_speaker(
        self,
        session: Dict[str, np.ndarray],
        embedding: np.ndarray,
    ) -> Optional[str]:
        """Match embedding against speakers seen in this session."""
        best_match = None
        best_similarity = self.SIMILARITY_THRESHOLD
        
        for label, known_embedding in session.items():
            similarity = self._cosine_similarity(embedding, known_embedding)
            if similarity > best_similarity:
                best_similarity = similarity
                best_match = label
        
        return best_match
    
    def _update_embedding(
        self,
        existing: Optional[np.ndarray],
        new: np.ndarray,
    ) -> np.ndarray:
        """Update speaker embedding with new sample (rolling average)."""
        if existing is None:
            return new
        
        # Weighted average favoring recent
        return 0.7 * existing + 0.3 * new
    
    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
    
    def clear_session(self, session_id: str):
        """Clear session speaker data."""
        self.session_speakers.pop(session_id, None)


class SpeakerEmbeddingModel:
    """Generate speaker embeddings from audio."""
    
    def __init__(self, model_path: str):
        # Use speechbrain or resemblyzer for speaker embeddings
        from speechbrain.pretrained import EncoderClassifier
        
        self.model = EncoderClassifier.from_hparams(
            source=model_path,
            run_opts={"device": "cuda"}
        )
    
    async def embed(self, audio: bytes) -> np.ndarray:
        """Generate embedding from audio."""
        # Convert bytes to tensor
        waveform = self._bytes_to_waveform(audio)
        
        # Get embedding
        loop = asyncio.get_event_loop()
        embedding = await loop.run_in_executor(
            None,
            lambda: self.model.encode_batch(waveform)
        )
        
        return embedding.squeeze().numpy()
    
    def _bytes_to_waveform(self, audio: bytes):
        import torch
        import numpy as np
        
        # Assuming 16-bit PCM at 16kHz
        samples = np.frombuffer(audio, dtype=np.int16).astype(np.float32)
        samples = samples / 32768.0  # Normalize
        return torch.tensor(samples).unsqueeze(0)
```

### 5.2 Voice Enrollment

```python
class VoiceEnrollment:
    """Enroll family members for speaker recognition."""
    
    MIN_SAMPLES = 3
    MIN_SAMPLE_DURATION_S = 5
    
    def __init__(
        self,
        embedding_model: SpeakerEmbeddingModel,
        speaker_db: 'SpeakerDatabase',
    ):
        self.embedding_model = embedding_model
        self.speaker_db = speaker_db
        self.enrollment_sessions: Dict[str, List[np.ndarray]] = {}
    
    async def start_enrollment(self, speaker_id: str) -> str:
        """Start enrollment session."""
        self.enrollment_sessions[speaker_id] = []
        return (
            f"Okay, I'll learn your voice. Please say a few sentences, "
            f"pausing between each. I need at least {self.MIN_SAMPLES} samples."
        )
    
    async def add_sample(
        self,
        speaker_id: str,
        audio: bytes,
    ) -> Tuple[bool, str]:
        """Add voice sample to enrollment."""
        if speaker_id not in self.enrollment_sessions:
            return False, "No active enrollment. Say 'enroll my voice' to start."
        
        # Check duration
        duration_s = len(audio) / 16000 / 2  # 16kHz, 16-bit
        if duration_s < self.MIN_SAMPLE_DURATION_S:
            return False, f"Sample too short. Please speak for at least {self.MIN_SAMPLE_DURATION_S} seconds."
        
        # Generate embedding
        embedding = await self.embedding_model.embed(audio)
        
        self.enrollment_sessions[speaker_id].append(embedding)
        
        samples_count = len(self.enrollment_sessions[speaker_id])
        
        if samples_count >= self.MIN_SAMPLES:
            return True, f"Got {samples_count} samples. Say 'done' to finish enrollment, or keep going for better accuracy."
        
        return True, f"Got it! {samples_count} of {self.MIN_SAMPLES} samples. Keep going."
    
    async def complete_enrollment(self, speaker_id: str) -> str:
        """Complete enrollment and save voice profile."""
        samples = self.enrollment_sessions.get(speaker_id, [])
        
        if len(samples) < self.MIN_SAMPLES:
            return f"Not enough samples. I need at least {self.MIN_SAMPLES}, you have {len(samples)}."
        
        # Average embeddings
        avg_embedding = np.mean(samples, axis=0)
        
        # Save
        await self.speaker_db.save_speaker_embedding(speaker_id, avg_embedding)
        
        # Clean up
        del self.enrollment_sessions[speaker_id]
        
        return f"Done! I'll now recognize your voice in meetings."
```

---

## 6. Post-Processing

### 6.1 Post-Processor

```python
@dataclass
class PostProcessingResult:
    transcript: str
    summary: str
    action_items: List['ActionItem']
    decisions: List[str]
    memory_ids: List[str]


class MeetingPostProcessor:
    """Post-process completed meeting sessions."""
    
    def __init__(
        self,
        llm_client: LLMClient,
        memory_creator: 'MemoryCreator',
        todo_manager: 'TodoManager',
    ):
        self.llm = llm_client
        self.memory = memory_creator
        self.todo = todo_manager
    
    async def process(self, session: MeetingSession) -> PostProcessingResult:
        """Run full post-processing pipeline."""
        
        # 1. Assemble transcript
        transcript = self._assemble_transcript(session.segments)
        
        # 2. Generate summary
        summary = await self._generate_summary(transcript, session.meeting_type)
        
        # 3. Extract action items
        action_items = await self._extract_action_items(transcript)
        
        # 4. Extract decisions
        decisions = await self._extract_decisions(transcript)
        
        # 5. Create memories
        memory_ids = await self._create_memories(
            session=session,
            summary=summary,
            decisions=decisions,
        )
        
        # 6. Create todos from action items
        for item in action_items:
            todo = await self.todo.create(
                title=item.description,
                source_type="meeting",
                source_id=session.id,
                assignee=item.assignee,
                due_date=item.due_date,
            )
            item.todo_id = todo.id
        
        return PostProcessingResult(
            transcript=transcript,
            summary=summary,
            action_items=action_items,
            decisions=decisions,
            memory_ids=memory_ids,
        )
    
    def _assemble_transcript(self, segments: List[TranscriptSegment]) -> str:
        """Assemble segments into formatted transcript."""
        lines = []
        current_speaker = None
        
        for segment in sorted(segments, key=lambda s: s.start_time):
            if segment.speaker_label != current_speaker:
                current_speaker = segment.speaker_label
                lines.append(f"\n{current_speaker}:")
            
            lines.append(segment.text)
        
        return "\n".join(lines)
    
    async def _generate_summary(
        self,
        transcript: str,
        meeting_type: MeetingType,
    ) -> str:
        """Generate meeting summary."""
        
        prompts = {
            MeetingType.MEETING: """Summarize this meeting in 3-5 sentences. Focus on:
- Main topics discussed
- Key decisions made
- Important outcomes

Meeting transcript:
{transcript}

Summary:""",
            
            MeetingType.JOURNAL: """Summarize this journal entry in 2-3 sentences, capturing the main thoughts and feelings expressed.

Entry:
{transcript}

Summary:""",
            
            MeetingType.NOTES: """Summarize these notes in 3-5 sentences, capturing the key information.

Notes:
{transcript}

Summary:""",
        }
        
        prompt = prompts.get(meeting_type, prompts[MeetingType.NOTES])
        prompt = prompt.format(transcript=transcript[:4000])  # Truncate for token limit
        
        summary = await self.llm.complete(prompt, max_tokens=200)
        return summary.strip()
    
    async def _extract_action_items(
        self,
        transcript: str,
    ) -> List[ActionItem]:
        """Extract action items from transcript."""
        
        prompt = """Extract action items from this meeting transcript.

For each action item, identify:
- What needs to be done
- Who should do it (if mentioned)
- When it's due (if mentioned)

Transcript:
{transcript}

Return as JSON array:
[{{"description": "...", "assignee": "..." or null, "due_date": "..." or null}}]

If no action items, return empty array: []

Action items:"""

        prompt = prompt.format(transcript=transcript[:4000])
        
        response = await self.llm.complete(prompt, max_tokens=500)
        
        try:
            items_data = json.loads(response)
            return [
                ActionItem(
                    id=generate_uuid(),
                    description=item["description"],
                    assignee=item.get("assignee"),
                    due_date=self._parse_due_date(item.get("due_date")),
                    status="pending",
                )
                for item in items_data
            ]
        except json.JSONDecodeError:
            return []
    
    async def _extract_decisions(self, transcript: str) -> List[str]:
        """Extract key decisions from transcript."""
        
        prompt = """Extract key decisions made in this meeting.

A decision is when the group agreed on something, chose an option, or committed to a course of action.

Transcript:
{transcript}

List each decision as a clear statement. If no decisions, return "NONE".

Decisions:"""

        prompt = prompt.format(transcript=transcript[:4000])
        
        response = await self.llm.complete(prompt, max_tokens=300)
        
        if "NONE" in response.upper():
            return []
        
        # Parse bullet points or numbered list
        decisions = re.findall(r'[-•\d.]\s*(.+)', response)
        return decisions if decisions else [response.strip()]
    
    async def _create_memories(
        self,
        session: MeetingSession,
        summary: str,
        decisions: List[str],
    ) -> List[str]:
        """Create memories from meeting content."""
        memory_ids = []
        
        # Create summary memory
        summary_memory = await self.memory.create(
            summary=f"Meeting: {session.title}",
            content=summary,
            memory_type="meeting",
            source_type="meeting",
            source_id=session.id,
            owner=session.initiated_by,
        )
        memory_ids.append(summary_memory.id)
        
        # Create decision memories
        for decision in decisions:
            decision_memory = await self.memory.create(
                summary=decision[:100],
                content=decision,
                memory_type="decision",
                source_type="meeting",
                source_id=session.id,
                owner=session.initiated_by,
            )
            memory_ids.append(decision_memory.id)
        
        return memory_ids
    
    def _parse_due_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse due date from extracted text."""
        if not date_str:
            return None
        
        try:
            from dateutil import parser
            return parser.parse(date_str, fuzzy=True)
        except:
            return None


@dataclass
class ActionItem:
    id: str
    description: str
    assignee: Optional[str]
    due_date: Optional[datetime]
    status: str
    meeting_id: Optional[str] = None
    todo_id: Optional[str] = None
```

---

## 7. Journal Mode

### 7.1 Journal Session Handler

```python
class JournalSessionHandler:
    """Handle journal mode with guided prompts."""
    
    PROMPTS = [
        "How are you feeling right now?",
        "What's been on your mind today?",
        "What are you grateful for?",
        "What challenged you today?",
        "What's one thing you want to remember about today?",
    ]
    
    def __init__(
        self,
        session_manager: MeetingSessionManager,
        response_generator: 'ResponseGenerator',
    ):
        self.sessions = session_manager
        self.response = response_generator
        self.journal_state: Dict[str, 'JournalState'] = {}
    
    async def start_journal(
        self,
        speaker_id: str,
    ) -> Tuple[MeetingSession, str]:
        """Start journal session with opening prompt."""
        
        # Start recording session
        session = await self.sessions.start_session(
            meeting_type=MeetingType.JOURNAL,
            initiated_by=speaker_id,
        )
        
        # Initialize journal state
        self.journal_state[session.id] = JournalState(
            prompts_given=[],
            current_prompt_index=0,
        )
        
        # Opening
        opening = random.choice([
            "Journal mode started. Take your time.",
            "Ready when you are. What's on your mind?",
            "Journal mode. Speak freely.",
        ])
        
        return session, opening
    
    async def maybe_prompt(
        self,
        session_id: str,
        silence_duration_s: float,
    ) -> Optional[str]:
        """Maybe provide a prompt after silence."""
        state = self.journal_state.get(session_id)
        if not state:
            return None
        
        # Only prompt after 10+ seconds of silence
        if silence_duration_s < 10:
            return None
        
        # Only prompt a few times
        if len(state.prompts_given) >= 3:
            return None
        
        # Select prompt
        prompt = self.PROMPTS[state.current_prompt_index % len(self.PROMPTS)]
        state.current_prompt_index += 1
        state.prompts_given.append(prompt)
        
        return prompt
    
    async def end_journal(
        self,
        session_id: str,
    ) -> str:
        """End journal session."""
        await self.sessions.end_session(session_id)
        self.journal_state.pop(session_id, None)
        
        return "Journal saved. Take care."


@dataclass
class JournalState:
    prompts_given: List[str]
    current_prompt_index: int
```

---

## 8. Integration with Main Pipeline

### 8.1 Mode Switching

```python
class ModeController:
    """Control switching between command and meeting modes."""
    
    def __init__(
        self,
        session_manager: MeetingSessionManager,
        journal_handler: JournalSessionHandler,
    ):
        self.sessions = session_manager
        self.journal = journal_handler
        self.current_mode: Dict[str, str] = {}  # device_id → mode
    
    async def handle_mode_intent(
        self,
        intent: str,
        speaker_id: str,
        device_id: str,
    ) -> Tuple[str, str]:
        """
        Handle mode change intents.
        
        Returns: (mode, response)
        """
        
        if intent == "start_notes":
            session = await self.sessions.start_session(
                meeting_type=MeetingType.NOTES,
                initiated_by=speaker_id,
            )
            self.current_mode[device_id] = "notes"
            return "notes", "Taking notes. I'll listen until you say 'stop notes'."
        
        elif intent == "start_journal":
            session, response = await self.journal.start_journal(speaker_id)
            self.current_mode[device_id] = "journal"
            return "journal", response
        
        elif intent == "end_notes" or intent == "end_journal":
            session = await self.sessions.end_session()
            self.current_mode[device_id] = "command"
            return "command", "Notes saved. I'll summarize them in a moment."
        
        return self.current_mode.get(device_id, "command"), ""
    
    def get_mode(self, device_id: str) -> str:
        """Get current mode for device."""
        return self.current_mode.get(device_id, "command")
    
    def is_recording(self, device_id: str) -> bool:
        """Check if device is in a recording mode."""
        return self.current_mode.get(device_id) in ("notes", "journal", "meeting")
```

---

## 9. File Structure

```
barnabeenet-v2/
├── src/
│   └── barnabee/
│       └── meeting/
│           ├── __init__.py
│           ├── config.py               # Settings
│           ├── models.py               # MeetingSession, TranscriptSegment, etc.
│           ├── session_manager.py      # MeetingSessionManager
│           ├── capture/
│           │   ├── __init__.py
│           │   ├── pipeline.py         # ContinuousCapturePipeline
│           │   └── audio_buffer.py     # AudioBuffer
│           ├── diarization/
│           │   ├── __init__.py
│           │   ├── diarizer.py         # SpeakerDiarizer
│           │   ├── embedding.py        # SpeakerEmbeddingModel
│           │   └── enrollment.py       # VoiceEnrollment
│           ├── processing/
│           │   ├── __init__.py
│           │   ├── post_processor.py   # MeetingPostProcessor
│           │   └── extraction.py       # Action item, decision extraction
│           ├── journal.py              # JournalSessionHandler
│           └── mode_controller.py      # ModeController
└── tests/
    └── meeting/
        ├── test_session.py
        ├── test_capture.py
        ├── test_diarization.py
        └── test_processing.py
```

---

## 10. Implementation Checklist

### Session Management

- [ ] Session creation for all types
- [ ] Active session tracking
- [ ] Session persistence
- [ ] Proper cleanup on end

### Continuous Capture

- [ ] Audio buffer management
- [ ] VAD-based chunking
- [ ] Timeout handling
- [ ] Integration with voice pipeline

### Speaker Diarization

- [ ] Speaker embedding model
- [ ] Within-session clustering
- [ ] Family member matching
- [ ] Voice enrollment flow

### Post-Processing

- [ ] Transcript assembly
- [ ] Summary generation
- [ ] Action item extraction
- [ ] Decision extraction
- [ ] Memory creation
- [ ] Todo creation

### Journal Mode

- [ ] Journal session handler
- [ ] Guided prompts
- [ ] Silence detection for prompts

### Integration

- [ ] Mode controller
- [ ] Integration with main pipeline
- [ ] Mode-aware command handling

### Validation

- [ ] Transcription accuracy >90%
- [ ] Speaker diarization accuracy >80%
- [ ] Action item extraction precision >80%
- [ ] Post-processing completes in <30s

### Acceptance Criteria

1. **"Start taking notes" begins capture** and confirms
2. **Speaker changes are tracked** and labeled
3. **Family members are recognized** if enrolled
4. **"Stop notes" triggers post-processing** and creates summary
5. **Action items become searchable todos**
6. **Transcript is searchable via memory system**

---

## 11. Handoff Notes for Implementation Agent

### Critical Points

1. **Chunking is tricky.** Too short = fragmented transcript. Too long = delayed processing. Use VAD silence detection for natural breaks.

2. **Diarization is "good enough" not perfect.** Production systems achieve 80-85% accuracy. Don't over-optimize.

3. **Post-processing is async.** User shouldn't wait. Start processing in background, notify when done.

4. **Journal mode needs silence handling.** Silence isn't end-of-session in journal mode. Use longer timeout.

5. **Privacy is paramount.** Never start recording without explicit trigger. Clear indicators of recording state.

### Common Pitfalls

- Not handling audio dropout gracefully
- Over-segmenting on brief pauses (ruins speaker attribution)
- Trying to real-time process instead of chunking
- Not persisting segments (data loss on crash)
- Forgetting to clean up session state on error

### Performance Tuning

- Batch STT processing of chunks
- Pre-load speaker embedding model
- Cache family member embeddings at startup
- Use async for all I/O in post-processing

---

**End of Area 07: Meeting/Scribe System**
