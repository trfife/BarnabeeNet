# Area 11: Deployment & Infrastructure

**Version:** 1.0  
**Status:** Implementation Ready  
**Dependencies:** All Areas (deployment target)  
**Phase:** Parallel (all phases)  

---

## 1. Overview

### 1.1 Purpose

This specification defines the deployment architecture, service orchestration, GPU resource allocation, backup strategy, and operational procedures for BarnabeeNet V2. The deployment target is a Proxmox environment running on Beelink hardware, with GitHub Copilot assisting in configuration generation.

### 1.2 Hardware Inventory

| Server | Role | Specs | Location |
|--------|------|-------|----------|
| **Beast** | Primary GPU workloads | RTX 4070 Ti Super (16GB VRAM), 64GB RAM, NVMe | Main server room |
| **BattleServer** | Proxmox host (Beelink) | CPU-only, 32GB RAM | Network closet |
| **ManOfWar** | Secondary/HA fallback | TBD Beelink | Alternate location |

### 1.3 Design Principles

1. **Container-first:** All services run in Docker containers on Proxmox LXC/VMs
2. **GPU passthrough:** RTX 4070 Ti passed through to Beast VM for STT/TTS/embeddings
3. **Declarative config:** All deployment defined in version-controlled docker-compose and Terraform
4. **Graceful degradation:** Service failures isolated; system continues with reduced capability
5. **Observable by default:** Every service exposes health endpoints and metrics

### 1.4 Deployment Topology

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PROXMOX CLUSTER (BattleServer)                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                    VM: barnabee-gpu (Beast GPU Passthrough)             │ │
│  │                                                                         │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │ │
│  │  │  Parakeet   │  │   Kokoro    │  │  Embedding  │  │   Whisper   │   │ │
│  │  │    STT      │  │    TTS      │  │   Service   │  │  (Fallback) │   │ │
│  │  │   4GB VRAM  │  │  3GB VRAM   │  │  2GB VRAM   │  │  5GB VRAM   │   │ │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘   │ │
│  │                                                                         │ │
│  │                    GPU Memory Budget: 14GB / 16GB                       │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                    LXC: barnabee-core                                   │ │
│  │                                                                         │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │ │
│  │  │   FastAPI   │  │   Pipecat   │  │    Redis    │  │    ARQ      │   │ │
│  │  │    Main     │  │   Voice     │  │   Session   │  │   Workers   │   │ │
│  │  │    API      │  │  Pipeline   │  │    Store    │  │             │   │ │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘   │ │
│  │                                                                         │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                    │ │
│  │  │   SQLite    │  │  Dashboard  │  │   Nginx     │                    │ │
│  │  │  (Volume)   │  │   (Preact)  │  │   Proxy     │                    │ │
│  │  └─────────────┘  └─────────────┘  └─────────────┘                    │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                    LXC: barnabee-monitoring                             │ │
│  │                                                                         │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │ │
│  │  │ Prometheus  │  │   Grafana   │  │    Loki     │  │ Alertmanager│   │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘

External Dependencies:
┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│    Home     │  │   Azure     │  │   Gmail     │  │   Azure     │
│  Assistant  │  │  OpenAI     │  │    API      │  │   Comms     │
│  WebSocket  │  │    API      │  │             │  │  Services   │
└─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘
```

---

## 2. GPU Resource Allocation

### 2.1 VRAM Budget

The RTX 4070 Ti Super has 16GB VRAM. All GPU services must fit within this budget with headroom for spikes.

| Service | Model | VRAM (Loaded) | VRAM (Peak) | Priority |
|---------|-------|---------------|-------------|----------|
| Parakeet STT | parakeet-tdt-1.1b | 3.5GB | 4.5GB | Critical |
| Kokoro TTS | kokoro-v0.8 | 2.5GB | 3.5GB | Critical |
| Embedding | all-MiniLM-L6-v2 | 0.5GB | 1.0GB | High |
| Wake Word | openWakeWord | 0.3GB | 0.5GB | Critical |
| Whisper Fallback | whisper-medium | 0GB (lazy load) | 5.0GB | Low |
| **Total (Normal)** | | **6.8GB** | **9.5GB** | |
| **Total (Fallback Active)** | | **11.8GB** | **14.5GB** | |

### 2.2 GPU Memory Management Strategy

```python
# Priority-based model loading
GPU_SERVICES = {
    "parakeet": {"vram_reserved": 4096, "priority": 1, "preload": True},
    "kokoro": {"vram_reserved": 3072, "priority": 1, "preload": True},
    "embeddings": {"vram_reserved": 1024, "priority": 2, "preload": True},
    "whisper_fallback": {"vram_reserved": 5120, "priority": 3, "preload": False},
}
# Preload priority 1-2 at startup
# Lazy-load priority 3 on first use
# LRU eviction if VRAM pressure detected
```

### 2.3 GPU Passthrough Configuration (Proxmox)

```bash
# /etc/modprobe.d/vfio.conf
options vfio-pci ids=10de:2782  # RTX 4070 Ti Super

# VM Configuration (barnabee-gpu.conf)
hostpci0: 0000:01:00,pcie=1,x-vga=1
machine: q35
cpu: host
```

---

## 3. Docker Compose Configuration

### 3.1 Core Services

```yaml
# docker-compose.yml
version: "3.9"

services:
  api:
    build: ./src
    container_name: barnabee-api
    restart: unless-stopped
    ports:
      - "8000:8000"
    environment:
      - DATABASE_PATH=/data/barnabee.db
      - REDIS_URL=redis://redis:6379/0
      - GPU_SERVICE_URL=http://gpu-services:8001
    volumes:
      - barnabee-data:/data
      - ./config:/app/config:ro
    depends_on:
      - redis
      - gpu-services
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    deploy:
      resources:
        limits:
          memory: 4G

  pipecat:
    build: ./voice
    container_name: barnabee-pipecat
    restart: unless-stopped
    ports:
      - "8080:8080"
      - "10000-10100:10000-10100/udp"
    environment:
      - API_URL=http://api:8000
      - GPU_SERVICE_URL=http://gpu-services:8001
    depends_on:
      - api
      - gpu-services

  gpu-services:
    build: ./gpu
    container_name: barnabee-gpu
    restart: unless-stopped
    ports:
      - "8001:8001"
    environment:
      - CUDA_VISIBLE_DEVICES=0
    volumes:
      - model-cache:/models
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]

  redis:
    image: redis:7.2-alpine
    container_name: barnabee-redis
    restart: unless-stopped
    volumes:
      - redis-data:/data
    command: redis-server --appendonly yes --maxmemory 512mb

  worker:
    build: ./src
    container_name: barnabee-worker
    restart: unless-stopped
    command: arq barnabee.workers.WorkerSettings
    environment:
      - DATABASE_PATH=/data/barnabee.db
      - REDIS_URL=redis://redis:6379/0
    volumes:
      - barnabee-data:/data
    depends_on:
      - redis

  nginx:
    image: nginx:alpine
    container_name: barnabee-nginx
    restart: unless-stopped
    ports:
      - "443:443"
      - "80:80"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/ssl:/etc/nginx/ssl:ro
      - dashboard-dist:/var/www/dashboard:ro
    depends_on:
      - api
      - pipecat

volumes:
  barnabee-data:
    driver: local
    driver_opts:
      type: none
      o: bind
      device: /mnt/barnabee/data
  redis-data:
  model-cache:
  dashboard-dist:
```

---

## 4. Backup & Recovery

### 4.1 Backup Strategy

| Data | Method | Frequency | Retention | Location |
|------|--------|-----------|-----------|----------|
| SQLite database | Litestream streaming | Continuous | 30 days | Backblaze B2 |
| SQLite snapshots | Manual | Daily | 90 days | Local + offsite |
| Audio recordings | rsync | Hourly | 30 days | NAS |
| Configuration | Git | On change | Forever | GitHub |

### 4.2 Litestream Configuration

```yaml
# litestream.yml
dbs:
  - path: /data/barnabee.db
    replicas:
      - type: s3
        bucket: barnabee-backups
        path: sqlite/barnabee
        endpoint: s3.us-west-000.backblazeb2.com
        access-key-id: ${B2_KEY_ID}
        secret-access-key: ${B2_APPLICATION_KEY}
        retention: 720h
        sync-interval: 1s
```

### 4.3 Recovery Procedures

```bash
# Restore from Litestream
litestream restore -o /data/barnabee.db \
  s3://barnabee-backups/sqlite/barnabee

# Verify integrity
sqlite3 /data/barnabee.db "PRAGMA integrity_check;"
```

---

## 5. Observability Stack

### 5.1 Components

| Component | Purpose | Retention |
|-----------|---------|-----------|
| Prometheus | Metrics | 30 days |
| Grafana | Visualization | - |
| Loki | Log aggregation | 14 days |
| Alertmanager | Alert routing | - |

### 5.2 Critical Alerts

```yaml
# monitoring/alerts/barnabee.yml
groups:
  - name: barnabee
    rules:
      - alert: HighLatencyP95
        expr: histogram_quantile(0.95, rate(barnabee_request_duration_seconds_bucket[5m])) > 2
        for: 5m
        labels:
          severity: warning

      - alert: GPUMemoryHigh
        expr: nvidia_gpu_memory_used_bytes / nvidia_gpu_memory_total_bytes > 0.9
        for: 5m
        labels:
          severity: warning

      - alert: STTServiceDown
        expr: up{job="barnabee-gpu"} == 0
        for: 1m
        labels:
          severity: critical

      - alert: DatabaseUnreachable
        expr: barnabee_health_check_database != 1
        for: 30s
        labels:
          severity: critical
```

### 5.3 Structured Logging (Critical for Debugging)

```python
# Every log entry must include:
# - trace_id (for request correlation)
# - component (api, pipecat, gpu, worker)
# - latency_ms (for performance tracking)
# - user_id / session_id (for context)

import structlog

logger = structlog.get_logger()

async def process_command(utterance: str, session_id: str):
    logger.info(
        "processing_command",
        utterance=utterance,
        session_id=session_id,
        component="api",
        stage="intent_classification"
    )
```

**Log Query Examples (Loki):**
```
# All errors in last hour
{component="api"} |= "error"

# Slow requests (>1s)
{component="api"} | json | latency_ms > 1000

# Trace a specific request
{trace_id="abc123"}
```

---

## 6. Filler Audio (Pre-Generated TTS)

### 6.1 Filler Library

Pre-generate filler audio in Barnabee's voice using Kokoro TTS at deployment time.

```python
FILLER_PHRASES = {
    "acknowledgment": [
        "Mmhmm",
        "Got it",
        "Okay",
        "Sure thing",
        "One sec",
    ],
    "thinking": [
        "Let me check",
        "Looking into that",
        "Give me a moment",
        "Checking now",
    ],
    "clarification": [
        "Just to make sure",
        "So you want",
    ],
}

# Generate at build time
# scripts/generate_fillers.py
for category, phrases in FILLER_PHRASES.items():
    for i, phrase in enumerate(phrases):
        audio = kokoro.synthesize(phrase, voice="barnabee")
        save(f"fillers/{category}_{i}.wav", audio)
```

### 6.2 Filler Selection Logic

```python
def select_filler(context: str, processing_estimate_ms: int) -> Optional[str]:
    if processing_estimate_ms < 300:
        return None  # No filler needed
    elif processing_estimate_ms < 800:
        return random.choice(FILLERS["acknowledgment"])
    else:
        return random.choice(FILLERS["thinking"])
```

---

## 7. GitHub Copilot Integration Notes

Structure prompts for Copilot-assisted deployment generation:

```
Context: Deploying BarnabeeNet V2 to Proxmox on Beelink BattleServer
Hardware: RTX 4070 Ti Super GPU passthrough, 64GB RAM
Stack: Docker Compose, Litestream backup, Nginx reverse proxy

Generate: [specific artifact]
```

### File Structure for Copilot

```
deployment/
├── proxmox/
│   ├── lxc-barnabee-core.conf
│   ├── vm-barnabee-gpu.conf
│   └── gpu-passthrough.md
├── docker/
│   ├── docker-compose.yml
│   ├── docker-compose.monitoring.yml
│   └── Dockerfile.*
├── nginx/
│   └── nginx.conf
├── monitoring/
│   ├── prometheus.yml
│   ├── alertmanager.yml
│   └── grafana/
└── scripts/
    ├── deploy-initial.sh
    ├── deploy-update.sh
    └── rollback.sh
```

---

## 8. Implementation Checklist

### Proxmox Setup
- [ ] GPU passthrough configured on BattleServer
- [ ] LXC template created with Docker
- [ ] Network bridge configured

### Container Deployment
- [ ] Docker Compose files validated
- [ ] All service images built
- [ ] Health checks passing

### Backup
- [ ] Litestream configured and tested
- [ ] Recovery procedure validated

### Monitoring
- [ ] Prometheus scraping all targets
- [ ] Grafana dashboards imported
- [ ] Loki receiving logs
- [ ] Alertmanager routing to HA notifications

### Filler Audio
- [ ] All filler phrases generated
- [ ] Audio files deployed to /data/fillers/

---

## 9. Acceptance Criteria

1. **Cold start to operational:** <5 minutes
2. **Health check cascade:** All services healthy within 60 seconds
3. **Log aggregation working:** Queries return results in Loki
4. **Backup verified:** Litestream replica 0-lag
5. **Alert delivery confirmed:** Test alert reaches Home Assistant

---

**End of Area 11: Deployment & Infrastructure**
