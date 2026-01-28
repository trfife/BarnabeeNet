# Area 23: Implementation Additions & Gap Fills

**Version:** 1.0  
**Status:** Implementation Ready  
**Dependencies:** All Areas  
**Phase:** Parallel (all phases)  

---

## 1. Overview

This document addresses implementation gaps identified during final review, plus enhancements for multi-user concurrent sessions.

---

## 2. Concurrent Sessions & Multi-User Support

### 2.1 Problem Statement

Area 14 handles wake word arbitration (multiple devices hearing "Hey Barnabee" simultaneously), but doesn't address:

1. **Concurrent active sessions:** Thom talking to kitchen tablet while Elizabeth talks to living room tablet
2. **Session isolation:** Ensuring context, memories, and responses don't cross-contaminate
3. **GPU resource contention:** Two STT/TTS streams competing for VRAM

### 2.2 Session Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     CONCURRENT SESSION MANAGEMENT                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                  │
│  │ Kitchen      │    │ Living Room  │    │ Office       │                  │
│  │ Tablet       │    │ Tablet       │    │ Desktop      │                  │
│  │              │    │              │    │              │                  │
│  │ Session: A   │    │ Session: B   │    │ (Idle)       │                  │
│  │ Speaker: Thom│    │ Speaker: Liz │    │              │                  │
│  └──────┬───────┘    └──────┬───────┘    └──────────────┘                  │
│         │                   │                                               │
│         │ Audio Stream      │ Audio Stream                                  │
│         │                   │                                               │
│         ▼                   ▼                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    SESSION MANAGER                                   │   │
│  │                                                                      │   │
│  │  Active Sessions:                                                    │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │ Session A                    │ Session B                     │   │   │
│  │  │ ─────────                    │ ─────────                     │   │   │
│  │  │ device: kitchen_tablet       │ device: living_room_tablet    │   │   │
│  │  │ speaker: thom                │ speaker: elizabeth            │   │   │
│  │  │ mode: command                │ mode: conversation            │   │   │
│  │  │ context: [turn history]      │ context: [turn history]       │   │   │
│  │  │ started: 10:05:32            │ started: 10:05:45             │   │   │
│  │  └─────────────────────────────────────────────────────────────┘   │   │
│  │                                                                      │   │
│  │  Max Concurrent Sessions: 4                                         │   │
│  │  GPU Queue: Session A (processing) → Session B (queued)             │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    GPU SERVICE QUEUE                                 │   │
│  │                                                                      │   │
│  │  STT Queue:  [Session A chunk] → [Session B chunk] → ...            │   │
│  │  TTS Queue:  [Session B response] → [Session A response] → ...      │   │
│  │                                                                      │   │
│  │  Strategy: Round-robin with priority for shorter utterances         │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.3 Session Manager Implementation

```python
# src/barnabee/sessions/manager.py

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict
import asyncio
import uuid

MAX_CONCURRENT_SESSIONS = 4
SESSION_TIMEOUT_SECONDS = 300  # 5 minutes of inactivity

@dataclass
class Session:
    id: str
    device_id: str
    speaker_id: Optional[str]
    mode: str  # command, conversation, notes, journal
    started_at: datetime
    last_activity: datetime
    context: dict = field(default_factory=dict)
    turn_count: int = 0
    
    def is_expired(self) -> bool:
        return (datetime.utcnow() - self.last_activity).seconds > SESSION_TIMEOUT_SECONDS


class SessionManager:
    """Manages concurrent voice sessions across devices."""
    
    def __init__(self, redis, db):
        self.redis = redis
        self.db = db
        self.active_sessions: Dict[str, Session] = {}
        self._lock = asyncio.Lock()
    
    async def create_session(
        self,
        device_id: str,
        speaker_id: Optional[str] = None,
        mode: str = "command"
    ) -> Session:
        """Create a new session for a device."""
        async with self._lock:
            # Check for existing session on this device
            existing = self._get_session_by_device(device_id)
            if existing:
                # Device already has active session - reuse it
                existing.last_activity = datetime.utcnow()
                return existing
            
            # Check max concurrent sessions
            self._cleanup_expired()
            if len(self.active_sessions) >= MAX_CONCURRENT_SESSIONS:
                # Evict oldest session
                oldest = min(self.active_sessions.values(), key=lambda s: s.last_activity)
                await self.end_session(oldest.id, reason="evicted_for_new_session")
            
            # Create new session
            session = Session(
                id=str(uuid.uuid4()),
                device_id=device_id,
                speaker_id=speaker_id,
                mode=mode,
                started_at=datetime.utcnow(),
                last_activity=datetime.utcnow(),
            )
            
            self.active_sessions[session.id] = session
            
            # Store in Redis for cross-service access
            await self._persist_session(session)
            
            logger.info(
                "session_created",
                session_id=session.id,
                device_id=device_id,
                speaker_id=speaker_id,
                concurrent_count=len(self.active_sessions),
            )
            
            return session
    
    async def get_session(self, session_id: str) -> Optional[Session]:
        """Get session by ID."""
        session = self.active_sessions.get(session_id)
        if session and not session.is_expired():
            return session
        return None
    
    async def update_session_context(
        self,
        session_id: str,
        turn: dict,
    ) -> None:
        """Add a turn to session context."""
        session = self.active_sessions.get(session_id)
        if not session:
            return
        
        session.last_activity = datetime.utcnow()
        session.turn_count += 1
        
        # Maintain context window (last 10 turns)
        if "turns" not in session.context:
            session.context["turns"] = []
        session.context["turns"].append(turn)
        session.context["turns"] = session.context["turns"][-10:]
        
        await self._persist_session(session)
    
    async def end_session(
        self,
        session_id: str,
        reason: str = "user_ended"
    ) -> None:
        """End a session and persist to database."""
        async with self._lock:
            session = self.active_sessions.pop(session_id, None)
            if not session:
                return
            
            # Persist to database for history
            await self.db.execute(
                """
                INSERT INTO conversations 
                (id, device_id, speaker_id, mode, created_at, ended_at, turn_count, status)
                VALUES (?, ?, ?, ?, ?, datetime('now'), ?, 'ended')
                """,
                [session.id, session.device_id, session.speaker_id, 
                 session.mode, session.started_at.isoformat(), session.turn_count]
            )
            
            # Clear from Redis
            await self.redis.delete(f"session:{session.id}")
            
            logger.info(
                "session_ended",
                session_id=session_id,
                reason=reason,
                turn_count=session.turn_count,
            )
    
    def _get_session_by_device(self, device_id: str) -> Optional[Session]:
        """Find active session for a device."""
        for session in self.active_sessions.values():
            if session.device_id == device_id and not session.is_expired():
                return session
        return None
    
    def _cleanup_expired(self) -> None:
        """Remove expired sessions."""
        expired = [sid for sid, s in self.active_sessions.items() if s.is_expired()]
        for sid in expired:
            del self.active_sessions[sid]
    
    async def _persist_session(self, session: Session) -> None:
        """Persist session to Redis."""
        await self.redis.setex(
            f"session:{session.id}",
            SESSION_TIMEOUT_SECONDS,
            json.dumps({
                "id": session.id,
                "device_id": session.device_id,
                "speaker_id": session.speaker_id,
                "mode": session.mode,
                "context": session.context,
            })
        )
```

### 2.4 GPU Queue for Concurrent Processing

```python
# src/barnabee/gpu/queue.py

import asyncio
from dataclasses import dataclass
from typing import Optional
from enum import Enum

class Priority(Enum):
    HIGH = 1      # Short commands, confirmations
    NORMAL = 2    # Standard requests
    LOW = 3       # Long-form content, meetings

@dataclass
class GPUTask:
    session_id: str
    task_type: str  # "stt" or "tts"
    data: bytes
    priority: Priority
    created_at: float
    future: asyncio.Future

class GPUTaskQueue:
    """
    Priority queue for GPU tasks across concurrent sessions.
    Ensures fair scheduling while prioritizing short interactions.
    """
    
    def __init__(self, max_concurrent: int = 2):
        self.max_concurrent = max_concurrent
        self.stt_queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self.tts_queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self.active_tasks = 0
        self._lock = asyncio.Lock()
    
    async def submit_stt(
        self,
        session_id: str,
        audio_data: bytes,
        priority: Priority = Priority.NORMAL
    ) -> str:
        """Submit STT task and wait for result."""
        future = asyncio.get_event_loop().create_future()
        task = GPUTask(
            session_id=session_id,
            task_type="stt",
            data=audio_data,
            priority=priority,
            created_at=time.time(),
            future=future,
        )
        
        await self.stt_queue.put((priority.value, task.created_at, task))
        
        # Return transcript when ready
        return await future
    
    async def submit_tts(
        self,
        session_id: str,
        text: str,
        priority: Priority = Priority.NORMAL
    ) -> bytes:
        """Submit TTS task and wait for result."""
        future = asyncio.get_event_loop().create_future()
        task = GPUTask(
            session_id=session_id,
            task_type="tts",
            data=text.encode(),
            priority=priority,
            created_at=time.time(),
            future=future,
        )
        
        await self.tts_queue.put((priority.value, task.created_at, task))
        
        # Return audio when ready
        return await future
    
    async def process_queue(self, stt_service, tts_service):
        """Main loop processing GPU tasks."""
        while True:
            # Process STT and TTS in parallel up to max_concurrent
            tasks = []
            
            async with self._lock:
                while self.active_tasks < self.max_concurrent:
                    task = None
                    
                    # Alternate between STT and TTS queues
                    if not self.stt_queue.empty():
                        _, _, task = await self.stt_queue.get()
                    elif not self.tts_queue.empty():
                        _, _, task = await self.tts_queue.get()
                    
                    if task:
                        self.active_tasks += 1
                        tasks.append(self._process_task(task, stt_service, tts_service))
                    else:
                        break
            
            if tasks:
                await asyncio.gather(*tasks)
            else:
                await asyncio.sleep(0.01)  # Prevent busy loop
    
    async def _process_task(self, task: GPUTask, stt_service, tts_service):
        """Process a single GPU task."""
        try:
            if task.task_type == "stt":
                result = await stt_service.transcribe(task.data)
            else:
                result = await tts_service.synthesize(task.data.decode())
            
            task.future.set_result(result)
        except Exception as e:
            task.future.set_exception(e)
        finally:
            async with self._lock:
                self.active_tasks -= 1
```

### 2.5 Session Isolation Guarantees

```python
# Ensure sessions don't cross-contaminate

class SessionIsolation:
    """
    Guarantees for session isolation:
    
    1. Context Isolation: Each session has its own conversation history
    2. Memory Isolation: Queries scoped to session's speaker_id
    3. HA Context: Device location context per session
    4. Response Routing: Audio response only to originating device
    """
    
    @staticmethod
    def build_context_for_session(session: Session, memory_repo, ha_cache) -> dict:
        """Build isolated context for a session."""
        return {
            # Session-specific
            "session_id": session.id,
            "device_id": session.device_id,
            "device_location": session.context.get("device_location"),
            
            # Speaker-specific (NOT shared across sessions)
            "speaker_id": session.speaker_id,
            "speaker_name": session.context.get("speaker_name"),
            "speaker_preferences": session.context.get("preferences", {}),
            
            # Conversation context (isolated to this session)
            "conversation_turns": session.context.get("turns", []),
            "conversation_mode": session.mode,
            
            # Memory queries will be scoped to speaker_id
            # HA context will be scoped to device_location
        }
    
    @staticmethod
    async def get_memories_for_session(
        session: Session,
        query: str,
        memory_repo
    ) -> list:
        """Get memories scoped to session's speaker."""
        # Only return memories owned by or visible to this speaker
        return await memory_repo.search(
            query=query,
            owner=session.speaker_id,
            visibility_filter=["owner", "family"],  # Not other users' private memories
        )
```

---

## 3. GPU Health & OOM Recovery

### 3.1 GPU Watchdog Service

```python
# src/barnabee/gpu/watchdog.py

import asyncio
import subprocess
from dataclasses import dataclass
from typing import Optional

@dataclass
class GPUHealth:
    memory_used_mb: int
    memory_total_mb: int
    memory_percent: float
    temperature_c: int
    utilization_percent: int
    processes: list[dict]

class GPUWatchdog:
    """
    Monitor GPU health and recover from OOM conditions.
    """
    
    OOM_THRESHOLD_PERCENT = 95
    RECOVERY_COOLDOWN_SECONDS = 60
    
    def __init__(self, docker_client):
        self.docker = docker_client
        self.last_recovery = 0
        self.oom_count = 0
    
    async def get_gpu_health(self) -> GPUHealth:
        """Query nvidia-smi for GPU stats."""
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used,memory.total,temperature.gpu,utilization.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True
        )
        
        mem_used, mem_total, temp, util = result.stdout.strip().split(", ")
        
        return GPUHealth(
            memory_used_mb=int(mem_used),
            memory_total_mb=int(mem_total),
            memory_percent=(int(mem_used) / int(mem_total)) * 100,
            temperature_c=int(temp),
            utilization_percent=int(util),
            processes=await self._get_gpu_processes(),
        )
    
    async def monitor(self):
        """Continuous GPU monitoring loop."""
        while True:
            try:
                health = await self.get_gpu_health()
                
                # Emit metrics
                GPU_MEMORY_USED.set(health.memory_used_mb)
                GPU_MEMORY_PERCENT.set(health.memory_percent)
                GPU_TEMPERATURE.set(health.temperature_c)
                GPU_UTILIZATION.set(health.utilization_percent)
                
                # Check for OOM condition
                if health.memory_percent > self.OOM_THRESHOLD_PERCENT:
                    await self._handle_high_memory(health)
                
            except Exception as e:
                logger.error("gpu_watchdog_error", error=str(e))
            
            await asyncio.sleep(5)  # Check every 5 seconds
    
    async def _handle_high_memory(self, health: GPUHealth):
        """Handle high GPU memory condition."""
        logger.warning(
            "gpu_memory_high",
            memory_percent=health.memory_percent,
            memory_used_mb=health.memory_used_mb,
        )
        
        # Check cooldown
        now = time.time()
        if now - self.last_recovery < self.RECOVERY_COOLDOWN_SECONDS:
            logger.info("gpu_recovery_cooldown", seconds_remaining=self.RECOVERY_COOLDOWN_SECONDS - (now - self.last_recovery))
            return
        
        # Try graceful recovery first
        await self._graceful_recovery()
        
        await asyncio.sleep(5)
        health = await self.get_gpu_health()
        
        if health.memory_percent > self.OOM_THRESHOLD_PERCENT:
            # Graceful didn't work - restart GPU services
            await self._force_recovery()
    
    async def _graceful_recovery(self):
        """Try to free memory without restart."""
        logger.info("gpu_graceful_recovery_started")
        
        # Unload low-priority models (Whisper fallback)
        await self._unload_model("whisper_fallback")
        
        # Force garbage collection
        import gc
        import torch
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    
    async def _force_recovery(self):
        """Restart GPU services container."""
        logger.warning("gpu_force_recovery_started")
        
        self.oom_count += 1
        self.last_recovery = time.time()
        
        GPU_OOM_RECOVERY_COUNT.inc()
        
        try:
            # Restart the GPU services container
            container = self.docker.containers.get("barnabee-gpu")
            container.restart(timeout=30)
            
            logger.info("gpu_services_restarted")
            
            # Wait for health check
            for _ in range(30):
                await asyncio.sleep(2)
                try:
                    async with httpx.AsyncClient() as client:
                        resp = await client.get("http://localhost:8001/health", timeout=5)
                        if resp.status_code == 200:
                            logger.info("gpu_services_healthy_after_restart")
                            return
                except:
                    pass
            
            logger.error("gpu_services_not_healthy_after_restart")
            
        except Exception as e:
            logger.error("gpu_restart_failed", error=str(e))
    
    async def _get_gpu_processes(self) -> list:
        """Get list of processes using GPU."""
        result = subprocess.run(
            ["nvidia-smi", "--query-compute-apps=pid,used_memory,name", 
             "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True
        )
        processes = []
        for line in result.stdout.strip().split("\n"):
            if line:
                parts = line.split(", ")
                if len(parts) >= 3:
                    processes.append({
                        "pid": parts[0],
                        "memory_mb": int(parts[1]),
                        "name": parts[2],
                    })
        return processes


# Prometheus metrics
from prometheus_client import Gauge, Counter

GPU_MEMORY_USED = Gauge('barnabee_gpu_memory_used_mb', 'GPU memory used in MB')
GPU_MEMORY_PERCENT = Gauge('barnabee_gpu_memory_percent', 'GPU memory usage percentage')
GPU_TEMPERATURE = Gauge('barnabee_gpu_temperature_celsius', 'GPU temperature')
GPU_UTILIZATION = Gauge('barnabee_gpu_utilization_percent', 'GPU utilization percentage')
GPU_OOM_RECOVERY_COUNT = Counter('barnabee_gpu_oom_recovery_total', 'GPU OOM recovery events')
```

### 3.2 Prometheus Alerts for GPU

```yaml
# Add to alerting/rules.yml

- alert: GPUMemoryCritical
  expr: barnabee_gpu_memory_percent > 95
  for: 1m
  labels:
    severity: critical
  annotations:
    summary: "GPU memory critical ({{ $value }}%)"
    runbook: "https://wiki/runbooks/gpu-oom"

- alert: GPUTemperatureHigh
  expr: barnabee_gpu_temperature_celsius > 85
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "GPU temperature high ({{ $value }}°C)"

- alert: GPUOOMRecoveryFrequent
  expr: increase(barnabee_gpu_oom_recovery_total[1h]) > 3
  labels:
    severity: warning
  annotations:
    summary: "GPU OOM recovery triggered {{ $value }} times in 1 hour"
    description: "Check for memory leak or reduce concurrent sessions"
```

---

## 4. Model Version Management

### 4.1 Model Manifest Schema

```python
# src/barnabee/models/manifest.py

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import hashlib
from pathlib import Path

@dataclass
class ModelVersion:
    model_name: str           # e.g., "wake_word", "tts_voice", "stt"
    version: str              # e.g., "1.0.0"
    file_path: str
    checksum_sha256: str
    deployed_at: datetime
    deployed_by: str
    status: str               # active, rollback_available, archived
    metrics: Optional[dict]   # Performance metrics from production
    
    @staticmethod
    def compute_checksum(file_path: Path) -> str:
        """Compute SHA-256 checksum of model file."""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()


# Database schema addition
MODEL_VERSION_SCHEMA = """
CREATE TABLE model_versions (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    model_name TEXT NOT NULL,
    version TEXT NOT NULL,
    file_path TEXT NOT NULL,
    checksum_sha256 TEXT NOT NULL,
    deployed_at TEXT NOT NULL DEFAULT (datetime('now')),
    deployed_by TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    metrics TEXT,  -- JSON
    
    UNIQUE(model_name, version),
    CHECK (status IN ('active', 'rollback_available', 'archived'))
);

CREATE INDEX idx_model_versions_name ON model_versions(model_name);
CREATE INDEX idx_model_versions_status ON model_versions(status);
"""


class ModelRegistry:
    """Manage model versions and deployments."""
    
    def __init__(self, db, models_dir: Path):
        self.db = db
        self.models_dir = models_dir
    
    async def register_model(
        self,
        model_name: str,
        version: str,
        file_path: Path,
        deployed_by: str,
    ) -> ModelVersion:
        """Register a new model version."""
        
        checksum = ModelVersion.compute_checksum(file_path)
        
        # Archive previous active version
        await self.db.execute(
            """
            UPDATE model_versions 
            SET status = 'rollback_available' 
            WHERE model_name = ? AND status = 'active'
            """,
            [model_name]
        )
        
        # Register new version
        await self.db.execute(
            """
            INSERT INTO model_versions 
            (model_name, version, file_path, checksum_sha256, deployed_by)
            VALUES (?, ?, ?, ?, ?)
            """,
            [model_name, version, str(file_path), checksum, deployed_by]
        )
        
        logger.info(
            "model_registered",
            model_name=model_name,
            version=version,
            checksum=checksum[:16] + "...",
        )
        
        return ModelVersion(
            model_name=model_name,
            version=version,
            file_path=str(file_path),
            checksum_sha256=checksum,
            deployed_at=datetime.utcnow(),
            deployed_by=deployed_by,
            status="active",
            metrics=None,
        )
    
    async def get_active_model(self, model_name: str) -> Optional[ModelVersion]:
        """Get currently active model version."""
        row = await self.db.fetchone(
            "SELECT * FROM model_versions WHERE model_name = ? AND status = 'active'",
            [model_name]
        )
        if row:
            return self._row_to_model(row)
        return None
    
    async def rollback(self, model_name: str) -> Optional[ModelVersion]:
        """Rollback to previous model version."""
        
        # Get rollback candidate
        row = await self.db.fetchone(
            """
            SELECT * FROM model_versions 
            WHERE model_name = ? AND status = 'rollback_available'
            ORDER BY deployed_at DESC LIMIT 1
            """,
            [model_name]
        )
        
        if not row:
            logger.warning("no_rollback_available", model_name=model_name)
            return None
        
        # Archive current active
        await self.db.execute(
            "UPDATE model_versions SET status = 'archived' WHERE model_name = ? AND status = 'active'",
            [model_name]
        )
        
        # Activate rollback version
        await self.db.execute(
            "UPDATE model_versions SET status = 'active' WHERE id = ?",
            [row["id"]]
        )
        
        logger.info(
            "model_rollback",
            model_name=model_name,
            rolled_back_to_version=row["version"],
        )
        
        return self._row_to_model(row)
    
    async def verify_integrity(self, model_name: str) -> bool:
        """Verify model file matches registered checksum."""
        model = await self.get_active_model(model_name)
        if not model:
            return False
        
        current_checksum = ModelVersion.compute_checksum(Path(model.file_path))
        return current_checksum == model.checksum_sha256
```

---

## 5. Startup Dependency Ordering

### 5.1 Docker Compose Health Check Chaining

```yaml
# docker-compose.yml updates

services:
  redis:
    image: redis:7.2-alpine
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5
      start_period: 5s

  gpu-services:
    build: ./gpu
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8001/health"]
      interval: 10s
      timeout: 5s
      retries: 10
      start_period: 60s  # Models take time to load
    depends_on:
      redis:
        condition: service_healthy

  api:
    build: ./src
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 30s
    depends_on:
      redis:
        condition: service_healthy
      gpu-services:
        condition: service_healthy

  pipecat:
    build: ./voice
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 30s
    depends_on:
      api:
        condition: service_healthy
      gpu-services:
        condition: service_healthy
```

### 5.2 Startup Sequence Script

```bash
#!/bin/bash
# scripts/startup-sequence.sh

set -e

echo "=== BarnabeeNet V2 Startup Sequence ==="

# 1. Infrastructure
echo "[1/5] Starting infrastructure (Redis)..."
docker compose up -d redis
docker compose exec redis redis-cli ping || exit 1

# 2. GPU Services (slowest to start)
echo "[2/5] Starting GPU services (this may take 60+ seconds)..."
docker compose up -d gpu-services

echo "Waiting for GPU services to load models..."
for i in {1..60}; do
    if curl -sf http://localhost:8001/health > /dev/null 2>&1; then
        echo "GPU services healthy!"
        break
    fi
    echo "  ... waiting ($i/60)"
    sleep 2
done

curl -sf http://localhost:8001/health || {
    echo "ERROR: GPU services failed to start"
    docker compose logs gpu-services --tail 50
    exit 1
}

# 3. API
echo "[3/5] Starting API..."
docker compose up -d api
sleep 5
curl -sf http://localhost:8000/health || exit 1

# 4. Pipecat Voice
echo "[4/5] Starting Pipecat voice pipeline..."
docker compose up -d pipecat
sleep 5
curl -sf http://localhost:8080/health || exit 1

# 5. Supporting services
echo "[5/5] Starting monitoring and nginx..."
docker compose up -d nginx prometheus grafana

echo "=== Startup complete ==="
echo "Dashboard: https://barnabee.local"
echo "Grafana: http://localhost:3000"
```

---

## 6. Graceful Shutdown for Voice Sessions

### 6.1 Session Draining

```python
# src/barnabee/lifecycle/shutdown.py

import asyncio
import signal

DRAIN_TIMEOUT_SECONDS = 30

class GracefulShutdown:
    """Handle graceful shutdown with session draining."""
    
    def __init__(self, session_manager, pipecat):
        self.session_manager = session_manager
        self.pipecat = pipecat
        self.shutting_down = False
    
    def setup_handlers(self):
        """Setup signal handlers."""
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)
    
    def _handle_signal(self, signum, frame):
        """Handle shutdown signal."""
        if not self.shutting_down:
            self.shutting_down = True
            asyncio.create_task(self._graceful_shutdown())
    
    async def _graceful_shutdown(self):
        """Perform graceful shutdown."""
        logger.info("graceful_shutdown_started")
        
        # 1. Stop accepting new connections
        self.pipecat.stop_accepting_connections()
        
        # 2. Notify active sessions
        active_count = len(self.session_manager.active_sessions)
        if active_count > 0:
            logger.info("draining_sessions", count=active_count)
            
            # Announce to users
            for session in self.session_manager.active_sessions.values():
                await self._notify_session_ending(session)
        
        # 3. Wait for sessions to complete (with timeout)
        start = time.time()
        while self.session_manager.active_sessions:
            if time.time() - start > DRAIN_TIMEOUT_SECONDS:
                logger.warning(
                    "drain_timeout",
                    remaining_sessions=len(self.session_manager.active_sessions)
                )
                break
            
            await asyncio.sleep(1)
            logger.info(
                "draining",
                remaining=len(self.session_manager.active_sessions),
                elapsed=int(time.time() - start)
            )
        
        # 4. Force end remaining sessions
        for session_id in list(self.session_manager.active_sessions.keys()):
            await self.session_manager.end_session(session_id, reason="shutdown")
        
        logger.info("graceful_shutdown_complete")
    
    async def _notify_session_ending(self, session):
        """Notify user their session is ending due to maintenance."""
        try:
            # Play brief announcement
            await self.pipecat.send_to_device(
                session.device_id,
                audio=PRERECORDED_RESPONSES["maintenance_restart"],
            )
        except Exception as e:
            logger.warning("session_notify_failed", session_id=session.id, error=str(e))
```

---

## 7. LLM Provider Offline Fallback

### 7.1 Automatic Provider Failover

```python
# src/barnabee/llm/failover.py

PROVIDER_FALLBACK_CHAIN = [
    "azure_openai",   # Primary
    "openai",         # Secondary cloud
    "anthropic",      # Tertiary cloud
    "ollama_local",   # Local fallback (always available)
]

class LLMFailoverClient:
    """LLM client with automatic failover."""
    
    def __init__(self, registry: LLMRegistry):
        self.registry = registry
        self.failed_providers: set = set()
        self.failure_timestamps: dict = {}
        self.retry_after_seconds = 300  # 5 minutes
    
    async def complete(
        self,
        system: str,
        user: str,
        **kwargs
    ) -> str:
        """Complete with automatic failover."""
        
        # Clear old failures
        self._clear_stale_failures()
        
        for provider_id in PROVIDER_FALLBACK_CHAIN:
            if provider_id in self.failed_providers:
                continue
            
            provider = self.registry._instances.get(provider_id)
            if not provider:
                continue
            
            try:
                response = await asyncio.wait_for(
                    provider.complete(
                        messages=[
                            LLMMessage(role="system", content=system),
                            LLMMessage(role="user", content=user),
                        ],
                        **kwargs
                    ),
                    timeout=10.0
                )
                
                # Success - clear any previous failure
                self.failed_providers.discard(provider_id)
                
                return response.content
                
            except (asyncio.TimeoutError, Exception) as e:
                logger.warning(
                    "llm_provider_failed",
                    provider=provider_id,
                    error=str(e),
                )
                self.failed_providers.add(provider_id)
                self.failure_timestamps[provider_id] = time.time()
                continue
        
        # All providers failed
        raise LLMUnavailableError("All LLM providers failed")
    
    def _clear_stale_failures(self):
        """Allow retrying providers after cooldown."""
        now = time.time()
        for provider_id, timestamp in list(self.failure_timestamps.items()):
            if now - timestamp > self.retry_after_seconds:
                self.failed_providers.discard(provider_id)
                del self.failure_timestamps[provider_id]


class OllamaLocalProvider(LLMProvider):
    """Local Ollama provider for offline operation."""
    
    provider_id = "ollama_local"
    
    def __init__(self, model: str = "mistral:7b"):
        self.model = model
        self.base_url = "http://localhost:11434"
    
    async def complete(self, messages, **kwargs) -> LLMResponse:
        """Complete using local Ollama."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": [{"role": m.role, "content": m.content} for m in messages],
                    "stream": False,
                },
                timeout=30.0
            )
            
            data = response.json()
            
            return LLMResponse(
                content=data["message"]["content"],
                model=self.model,
                usage={"input_tokens": 0, "output_tokens": 0},  # Ollama doesn't report
                latency_ms=0,
            )
```

---

## 8. Embedding Model Consistency

### 8.1 Configuration-Driven Embedding Dimension

```python
# src/barnabee/config.py

from pydantic_settings import BaseSettings

class EmbeddingConfig(BaseSettings):
    """Embedding configuration - must be consistent across all uses."""
    
    # Choose ONE model and stick with it
    model: str = "all-MiniLM-L6-v2"  # Local, fast, 384 dims
    dimension: int = 384
    
    # Alternative: OpenAI (cloud, 1536 dims)
    # model: str = "text-embedding-ada-002"
    # dimension: int = 1536
    
    class Config:
        env_prefix = "BARNABEE_EMBEDDING_"


# Use throughout codebase
EMBEDDING_CONFIG = EmbeddingConfig()
```

### 8.2 Schema Migration for Flexible Dimensions

```sql
-- migrations/004_flexible_embedding_dimension.sql

-- Drop existing VSS table if dimension changes
DROP TABLE IF EXISTS memory_embeddings;

-- Create with configurable dimension
-- Note: This requires reading BARNABEE_EMBEDDING_DIMENSION at migration time
CREATE VIRTUAL TABLE memory_embeddings USING vss0(
    embedding(384)  -- Match EMBEDDING_CONFIG.dimension
);

-- Add dimension tracking
CREATE TABLE IF NOT EXISTS embedding_metadata (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    model_name TEXT NOT NULL,
    dimension INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

INSERT INTO embedding_metadata (id, model_name, dimension) VALUES (1, 'all-MiniLM-L6-v2', 384);
```

---

## 9. Voice Command Rate Limiting

### 9.1 Per-Device Rate Limiter

```python
# src/barnabee/security/rate_limit.py

from collections import defaultdict
import time

class VoiceRateLimiter:
    """Rate limit voice commands per device to prevent abuse."""
    
    def __init__(
        self,
        max_commands_per_minute: int = 30,
        max_commands_per_hour: int = 300,
    ):
        self.max_per_minute = max_commands_per_minute
        self.max_per_hour = max_commands_per_hour
        self.device_commands: dict[str, list[float]] = defaultdict(list)
    
    def check_rate_limit(self, device_id: str) -> tuple[bool, str]:
        """
        Check if device is within rate limits.
        Returns (allowed, reason).
        """
        now = time.time()
        minute_ago = now - 60
        hour_ago = now - 3600
        
        # Get command timestamps for this device
        timestamps = self.device_commands[device_id]
        
        # Clean old timestamps
        timestamps = [t for t in timestamps if t > hour_ago]
        self.device_commands[device_id] = timestamps
        
        # Check per-minute limit
        recent_minute = sum(1 for t in timestamps if t > minute_ago)
        if recent_minute >= self.max_per_minute:
            return False, f"Rate limit: {self.max_per_minute}/minute exceeded"
        
        # Check per-hour limit
        if len(timestamps) >= self.max_per_hour:
            return False, f"Rate limit: {self.max_per_hour}/hour exceeded"
        
        return True, ""
    
    def record_command(self, device_id: str):
        """Record a command for rate limiting."""
        self.device_commands[device_id].append(time.time())


# Integration with voice pipeline
voice_rate_limiter = VoiceRateLimiter()

async def process_voice_command(device_id: str, utterance: str):
    # Check rate limit
    allowed, reason = voice_rate_limiter.check_rate_limit(device_id)
    if not allowed:
        logger.warning(
            "voice_rate_limited",
            device_id=device_id,
            reason=reason,
        )
        VOICE_RATE_LIMIT_EVENTS.labels(device_id=device_id).inc()
        return RateLimitResponse(reason)
    
    # Record command
    voice_rate_limiter.record_command(device_id)
    
    # Process normally...
```

---

## 10. Wake Word False Positive Tracking

### 10.1 Wake Word Metrics

```python
# src/barnabee/voice/wake_word_metrics.py

from prometheus_client import Counter, Histogram
from datetime import datetime

# Metrics
WAKE_WORD_DETECTIONS = Counter(
    'barnabee_wake_word_detections_total',
    'Total wake word detections',
    ['device_id', 'result']  # result: confirmed, false_positive, timeout
)

WAKE_WORD_CONFIDENCE = Histogram(
    'barnabee_wake_word_confidence',
    'Wake word detection confidence distribution',
    ['device_id'],
    buckets=[0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95, 0.99]
)

WAKE_WORD_FALSE_POSITIVES_PER_HOUR = Counter(
    'barnabee_wake_word_false_positives_hourly',
    'False positive wake word detections per hour',
    ['device_id']
)


class WakeWordTracker:
    """Track wake word detection quality."""
    
    def __init__(self, db):
        self.db = db
        self.pending_detections: dict[str, dict] = {}
    
    async def record_detection(
        self,
        device_id: str,
        confidence: float,
        event_id: str,
    ):
        """Record a wake word detection."""
        WAKE_WORD_CONFIDENCE.labels(device_id=device_id).observe(confidence)
        
        self.pending_detections[event_id] = {
            "device_id": device_id,
            "confidence": confidence,
            "timestamp": datetime.utcnow(),
        }
    
    async def confirm_detection(self, event_id: str):
        """User spoke after wake word - confirmed true positive."""
        if event_id in self.pending_detections:
            detection = self.pending_detections.pop(event_id)
            WAKE_WORD_DETECTIONS.labels(
                device_id=detection["device_id"],
                result="confirmed"
            ).inc()
    
    async def mark_false_positive(self, event_id: str):
        """No speech followed wake word - likely false positive."""
        if event_id in self.pending_detections:
            detection = self.pending_detections.pop(event_id)
            WAKE_WORD_DETECTIONS.labels(
                device_id=detection["device_id"],
                result="false_positive"
            ).inc()
            WAKE_WORD_FALSE_POSITIVES_PER_HOUR.labels(
                device_id=detection["device_id"]
            ).inc()
            
            # Log for analysis
            await self.db.execute(
                """
                INSERT INTO wake_word_events 
                (device_id, confidence, result, timestamp)
                VALUES (?, ?, 'false_positive', ?)
                """,
                [detection["device_id"], detection["confidence"], 
                 detection["timestamp"].isoformat()]
            )
    
    async def mark_timeout(self, event_id: str):
        """Detection timed out - ambiguous."""
        if event_id in self.pending_detections:
            detection = self.pending_detections.pop(event_id)
            WAKE_WORD_DETECTIONS.labels(
                device_id=detection["device_id"],
                result="timeout"
            ).inc()


# Database table for wake word events
WAKE_WORD_EVENTS_SCHEMA = """
CREATE TABLE wake_word_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id TEXT NOT NULL,
    confidence REAL NOT NULL,
    result TEXT NOT NULL,  -- confirmed, false_positive, timeout
    timestamp TEXT NOT NULL,
    
    CHECK (result IN ('confirmed', 'false_positive', 'timeout'))
);

CREATE INDEX idx_wake_events_device ON wake_word_events(device_id);
CREATE INDEX idx_wake_events_result ON wake_word_events(result);
CREATE INDEX idx_wake_events_timestamp ON wake_word_events(timestamp);
"""
```

### 10.2 Grafana Dashboard Panel

```json
{
  "title": "Wake Word False Positive Rate",
  "type": "graph",
  "targets": [
    {
      "expr": "rate(barnabee_wake_word_false_positives_hourly[1h])",
      "legendFormat": "{{ device_id }}"
    }
  ],
  "alert": {
    "name": "High Wake Word False Positive Rate",
    "conditions": [
      {
        "evaluator": {"type": "gt", "params": [0.5]},
        "operator": {"type": "and"},
        "query": {"params": ["A", "1h", "now"]},
        "reducer": {"type": "avg"}
      }
    ],
    "message": "Wake word false positive rate > 0.5/hour on {{ device_id }}"
  }
}
```

---

## 11. Database Maintenance Tasks

### 11.1 Scheduled Maintenance Script

```python
# scripts/db_maintenance.py

import asyncio
import aiosqlite
from datetime import datetime, timedelta

async def run_maintenance(db_path: str):
    """Run scheduled database maintenance tasks."""
    
    async with aiosqlite.connect(db_path) as db:
        # 1. Vacuum (reclaim space from deleted rows)
        print("Running VACUUM...")
        await db.execute("VACUUM")
        
        # 2. Analyze (update query planner statistics)
        print("Running ANALYZE...")
        await db.execute("ANALYZE")
        
        # 3. Integrity check
        print("Running integrity check...")
        result = await db.execute("PRAGMA integrity_check")
        check = await result.fetchone()
        if check[0] != "ok":
            print(f"WARNING: Integrity check failed: {check}")
            return False
        
        # 4. Clean old operational logs (90 days)
        cutoff = (datetime.utcnow() - timedelta(days=90)).isoformat()
        cursor = await db.execute(
            "DELETE FROM operational_logs WHERE created_at < ?",
            [cutoff]
        )
        print(f"Deleted {cursor.rowcount} old log entries")
        
        # 5. Clean old wake word events (30 days)
        cutoff = (datetime.utcnow() - timedelta(days=30)).isoformat()
        cursor = await db.execute(
            "DELETE FROM wake_word_events WHERE timestamp < ?",
            [cutoff]
        )
        print(f"Deleted {cursor.rowcount} old wake word events")
        
        # 6. Optimize FTS indexes
        print("Optimizing FTS indexes...")
        await db.execute("INSERT INTO memories_fts(memories_fts) VALUES('optimize')")
        await db.execute("INSERT INTO meetings_fts(meetings_fts) VALUES('optimize')")
        
        await db.commit()
        
        print("Maintenance complete!")
        return True


# Cron entry: Run daily at 3 AM
# 0 3 * * * /opt/barnabee/scripts/db_maintenance.py
```

### 11.2 Systemd Timer for Maintenance

```ini
# /etc/systemd/system/barnabee-maintenance.timer

[Unit]
Description=BarnabeeNet daily database maintenance

[Timer]
OnCalendar=*-*-* 03:00:00
Persistent=true

[Install]
WantedBy=timers.target


# /etc/systemd/system/barnabee-maintenance.service

[Unit]
Description=BarnabeeNet database maintenance

[Service]
Type=oneshot
ExecStart=/opt/barnabee/venv/bin/python /opt/barnabee/scripts/db_maintenance.py
User=barnabee
```

---

## 12. Summary of Additions

| Gap | Section | Status |
|-----|---------|--------|
| Concurrent sessions support | 2 | ✅ Added |
| GPU OOM recovery | 3 | ✅ Added |
| Model version management | 4 | ✅ Added |
| Startup dependency ordering | 5 | ✅ Added |
| Graceful shutdown | 6 | ✅ Added |
| LLM offline fallback | 7 | ✅ Added |
| Embedding model consistency | 8 | ✅ Added |
| Voice command rate limiting | 9 | ✅ Added |
| Wake word false positive tracking | 10 | ✅ Added |
| Database maintenance tasks | 11 | ✅ Added |

---

## 13. Speed Optimizations

### 13.1 Parallel Context Assembly

**Problem:** Context gathering (memories, HA state, calendar, email) is shown as sequential, adding 200-400ms.

**Solution:** Fetch all context in parallel.

```python
# src/barnabee/context/assembler.py

import asyncio
from dataclasses import dataclass
from typing import Optional

@dataclass
class AssembledContext:
    ha_state: Optional[dict]
    relevant_memories: list
    calendar_events: list
    speaker_profile: Optional[dict]
    assembly_time_ms: float

class ParallelContextAssembler:
    """Assemble all context in parallel for minimum latency."""
    
    def __init__(self, ha_client, memory_repo, calendar_client, profile_repo):
        self.ha = ha_client
        self.memories = memory_repo
        self.calendar = calendar_client
        self.profiles = profile_repo
    
    async def assemble(
        self,
        utterance: str,
        intent: str,
        speaker_id: Optional[str],
        device_location: Optional[str],
    ) -> AssembledContext:
        """Assemble all context in parallel."""
        start = time.perf_counter()
        
        # Determine what context we need based on intent
        needs_ha = intent in HA_RELEVANT_INTENTS
        needs_memory = intent in MEMORY_RELEVANT_INTENTS
        needs_calendar = intent in CALENDAR_RELEVANT_INTENTS
        needs_profile = speaker_id is not None
        
        # Build parallel tasks
        tasks = {}
        
        if needs_ha:
            tasks['ha'] = self._get_ha_context(intent, device_location)
        
        if needs_memory:
            tasks['memories'] = self._get_memory_context(utterance, speaker_id)
        
        if needs_calendar:
            tasks['calendar'] = self._get_calendar_context(speaker_id)
        
        if needs_profile:
            tasks['profile'] = self._get_speaker_profile(speaker_id)
        
        # Execute all in parallel
        results = {}
        if tasks:
            task_results = await asyncio.gather(
                *tasks.values(),
                return_exceptions=True
            )
            for key, result in zip(tasks.keys(), task_results):
                if isinstance(result, Exception):
                    logger.warning(f"Context fetch failed: {key}", error=str(result))
                    results[key] = None
                else:
                    results[key] = result
        
        assembly_time = (time.perf_counter() - start) * 1000
        
        return AssembledContext(
            ha_state=results.get('ha'),
            relevant_memories=results.get('memories', []),
            calendar_events=results.get('calendar', []),
            speaker_profile=results.get('profile'),
            assembly_time_ms=assembly_time,
        )
    
    async def _get_ha_context(self, intent: str, location: Optional[str]) -> dict:
        """Get relevant HA state (filtered by intent and location)."""
        # Don't fetch all 2,291 entities - filter by relevance
        relevant_domains = INTENT_TO_HA_DOMAINS.get(intent, [])
        
        states = await self.ha.get_states(
            domains=relevant_domains,
            areas=[location] if location else None,
            limit=20,  # Max entities to include in context
        )
        
        return {
            "entities": states,
            "location": location,
        }
    
    async def _get_memory_context(self, utterance: str, speaker_id: str) -> list:
        """Get relevant memories via semantic search."""
        return await self.memories.search(
            query=utterance,
            owner=speaker_id,
            limit=5,
            min_similarity=0.7,
        )
    
    async def _get_calendar_context(self, speaker_id: str) -> list:
        """Get upcoming calendar events."""
        return await self.calendar.get_upcoming(
            user_id=speaker_id,
            hours_ahead=24,
            limit=5,
        )
    
    async def _get_speaker_profile(self, speaker_id: str) -> dict:
        """Get speaker preferences and profile."""
        return await self.profiles.get(speaker_id)


# Intent mappings
HA_RELEVANT_INTENTS = {
    'light_control', 'climate_control', 'lock_control', 'cover_control',
    'media_control', 'scene_activation', 'location_query',
}

MEMORY_RELEVANT_INTENTS = {
    'memory_query', 'memory_search', 'general_query', 'follow_up',
}

CALENDAR_RELEVANT_INTENTS = {
    'calendar_query', 'reminder_set', 'general_query',
}

INTENT_TO_HA_DOMAINS = {
    'light_control': ['light'],
    'climate_control': ['climate', 'sensor'],
    'lock_control': ['lock'],
    'cover_control': ['cover'],
    'media_control': ['media_player'],
    'location_query': ['person', 'device_tracker'],
}
```

### 13.2 Speculative Execution for High-Confidence Commands

**Problem:** For "turn on the lights", we wait for response generation before executing. This adds 200-400ms of perceived latency.

**Solution:** Start HA command execution immediately for high-confidence commands, generate response in parallel.

```python
# src/barnabee/execution/speculative.py

import asyncio
from dataclasses import dataclass
from typing import Optional, Tuple

SPECULATIVE_THRESHOLD = 0.95  # Only for very high confidence
SPECULATIVE_INTENTS = {
    'light_control', 'climate_control', 'media_control', 
    'lock_control', 'cover_control', 'scene_activation',
}

@dataclass
class SpeculativeResult:
    command_task: Optional[asyncio.Task]
    should_execute: bool
    can_rollback: bool

class SpeculativeExecutor:
    """Execute commands speculatively while generating response."""
    
    def __init__(self, ha_client, command_executor):
        self.ha = ha_client
        self.executor = command_executor
    
    async def maybe_start_execution(
        self,
        intent: str,
        confidence: float,
        entities: dict,
    ) -> SpeculativeResult:
        """Start command execution if confidence is high enough."""
        
        # Check if eligible for speculative execution
        if intent not in SPECULATIVE_INTENTS:
            return SpeculativeResult(None, False, False)
        
        if confidence < SPECULATIVE_THRESHOLD:
            return SpeculativeResult(None, False, False)
        
        if not entities.get('devices'):
            return SpeculativeResult(None, False, False)
        
        # Check if command is rollback-able
        can_rollback = self._can_rollback(intent, entities)
        
        # Start execution as background task
        command_task = asyncio.create_task(
            self.executor.execute(intent, entities)
        )
        
        logger.info(
            "speculative_execution_started",
            intent=intent,
            confidence=confidence,
            can_rollback=can_rollback,
        )
        
        return SpeculativeResult(
            command_task=command_task,
            should_execute=True,
            can_rollback=can_rollback,
        )
    
    def _can_rollback(self, intent: str, entities: dict) -> bool:
        """Check if this command can be rolled back if needed."""
        # Lights, media: can always toggle back
        if intent in ('light_control', 'media_control'):
            return True
        
        # Locks: depends on security policy
        if intent == 'lock_control':
            return False  # Don't speculatively unlock
        
        # Climate: can restore previous setting
        if intent == 'climate_control':
            return True
        
        return False
    
    async def cancel_if_needed(
        self,
        speculative_result: SpeculativeResult,
        reason: str,
    ):
        """Cancel speculative execution if classification was wrong."""
        if speculative_result.command_task:
            speculative_result.command_task.cancel()
            logger.warning(
                "speculative_execution_cancelled",
                reason=reason,
            )
            
            # Attempt rollback if already executed
            if speculative_result.can_rollback:
                await self._rollback_command(speculative_result)


class CommandPipeline:
    """Coordinate speculative execution with response generation."""
    
    def __init__(self, speculative_executor, response_generator):
        self.speculative = speculative_executor
        self.response = response_generator
    
    async def process(self, classification_result) -> Tuple[str, dict]:
        """Process command with speculative execution."""
        
        # Start speculative execution
        spec_result = await self.speculative.maybe_start_execution(
            intent=classification_result.intent,
            confidence=classification_result.confidence,
            entities=classification_result.entities,
        )
        
        # Generate response in parallel
        response_task = asyncio.create_task(
            self.response.generate(classification_result)
        )
        
        # Wait for both
        try:
            # Wait for command (if started)
            command_result = None
            if spec_result.command_task:
                command_result = await spec_result.command_task
            
            # Wait for response
            response_text = await response_task
            
            return response_text, command_result
            
        except Exception as e:
            # Cancel speculative execution on error
            await self.speculative.cancel_if_needed(spec_result, str(e))
            raise
```

### 13.3 Connection Pooling & Keep-Alive

```python
# src/barnabee/connections/pool.py

import httpx
from contextlib import asynccontextmanager

class ConnectionPool:
    """Maintain persistent connections to external services."""
    
    def __init__(self):
        # HTTP client pools with keep-alive
        self.llm_client = httpx.AsyncClient(
            timeout=30.0,
            limits=httpx.Limits(
                max_keepalive_connections=5,
                max_connections=10,
                keepalive_expiry=300,  # 5 minutes
            ),
        )
        
        self.ha_client = httpx.AsyncClient(
            base_url="http://homeassistant.local:8123",
            timeout=10.0,
            limits=httpx.Limits(
                max_keepalive_connections=3,
                max_connections=5,
                keepalive_expiry=600,  # 10 minutes
            ),
        )
        
        # WebSocket connections (HA real-time)
        self.ha_websocket = None
        self._ws_lock = asyncio.Lock()
    
    async def get_ha_websocket(self):
        """Get or create HA WebSocket connection."""
        async with self._ws_lock:
            if self.ha_websocket is None or self.ha_websocket.closed:
                self.ha_websocket = await self._connect_ha_ws()
            return self.ha_websocket
    
    async def warmup(self):
        """Warm up all connections at startup."""
        logger.info("warming_up_connections")
        
        # Ping LLM provider
        try:
            await self.llm_client.get("https://api.openai.com/")
        except:
            pass  # Just establishing connection
        
        # Ping HA
        try:
            await self.ha_client.get("/api/")
        except:
            pass
        
        # Establish HA WebSocket
        await self.get_ha_websocket()
        
        logger.info("connections_warmed_up")
    
    async def close(self):
        """Close all connections."""
        await self.llm_client.aclose()
        await self.ha_client.aclose()
        if self.ha_websocket:
            await self.ha_websocket.close()


# Global pool instance
connection_pool = ConnectionPool()
```

### 13.4 Response Caching

```python
# src/barnabee/cache/response_cache.py

from cachetools import TTLCache
import hashlib

class ResponseCache:
    """Cache responses for identical queries."""
    
    def __init__(self):
        # Short TTL caches for different response types
        self.time_cache = TTLCache(maxsize=10, ttl=30)      # 30 seconds
        self.weather_cache = TTLCache(maxsize=10, ttl=300)  # 5 minutes
        self.ha_state_cache = TTLCache(maxsize=100, ttl=10) # 10 seconds
    
    def get_time_response(self) -> Optional[str]:
        """Get cached time response if within same minute."""
        minute_key = datetime.now().strftime("%Y%m%d%H%M")
        return self.time_cache.get(minute_key)
    
    def set_time_response(self, response: str):
        """Cache time response."""
        minute_key = datetime.now().strftime("%Y%m%d%H%M")
        self.time_cache[minute_key] = response
    
    def get_weather_response(self, location: str) -> Optional[str]:
        """Get cached weather response."""
        return self.weather_cache.get(location)
    
    def set_weather_response(self, location: str, response: str):
        """Cache weather response."""
        self.weather_cache[location] = response
    
    def get_ha_state(self, entity_id: str) -> Optional[dict]:
        """Get cached HA entity state."""
        return self.ha_state_cache.get(entity_id)
    
    def set_ha_state(self, entity_id: str, state: dict):
        """Cache HA entity state."""
        self.ha_state_cache[entity_id] = state


response_cache = ResponseCache()
```

### 13.5 GPU Model Warmup

```python
# src/barnabee/gpu/warmup.py

class ModelWarmup:
    """Warm up GPU models at startup to avoid cold-start latency."""
    
    WARMUP_TEXTS = {
        "stt": b"<16khz silence audio bytes>",  # 1 second of silence
        "tts": "Hello, this is a warmup.",
        "embedding": "This is a test sentence for embedding warmup.",
        "wake_word": b"<audio with no wake word>",
    }
    
    async def warmup_all(self, gpu_services):
        """Warm up all GPU models."""
        logger.info("gpu_warmup_started")
        start = time.perf_counter()
        
        warmup_tasks = [
            self._warmup_stt(gpu_services),
            self._warmup_tts(gpu_services),
            self._warmup_embedding(gpu_services),
            self._warmup_wake_word(gpu_services),
        ]
        
        results = await asyncio.gather(*warmup_tasks, return_exceptions=True)
        
        for name, result in zip(['stt', 'tts', 'embedding', 'wake_word'], results):
            if isinstance(result, Exception):
                logger.error(f"warmup_failed", model=name, error=str(result))
            else:
                logger.info(f"warmup_complete", model=name, latency_ms=result)
        
        total_time = (time.perf_counter() - start) * 1000
        logger.info("gpu_warmup_complete", total_ms=total_time)
    
    async def _warmup_stt(self, gpu_services) -> float:
        """Warm up STT model."""
        start = time.perf_counter()
        await gpu_services.transcribe(self.WARMUP_TEXTS["stt"])
        return (time.perf_counter() - start) * 1000
    
    async def _warmup_tts(self, gpu_services) -> float:
        """Warm up TTS model."""
        start = time.perf_counter()
        await gpu_services.synthesize(self.WARMUP_TEXTS["tts"])
        return (time.perf_counter() - start) * 1000
    
    async def _warmup_embedding(self, gpu_services) -> float:
        """Warm up embedding model."""
        start = time.perf_counter()
        await gpu_services.embed(self.WARMUP_TEXTS["embedding"])
        return (time.perf_counter() - start) * 1000
    
    async def _warmup_wake_word(self, gpu_services) -> float:
        """Warm up wake word model."""
        start = time.perf_counter()
        await gpu_services.detect_wake_word(self.WARMUP_TEXTS["wake_word"])
        return (time.perf_counter() - start) * 1000
```

### 13.6 Streaming TTS Pipeline (LLM → TTS Parallelization)

**Problem:** Current design buffers sentences, then sends to TTS. We should stream TTS of sentence N while generating sentence N+1.

```python
# src/barnabee/voice/streaming_pipeline.py

import asyncio
from collections import deque

class StreamingTTSPipeline:
    """
    Stream LLM output to TTS with parallelization.
    
    While TTS is speaking sentence 1, we're:
    - Generating sentence 2 from LLM
    - Synthesizing sentence 2 to audio
    
    This hides TTS latency almost entirely.
    """
    
    def __init__(self, llm_client, tts_service, audio_output):
        self.llm = llm_client
        self.tts = tts_service
        self.audio = audio_output
        
        self.sentence_queue: asyncio.Queue = asyncio.Queue(maxsize=3)
        self.audio_queue: asyncio.Queue = asyncio.Queue(maxsize=3)
    
    async def stream_response(
        self,
        messages: list,
        session_id: str,
    ):
        """Stream LLM response through TTS to audio output."""
        
        # Start three parallel tasks
        tasks = [
            asyncio.create_task(self._llm_producer(messages)),
            asyncio.create_task(self._tts_processor()),
            asyncio.create_task(self._audio_consumer(session_id)),
        ]
        
        try:
            await asyncio.gather(*tasks)
        except Exception as e:
            # Cancel all tasks on error
            for task in tasks:
                task.cancel()
            raise
    
    async def _llm_producer(self, messages: list):
        """Generate LLM output, buffer into sentences."""
        buffer = SentenceBuffer()
        
        async for chunk in self.llm.stream_complete(messages):
            sentences = buffer.add(chunk)
            for sentence in sentences:
                await self.sentence_queue.put(sentence)
        
        # Flush remaining
        remaining = buffer.flush()
        if remaining:
            await self.sentence_queue.put(remaining)
        
        # Signal end
        await self.sentence_queue.put(None)
    
    async def _tts_processor(self):
        """Convert sentences to audio."""
        while True:
            sentence = await self.sentence_queue.get()
            
            if sentence is None:
                # Signal end to audio consumer
                await self.audio_queue.put(None)
                break
            
            # Synthesize to audio (this runs in parallel with next sentence generation)
            audio_bytes = await self.tts.synthesize(sentence)
            await self.audio_queue.put(audio_bytes)
    
    async def _audio_consumer(self, session_id: str):
        """Play audio to output device."""
        while True:
            audio = await self.audio_queue.get()
            
            if audio is None:
                break
            
            await self.audio.play(session_id, audio)
```

---

## 14. Quality Safeguards

### 14.1 Response Validation Against HA State

**Problem:** LLM might hallucinate about home state ("The lights are off" when they're on).

```python
# src/barnabee/quality/validator.py

import re
from typing import Optional, Tuple

class ResponseValidator:
    """Validate LLM responses against known facts."""
    
    def __init__(self, ha_client):
        self.ha = ha_client
    
    async def validate_and_fix(
        self,
        response: str,
        intent: str,
        ha_context: dict,
    ) -> Tuple[str, list]:
        """
        Validate response against HA state.
        Returns (fixed_response, warnings).
        """
        warnings = []
        
        # Check for state claims that contradict HA
        if intent in ('light_control', 'location_query', 'climate_control'):
            response, state_warnings = await self._validate_state_claims(
                response, ha_context
            )
            warnings.extend(state_warnings)
        
        # Check for hallucinated entities
        entity_warnings = self._validate_entities(response, ha_context)
        warnings.extend(entity_warnings)
        
        return response, warnings
    
    async def _validate_state_claims(
        self,
        response: str,
        ha_context: dict,
    ) -> Tuple[str, list]:
        """Check if response claims match actual state."""
        warnings = []
        
        # Extract state claims from response
        claims = self._extract_state_claims(response)
        
        for claim in claims:
            entity_id = claim.get('entity_id')
            claimed_state = claim.get('state')
            
            if entity_id and claimed_state:
                actual = ha_context.get('entities', {}).get(entity_id, {})
                actual_state = actual.get('state')
                
                if actual_state and actual_state != claimed_state:
                    warnings.append(f"State mismatch: {entity_id} is {actual_state}, not {claimed_state}")
                    
                    # Fix the response
                    response = response.replace(claimed_state, actual_state)
        
        return response, warnings
    
    def _extract_state_claims(self, response: str) -> list:
        """Extract state claims from response text."""
        claims = []
        
        # Pattern: "the X is on/off"
        patterns = [
            r"the (\w+(?:\s+\w+)*) (?:is|are) (on|off)",
            r"(\w+(?:\s+\w+)*) (?:is|are) (on|off)",
            r"turned (on|off) the (\w+(?:\s+\w+)*)",
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, response, re.IGNORECASE)
            for match in matches:
                claims.append({
                    'entity_name': match[0] if len(match) > 1 else match[0],
                    'state': match[1] if len(match) > 1 else match[0],
                })
        
        return claims
    
    def _validate_entities(self, response: str, ha_context: dict) -> list:
        """Check for mentions of entities that don't exist."""
        warnings = []
        known_entities = set(ha_context.get('entities', {}).keys())
        known_friendly_names = {
            e.get('attributes', {}).get('friendly_name', '').lower()
            for e in ha_context.get('entities', {}).values()
        }
        
        # Check for mentions of unknown rooms/devices
        # This is heuristic - won't catch everything
        room_pattern = r"in the (\w+(?:\s+\w+)*)"
        matches = re.findall(room_pattern, response, re.IGNORECASE)
        
        for match in matches:
            if match.lower() not in known_friendly_names:
                # Could be a room we don't know about
                warnings.append(f"Unknown location mentioned: {match}")
        
        return warnings
```

### 14.2 Response Quality Metrics

```python
# src/barnabee/quality/metrics.py

from prometheus_client import Counter, Histogram

# Quality metrics
RESPONSE_LENGTH = Histogram(
    'barnabee_response_length_words',
    'Response length in words',
    ['intent', 'path'],
    buckets=[5, 10, 15, 20, 30, 50, 75, 100]
)

PERSONA_VIOLATIONS = Counter(
    'barnabee_persona_violations_total',
    'Persona consistency violations detected',
    ['violation_type']
)

STATE_MISMATCHES = Counter(
    'barnabee_state_mismatches_total',
    'Response state claims that contradicted HA',
    ['entity_type']
)

RESPONSE_REGENERATIONS = Counter(
    'barnabee_response_regenerations_total',
    'Responses that had to be regenerated due to quality issues',
    ['reason']
)

class QualityTracker:
    """Track response quality metrics."""
    
    def track_response(
        self,
        response: str,
        intent: str,
        path: str,
        persona_violations: list,
        state_mismatches: list,
    ):
        """Track quality metrics for a response."""
        
        # Track length
        word_count = len(response.split())
        RESPONSE_LENGTH.labels(intent=intent, path=path).observe(word_count)
        
        # Track persona violations
        for violation in persona_violations:
            PERSONA_VIOLATIONS.labels(violation_type=violation).inc()
        
        # Track state mismatches
        for mismatch in state_mismatches:
            entity_type = mismatch.split('.')[0] if '.' in mismatch else 'unknown'
            STATE_MISMATCHES.labels(entity_type=entity_type).inc()
```

### 14.3 Pre-computed Audio for Common Responses

**Problem:** Even template responses go through TTS at runtime (150ms+).

**Solution:** Pre-generate audio for the most common responses.

```python
# src/barnabee/audio/precomputed.py

from pathlib import Path
import random

class PrecomputedAudio:
    """
    Pre-generated audio for common responses.
    Eliminates TTS latency for frequent queries.
    """
    
    PRECOMPUTED_DIR = Path("/data/audio/precomputed")
    
    # Responses that should be pre-generated
    PRECOMPUTED_RESPONSES = {
        "confirmation": {
            "done": ["Done.", "Got it.", "Okay."],
            "on": ["On.", "Turned on.", "It's on."],
            "off": ["Off.", "Turned off.", "It's off."],
        },
        "greeting": {
            "morning": ["Good morning!", "Morning!"],
            "afternoon": ["Good afternoon!", "Hey there."],
            "evening": ["Good evening!", "Evening!"],
            "default": ["Hey!", "Hi there.", "Hello!"],
        },
        "farewell": ["Bye!", "See you later.", "Take care!"],
        "acknowledgment": ["Mm-hmm.", "Okay.", "Got it.", "Sure."],
        "error": {
            "not_found": ["I couldn't find that.", "I'm not sure which one you mean."],
            "unavailable": ["That's not responding right now.", "I'm having trouble with that."],
        },
    }
    
    def __init__(self):
        self.audio_cache: dict[str, list[Path]] = {}
        self._load_cache()
    
    def _load_cache(self):
        """Load pre-computed audio file paths."""
        for category in self.PRECOMPUTED_DIR.iterdir():
            if category.is_dir():
                self.audio_cache[category.name] = list(category.glob("*.wav"))
    
    def get_audio(self, category: str, subcategory: str = None) -> Optional[Path]:
        """Get pre-computed audio file for response."""
        key = f"{category}/{subcategory}" if subcategory else category
        
        if key in self.audio_cache and self.audio_cache[key]:
            return random.choice(self.audio_cache[key])
        
        # Fallback to category only
        if category in self.audio_cache and self.audio_cache[category]:
            return random.choice(self.audio_cache[category])
        
        return None
    
    @classmethod
    async def generate_all(cls, tts_service):
        """Generate all pre-computed audio files (run at deploy time)."""
        cls.PRECOMPUTED_DIR.mkdir(parents=True, exist_ok=True)
        
        for category, items in cls.PRECOMPUTED_RESPONSES.items():
            category_dir = cls.PRECOMPUTED_DIR / category
            category_dir.mkdir(exist_ok=True)
            
            if isinstance(items, dict):
                for subcategory, phrases in items.items():
                    subcat_dir = category_dir / subcategory
                    subcat_dir.mkdir(exist_ok=True)
                    for i, phrase in enumerate(phrases):
                        audio = await tts_service.synthesize(phrase)
                        (subcat_dir / f"{i}.wav").write_bytes(audio)
            else:
                for i, phrase in enumerate(items):
                    audio = await tts_service.synthesize(phrase)
                    (category_dir / f"{i}.wav").write_bytes(audio)
        
        print(f"Generated pre-computed audio in {cls.PRECOMPUTED_DIR}")


# Integration with response pipeline
class FastResponsePath:
    """Ultra-fast response path using pre-computed audio."""
    
    def __init__(self, precomputed: PrecomputedAudio):
        self.precomputed = precomputed
    
    async def maybe_get_precomputed(
        self,
        intent: str,
        context: dict,
    ) -> Optional[Path]:
        """Get pre-computed audio if available."""
        
        if intent == "light_control":
            action = context.get("action", "on")
            return self.precomputed.get_audio("confirmation", action)
        
        if intent == "greeting":
            time_of_day = self._get_time_of_day()
            return self.precomputed.get_audio("greeting", time_of_day)
        
        if intent == "farewell":
            return self.precomputed.get_audio("farewell")
        
        return None
    
    def _get_time_of_day(self) -> str:
        hour = datetime.now().hour
        if hour < 12:
            return "morning"
        elif hour < 17:
            return "afternoon"
        else:
            return "evening"
```

---

## 15. Latency Budget Summary

### End-to-End Latency Targets (Updated)

| Path | Component | Target | Optimization |
|------|-----------|--------|--------------|
| **Ultra-Fast (Pre-computed)** | | **<30ms** | |
| | Wake word → audio play | 30ms | Pre-computed audio, no TTS |
| **Fast (Template)** | | **<100ms** | |
| | Classification | 25ms | Fast pattern match |
| | Context (minimal) | 10ms | Cached HA state |
| | Template fill | 5ms | String substitution |
| | TTS | 60ms | Streaming first chunk |
| **Standard (Speculative)** | | **<400ms** | |
| | Classification | 45ms | Embedding classifier |
| | Context assembly | 80ms | **Parallel fetch** |
| | HA command | 150ms | **Speculative, parallel** |
| | Response generation | 100ms | Minimal LLM |
| | TTS | 60ms | Streaming, parallel |
| **Conversational** | | **<800ms** | |
| | Classification | 45ms | |
| | Context assembly | 100ms | Parallel |
| | LLM generation | 400ms | Streaming |
| | TTS | 150ms | **Parallel with LLM** |

### Key Optimizations Summary

| Optimization | Latency Saved | Section |
|--------------|---------------|---------|
| Parallel context assembly | 150-250ms | 13.1 |
| Speculative execution | 200-400ms | 13.2 |
| Connection pooling | 50-100ms cold start | 13.3 |
| Response caching | 100-200ms | 13.4 |
| GPU model warmup | 500ms+ first request | 13.5 |
| Streaming TTS pipeline | 150-300ms | 13.6 |
| Pre-computed audio | 150ms+ | 14.3 |

---

## 16. Summary of All Additions

| Section | Topic | Status |
|---------|-------|--------|
| 2 | Concurrent sessions & multi-user | ✅ Added |
| 3 | GPU health & OOM recovery | ✅ Added |
| 4 | Model version management | ✅ Added |
| 5 | Startup dependency ordering | ✅ Added |
| 6 | Graceful shutdown | ✅ Added |
| 7 | LLM offline fallback | ✅ Added |
| 8 | Embedding model consistency | ✅ Added |
| 9 | Voice command rate limiting | ✅ Added |
| 10 | Wake word false positive tracking | ✅ Added |
| 11 | Database maintenance tasks | ✅ Added |
| 13 | **Speed: Parallel context assembly** | ✅ Added |
| 13 | **Speed: Speculative execution** | ✅ Added |
| 13 | **Speed: Connection pooling** | ✅ Added |
| 13 | **Speed: Response caching** | ✅ Added |
| 13 | **Speed: GPU model warmup** | ✅ Added |
| 13 | **Speed: Streaming TTS pipeline** | ✅ Added |
| 14 | **Quality: Response validation** | ✅ Added |
| 14 | **Quality: Metrics tracking** | ✅ Added |
| 14 | **Quality: Pre-computed audio** | ✅ Added |

---

**End of Area 23: Implementation Additions**
