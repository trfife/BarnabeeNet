# Area 16: Migration Execution Runbook

**Version:** 1.0  
**Status:** Implementation Ready  
**Dependencies:** All Areas  
**Phase:** Migration  

---

## 1. Overview

### 1.1 Purpose

This runbook provides step-by-step procedures for migrating from BarnabeeNet V1 to V2, including validation checkpoints, rollback procedures, and success criteria. Designed for execution by GitHub Copilot with human oversight.

### 1.2 Migration Scope

| Component | V1 State | V2 State | Migration Type |
|-----------|----------|----------|----------------|
| Data Store | JSON files + SQLite fragments | SQLite unified | Data migration |
| Voice Pipeline | Custom Python | Pipecat | Replace |
| STT | Whisper (various) | Parakeet TDT | Replace |
| TTS | Various | Kokoro | Replace |
| LLM | Hardcoded Azure | Multi-provider abstraction | Refactor |
| Memory | Ad-hoc | Three-tier structured | Redesign |
| HA Integration | REST polling | WebSocket | Replace |
| Dashboard | None | Preact SPA | New |

### 1.3 Timeline Estimate

| Phase | Duration | Parallelizable |
|-------|----------|----------------|
| Pre-migration prep | 2 days | No |
| Data migration | 4 hours | No |
| Service deployment | 2 hours | Partially |
| Integration testing | 4 hours | No |
| Parallel running | 3-7 days | Yes |
| Cutover | 1 hour | No |
| Post-migration validation | 2 hours | No |
| **Total** | **~5-10 days** | |

---

## 2. Pre-Migration Checklist

### 2.1 Infrastructure Ready

```bash
# Run on BattleServer (Proxmox host)
#!/bin/bash

echo "=== Pre-Migration Infrastructure Check ==="

# 1. Verify Proxmox is operational
pvesh get /cluster/status && echo "✓ Proxmox cluster OK" || echo "✗ Proxmox issue"

# 2. Check available storage
STORAGE=$(pvesm status | grep local-lvm | awk '{print $5}')
if [ "$STORAGE" -gt 100000 ]; then
    echo "✓ Storage OK (${STORAGE}MB available)"
else
    echo "✗ Insufficient storage"
fi

# 3. Verify GPU passthrough configured
if grep -q "vfio-pci" /etc/modprobe.d/vfio.conf 2>/dev/null; then
    echo "✓ GPU passthrough configured"
else
    echo "✗ GPU passthrough not configured"
fi

# 4. Network bridge exists
if ip link show vmbr0 &>/dev/null; then
    echo "✓ Network bridge vmbr0 exists"
else
    echo "✗ Network bridge missing"
fi

# 5. DNS resolution for required domains
for domain in github.com pypi.org registry.npmjs.org; do
    if host $domain &>/dev/null; then
        echo "✓ DNS resolves $domain"
    else
        echo "✗ Cannot resolve $domain"
    fi
done

# 6. Check Beast (GPU server) is reachable
if ping -c 1 beast.local &>/dev/null; then
    echo "✓ Beast server reachable"
else
    echo "✗ Beast server unreachable"
fi

echo "=== End Infrastructure Check ==="
```

### 2.2 Dependencies Available

| Dependency | Version | Check Command |
|------------|---------|---------------|
| Docker | 24.x+ | `docker --version` |
| Docker Compose | 2.20+ | `docker compose version` |
| Python | 3.11+ | `python3 --version` |
| Node.js | 20.x+ | `node --version` |
| SQLite | 3.40+ | `sqlite3 --version` |
| CUDA (Beast) | 12.x | `nvidia-smi` |

### 2.3 Credentials Ready

- [ ] Azure OpenAI API key
- [ ] Google OAuth credentials (client ID + secret)
- [ ] Azure Communication Services connection string + phone number
- [ ] Backblaze B2 credentials for Litestream
- [ ] Home Assistant long-lived access token
- [ ] GitHub PAT for repository access

### 2.4 V1 Backup Complete

```bash
# Create full V1 backup before any migration
#!/bin/bash

BACKUP_DIR="/mnt/backups/barnabee-v1-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_DIR"

# 1. Stop V1 services (brief downtime)
docker compose -f /opt/barnabee-v1/docker-compose.yml down

# 2. Copy all data
cp -r /opt/barnabee-v1/data "$BACKUP_DIR/"
cp -r /opt/barnabee-v1/config "$BACKUP_DIR/"
cp -r /opt/barnabee-v1/logs "$BACKUP_DIR/"

# 3. Export any SQLite databases
for db in /opt/barnabee-v1/data/*.db; do
    sqlite3 "$db" ".dump" > "$BACKUP_DIR/$(basename $db).sql"
done

# 4. Restart V1
docker compose -f /opt/barnabee-v1/docker-compose.yml up -d

# 5. Verify backup integrity
echo "Backup created at $BACKUP_DIR"
du -sh "$BACKUP_DIR"
```

---

## 3. Data Migration

### 3.1 Schema Creation

```bash
# Create V2 database with full schema
#!/bin/bash

DB_PATH="/mnt/barnabee/data/barnabee.db"

# Ensure directory exists
mkdir -p /mnt/barnabee/data

# Create database with schema from all areas
sqlite3 "$DB_PATH" < /opt/barnabee-v2/schema/00-core.sql
sqlite3 "$DB_PATH" < /opt/barnabee-v2/schema/01-memories.sql
sqlite3 "$DB_PATH" < /opt/barnabee-v2/schema/02-conversations.sql
sqlite3 "$DB_PATH" < /opt/barnabee-v2/schema/03-calendar-email.sql
sqlite3 "$DB_PATH" < /opt/barnabee-v2/schema/04-devices.sql
sqlite3 "$DB_PATH" < /opt/barnabee-v2/schema/05-notifications.sql
sqlite3 "$DB_PATH" < /opt/barnabee-v2/schema/06-llm-providers.sql

# Verify schema
echo "Tables created:"
sqlite3 "$DB_PATH" ".tables"

# Run integrity check
sqlite3 "$DB_PATH" "PRAGMA integrity_check;"
```

### 3.2 Memory Migration Script

```python
#!/usr/bin/env python3
"""
Migrate memories from V1 JSON/ad-hoc format to V2 structured schema.
"""

import json
import sqlite3
import hashlib
from pathlib import Path
from datetime import datetime

V1_DATA_DIR = Path("/opt/barnabee-v1/data")
V2_DB_PATH = Path("/mnt/barnabee/data/barnabee.db")

def generate_id() -> str:
    """Generate UUID-like ID."""
    import secrets
    return secrets.token_hex(16)

def migrate_memories():
    """Migrate V1 memories to V2 schema."""
    conn = sqlite3.connect(V2_DB_PATH)
    cursor = conn.cursor()
    
    migrated = 0
    errors = []
    
    # V1 stores memories in various JSON files
    memory_files = list(V1_DATA_DIR.glob("**/memories*.json"))
    
    for memory_file in memory_files:
        try:
            with open(memory_file) as f:
                v1_memories = json.load(f)
            
            for mem in v1_memories:
                # Map V1 fields to V2 schema
                memory_id = generate_id()
                
                # Determine memory type from V1 tags/categories
                v1_type = mem.get("type", mem.get("category", "fact"))
                v2_type = map_memory_type(v1_type)
                
                # Extract owner from V1 data
                owner = mem.get("owner", mem.get("user", "family"))
                
                cursor.execute("""
                    INSERT INTO memories (
                        id, summary, content, keywords, memory_type,
                        source_type, source_id, owner, visibility, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    memory_id,
                    mem.get("summary", mem.get("title", ""))[:500],
                    mem.get("content", mem.get("text", "")),
                    json.dumps(mem.get("keywords", mem.get("tags", []))),
                    v2_type,
                    "migration",
                    f"v1:{memory_file.name}",
                    owner,
                    mem.get("visibility", "private"),
                    mem.get("created_at", datetime.utcnow().isoformat()),
                ))
                migrated += 1
                
        except Exception as e:
            errors.append(f"{memory_file}: {e}")
    
    conn.commit()
    conn.close()
    
    print(f"Migrated {migrated} memories")
    if errors:
        print(f"Errors ({len(errors)}):")
        for e in errors[:10]:  # Show first 10 errors
            print(f"  - {e}")
    
    return migrated, errors


def map_memory_type(v1_type: str) -> str:
    """Map V1 memory types to V2 enum values."""
    mapping = {
        "fact": "fact",
        "preference": "preference",
        "preference_food": "preference",
        "preference_media": "preference",
        "decision": "decision",
        "event": "event",
        "person": "person",
        "project": "project",
        "meeting": "meeting",
        "journal": "journal",
        # Default fallback
        "note": "fact",
        "reminder": "fact",
    }
    return mapping.get(v1_type.lower(), "fact")


if __name__ == "__main__":
    migrate_memories()
```

### 3.3 Conversation History Migration

```python
#!/usr/bin/env python3
"""
Migrate conversation history from V1 to V2.
"""

import json
import sqlite3
from pathlib import Path
from datetime import datetime
import secrets

V1_DATA_DIR = Path("/opt/barnabee-v1/data")
V2_DB_PATH = Path("/mnt/barnabee/data/barnabee.db")

def migrate_conversations():
    """Migrate V1 conversation logs to V2 schema."""
    conn = sqlite3.connect(V2_DB_PATH)
    cursor = conn.cursor()
    
    migrated_convos = 0
    migrated_turns = 0
    
    # V1 stores conversations in various formats
    convo_files = list(V1_DATA_DIR.glob("**/conversations*.json"))
    convo_files.extend(V1_DATA_DIR.glob("**/chat_history*.json"))
    
    for convo_file in convo_files:
        try:
            with open(convo_file) as f:
                v1_convos = json.load(f)
            
            # Handle both list and dict formats
            if isinstance(v1_convos, dict):
                v1_convos = [v1_convos]
            
            for convo in v1_convos:
                convo_id = secrets.token_hex(16)
                
                # Create conversation record
                cursor.execute("""
                    INSERT INTO conversations (
                        id, started_at, ended_at, speaker_id, mode,
                        summary, topic_tags
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    convo_id,
                    convo.get("started_at", convo.get("timestamp", datetime.utcnow().isoformat())),
                    convo.get("ended_at"),
                    convo.get("speaker", convo.get("user", "unknown")),
                    "voice",  # Assume voice for V1
                    convo.get("summary", ""),
                    json.dumps(convo.get("tags", [])),
                ))
                migrated_convos += 1
                
                # Migrate turns
                turns = convo.get("turns", convo.get("messages", []))
                for i, turn in enumerate(turns):
                    turn_id = secrets.token_hex(16)
                    
                    cursor.execute("""
                        INSERT INTO conversation_turns (
                            id, conversation_id, turn_number, role,
                            utterance, response, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        turn_id,
                        convo_id,
                        i + 1,
                        turn.get("role", "user"),
                        turn.get("utterance", turn.get("input", "")),
                        turn.get("response", turn.get("output", "")),
                        turn.get("timestamp", datetime.utcnow().isoformat()),
                    ))
                    migrated_turns += 1
                    
        except Exception as e:
            print(f"Error migrating {convo_file}: {e}")
    
    conn.commit()
    conn.close()
    
    print(f"Migrated {migrated_convos} conversations with {migrated_turns} turns")
    return migrated_convos, migrated_turns


if __name__ == "__main__":
    migrate_conversations()
```

### 3.4 Migration Validation

```bash
#!/bin/bash
# Validate data migration completeness

V2_DB="/mnt/barnabee/data/barnabee.db"

echo "=== Data Migration Validation ==="

# Count records
echo "Record counts:"
sqlite3 "$V2_DB" "SELECT 'memories', COUNT(*) FROM memories;"
sqlite3 "$V2_DB" "SELECT 'conversations', COUNT(*) FROM conversations;"
sqlite3 "$V2_DB" "SELECT 'turns', COUNT(*) FROM conversation_turns;"

# Check for orphans
echo ""
echo "Orphan check:"
ORPHAN_TURNS=$(sqlite3 "$V2_DB" "
    SELECT COUNT(*) FROM conversation_turns 
    WHERE conversation_id NOT IN (SELECT id FROM conversations);
")
if [ "$ORPHAN_TURNS" -eq 0 ]; then
    echo "✓ No orphan turns"
else
    echo "✗ $ORPHAN_TURNS orphan turns found"
fi

# Validate FTS indexes
echo ""
echo "FTS index validation:"
FTS_MEMORIES=$(sqlite3 "$V2_DB" "SELECT COUNT(*) FROM memories_fts;")
TOTAL_MEMORIES=$(sqlite3 "$V2_DB" "SELECT COUNT(*) FROM memories;")
if [ "$FTS_MEMORIES" -eq "$TOTAL_MEMORIES" ]; then
    echo "✓ Memory FTS index complete ($FTS_MEMORIES records)"
else
    echo "✗ Memory FTS mismatch: $FTS_MEMORIES vs $TOTAL_MEMORIES"
fi

# Run integrity check
echo ""
echo "Database integrity:"
sqlite3 "$V2_DB" "PRAGMA integrity_check;" | head -1

echo "=== End Validation ==="
```

---

## 4. Service Deployment

### 4.1 Deployment Order

```
Phase 1: Infrastructure (can run V1 and V2 in parallel)
├── 1.1 Create Proxmox LXC for barnabee-core
├── 1.2 Create Proxmox VM for barnabee-gpu
├── 1.3 Configure networking
└── 1.4 Mount shared storage

Phase 2: Supporting Services
├── 2.1 Deploy Redis
├── 2.2 Deploy monitoring stack
└── 2.3 Configure Litestream backup

Phase 3: GPU Services (on Beast)
├── 3.1 Install NVIDIA drivers
├── 3.2 Install nvidia-container-toolkit
├── 3.3 Deploy GPU service container
└── 3.4 Verify model loading

Phase 4: Core Services
├── 4.1 Deploy API service
├── 4.2 Deploy Pipecat voice pipeline
├── 4.3 Deploy ARQ workers
└── 4.4 Deploy Nginx + Dashboard

Phase 5: Integration
├── 5.1 Configure Home Assistant connection
├── 5.2 Configure Gmail OAuth
├── 5.3 Configure Azure Communication Services
└── 5.4 Configure LLM providers
```

### 4.2 Deployment Commands

```bash
#!/bin/bash
# deploy-v2.sh - Full V2 deployment

set -euo pipefail

BARNABEE_DIR="/opt/barnabee-v2"
cd "$BARNABEE_DIR"

echo "=== Phase 1: Pull latest code ==="
git pull origin main

echo "=== Phase 2: Build images ==="
docker compose build

echo "=== Phase 3: Deploy supporting services ==="
docker compose up -d redis
sleep 5
docker compose exec redis redis-cli ping

echo "=== Phase 4: Deploy monitoring ==="
docker compose -f docker-compose.monitoring.yml up -d
sleep 10

echo "=== Phase 5: Deploy GPU services ==="
docker compose up -d gpu-services
sleep 30
# Verify GPU services
curl -f http://localhost:8001/health || exit 1

echo "=== Phase 6: Deploy core services ==="
docker compose up -d api worker pipecat
sleep 20

echo "=== Phase 7: Deploy nginx and dashboard ==="
docker compose up -d nginx

echo "=== Phase 8: Health check cascade ==="
sleep 10
curl -f https://barnabee.local/health || exit 1

echo "=== Deployment Complete ==="
docker compose ps
```

### 4.3 GPU Service Verification

```bash
#!/bin/bash
# verify-gpu-services.sh

echo "=== GPU Service Verification ==="

# 1. Check NVIDIA driver
nvidia-smi || { echo "✗ NVIDIA driver not working"; exit 1; }
echo "✓ NVIDIA driver OK"

# 2. Check CUDA in container
docker compose exec gpu-services python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}')"

# 3. Check model loading
echo "Checking model status..."
curl -s http://localhost:8001/health | jq .

# 4. Test STT
echo "Testing STT..."
curl -X POST http://localhost:8001/stt/test \
  -H "Content-Type: application/json" \
  -d '{"test": true}' | jq .

# 5. Test TTS
echo "Testing TTS..."
curl -X POST http://localhost:8001/tts/test \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello, this is a test"}' | jq .

# 6. Check VRAM usage
nvidia-smi --query-gpu=memory.used,memory.total --format=csv

echo "=== GPU Verification Complete ==="
```

---

## 5. Integration Testing

### 5.1 Test Suite

```python
#!/usr/bin/env python3
"""
Integration test suite for V2 deployment.
Run after deployment, before cutover.
"""

import asyncio
import httpx
import pytest
from datetime import datetime

BASE_URL = "https://barnabee.local"

@pytest.fixture
async def client():
    async with httpx.AsyncClient(base_url=BASE_URL, verify=False) as client:
        yield client

class TestHealth:
    async def test_health_endpoint(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ["healthy", "degraded"]
    
    async def test_detailed_health(self, client):
        resp = await client.get("/health/detailed")
        assert resp.status_code == 200
        data = resp.json()
        assert "checks" in data
        assert data["checks"].get("database") == "ok"
        assert data["checks"].get("redis") == "ok"

class TestVoice:
    async def test_wake_word_arbitration(self, client):
        event = {
            "event_id": "test-123",
            "device_id": "test-device",
            "timestamp": datetime.utcnow().timestamp(),
            "wake_confidence": 0.95,
        }
        resp = await client.post("/api/v2/voice/wake", json=event)
        assert resp.status_code == 200
        data = resp.json()
        assert "winner_device_id" in data
    
    async def test_voice_command(self, client):
        command = {
            "text": "What time is it?",
            "session_id": "test-session",
            "device_id": "test-device",
        }
        resp = await client.post("/api/v2/voice/process", json=command)
        assert resp.status_code == 200
        data = resp.json()
        assert "text" in data  # Response text

class TestMemories:
    async def test_list_memories(self, client):
        resp = await client.get("/api/v2/memories")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
    
    async def test_search_memories(self, client):
        search = {"query": "test"}
        resp = await client.post("/api/v2/memories/search", json=search)
        assert resp.status_code == 200

class TestHomeAssistant:
    async def test_ha_connection(self, client):
        resp = await client.get("/api/v2/admin/ha/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["connected"] == True

class TestLLM:
    async def test_llm_provider_list(self, client):
        resp = await client.get("/api/v2/admin/llm/providers")
        assert resp.status_code == 200
        data = resp.json()
        assert "providers" in data
        assert len(data["providers"]) > 0
    
    async def test_llm_active(self, client):
        resp = await client.get("/api/v2/admin/llm/active")
        assert resp.status_code == 200
        data = resp.json()
        assert "provider" in data

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

### 5.2 End-to-End Voice Test

```bash
#!/bin/bash
# e2e-voice-test.sh

echo "=== End-to-End Voice Test ==="

# 1. Test wake word detection
echo "1. Testing wake word detection..."
# Simulate wake word event
curl -X POST https://barnabee.local/api/v2/voice/wake \
  -H "Content-Type: application/json" \
  -d '{
    "event_id": "e2e-test-1",
    "device_id": "test-device",
    "timestamp": '$(date +%s.%N)',
    "wake_confidence": 0.95
  }' | jq .

# 2. Test voice command processing
echo "2. Testing voice command..."
curl -X POST https://barnabee.local/api/v2/voice/process \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Turn on the living room lights",
    "session_id": "e2e-test-session",
    "device_id": "test-device"
  }' | jq .

# 3. Check HA received command
echo "3. Verifying HA command execution..."
# This would check HA state - implementation depends on setup

# 4. Test memory query
echo "4. Testing memory query..."
curl -X POST https://barnabee.local/api/v2/voice/process \
  -H "Content-Type: application/json" \
  -d '{
    "text": "What did we talk about yesterday?",
    "session_id": "e2e-test-session",
    "device_id": "test-device"
  }' | jq .

echo "=== E2E Test Complete ==="
```

---

## 6. Parallel Running Period

### 6.1 Traffic Splitting Strategy

During the parallel running period, both V1 and V2 run simultaneously:

```
                          ┌─────────────┐
                          │    User     │
                          │   Device    │
                          └──────┬──────┘
                                 │
                                 │ Wake word detected
                                 │
                          ┌──────▼──────┐
                          │   Router    │
                          │  (Nginx)    │
                          └──────┬──────┘
                                 │
                    ┌────────────┼────────────┐
                    │            │            │
                    │ 90%        │ 10%        │
                    │            │ (shadow)   │
                    ▼            ▼            │
             ┌──────────┐ ┌──────────┐       │
             │    V1    │ │    V2    │◄──────┘
             │ (active) │ │ (shadow) │
             └──────────┘ └──────────┘
                                 │
                                 │ Log responses
                                 │ Compare latency
                                 ▼
                          ┌──────────────┐
                          │  Comparison  │
                          │     Log      │
                          └──────────────┘
```

### 6.2 Shadow Mode Configuration

```nginx
# nginx.conf - Shadow traffic to V2

upstream barnabee_v1 {
    server v1-api:8000;
}

upstream barnabee_v2 {
    server v2-api:8000;
}

server {
    listen 443 ssl;
    server_name barnabee.local;
    
    location /api/ {
        # Primary traffic goes to V1
        proxy_pass http://barnabee_v1;
        
        # Shadow 10% to V2 for comparison
        mirror /shadow;
        mirror_request_body on;
    }
    
    location /shadow {
        internal;
        proxy_pass http://barnabee_v2$request_uri;
        proxy_set_header X-Shadow "true";
    }
}
```

### 6.3 Comparison Metrics

```python
# Monitor during parallel running period

COMPARISON_METRICS = {
    "latency_p50": "V2 should be within 20% of V1",
    "latency_p95": "V2 should be within 50% of V1",
    "error_rate": "V2 error rate < V1 error rate",
    "intent_accuracy": "V2 should match V1 intent 95%+ of time",
    "ha_command_success": "V2 HA commands should succeed 99%+",
}

# Query Prometheus for comparison
# promql: histogram_quantile(0.5, rate(request_duration_seconds_bucket{version="v2"}[5m]))
```

### 6.4 Cutover Criteria

Before cutting over to V2:

- [ ] V2 latency P95 < V1 latency P95 + 50%
- [ ] V2 error rate < 1%
- [ ] V2 intent accuracy > 95% (compared to V1 for same inputs)
- [ ] V2 HA command success rate > 99%
- [ ] All integration tests passing
- [ ] 3+ days of stable parallel running
- [ ] No critical bugs in V2 during parallel period

---

## 7. Cutover Procedure

### 7.1 Pre-Cutover Checklist

```bash
#!/bin/bash
# pre-cutover-checklist.sh

echo "=== Pre-Cutover Checklist ==="

# 1. Verify V2 health
echo "1. V2 Health:"
curl -s https://barnabee.local/api/v2/health | jq .

# 2. Check parallel running metrics
echo "2. Parallel running duration:"
# Days since V2 started
V2_START=$(docker inspect barnabee-api --format '{{.State.StartedAt}}')
echo "V2 running since: $V2_START"

# 3. Check error rate
echo "3. V2 error rate (last 24h):"
curl -s 'http://prometheus:9090/api/v1/query?query=rate(http_requests_total{status=~"5.."}[24h])' | jq .

# 4. Verify backup is current
echo "4. Litestream backup status:"
curl -s http://localhost:9090/api/v1/query?query=litestream_replica_lag_seconds | jq .

# 5. Confirm rollback procedure is ready
echo "5. Rollback script exists:"
ls -la /opt/barnabee-v2/scripts/rollback.sh

echo "=== Checklist Complete ==="
echo "Proceed with cutover? (requires manual confirmation)"
```

### 7.2 Cutover Steps

```bash
#!/bin/bash
# cutover.sh - Switch from V1 to V2

set -euo pipefail

echo "=== Starting V1 → V2 Cutover ==="
echo "Time: $(date)"

# 1. Create final V1 backup
echo "Step 1: Final V1 backup..."
/opt/barnabee-v1/scripts/backup.sh

# 2. Stop V1 services
echo "Step 2: Stopping V1..."
docker compose -f /opt/barnabee-v1/docker-compose.yml down

# 3. Update nginx to route all traffic to V2
echo "Step 3: Updating nginx routing..."
cp /opt/barnabee-v2/nginx/nginx-v2-only.conf /opt/barnabee-v2/nginx/nginx.conf
docker compose exec nginx nginx -s reload

# 4. Verify V2 is handling traffic
echo "Step 4: Verifying V2..."
sleep 5
curl -f https://barnabee.local/health || {
    echo "V2 health check failed! Rolling back..."
    /opt/barnabee-v2/scripts/rollback.sh
    exit 1
}

# 5. Update DNS if needed
echo "Step 5: DNS update (if applicable)..."
# Depends on your DNS setup

# 6. Final verification
echo "Step 6: Final verification..."
curl -s https://barnabee.local/health | jq .

echo "=== Cutover Complete ==="
echo "V2 is now live!"
echo "Monitor closely for the next 24 hours."
echo "Rollback available at: /opt/barnabee-v2/scripts/rollback.sh"
```

### 7.3 Rollback Procedure

```bash
#!/bin/bash
# rollback.sh - Emergency rollback to V1

set -euo pipefail

echo "!!! EMERGENCY ROLLBACK TO V1 !!!"
echo "Time: $(date)"

# 1. Stop V2 traffic
echo "Step 1: Stopping V2 traffic..."
docker compose -f /opt/barnabee-v2/docker-compose.yml exec nginx nginx -s stop 2>/dev/null || true

# 2. Start V1 services
echo "Step 2: Starting V1..."
docker compose -f /opt/barnabee-v1/docker-compose.yml up -d

# 3. Wait for V1 to be healthy
echo "Step 3: Waiting for V1 health..."
for i in {1..30}; do
    if curl -f http://localhost:8000/health 2>/dev/null; then
        echo "V1 is healthy"
        break
    fi
    sleep 2
done

# 4. Update nginx to route to V1
echo "Step 4: Routing traffic to V1..."
cp /opt/barnabee-v1/nginx/nginx.conf /etc/nginx/nginx.conf
systemctl reload nginx

# 5. Stop V2 (keep data)
echo "Step 5: Stopping V2 services..."
docker compose -f /opt/barnabee-v2/docker-compose.yml down

# 6. Verify V1 is serving
echo "Step 6: Verifying V1..."
curl -f https://barnabee.local/health || echo "WARNING: Health check failed"

echo "=== Rollback Complete ==="
echo "V1 is now live."
echo "Investigate V2 issues before attempting cutover again."
```

---

## 8. Post-Migration Validation

### 8.1 Validation Checklist

```bash
#!/bin/bash
# post-migration-validation.sh

echo "=== Post-Migration Validation ==="

# 1. Core functionality
echo "1. Core API health:"
curl -s https://barnabee.local/health | jq .

# 2. Voice pipeline
echo "2. Voice pipeline test:"
curl -s -X POST https://barnabee.local/api/v2/voice/process \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello Barnabee", "session_id": "validation"}' | jq .

# 3. Memory retrieval
echo "3. Memory retrieval:"
curl -s https://barnabee.local/api/v2/memories?limit=5 | jq '.items | length'

# 4. Home Assistant integration
echo "4. Home Assistant status:"
curl -s https://barnabee.local/api/v2/admin/ha/status | jq .

# 5. LLM provider
echo "5. LLM provider status:"
curl -s https://barnabee.local/api/v2/admin/llm/active | jq .

# 6. Monitoring
echo "6. Prometheus targets:"
curl -s http://prometheus:9090/api/v1/targets | jq '.data.activeTargets | length'

# 7. Logging
echo "7. Recent logs:"
curl -s 'http://loki:3100/loki/api/v1/query_range?query={app="barnabee"}&limit=5' | jq '.data.result | length'

# 8. Backup status
echo "8. Litestream backup:"
curl -s http://prometheus:9090/api/v1/query?query=litestream_replica_lag_seconds | jq '.data.result[0].value[1]'

echo "=== Validation Complete ==="
```

### 8.2 Success Criteria

| Metric | Target | Validation Method |
|--------|--------|-------------------|
| API response time P50 | < 100ms | Prometheus query |
| API response time P95 | < 500ms | Prometheus query |
| Error rate | < 0.1% | Prometheus query |
| Voice pipeline latency | < 2s end-to-end | Manual test |
| Memory query latency | < 200ms | API timing |
| HA command execution | 100% success | Log analysis |
| Backup lag | < 5 seconds | Litestream metrics |
| GPU utilization | < 80% | nvidia-smi |

---

## 9. Cleanup

### 9.1 Post-Cutover Cleanup (After 7 Days Stable)

```bash
#!/bin/bash
# cleanup.sh - Run after 7 days of stable V2 operation

echo "=== Post-Cutover Cleanup ==="

# Verify 7 days have passed since cutover
CUTOVER_DATE=$(cat /opt/barnabee-v2/.cutover_date)
DAYS_SINCE=$(( ($(date +%s) - $(date -d "$CUTOVER_DATE" +%s)) / 86400 ))

if [ "$DAYS_SINCE" -lt 7 ]; then
    echo "Only $DAYS_SINCE days since cutover. Wait until 7 days for cleanup."
    exit 1
fi

echo "Proceeding with cleanup ($DAYS_SINCE days since cutover)..."

# 1. Archive V1 data
echo "1. Archiving V1 data..."
tar -czf /mnt/archive/barnabee-v1-archive-$(date +%Y%m%d).tar.gz /opt/barnabee-v1/

# 2. Remove V1 containers and images
echo "2. Removing V1 containers..."
docker compose -f /opt/barnabee-v1/docker-compose.yml down --rmi all --volumes

# 3. Remove V1 code (keep archive)
echo "3. Removing V1 code directory..."
rm -rf /opt/barnabee-v1

# 4. Clean up old Docker images
echo "4. Pruning Docker..."
docker system prune -af --volumes

# 5. Update documentation
echo "5. Don't forget to:"
echo "   - Update README to reflect V2"
echo "   - Archive V1 documentation"
echo "   - Update runbooks"

echo "=== Cleanup Complete ==="
```

---

## 10. Appendix: Troubleshooting

### Common Issues

| Issue | Symptom | Solution |
|-------|---------|----------|
| GPU not detected | `nvidia-smi` fails in container | Verify GPU passthrough config, reinstall nvidia-container-toolkit |
| Slow STT | High latency on first request | Models not preloaded; check GPU memory, increase warm-up time |
| HA disconnection | WebSocket errors in logs | Check HA token, verify network connectivity |
| LLM timeout | Voice response delayed | Check LLM provider status, switch provider in dashboard |
| Memory search slow | >500ms queries | Rebuild FTS index, check SQLite ANALYZE |
| Litestream lag | Backup falling behind | Check network to B2, verify credentials |

### Emergency Contacts

| Issue Type | Contact | Escalation |
|------------|---------|------------|
| Infrastructure | GitHub Copilot (automated) | Thom manual |
| HA Integration | Check HA logs first | HA Discord |
| LLM Provider | Check provider status page | Switch to backup provider |
| Azure Services | Azure portal alerts | Azure support |

---

**End of Area 16: Migration Execution Runbook**
