# BarnabeeNet Operations Runbook

**Version:** 1.0  
**Last Updated:** January 16, 2026  
**Status:** Production Reference  
**Classification:** Internal Operations

---

## Table of Contents

1. [Executive Overview](#executive-overview)
2. [Monitoring Architecture](#monitoring-architecture)
3. [Metrics & Alerting](#metrics--alerting)
4. [Cost Tracking & Management](#cost-tracking--management)
5. [Troubleshooting Guides](#troubleshooting-guides)
6. [Backup & Recovery](#backup--recovery)
7. [Upgrade Procedures](#upgrade-procedures)
8. [Incident Response](#incident-response)
9. [Routine Maintenance](#routine-maintenance)
10. [Health Checks & Runbooks](#health-checks--runbooks)

---

## Executive Overview

### Purpose

This Operations Runbook provides standardized procedures for maintaining, monitoring, troubleshooting, and recovering BarnabeeNet. It ensures consistent operations across all system components and enables rapid response to incidents.

### System Overview

| Component | Platform | Criticality |
|-----------|----------|-------------|
| Home Assistant Core | Proxmox VM (Beelink) | Critical |
| BarnabeeNet Integration | HA Custom Component | Critical |
| Redis (Working Memory) | Docker Container | High |
| SQLite (Long-term Memory) | Local Storage | High |
| Voice Pipeline (STT/TTS) | Local Services | High |
| Gaming PC (Heavy Compute) | On-demand | Medium |
| LLM APIs (OpenRouter) | Cloud | Medium |

### Contact Information

| Role | Responsibility | Escalation |
|------|---------------|------------|
| System Owner | Overall system health | Primary |
| HA Admin | Home Assistant operations | Secondary |
| Network Admin | Connectivity issues | As needed |

---

## Monitoring Architecture

### Stack Overview

BarnabeeNet uses a **Prometheus + Grafana** monitoring stack integrated with Home Assistant's native metrics exposure.

```
┌─────────────────────────────────────────────────────────────────┐
│                    MONITORING ARCHITECTURE                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐         │
│  │   Grafana   │◄───│  Prometheus │◄───│    Home     │         │
│  │ Dashboards  │    │   (Scraper) │    │  Assistant  │         │
│  │  & Alerts   │    │             │    │  Prometheus │         │
│  └─────────────┘    └──────┬──────┘    │  Exporter   │         │
│                            │           └─────────────┘         │
│                            │                                    │
│        ┌───────────────────┼───────────────────┐               │
│        │                   │                   │               │
│        ▼                   ▼                   ▼               │
│  ┌───────────┐      ┌───────────┐      ┌───────────┐          │
│  │   Redis   │      │  Proxmox  │      │ BarnabeeNet│          │
│  │  Exporter │      │  Metrics  │      │   Custom   │          │
│  └───────────┘      └───────────┘      │  Metrics   │          │
│                                        └───────────┘          │
└─────────────────────────────────────────────────────────────────┘
```

### Home Assistant Prometheus Integration

Enable the Prometheus exporter in Home Assistant:

```yaml
# configuration.yaml
prometheus:
  namespace: hass
  filter:
    include_domains:
      - sensor
      - binary_sensor
      - climate
      - light
      - switch
    include_entity_globs:
      - sensor.barnabeenet_*
```

### Prometheus Configuration

```yaml
# prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'homeassistant'
    scrape_interval: 60s
    metrics_path: /api/prometheus
    bearer_token: '<HOME_ASSISTANT_LONG_LIVED_TOKEN>'
    scheme: http
    static_configs:
      - targets: ['homeassistant.local:8123']

  - job_name: 'redis'
    static_configs:
      - targets: ['redis-exporter:9121']

  - job_name: 'node'
    static_configs:
      - targets: ['beelink:9100', 'gamingpc:9100']

  - job_name: 'proxmox'
    static_configs:
      - targets: ['proxmox:9221']
```

### Grafana Dashboard Setup

Import the following community dashboards:

| Dashboard | ID | Purpose |
|-----------|-----|---------|
| Home Assistant System | 15832 | HA system metrics |
| Prometheus Home Dashboard | 15294 | Host overview |
| Redis Dashboard | 763 | Redis performance |
| Node Exporter Full | 1860 | System metrics |

---

## Metrics & Alerting

### Critical Metrics to Monitor

#### 1. Voice Pipeline Metrics

| Metric | Description | Warning | Critical |
|--------|-------------|---------|----------|
| `barnabeenet_stt_latency_ms` | Speech-to-text processing time | > 200ms | > 500ms |
| `barnabeenet_tts_latency_ms` | Text-to-speech processing time | > 150ms | > 300ms |
| `barnabeenet_total_latency_ms` | End-to-end command latency | > 400ms | > 1000ms |
| `barnabeenet_stt_error_rate` | STT failure rate | > 5% | > 15% |
| `barnabeenet_speaker_id_confidence` | Speaker recognition confidence | < 0.75 | < 0.60 |

#### 2. Agent Performance Metrics

| Metric | Description | Warning | Critical |
|--------|-------------|---------|----------|
| `barnabeenet_meta_agent_latency_ms` | Router decision time | > 15ms | > 50ms |
| `barnabeenet_action_agent_latency_ms` | Device control latency | > 80ms | > 200ms |
| `barnabeenet_interaction_agent_latency_ms` | Conversation response time | > 2s | > 5s |
| `barnabeenet_llm_fallback_rate` | Meta Agent LLM fallback frequency | > 20% | > 40% |

#### 3. Memory System Metrics

| Metric | Description | Warning | Critical |
|--------|-------------|---------|----------|
| `barnabeenet_redis_used_memory_bytes` | Redis memory consumption | > 80% of max | > 95% of max |
| `barnabeenet_redis_hit_rate` | Cache hit ratio | < 90% | < 70% |
| `barnabeenet_sqlite_query_latency_ms` | SQLite query time | > 30ms | > 100ms |
| `barnabeenet_memory_retrieval_latency_ms` | Semantic search time | > 40ms | > 100ms |

#### 4. System Health Metrics

| Metric | Description | Warning | Critical |
|--------|-------------|---------|----------|
| `node_cpu_seconds_total` | CPU utilization | > 70% | > 90% |
| `node_memory_MemAvailable_bytes` | Available memory | < 4GB | < 2GB |
| `node_filesystem_avail_bytes` | Disk space | < 20% | < 10% |
| `node_load1` | System load (1 min) | > 8 | > 12 |

### Alert Rules Configuration

```yaml
# alerts.yml
groups:
  - name: barnabeenet_critical
    rules:
      - alert: VoicePipelineHighLatency
        expr: barnabeenet_total_latency_ms > 1000
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Voice pipeline latency exceeds 1 second"
          description: "End-to-end latency is {{ $value }}ms"

      - alert: SpeakerRecognitionDegraded
        expr: barnabeenet_speaker_id_confidence < 0.60
        for: 10m
        labels:
          severity: critical
        annotations:
          summary: "Speaker recognition confidence critically low"
          description: "Average confidence is {{ $value }}"

      - alert: RedisMemoryCritical
        expr: redis_memory_used_bytes / redis_memory_max_bytes > 0.95
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Redis memory usage exceeds 95%"

      - alert: LLMCostLimitApproaching
        expr: barnabeenet_daily_cost_usd > 0.80
        for: 1m
        labels:
          severity: warning
        annotations:
          summary: "Daily LLM cost limit approaching (80%)"

      - alert: HomeAssistantUnreachable
        expr: up{job="homeassistant"} == 0
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Home Assistant is unreachable"
```

### Notification Channels

Configure Grafana alerting to multiple channels:

| Channel | Use Case | Priority |
|---------|----------|----------|
| Push Notification (Mobile) | Critical alerts | P1 |
| Email | Warning alerts | P2 |
| Home Assistant Notification | Local alerts | P3 |
| Slack/Discord (optional) | Team notifications | P3 |

---

## Cost Tracking & Management

### OpenRouter Cost Monitoring

OpenRouter provides built-in cost tracking through their Activity Dashboard:

**Dashboard URL:** `https://openrouter.ai/activity`

#### Key Metrics

| Metric | Description | Tracking Method |
|--------|-------------|-----------------|
| Token Consumption | Input/output tokens per model | OpenRouter Dashboard |
| Cost per Request | Computed from model pricing | OpenRouter API |
| Daily Spend | Aggregated daily cost | Custom tracking |
| Model Distribution | Usage breakdown by model | OpenRouter Analytics |

#### Enable Usage Accounting

Always include usage tracking in API calls:

```python
response = openrouter.chat.completions.create(
    model="anthropic/claude-3.5-sonnet",
    messages=[...],
    extra_body={
        "usage": {"include": True}
    }
)

# Access usage data
usage = response.usage
cost_estimate = (usage.prompt_tokens * input_price + 
                 usage.completion_tokens * output_price) / 1_000_000
```

### Cost Budget Structure

```yaml
# barnabeenet_cost_config.yaml
cost_controls:
  daily_limit_usd: 1.00
  monthly_limit_usd: 25.00
  
  alert_thresholds:
    warning: 0.50  # 50% of daily limit
    critical: 0.80  # 80% of daily limit
    
  model_priorities:
    - tier: instant
      models: []  # Pattern matching - $0
      daily_budget: unlimited
      
    - tier: local
      models: ["phi-3.5-mini", "llama-3.1-8b"]
      daily_budget: unlimited  # $0 (local)
      
    - tier: cloud_fast
      models: ["gemini-2.0-flash", "claude-haiku"]
      daily_budget: 0.30
      
    - tier: cloud_powerful
      models: ["anthropic/claude-3.5-sonnet", "openai/gpt-4o"]
      daily_budget: 0.50
      
  degradation_policy:
    green:  # < 50% daily limit
      all_features: enabled
      
    yellow:  # 50-80% daily limit
      interaction_agent: local_only
      complex_queries: rate_limited
      
    red:  # > 80% daily limit
      interaction_agent: disabled
      action_only: true
      user_message: "Cost limit approaching. Basic commands only."
```

### Langfuse Integration (Optional Advanced Tracking)

For detailed LLM observability, integrate Langfuse:

```python
from langfuse.openai import openai

# OpenRouter via Langfuse wrapper
client = openai.OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY")
)

# All calls automatically traced
response = client.chat.completions.create(
    model="anthropic/claude-3.5-sonnet",
    messages=[{"role": "user", "content": query}]
)
```

**Langfuse Dashboard provides:**
- Per-request cost breakdown
- Model comparison analytics
- Latency distributions
- Token usage patterns
- Custom cost attribution (by user, by agent type)

### Monthly Cost Report Template

```
╔══════════════════════════════════════════════════════════════╗
║             BARNABEENET MONTHLY COST REPORT                  ║
║                     January 2026                              ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  SUMMARY                                                     ║
║  ─────────────────────────────────────────────────────────  ║
║  Total Requests:           3,127                            ║
║  Total Tokens:             4.2M input / 1.8M output         ║
║  Total Cost:               $1.47                            ║
║  Daily Average:            $0.047                           ║
║                                                              ║
║  BREAKDOWN BY TIER                                          ║
║  ─────────────────────────────────────────────────────────  ║
║  Instant (Pattern Match):  1,240 requests    $0.00         ║
║  Local LLM:                   892 requests    $0.00         ║
║  Cloud Fast (Haiku/Flash):    784 requests    $0.08         ║
║  Cloud Powerful (Sonnet):     211 requests    $1.39         ║
║                                                              ║
║  TOP COST DRIVERS                                           ║
║  ─────────────────────────────────────────────────────────  ║
║  1. Complex Conversations:    $0.89  (60%)                  ║
║  2. Memory-Intensive Queries: $0.31  (21%)                  ║
║  3. Ambiguous Commands:       $0.19  (13%)                  ║
║  4. Evolver Benchmarks:       $0.08  (5%)                   ║
║                                                              ║
║  RECOMMENDATIONS                                             ║
║  ─────────────────────────────────────────────────────────  ║
║  • Improve routing rules for "ambiguous" category           ║
║  • Consider local Llama for memory queries                  ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
```

---

## Troubleshooting Guides

### Voice Pipeline Issues

#### Problem: Voice Commands Not Recognized

**Symptoms:**
- Wake word triggers but no response
- STT returns empty or incorrect transcription
- High error rate in voice pipeline metrics

**Diagnostic Steps:**

```bash
# 1. Check STT service health
docker logs faster-whisper-container --tail 50

# 2. Test STT directly
curl -X POST http://localhost:10300/api/speech-to-text \
  -H "Content-Type: audio/wav" \
  --data-binary @test_audio.wav

# 3. Check audio capture
arecord -l  # List audio devices
arecord -d 5 -f S16_LE -r 16000 test.wav  # Test recording

# 4. Review HA Assist debug
# Settings > Voice Assistants > [Your Assistant] > Debug
```

**Common Causes & Solutions:**

| Cause | Symptoms | Solution |
|-------|----------|----------|
| Audio gain too low | Whisper returns empty | Increase `volume_multiplier` in ESPHome config |
| Background noise | Transcription errors | Increase `noise_suppression_level` (max 4) |
| Model too small | Consistent misrecognition | Upgrade to `distil-whisper/distil-medium.en` |
| CPU overload | High latency | Check system load, consider offloading |

**ESPHome Voice Configuration Tuning:**

```yaml
# esphome voice device config
voice_assistant:
  noise_suppression_level: 3  # 0-4, higher = more aggressive
  auto_gain: 31dBFS           # Automatic gain control
  volume_multiplier: 2.0      # Audio amplification
```

#### Problem: Speaker Recognition Failures

**Symptoms:**
- Known speakers identified as "guest"
- Wrong family member identified
- Low confidence scores consistently

**Diagnostic Steps:**

```bash
# 1. Check speaker embeddings
sqlite3 /config/barnabeenet.db "SELECT name, embedding_count, last_updated FROM speaker_profiles;"

# 2. Test speaker verification
curl -X POST http://localhost:8080/api/speaker/verify \
  -H "Content-Type: audio/wav" \
  --data-binary @speaker_test.wav

# 3. Review confidence history
sqlite3 /config/barnabeenet.db "SELECT speaker_id, AVG(confidence) FROM audit_log WHERE timestamp > datetime('now', '-1 day') GROUP BY speaker_id;"
```

**Solutions:**

| Issue | Solution |
|-------|----------|
| Stale embeddings | Re-enroll speaker with fresh samples |
| Voice change (illness, aging) | Add supplementary enrollment samples |
| Noisy environment | Combine with presence sensor weighting |
| Similar voices (family) | Enable multi-factor auth for sensitive actions |

**Re-enrollment Procedure:**

1. Open BarnabeeNet Dashboard
2. Navigate to **Family Management > Speaker Profiles**
3. Select the affected speaker
4. Click **Re-enroll**
5. Record 5 varied phrases in different conditions
6. Verify confidence improvement over 24 hours

#### Problem: High End-to-End Latency

**Symptoms:**
- Commands take > 500ms to execute
- Noticeable delay between speech and response
- User complaints about "slow" assistant

**Diagnostic Steps:**

```bash
# 1. Identify bottleneck stage
curl http://localhost:8080/api/metrics/latency-breakdown

# Expected output:
# {
#   "stt": 145,
#   "speaker_id": 18,
#   "meta_agent": 12,
#   "action_agent": 67,
#   "tts": 89,
#   "total": 331
# }

# 2. Check system resources
htop  # CPU/memory usage
iostat -x 1  # Disk I/O

# 3. Check network latency (if cloud calls)
curl -w "@curl-format.txt" -o /dev/null -s "https://api.openrouter.ai/api/v1/models"
```

**Optimization Actions:**

| Bottleneck | Action |
|------------|--------|
| STT > 200ms | Use smaller model or enable streaming STT |
| Meta Agent > 20ms | Expand rule-based patterns, reduce LLM fallback |
| Action Agent > 100ms | Cache common HA states, optimize service calls |
| TTS > 150ms | Pre-cache common responses, use faster voice |
| Network > 100ms | Shift more processing to local models |

### Memory System Issues

#### Problem: Redis Memory Pressure

**Symptoms:**
- `redis_memory_used_bytes` exceeding limits
- OOM errors in logs
- Slow working memory operations

**Diagnostic Steps:**

```bash
# 1. Check Redis memory status
redis-cli INFO memory

# Key metrics:
# used_memory_human: Current memory usage
# used_memory_peak_human: Peak usage
# mem_fragmentation_ratio: Should be ~1.0

# 2. Analyze key distribution
redis-cli --bigkeys

# 3. Check TTL distribution
redis-cli DEBUG SLEEP 0  # Get key TTLs
```

**Solutions:**

```bash
# Clear expired keys manually
redis-cli SCAN 0 COUNT 1000 MATCH "session:*"

# Set memory limit and eviction policy
redis-cli CONFIG SET maxmemory 2gb
redis-cli CONFIG SET maxmemory-policy allkeys-lru

# Force memory defragmentation
redis-cli CONFIG SET activedefrag yes
```

#### Problem: SQLite Query Slowness

**Symptoms:**
- Memory retrieval latency > 50ms
- Semantic search timeouts
- Database locks

**Diagnostic Steps:**

```bash
# 1. Check database size
ls -lh /config/barnabeenet.db

# 2. Analyze query performance
sqlite3 /config/barnabeenet.db ".timer on"
sqlite3 /config/barnabeenet.db "EXPLAIN QUERY PLAN SELECT * FROM conversations WHERE speaker_id = 'thom' ORDER BY timestamp DESC LIMIT 10;"

# 3. Check for locks
sqlite3 /config/barnabeenet.db "PRAGMA busy_timeout;"
```

**Solutions:**

```sql
-- Rebuild indexes
REINDEX;

-- Vacuum database
VACUUM;

-- Analyze for query optimizer
ANALYZE;

-- Check and fix integrity
PRAGMA integrity_check;
```

### Home Assistant Integration Issues

#### Problem: HA Voice Assistant Pipeline Errors

**Symptoms:**
- "stt-stream-failed" errors
- "no_intent_match" responses
- Pipeline stuck in "responding" state

**Recent Known Issues (2025-2026):**

| HA Version | Issue | Workaround |
|------------|-------|------------|
| 2026.1.0 | OpenAI schema error for HassStartTimer | Wait for patch or disable timer intents |
| 2025.11.3 | Orphaned voice pipeline state | Delete and recreate assistant |
| 2025.8.0 | TTS hangs | Restart BarnabeeNet service (Kokoro runs in-process) |

**Debug Procedure:**

1. Open **Settings > Voice Assistants**
2. Select your assistant > **Debug**
3. Review the pipeline stages:
   - `stt-start` → `stt-end`: STT processing
   - `intent-start` → `intent-end`: Intent recognition
   - `tts-start` → `tts-end`: Speech synthesis

4. Check for error codes:
   - `stt-stream-failed`: Audio capture/processing issue
   - `no_intent_match`: Sentence not understood
   - `intent-failed`: HA action execution failed

**Pipeline Reset Procedure:**

```bash
# 1. Stop voice processing
ha core stop

# 2. Clear orphaned state
rm -rf /config/.storage/assist_pipeline

# 3. Restart
ha core start

# 4. Recreate assistant in UI
```

---

## Backup & Recovery

### Backup Strategy Overview

BarnabeeNet uses a **3-2-1 backup strategy**:
- **3** copies of data
- **2** different storage media
- **1** off-site backup

```
┌─────────────────────────────────────────────────────────────────┐
│                     BACKUP ARCHITECTURE                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │   Primary    │    │   Proxmox    │    │   Cloud      │      │
│  │   System     │───►│   Backup     │───►│   Backup     │      │
│  │  (Beelink)   │    │   (NAS)      │    │  (B2/GDrive) │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│        │                    │                    │              │
│        ▼                    ▼                    ▼              │
│    Live Data          Nightly VM           Weekly Sync         │
│                       Snapshots            to Cloud            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Home Assistant Backup (2025.1+)

Home Assistant 2025.1 introduced an enhanced backup system with automated scheduling:

**Configuration:**

1. Navigate to **Settings > System > Backups**
2. Configure automatic backups:
   - Schedule: Daily at 3:00 AM
   - Keep: Last 7 backups
   - Include: Full backup (config, addons, database)
3. Enable encryption with a strong password
4. Configure backup location (Google Drive, NAS, or Home Assistant Cloud)

**Manual Backup Trigger:**

```yaml
# Automation to backup before updates
automation:
  - alias: "Backup Before Update"
    trigger:
      - platform: homeassistant
        event: core_config_updated
    action:
      - service: backup.create
        data:
          name: "Pre-Update Backup {{ now().strftime('%Y-%m-%d') }}"
```

### Proxmox VM Backup

**Scheduled VM Backup Configuration:**

1. In Proxmox UI: **Datacenter > Backup**
2. Click **Add** to create backup job:

| Setting | Value |
|---------|-------|
| Node | beelink |
| Storage | NAS-backup (NFS mount) |
| Schedule | Daily at 4:00 AM |
| Selection Mode | Include selected VMs |
| VMs | Home Assistant (VM ID) |
| Mode | Snapshot |
| Compression | ZSTD (fast) |
| Retention | Keep last 7 |

**Manual Snapshot Before Changes:**

```bash
# Create snapshot via CLI
qm snapshot <VMID> pre-upgrade --description "Before BarnabeeNet update"

# List snapshots
qm listsnapshot <VMID>

# Rollback if needed
qm rollback <VMID> pre-upgrade
```

### Database-Specific Backups

#### SQLite Backup

```bash
#!/bin/bash
# sqlite_backup.sh - Run daily via cron

BACKUP_DIR="/backup/barnabeenet"
DATE=$(date +%Y%m%d_%H%M%S)
DB_PATH="/config/barnabeenet.db"

# Create backup with sqlite3 backup command (safe for live DB)
sqlite3 "$DB_PATH" ".backup '${BACKUP_DIR}/barnabeenet_${DATE}.db'"

# Compress
gzip "${BACKUP_DIR}/barnabeenet_${DATE}.db"

# Retain last 14 days
find "$BACKUP_DIR" -name "barnabeenet_*.db.gz" -mtime +14 -delete

echo "Backup completed: barnabeenet_${DATE}.db.gz"
```

#### Redis Backup

```bash
#!/bin/bash
# redis_backup.sh

BACKUP_DIR="/backup/redis"
DATE=$(date +%Y%m%d_%H%M%S)

# Trigger RDB save
redis-cli BGSAVE

# Wait for save to complete
while [ $(redis-cli LASTSAVE) == $(redis-cli LASTSAVE) ]; do
    sleep 1
done

# Copy RDB file
cp /var/lib/redis/dump.rdb "${BACKUP_DIR}/dump_${DATE}.rdb"

# Retain last 7 days
find "$BACKUP_DIR" -name "dump_*.rdb" -mtime +7 -delete
```

### Recovery Procedures

#### Full System Recovery

**Scenario:** Complete Beelink failure, need to restore to new hardware.

**Steps:**

1. **Install Proxmox VE on new hardware**
   ```bash
   # Download Proxmox VE ISO and install
   # Configure network with same IP as original Beelink
   ```

2. **Restore VM from Proxmox Backup**
   ```bash
   # Copy backup file to new Proxmox storage
   # In Proxmox UI: Storage > Backup > Restore
   # Select backup file, configure VM ID, restore
   ```

3. **Or restore via HA Backup**
   - Install fresh Home Assistant OS VM
   - During onboarding, select "Restore from backup"
   - Upload backup file or connect to cloud backup
   - Wait for restoration (may take 15-30 minutes)

4. **Verify services**
   ```bash
   # Check HA is running
   ha core info
   
   # Check BarnabeeNet integration
   ha integration info barnabeenet
   
   # Test voice pipeline
   # Speak test command and verify response
   ```

#### BarnabeeNet Database Recovery

**Scenario:** Corrupted SQLite database.

```bash
# 1. Stop BarnabeeNet
ha core stop

# 2. Attempt repair
sqlite3 /config/barnabeenet.db "PRAGMA integrity_check;"

# 3. If corrupted, restore from backup
cp /backup/barnabeenet/barnabeenet_latest.db.gz /config/
gunzip /config/barnabeenet_latest.db.gz
mv /config/barnabeenet_latest.db /config/barnabeenet.db

# 4. Or rebuild if no backup
sqlite3 /config/barnabeenet_new.db < /config/custom_components/barnabeenet/schema.sql
mv /config/barnabeenet.db /config/barnabeenet_corrupted.db
mv /config/barnabeenet_new.db /config/barnabeenet.db

# 5. Restart
ha core start
```

---

## Upgrade Procedures

### Home Assistant Core Upgrade

**Pre-Upgrade Checklist:**

- [ ] Create manual backup
- [ ] Create Proxmox snapshot
- [ ] Review release notes for breaking changes
- [ ] Check BarnabeeNet compatibility
- [ ] Schedule upgrade during low-usage period
- [ ] Notify family members

**Upgrade Procedure:**

```bash
# 1. Create snapshot
qm snapshot <VMID> pre-upgrade-$(date +%Y%m%d)

# 2. Trigger backup
ha backup create --name "Pre-upgrade $(date +%Y-%m-%d)"

# 3. Update via CLI or UI
ha core update

# 4. Monitor logs during startup
ha core logs --follow

# 5. Verify critical functions
#    - Voice commands work
#    - Automations running
#    - BarnabeeNet dashboard accessible
```

**Rollback Procedure:**

```bash
# If issues detected within first hour:

# Option 1: HA Rollback (if supported)
ha core rollback

# Option 2: Proxmox snapshot rollback
qm rollback <VMID> pre-upgrade-YYYYMMDD

# Option 3: Restore from backup
# (Re-install HA and restore from backup)
```

### BarnabeeNet Component Upgrade

**Upgrade Procedure:**

```bash
# 1. Pull latest from repository
cd /config/custom_components/barnabeenet
git fetch origin
git checkout v3.1.0  # Or latest version tag

# 2. Install updated requirements
pip install -r requirements.txt --break-system-packages

# 3. Run database migrations
python migrations/migrate.py

# 4. Restart Home Assistant
ha core restart

# 5. Verify integration
ha integration info barnabeenet
```

### LLM Model Updates

**Local Model Update (Gaming PC):**

```bash
# 1. Download new model
ollama pull llama3.1:8b-q4_K_M

# 2. Test locally
ollama run llama3.1:8b-q4_K_M "Test prompt for BarnabeeNet"

# 3. Update BarnabeeNet config
# Edit /config/barnabeenet/config.yaml
# models:
#   local_default: "llama3.1:8b-q4_K_M"

# 4. Restart integration
ha integration reload barnabeenet

# 5. Benchmark new model
curl -X POST http://localhost:8080/api/benchmark \
  -H "Content-Type: application/json" \
  -d '{"model": "llama3.1:8b-q4_K_M", "prompts": "standard"}'
```

### Proxmox Upgrade

**Pre-Upgrade:**

1. Backup all VMs and containers
2. Review Proxmox release notes
3. Ensure sufficient disk space (>10GB free)

**Upgrade Procedure:**

```bash
# 1. Update package lists
apt update

# 2. Perform distribution upgrade
apt dist-upgrade

# 3. Reboot if kernel updated
reboot

# 4. Verify all VMs start correctly
qm list
```

---

## Incident Response

### Incident Classification

| Severity | Description | Response Time | Examples |
|----------|-------------|---------------|----------|
| P1 - Critical | Complete system outage | < 15 minutes | HA unreachable, all voice commands fail |
| P2 - High | Major feature degraded | < 1 hour | Voice recognition < 50%, security features down |
| P3 - Medium | Minor feature impact | < 4 hours | Single agent slow, one device unresponsive |
| P4 - Low | Cosmetic/minor | Next business day | Dashboard display issue, non-critical logs |

### Incident Response Playbook

#### Phase 1: Detection & Assessment (0-5 minutes)

```
┌─────────────────────────────────────────────────────────────────┐
│                    INCIDENT DETECTED                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. ACKNOWLEDGE ALERT                                           │
│     □ Note incident start time                                  │
│     □ Identify alerting system/metric                           │
│                                                                  │
│  2. ASSESS IMPACT                                               │
│     □ Which users affected?                                     │
│     □ Which features impacted?                                  │
│     □ Is this security-related?                                 │
│                                                                  │
│  3. CLASSIFY SEVERITY                                           │
│     □ P1: Total outage → Immediate action                       │
│     □ P2: Major degradation → Escalate                          │
│     □ P3: Minor issue → Schedule fix                            │
│                                                                  │
│  4. NOTIFY STAKEHOLDERS                                         │
│     □ Update family if voice control down                       │
│     □ Log incident in tracking system                           │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

#### Phase 2: Containment (5-15 minutes)

**Priority: Stop the bleeding, don't fix root cause yet.**

**Quick Containment Actions:**

| Symptom | Containment Action |
|---------|-------------------|
| HA unresponsive | Restart HA core: `ha core restart` |
| Voice pipeline stuck | Restart STT/TTS containers |
| High CPU/Memory | Identify and kill runaway process |
| LLM costs spiking | Disable cloud routing: set local_only mode |
| Security concern | Isolate affected component from network |

```bash
# Emergency restart sequence
ha core stop
docker restart distil-whisper redis  # Kokoro runs in-process with BarnabeeNet
ha core start
```

#### Phase 3: Diagnosis (15-60 minutes)

**Log Collection:**

```bash
# Collect all relevant logs
mkdir /tmp/incident_$(date +%Y%m%d_%H%M%S)
cd /tmp/incident_*

# Home Assistant logs
ha core logs > ha_core.log

# BarnabeeNet specific
grep -i barnabeenet /config/home-assistant.log > barnabeenet.log

# Docker container logs
docker logs distil-whisper > stt.log 2>&1
# Kokoro TTS logs are in BarnabeeNet logs (runs in-process)
docker logs redis > redis.log 2>&1

# System logs
dmesg > dmesg.log
journalctl -u proxmox* > proxmox.log
```

**Common Diagnostic Queries:**

```bash
# Check for OOM kills
dmesg | grep -i "out of memory"

# Check disk space
df -h

# Check process states
ps aux | grep -E "(python|whisper|kokoro)"

# Check network connectivity
ping -c 3 api.openrouter.ai
```

#### Phase 4: Resolution

**Document the fix as you implement it.**

```
Resolution Log Template:
------------------------
Incident ID: INC-2026-001
Start Time: 2026-01-16 14:30 UTC
Resolution Time: 2026-01-16 15:15 UTC
Duration: 45 minutes

Root Cause:
Redis memory limit reached due to conversation sessions not expiring.

Resolution Steps:
1. Cleared expired Redis keys manually
2. Increased maxmemory from 1GB to 2GB
3. Fixed TTL setting in session handler (was 0, should be 600)
4. Deployed fix to production

Verification:
- Voice commands working
- Memory usage stable at 45%
- No new alerts
```

#### Phase 5: Post-Incident Review

**Conduct within 48 hours of resolution.**

**Post-Incident Review Template:**

```markdown
# Post-Incident Review: INC-2026-001

## Summary
Brief description of what happened.

## Timeline
- 14:30 - Alert triggered: Redis memory > 95%
- 14:32 - On-call acknowledged alert
- 14:35 - Initial assessment: Redis OOM affecting voice pipeline
- 14:40 - Containment: Cleared 50% of keys, service restored
- 14:55 - Root cause identified: Missing TTL on session keys
- 15:10 - Permanent fix deployed
- 15:15 - Incident closed

## Root Cause
Session keys were being created without TTL, causing unbounded memory growth.

## Impact
- Duration: 45 minutes
- Users affected: All family members
- Features impacted: Voice commands (100% failure during peak)

## What Went Well
- Alert fired promptly
- Containment was quick
- Root cause found efficiently

## What Could Be Improved
- Missing monitoring for key count growth
- No automated key cleanup job

## Action Items
| Action | Owner | Due Date |
|--------|-------|----------|
| Add Redis key count monitoring | Thom | 2026-01-20 |
| Implement automated TTL audit | Thom | 2026-01-25 |
| Update runbook with Redis procedures | Thom | 2026-01-18 |
```

### Common Incident Playbooks

#### Playbook: Voice Pipeline Complete Failure

```
TRIGGER: Voice commands return no response for > 2 minutes

IMMEDIATE ACTIONS:
1. Check HA status: ha core info
2. Check STT container: docker ps | grep whisper
3. Check TTS (in-process): Check BarnabeeNet logs for Kokoro errors

RESTART SEQUENCE:
docker restart distil-whisper
# Kokoro restarts with BarnabeeNet
ha core restart

VERIFICATION:
- Test wake word activation
- Test simple command ("What time is it?")
- Monitor barnabeenet_stt_error_rate for 5 minutes

ESCALATION:
If restart doesn't resolve, check:
- Audio device connectivity (arecord -l)
- Disk space on Beelink
- Recent HA or BarnabeeNet updates
```

#### Playbook: LLM Cost Spike

```
TRIGGER: barnabeenet_daily_cost_usd > $0.80

IMMEDIATE ACTIONS:
1. Enable local-only mode in BarnabeeNet config
2. Check OpenRouter activity dashboard for anomaly

INVESTIGATION:
1. Identify cost driver:
   - Which model?
   - Which agent?
   - What time period?

2. Common causes:
   - Runaway conversation loop
   - Evolver benchmark left running
   - Misconfigured routing (everything to Sonnet)

RESOLUTION:
1. Fix routing configuration
2. Add budget caps if missing
3. Reset daily cost counter if false positive

PREVENTION:
- Set hard daily limit in OpenRouter
- Add per-model cost alerts
```

---

## Routine Maintenance

### Daily Tasks (Automated)

| Task | Schedule | Method |
|------|----------|--------|
| HA backup | 03:00 | HA built-in scheduler |
| Log rotation | 04:00 | logrotate |
| Cost report check | 09:00 | Grafana scheduled report |
| Health check ping | Every 5 min | Uptime monitor |

### Weekly Tasks

| Task | Day | Procedure |
|------|-----|-----------|
| Review Grafana dashboards | Monday | Check for anomalies, clear false alerts |
| SQLite VACUUM | Wednesday | `sqlite3 barnabeenet.db "VACUUM;"` |
| Proxmox VM backup verification | Friday | Test restore of latest backup |
| Update check | Sunday | Review pending HA/component updates |

**Weekly Review Checklist:**

```markdown
## Weekly Maintenance Review - Week of YYYY-MM-DD

### System Health
- [ ] All services running (HA, Redis, STT, TTS)
- [ ] No critical alerts in past 7 days
- [ ] Memory usage stable (< 80%)
- [ ] Disk usage acceptable (< 80%)

### Voice Pipeline
- [ ] Average latency < 500ms
- [ ] Error rate < 5%
- [ ] Speaker recognition accuracy > 90%

### Cost Tracking
- [ ] Weekly spend within budget
- [ ] No unusual model usage patterns
- [ ] OpenRouter credits sufficient

### Backups
- [ ] Daily HA backups successful
- [ ] Weekly Proxmox backup verified
- [ ] Oldest backup within retention policy

### Updates
- [ ] HA updates reviewed (not necessarily applied)
- [ ] Security advisories checked
- [ ] BarnabeeNet repo checked for updates
```

### Monthly Tasks

| Task | Procedure |
|------|-----------|
| Full backup test restore | Restore to test environment, verify functionality |
| Speaker profile review | Check for profiles needing re-enrollment |
| Cost analysis | Generate monthly cost report, identify optimizations |
| Performance baseline | Compare current metrics to previous month |
| Security audit | Review access logs, check for anomalies |

### Quarterly Tasks

| Task | Procedure |
|------|-----------|
| Model benchmark | Compare current models to newer alternatives |
| Evolver review | Evaluate proposed optimizations |
| Documentation update | Ensure runbook reflects current system |
| Disaster recovery drill | Practice full system restoration |

---

## Health Checks & Runbooks

### Quick Health Check Script

```bash
#!/bin/bash
# barnabeenet_health_check.sh

echo "═══════════════════════════════════════════════════"
echo "          BARNABEENET HEALTH CHECK                  "
echo "          $(date)"
echo "═══════════════════════════════════════════════════"

# Check Home Assistant
echo -e "\n[Home Assistant]"
if ha core info > /dev/null 2>&1; then
    echo "  ✓ HA Core: Running"
    HA_VERSION=$(ha core info | grep version | awk '{print $2}')
    echo "  ✓ Version: $HA_VERSION"
else
    echo "  ✗ HA Core: NOT RUNNING"
fi

# Check Docker containers
echo -e "\n[Docker Containers]"
for container in distil-whisper redis; do
    if docker ps | grep -q $container; then
        echo "  ✓ $container: Running"
    else
        echo "  ✗ $container: NOT RUNNING"
    fi
done

# Check Redis
echo -e "\n[Redis]"
REDIS_MEM=$(redis-cli INFO memory | grep used_memory_human | cut -d: -f2 | tr -d '\r')
REDIS_KEYS=$(redis-cli DBSIZE | awk '{print $2}')
echo "  Memory: $REDIS_MEM"
echo "  Keys: $REDIS_KEYS"

# Check Disk Space
echo -e "\n[Disk Space]"
df -h / | tail -1 | awk '{print "  Used: " $5 " (" $3 " of " $2 ")"}'

# Check Memory
echo -e "\n[System Memory]"
free -h | grep Mem | awk '{print "  Used: " $3 " of " $2 " (" int($3/$2*100) "%)"}'

# Check Voice Pipeline Latency (if metrics available)
echo -e "\n[Voice Pipeline]"
# This would query Prometheus/internal metrics
# curl -s http://localhost:8080/api/metrics/latency | jq '.total_latency_ms'

echo -e "\n═══════════════════════════════════════════════════"
echo "Health check complete"
```

### Service Restart Runbook

```bash
#!/bin/bash
# restart_services.sh [all|voice|memory|ha]

case "$1" in
    all)
        echo "Restarting all BarnabeeNet services..."
        docker restart distil-whisper redis
        ha core restart  # This also restarts Kokoro TTS (in-process)
        ;;
    voice)
        echo "Restarting voice pipeline..."
        docker restart distil-whisper
        ha core restart  # Kokoro TTS runs in-process
        ;;
    memory)
        echo "Restarting memory services..."
        docker restart redis
        ;;
    ha)
        echo "Restarting Home Assistant..."
        ha core restart
        ;;
    *)
        echo "Usage: $0 {all|voice|memory|ha}"
        exit 1
        ;;
esac

echo "Waiting for services to stabilize..."
sleep 30

echo "Running health check..."
./barnabeenet_health_check.sh
```

### Emergency Contact Card

```
╔══════════════════════════════════════════════════════════════╗
║                 BARNABEENET EMERGENCY CARD                    ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  CRITICAL COMMANDS                                           ║
║  ─────────────────────────────────────────────────────────  ║
║  Restart HA:        ha core restart                         ║
║  Restart Voice:     docker restart distil-whisper && ha core restart  ║
║  Restart All:       ./restart_services.sh all               ║
║  Health Check:      ./barnabeenet_health_check.sh           ║
║                                                              ║
║  ROLLBACK                                                    ║
║  ─────────────────────────────────────────────────────────  ║
║  Proxmox Snapshot:  qm rollback <VMID> <snapshot-name>      ║
║  HA Rollback:       ha core rollback                        ║
║                                                              ║
║  DASHBOARDS                                                  ║
║  ─────────────────────────────────────────────────────────  ║
║  Grafana:           http://beelink:3000                     ║
║  HA Dashboard:      http://homeassistant.local:8123         ║
║  BarnabeeNet:       http://homeassistant.local:8123/barnabee║
║  OpenRouter:        https://openrouter.ai/activity          ║
║                                                              ║
║  LOGS                                                        ║
║  ─────────────────────────────────────────────────────────  ║
║  HA Logs:           ha core logs --follow                   ║
║  STT Logs:          docker logs faster-whisper --follow     ║
║  System Logs:       journalctl -f                           ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
```

---

## Appendix A: Metric Reference

### BarnabeeNet Custom Metrics

| Metric Name | Type | Description |
|-------------|------|-------------|
| `barnabeenet_requests_total` | Counter | Total requests processed |
| `barnabeenet_requests_by_agent` | Counter | Requests per agent type |
| `barnabeenet_stt_latency_ms` | Histogram | STT processing time |
| `barnabeenet_tts_latency_ms` | Histogram | TTS processing time |
| `barnabeenet_total_latency_ms` | Histogram | End-to-end latency |
| `barnabeenet_speaker_id_confidence` | Gauge | Latest speaker recognition confidence |
| `barnabeenet_llm_requests_total` | Counter | LLM API calls |
| `barnabeenet_llm_tokens_total` | Counter | Total tokens consumed |
| `barnabeenet_daily_cost_usd` | Gauge | Estimated daily LLM cost |
| `barnabeenet_memory_retrieval_latency_ms` | Histogram | Semantic search time |
| `barnabeenet_active_sessions` | Gauge | Current conversation sessions |

---

## Appendix B: Configuration File Locations

| File | Location | Purpose |
|------|----------|---------|
| HA Configuration | `/config/configuration.yaml` | Home Assistant core config |
| BarnabeeNet Config | `/config/barnabeenet/config.yaml` | Integration settings |
| SQLite Database | `/config/barnabeenet.db` | Long-term memory |
| Speaker Profiles | `/config/barnabeenet/speakers/` | Speaker embeddings |
| Prometheus Config | `/etc/prometheus/prometheus.yml` | Metrics collection |
| Grafana Dashboards | `/var/lib/grafana/dashboards/` | Visualization |
| Alert Rules | `/etc/prometheus/alerts.yml` | Alerting configuration |

---

## Document History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-01-16 | Initial operations runbook |

---

*This runbook should be reviewed and updated quarterly, or whenever significant system changes occur.*
