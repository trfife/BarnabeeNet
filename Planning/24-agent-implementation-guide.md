# Area 24: Agent Implementation Guide

**Version:** 2.0  
**Status:** Implementation Ready  
**Purpose:** Step-by-step guide for AI coding agents (Cursor/Copilot) to build BarnabeeNet V2  

---

## 1. Overview

### 1.1 What This Document Is

This is an executable guide for an AI coding agent to implement BarnabeeNet V2 from scratch. The agent should **complete the entire project autonomously**, stopping only at 4 major milestones for human testing.

**Key principle: The agent is empowered to complete this project.** Don't pause for permission. Don't wait for approval on phases. Build it, test it, move on. Only stop when you genuinely need something from the human (credentials) or when a milestone is ready for human testing.

### 1.2 Critical Design Philosophy: Graceful Fallbacks

**The system should NEVER say "I don't know" or fail ungracefully.**

When implementing NLU, entity resolution, or command execution, follow this principle:

```
GRACEFUL FALLBACK PRINCIPLE:

When the fast path fails (pattern match, exact entity match, etc.):
1. DO NOT return an error like "I don't know what you mean"
2. DO NOT ask "can you be more specific?"
3. INSTEAD: Escalate to LLM with FULL CONTEXT

The LLM has access to:
- All Home Assistant entities
- User's current location/area
- Recent commands from this user
- The original utterance and intent

With this context, the LLM can ALWAYS make an intelligent guess.

Example:
  User: "turn on the liv room lamp"
  Fast path: No entity match for "liv room lamp"
  
  BAD: "I couldn't find a device called liv room lamp"
  
  GOOD: LLM sees all entities, realizes "liv room" = "living room",
        finds light.living_room_lamp, executes it, and responds:
        "I've turned on the living room lamp."
        
        Then logs this resolution for self-improvement.
```

This applies to:
- Entity resolution (Area 03, 04)
- Intent classification fallback (Area 03)
- Command execution (Area 04)
- Memory retrieval (Area 05)

See `03-intent-classification.md` section 9.3 for implementation details.

This guide includes:
- Exact commands to run
- When to stop (only 4 milestones + credential needs)
- Git workflow and commit standards
- Testing requirements before proceeding
- File structure expectations
- How to verify each step succeeded

### 1.2 Agent Operating Principles

```
GOLDEN RULES FOR THE AGENT:
1. BE AUTONOMOUS - complete phases without waiting for approval
2. TRACK PROGRESS - update PROGRESS.md after every step
3. ALWAYS run tests after implementing a feature
4. COMMIT frequently with descriptive messages  
5. FIX issues yourself - only stop if stuck after 3+ attempts
6. CHECK linter errors after every file edit
7. VERIFY services are running before testing them
8. READ error messages carefully - research and fix, don't retry blindly
9. MAKE reasonable decisions - don't stop for every small choice
10. STOP at the 4 major milestones so human can test
11. STOP if you need credentials/secrets
12. ON RESUME - read PROGRESS.md first, continue where left off
```

### 1.3 Progress Tracking

**The agent MUST maintain a progress log at `/opt/barnabee-v2/PROGRESS.md`**

Update this file after completing each step. This allows:
- Resuming after interruptions
- Human visibility into status
- New agent sessions to continue where the last left off

```markdown
# BarnabeeNet V2 - Build Progress

## Current Status
**Phase:** 1B  
**Step:** Voice pipeline - TTS implementation  
**Started:** 2026-01-27 10:30 UTC  
**Last Updated:** 2026-01-27 14:45 UTC

## Completed
- [x] Phase 0: Environment setup (2026-01-27 10:30)
- [x] Phase 1A: Core data layer (2026-01-27 12:15)
  - [x] SQLite schema
  - [x] Redis session store
  - [x] Memory repository
  - [x] FTS5 search
  - [x] Tests passing (47/47)
- [ ] Phase 1B: Voice pipeline (IN PROGRESS)
  - [x] Pipecat dependencies
  - [x] Audio transport
  - [x] Wake word detection
  - [x] STT (Parakeet)
  - [ ] TTS (Kokoro) ← CURRENT
  - [ ] Pipeline orchestrator
  - [ ] Integration tests

## Blocked / Waiting
(none)

## Issues Encountered
- 2026-01-27 11:20: sqlite-vss install failed on first try, fixed by installing build-essential
- 2026-01-27 13:45: Parakeet model download took 15 minutes (2.1GB)

## Next Steps
1. Complete TTS implementation
2. Build pipeline orchestrator
3. Write integration tests
4. MILESTONE 1 - ready for human testing

## Credentials Status
- [x] None needed yet
- [ ] HA_TOKEN (needed Phase 2B)
- [ ] AZURE_OPENAI_* (needed Phase 2A)
```

**Update rules:**
1. Update `Current Status` section whenever you start a new step
2. Check off items in `Completed` as you finish them
3. Add timestamps to major completions
4. Log any issues in `Issues Encountered`
5. Update `Next Steps` to show what's coming
6. Commit PROGRESS.md with each significant update

**On session start, ALWAYS:**
1. Read PROGRESS.md first (if it exists)
2. Continue from where the last session left off
3. Don't restart completed phases

### 1.4 Check-In Protocol

The agent should be **autonomous by default**. Only stop when you genuinely cannot proceed.

| Situation | Agent Action |
|-----------|--------------|
| Phase complete, tests pass | **CONTINUE** to next phase. Log completion. |
| Phase complete, tests fail | Fix the tests, then continue. |
| Need credentials/secrets | **STOP** - cannot proceed without them |
| Stuck after 3+ different attempts | **STOP** - need human help |
| Major milestone ready for human testing | **STOP** - let human verify |
| Ambiguous requirement with big impact | **STOP** - need clarification |

**Major Milestones (stop for human testing):**
1. End of Phase 1: Voice in → text → voice out works
2. End of Phase 2: Voice commands control Home Assistant  
3. End of Phase 4: Full system working end-to-end

**DO NOT stop for:**
- Starting a new phase
- Completing a sub-step
- Minor decisions with obvious answers
- Progress updates (just log them)

---

## 2. Environment Setup

### 2.1 Agent Access Verification (MUST RUN FIRST)

**Before doing ANYTHING else, the agent MUST verify it has the access needed to work autonomously.**

Run these checks sequentially. If ANY critical check fails, STOP and tell the human exactly what to fix.

```bash
echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║         Phase 0: Agent Access Verification                        ║"
echo "╚══════════════════════════════════════════════════════════════════╝"

CRITICAL_FAIL=0

# === CRITICAL: Agent Access Checks ===

# 1. Passwordless sudo (CRITICAL)
echo -n "Checking passwordless sudo... "
if sudo -n true 2>/dev/null; then
  echo "✅ PASS"
else
  echo "❌ FAIL"
  echo ""
  echo "🛑 STOP: Passwordless sudo is required for the agent to work autonomously."
  echo ""
  echo "FIX: Run these commands as root or with sudo:"
  echo "  sudo visudo -f /etc/sudoers.d/\$USER"
  echo "  # Add this line: \$USER ALL=(ALL) NOPASSWD: ALL"
  echo ""
  CRITICAL_FAIL=1
fi

# 2. Docker without sudo (CRITICAL)
echo -n "Checking Docker access... "
if docker ps >/dev/null 2>&1; then
  echo "✅ PASS"
else
  echo "❌ FAIL"
  echo ""
  echo "🛑 STOP: Cannot run Docker commands without sudo."
  echo ""
  echo "FIX: Add user to docker group:"
  echo "  sudo usermod -aG docker \$USER"
  echo "  newgrp docker  # or log out and back in"
  echo ""
  CRITICAL_FAIL=1
fi

# 3. /opt/barnabee-v2 writable (CRITICAL)
echo -n "Checking /opt/barnabee-v2 access... "
mkdir -p /opt/barnabee-v2 2>/dev/null
if touch /opt/barnabee-v2/.writetest 2>/dev/null && rm /opt/barnabee-v2/.writetest; then
  echo "✅ PASS"
else
  echo "❌ FAIL"
  echo ""
  echo "🛑 STOP: Cannot write to /opt/barnabee-v2"
  echo ""
  echo "FIX: Create directory with correct ownership:"
  echo "  sudo mkdir -p /opt/barnabee-v2"
  echo "  sudo chown -R \$USER:\$USER /opt/barnabee-v2"
  echo ""
  CRITICAL_FAIL=1
fi

# 4. Git identity (CRITICAL - will auto-fix if possible)
echo -n "Checking Git configuration... "
if git config user.name >/dev/null 2>&1 && git config user.email >/dev/null 2>&1; then
  echo "✅ PASS ($(git config user.name))"
else
  echo "⚠️  Not configured - attempting auto-fix..."
  git config --global user.name "Barnabee Builder"
  git config --global user.email "barnabee@local"
  git config --global init.defaultBranch main
  echo "   Set to: Barnabee Builder <barnabee@local>"
fi

# 5. Planning docs accessible (CRITICAL)
echo -n "Checking planning documents... "
if [ -f /home/thom/projects/Planning/00-v2-summary.md ] && [ -f /home/thom/projects/Planning/24-agent-implementation-guide.md ]; then
  DOCCOUNT=$(ls /home/thom/projects/Planning/*.md 2>/dev/null | wc -l)
  echo "✅ PASS ($DOCCOUNT documents)"
else
  echo "❌ FAIL"
  echo ""
  echo "🛑 STOP: Cannot find planning documents"
  echo ""
  echo "Expected location: /home/thom/projects/Planning/"
  echo ""
  CRITICAL_FAIL=1
fi

# 6. Internet connectivity (CRITICAL)
echo -n "Checking internet access... "
if curl -s --connect-timeout 5 https://pypi.org >/dev/null; then
  echo "✅ PASS"
else
  echo "❌ FAIL"
  echo ""
  echo "🛑 STOP: No internet access - cannot download dependencies"
  echo ""
  CRITICAL_FAIL=1
fi

# === Check result ===
echo ""
if [ "$CRITICAL_FAIL" -eq 1 ]; then
  echo "╔══════════════════════════════════════════════════════════════════╗"
  echo "║  ❌ CRITICAL CHECKS FAILED - Cannot proceed                      ║"
  echo "║                                                                   ║"
  echo "║  Fix the issues above and tell me: 'Fixed. Continue.'            ║"
  echo "╚══════════════════════════════════════════════════════════════════╝"
  exit 1
fi

echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║  ✅ All agent access checks passed - proceeding with build       ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
```

**Agent action:** If CRITICAL_FAIL is set, STOP IMMEDIATELY and report the exact failure and fix instructions to the human. Do not proceed until they confirm the fix.

### 2.2 Infrastructure Prerequisites Check

After agent access is verified, check the build environment:

```bash
echo "=== Infrastructure Check ==="

# 1. Python version (CRITICAL)
PYVER=$(python3 --version 2>&1 | grep -oP '\d+\.\d+')
echo -n "Python: $PYVER - "
if [[ "$(echo "$PYVER >= 3.11" | bc -l)" -eq 1 ]]; then
  echo "✅ OK"
else
  echo "❌ FAIL - Python 3.11+ required"
  echo "FIX: Install Python 3.11+"
  exit 1
fi

# 2. Node version (CRITICAL)
NODEVER=$(node --version 2>&1 | grep -oP '\d+' | head -1)
echo -n "Node: v$NODEVER - "
if [ "$NODEVER" -ge 20 ]; then
  echo "✅ OK"
else
  echo "❌ FAIL - Node 20+ required"
  echo "FIX: Install Node.js 20+"
  exit 1
fi

# 3. Docker (CRITICAL)
DOCKERVER=$(docker --version 2>&1 | grep -oP '\d+' | head -1)
echo -n "Docker: v$DOCKERVER - "
if [ "$DOCKERVER" -ge 24 ]; then
  echo "✅ OK"
else
  echo "⚠️  v24+ recommended, found v$DOCKERVER"
fi

# 4. Docker Compose
docker compose version >/dev/null 2>&1 && echo "Docker Compose: ✅ OK" || echo "Docker Compose: ❌ FAIL"

# 5. Git
git --version >/dev/null 2>&1 && echo "Git: ✅ OK" || echo "Git: ❌ FAIL"

# 6. Disk space
DISKFREE=$(df /opt | tail -1 | awk '{print $4}')
echo -n "Disk space: $(df -h /opt | tail -1 | awk '{print $4}') - "
if [ "$DISKFREE" -gt 50000000 ]; then
  echo "✅ OK"
else
  echo "⚠️  Low space (50GB+ recommended)"
fi

# 7. Python venv and pip
python3 -m venv --help >/dev/null 2>&1 && echo "Python venv: ✅ OK" || echo "Python venv: ❌ FAIL - install python3-venv"
python3 -m pip --version >/dev/null 2>&1 && echo "pip: ✅ OK" || echo "pip: ❌ FAIL"

echo "=== Infrastructure Check Complete ==="
```

**Agent action:** If any critical check fails, STOP and report to human.

### 2.3 SSH to Beast (GPU Server) - Verify if Needed

```bash
echo "=== Beast GPU Server Check ==="

# Check if Beast is reachable
echo -n "Beast reachable: "
if ping -c 1 -W 2 beast.local >/dev/null 2>&1; then
  echo "✅ Yes"
  
  # Check SSH access
  echo -n "SSH access: "
  if ssh -o BatchMode=yes -o ConnectTimeout=5 beast.local "true" 2>/dev/null; then
    echo "✅ Passwordless"
    
    # Check GPU
    echo -n "GPU status: "
    ssh beast.local "nvidia-smi --query-gpu=name --format=csv,noheader" 2>/dev/null || echo "❌ Cannot query GPU"
    
    # Check Docker on Beast
    echo -n "Docker on Beast: "
    ssh beast.local "docker ps" >/dev/null 2>&1 && echo "✅ OK" || echo "⚠️  May need sudo"
  else
    echo "⚠️  Needs password - GPU deployment may require manual intervention"
    echo "   FIX: Run 'ssh-copy-id beast.local' to enable passwordless SSH"
  fi
else
  echo "⚠️  Not reachable (OK if building on same machine)"
fi

echo "=== Beast Check Complete ==="
```

**Note:** If Beast SSH requires a password, the agent will need to STOP when deploying GPU services and ask the human to either:
1. Set up SSH key auth: `ssh-copy-id beast.local`
2. Manually run the GPU service deployment commands on Beast

### 2.4 Repository Setup

```bash
# Create project directory
mkdir -p /opt/barnabee-v2
cd /opt/barnabee-v2

# Initialize git repository
git init
git branch -M main

# Create initial structure
mkdir -p src/barnabee/{api,voice,nlu,memory,ha,response,dashboard,workers}
mkdir -p src/barnabee/{sessions,gpu,cache,quality,connections}
mkdir -p tests/{unit,integration,e2e}
mkdir -p scripts/{deploy,migrate,maintenance}
mkdir -p config
mkdir -p schema
mkdir -p docs

# Create initial files
touch src/barnabee/__init__.py
touch src/barnabee/api/__init__.py
touch src/barnabee/voice/__init__.py
touch src/barnabee/nlu/__init__.py
touch src/barnabee/memory/__init__.py
touch src/barnabee/ha/__init__.py
touch src/barnabee/response/__init__.py

# Create pyproject.toml
cat > pyproject.toml << 'EOF'
[project]
name = "barnabee"
version = "2.0.0"
description = "BarnabeeNet V2 - Family Voice Assistant"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.109.0",
    "uvicorn[standard]>=0.27.0",
    "pydantic>=2.5.0",
    "httpx>=0.26.0",
    "redis>=5.0.0",
    "arq>=0.26.0",
    "structlog>=24.1.0",
    "python-dotenv>=1.0.0",
    "prometheus-client>=0.19.0",
    "opentelemetry-api>=1.22.0",
    "opentelemetry-sdk>=1.22.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=4.1.0",
    "ruff>=0.1.0",
    "mypy>=1.8.0",
    "pre-commit>=3.6.0",
]
gpu = [
    "torch>=2.1.0",
    "transformers>=4.36.0",
    "sentence-transformers>=2.2.0",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.mypy]
python_version = "3.11"
strict = true
EOF

# Create .gitignore
cat > .gitignore << 'EOF'
__pycache__/
*.py[cod]
.env
.env.local
*.db
*.db-journal
.venv/
venv/
node_modules/
dist/
build/
*.egg-info/
.coverage
htmlcov/
.pytest_cache/
.mypy_cache/
.ruff_cache/
*.log
EOF

# Initial commit
git add .
git commit -m "$(cat <<'EOF'
Initial project structure

- Set up Python package structure with pyproject.toml
- Create directory layout for all major components
- Add development dependencies and tooling config
- Initialize test directories

EOF
)"

echo "✅ Repository initialized"
```

### 2.5 Virtual Environment Setup

```bash
cd /opt/barnabee-v2

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e ".[dev]"

# Verify installation
python -c "import fastapi; print(f'FastAPI {fastapi.__version__}')"

# Set up pre-commit hooks
cat > .pre-commit-config.yaml << 'EOF'
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.9
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.8.0
    hooks:
      - id: mypy
        additional_dependencies: [pydantic>=2.0]
EOF

pre-commit install

git add .pre-commit-config.yaml
git commit -m "Add pre-commit hooks for code quality"

echo "✅ Virtual environment ready"
```

---

## 3. Git Workflow

### 3.1 Branching Strategy

```
main           - Production-ready code only
└── develop    - Integration branch for features
    ├── feature/area-01-core-data
    ├── feature/area-02-voice-pipeline
    └── feature/area-XX-*
```

**Agent commands:**

```bash
# Create develop branch (one time)
git checkout -b develop
git push -u origin develop

# Start a new feature area
git checkout develop
git pull
git checkout -b feature/area-01-core-data

# After completing a feature
git checkout develop
git merge --no-ff feature/area-01-core-data
git push

# Only merge to main after human approval of entire phase
git checkout main
git merge --no-ff develop
git push
```

### 3.2 Commit Standards

```bash
# Commit message format:
# <type>(<scope>): <description>
#
# Types: feat, fix, refactor, test, docs, chore
# Scope: area-XX, config, ci, deps

# Good examples:
git commit -m "feat(area-01): implement SQLite schema with FTS5"
git commit -m "test(area-01): add unit tests for memory CRUD"
git commit -m "fix(area-02): correct WebRTC connection timeout"
git commit -m "docs(area-01): add schema migration notes"

# Bad examples:
git commit -m "updates"              # Too vague
git commit -m "fixed stuff"          # Not descriptive
git commit -m "WIP"                  # Incomplete work shouldn't be committed
```

### 3.3 Commit Frequency

| Situation | Commit? |
|-----------|---------|
| File compiles/lints clean | YES |
| Tests pass for a component | YES, with test results |
| Before trying something risky | YES, as checkpoint |
| End of work session | YES, even if incomplete (use WIP: prefix) |
| After fixing a bug | YES |
| Mid-implementation, broken state | NO |

---

## 4. Testing Requirements

### 4.1 Test-Before-Proceed Policy

**AGENT RULE: Do not proceed to the next component until tests pass.**

```bash
# After implementing any component, run:
cd /opt/barnabee-v2
source .venv/bin/activate

# 1. Lint check
ruff check src/

# 2. Type check
mypy src/

# 3. Unit tests for the component
pytest tests/unit/test_<component>.py -v

# 4. Report results to human
echo "=== Test Results ==="
echo "Lint: [PASS/FAIL]"
echo "Types: [PASS/FAIL]"
echo "Tests: X passed, Y failed"
```

### 4.2 Test Coverage Requirements

| Phase | Coverage Target | Enforcement |
|-------|-----------------|-------------|
| Phase 1 (Infrastructure) | 80% | Must meet before Phase 2 |
| Phase 2 (Backbone) | 85% | Must meet before Phase 3 |
| Phase 3+ | 90% | Must meet before production |

```bash
# Run coverage report
pytest --cov=src/barnabee --cov-report=term-missing tests/

# Coverage must meet target before proceeding
```

### 4.3 Test File Structure

```
tests/
├── unit/
│   ├── test_db.py           # Area 01
│   ├── test_memory_repo.py  # Area 01
│   ├── test_voice.py        # Area 02
│   ├── test_intent.py       # Area 03
│   └── ...
├── integration/
│   ├── test_voice_pipeline.py
│   ├── test_ha_integration.py
│   └── ...
├── e2e/
│   ├── test_voice_command.py
│   └── ...
└── conftest.py              # Shared fixtures
```

---

## 5. Service Management

### 5.1 Docker Compose Structure

```yaml
# docker-compose.yml - Agent creates this in Phase 1
version: '3.8'

services:
  redis:
    image: redis:7.2-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 3

  api:
    build: 
      context: .
      dockerfile: Dockerfile.api
    ports:
      - "8000:8000"
    environment:
      - DATABASE_PATH=/data/barnabee.db
      - REDIS_URL=redis://redis:6379
    volumes:
      - ./data:/data
    depends_on:
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 10s
      timeout: 5s
      retries: 3

  # GPU services (on Beast only)
  gpu-services:
    build:
      context: .
      dockerfile: Dockerfile.gpu
    ports:
      - "8001:8001"
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    volumes:
      - ./models:/models

volumes:
  redis_data:
```

### 5.2 Starting/Stopping Services

```bash
# Start all services
docker compose up -d

# Check status
docker compose ps

# View logs
docker compose logs -f api

# Stop services
docker compose down

# Restart a specific service
docker compose restart api

# Rebuild and restart
docker compose up -d --build api
```

### 5.3 Verifying Services

**Agent must verify services are healthy before testing:**

```bash
#!/bin/bash
# scripts/verify-services.sh

echo "=== Service Verification ==="

# Check Redis
redis-cli ping && echo "✅ Redis OK" || echo "❌ Redis DOWN"

# Check API
curl -s http://localhost:8000/health | jq . && echo "✅ API OK" || echo "❌ API DOWN"

# Check GPU services (if applicable)
curl -s http://localhost:8001/health | jq . && echo "✅ GPU OK" || echo "⚠️ GPU not running"

echo "=== Verification Complete ==="
```

---

## 6. Persistent Processes (Systemd)

### 6.1 Creating Systemd Services

After Docker Compose is working, create systemd services for auto-start:

```bash
# Create systemd service file
sudo cat > /etc/systemd/system/barnabee.service << 'EOF'
[Unit]
Description=BarnabeeNet V2
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/barnabee-v2
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down
ExecReload=/usr/bin/docker compose restart

[Install]
WantedBy=multi-user.target
EOF

# Enable auto-start
sudo systemctl daemon-reload
sudo systemctl enable barnabee.service

# Start/stop/restart
sudo systemctl start barnabee
sudo systemctl stop barnabee
sudo systemctl restart barnabee

# Check status
sudo systemctl status barnabee
```

### 6.2 Log Rotation

```bash
# Create logrotate config
sudo cat > /etc/logrotate.d/barnabee << 'EOF'
/opt/barnabee-v2/logs/*.log {
    daily
    rotate 14
    compress
    delaycompress
    missingok
    notifempty
    create 0640 barnabee barnabee
}
EOF
```

### 6.3 Cron Jobs for Maintenance

```bash
# Edit crontab
crontab -e

# Add maintenance tasks
# Database maintenance - daily at 3am
0 3 * * * /opt/barnabee-v2/scripts/maintenance/db_maintenance.py >> /opt/barnabee-v2/logs/maintenance.log 2>&1

# Backup verification - weekly
0 4 * * 0 /opt/barnabee-v2/scripts/maintenance/verify_backup.sh >> /opt/barnabee-v2/logs/backup-verify.log 2>&1

# Model warmup after reboot
@reboot sleep 60 && /opt/barnabee-v2/scripts/warmup.sh >> /opt/barnabee-v2/logs/warmup.log 2>&1
```

---

## 7. Implementation Phases (Detailed)

### Phase 0: Setup & Verification
**Duration:** ~30 minutes  
**Human Check-in:** Only if access checks fail

```
┌─────────────────────────────────────────────────────────────────────┐
│ PHASE 0: Setup & Verification                                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│ □ Step 0.0: CHECK FOR RESUME (always do this first!)                │
│   └── If /opt/barnabee-v2/PROGRESS.md exists:                       │
│       └── READ IT and resume from where left off                    │
│       └── Skip the rest of Phase 0                                  │
│   └── If not: Continue with fresh setup                             │
│                                                                      │
│ ═══════════════════════════════════════════════════════════════════ │
│ AGENT ACCESS VERIFICATION (Section 2.1) - STOP IF ANY FAIL          │
│ ═══════════════════════════════════════════════════════════════════ │
│                                                                      │
│ □ Step 0.1: Passwordless sudo                                       │
│   └── Run: sudo -n true                                             │
│   └── If FAIL: STOP - tell human to configure sudoers               │
│                                                                      │
│ □ Step 0.2: Docker without sudo                                     │
│   └── Run: docker ps                                                │
│   └── If FAIL: STOP - tell human to add user to docker group        │
│                                                                      │
│ □ Step 0.3: /opt/barnabee-v2 writable                               │
│   └── Run: mkdir -p /opt/barnabee-v2 && touch /opt/barnabee-v2/.test│
│   └── If FAIL: STOP - tell human to fix permissions                 │
│                                                                      │
│ □ Step 0.4: Git identity configured                                 │
│   └── Run: git config user.name && git config user.email            │
│   └── If FAIL: Auto-configure with defaults, continue               │
│                                                                      │
│ □ Step 0.5: Internet connectivity                                   │
│   └── Run: curl -s https://pypi.org                                 │
│   └── If FAIL: STOP - cannot download dependencies                  │
│                                                                      │
│ □ Step 0.6: Planning docs accessible                                │
│   └── Verify: /home/thom/projects/Planning/*.md readable            │
│   └── If FAIL: STOP - cannot proceed without specs                  │
│                                                                      │
│ ═══════════════════════════════════════════════════════════════════ │
│ INFRASTRUCTURE CHECK (Section 2.2)                                   │
│ ═══════════════════════════════════════════════════════════════════ │
│                                                                      │
│ □ Step 0.7: Python 3.11+ available                                  │
│   └── Run: python3 --version                                        │
│   └── If <3.11: STOP - tell human to install Python 3.11+           │
│                                                                      │
│ □ Step 0.8: Node 20+ available                                      │
│   └── Run: node --version                                           │
│   └── If <20: STOP - tell human to install Node.js 20+              │
│                                                                      │
│ □ Step 0.9: Docker 24+ available                                    │
│   └── Run: docker --version                                         │
│   └── If <24: WARN but continue                                     │
│                                                                      │
│ □ Step 0.10: Docker Compose available                               │
│   └── Run: docker compose version                                   │
│   └── If FAIL: STOP - required for services                         │
│                                                                      │
│ ═══════════════════════════════════════════════════════════════════ │
│ OPTIONAL: BEAST SERVER CHECK (Section 2.3)                           │
│ ═══════════════════════════════════════════════════════════════════ │
│                                                                      │
│ □ Step 0.11: SSH to Beast (if separate GPU server)                  │
│   └── Run: ssh -o BatchMode=yes beast.local "true"                  │
│   └── If FAIL: WARN - GPU deployment may need manual steps          │
│   └── Note in PROGRESS.md if Beast SSH needs password               │
│                                                                      │
│ ═══════════════════════════════════════════════════════════════════ │
│ REPOSITORY SETUP (Section 2.4)                                       │
│ ═══════════════════════════════════════════════════════════════════ │
│                                                                      │
│ □ Step 0.12: Create repository structure                            │
│   └── Follow commands in Section 2.4                                │
│   └── Verify: git log shows initial commit                          │
│                                                                      │
│ □ Step 0.13: Set up virtual environment                             │
│   └── Follow commands in Section 2.5                                │
│   └── Verify: pip list shows fastapi installed                      │
│                                                                      │
│ □ Step 0.14: Install pre-commit hooks                               │
│   └── Verify: pre-commit run works                                  │
│                                                                      │
│ □ Step 0.15: Create PROGRESS.md                                     │
│   └── Initialize with Phase 0 complete, Phase 1A starting           │
│   └── Note any warnings (Beast SSH, low disk, etc.)                 │
│   └── Commit: "chore: initialize progress tracking"                 │
│                                                                      │
│ ✅ Continue immediately to Phase 1                                   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

**Critical Stop Conditions in Phase 0:**

| Check | If Fails | Message to Human |
|-------|----------|------------------|
| Passwordless sudo | STOP | "🛑 Need passwordless sudo. Run: `sudo visudo -f /etc/sudoers.d/$USER` and add `$USER ALL=(ALL) NOPASSWD: ALL`" |
| Docker without sudo | STOP | "🛑 Need Docker access without sudo. Run: `sudo usermod -aG docker $USER && newgrp docker`" |
| /opt writable | STOP | "🛑 Cannot write to /opt/barnabee-v2. Run: `sudo mkdir -p /opt/barnabee-v2 && sudo chown $USER:$USER /opt/barnabee-v2`" |
| Internet access | STOP | "🛑 No internet access - cannot download dependencies. Check network/proxy." |
| Planning docs | STOP | "🛑 Cannot find planning docs at /home/thom/projects/Planning/. Verify path." |
| Python <3.11 | STOP | "🛑 Python 3.11+ required. Current: X.X. Install newer Python." |
| Node <20 | STOP | "🛑 Node 20+ required. Current: vX. Install newer Node.js." |
| Docker Compose | STOP | "🛑 Docker Compose not found. Install docker-compose-plugin." |
| Beast SSH | WARN | "⚠️ SSH to Beast requires password. Will need manual intervention for GPU deployment." |

---

### Phase 1: Core Infrastructure (Area 01 + 02)

**Duration:** Estimated 4-8 hours agent time  
**Human Check-ins:** After each area

#### Phase 1A: Core Data Layer (Area 01)

```
┌─────────────────────────────────────────────────────────────────────┐
│ PHASE 1A: Core Data Layer                                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│ □ Step 1A.1: Create database schema files                           │
│   ├── File: schema/01-core.sql                                      │
│   ├── File: schema/02-memories.sql                                  │
│   ├── File: schema/03-conversations.sql                             │
│   └── Verify: sqlite3 < schema/*.sql succeeds                       │
│                                                                      │
│ □ Step 1A.2: Implement database connection                          │
│   ├── File: src/barnabee/db/connection.py                           │
│   ├── File: src/barnabee/db/migrations.py                           │
│   └── Verify: pytest tests/unit/test_db.py passes                   │
│                                                                      │
│ □ Step 1A.3: Implement memory repository                            │
│   ├── File: src/barnabee/memory/repository.py                       │
│   ├── File: src/barnabee/memory/models.py                           │
│   └── Verify: pytest tests/unit/test_memory_repo.py passes          │
│                                                                      │
│ □ Step 1A.4: Implement Redis session store                          │
│   ├── File: src/barnabee/sessions/redis_store.py                    │
│   ├── Start Redis: docker compose up -d redis                       │
│   └── Verify: pytest tests/integration/test_redis.py passes         │
│                                                                      │
│ □ Step 1A.5: Implement FTS5 search                                  │
│   ├── File: src/barnabee/memory/search.py                           │
│   └── Verify: Search queries return results                         │
│                                                                      │
│ □ Step 1A.6: Write tests                                            │
│   ├── Coverage target: 80%                                          │
│   └── Verify: pytest --cov shows >=80%                              │
│                                                                      │
│ Commit: git commit -m "feat(area-01): implement core data layer"    │
│                                                                      │
│ ✅ Continue immediately to Phase 1B                                  │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

#### Phase 1B: Voice Pipeline (Area 02)

```
┌─────────────────────────────────────────────────────────────────────┐
│ PHASE 1B: Voice Pipeline                                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│ □ Step 1B.1: Install Pipecat dependencies                           │
│   ├── Add to pyproject.toml: pipecat-ai[...] dependencies           │
│   ├── pip install -e ".[gpu]" (on Beast)                            │
│   └── Verify: python -c "import pipecat" succeeds                   │
│                                                                      │
│ □ Step 1B.2: Implement audio transport                              │
│   ├── File: src/barnabee/voice/transport.py                         │
│   ├── File: src/barnabee/voice/webrtc.py                            │
│   └── Verify: WebRTC connection test passes                         │
│                                                                      │
│ □ Step 1B.3: Implement wake word detection                          │
│   ├── File: src/barnabee/voice/wake_word.py                         │
│   ├── Download: openWakeWord model                                  │
│   └── Verify: Wake word detected in test audio                      │
│                                                                      │
│ □ Step 1B.4: Implement STT (Parakeet)                               │
│   ├── File: src/barnabee/voice/stt.py                               │
│   ├── Download: Parakeet model (~2GB)                               │
│   └── Verify: Transcription of test audio succeeds                  │
│                                                                      │
│ □ Step 1B.5: Implement TTS (Kokoro)                                 │
│   ├── File: src/barnabee/voice/tts.py                               │
│   ├── Download: Kokoro model                                        │
│   └── Verify: Audio synthesis produces valid wav                    │
│                                                                      │
│ □ Step 1B.6: Implement voice pipeline orchestrator                  │
│   ├── File: src/barnabee/voice/pipeline.py                          │
│   └── Verify: End-to-end audio → text → audio works                 │
│                                                                      │
│ □ Step 1B.7: Write integration tests                                │
│   ├── File: tests/integration/test_voice_pipeline.py                │
│   └── Verify: All voice tests pass                                  │
│                                                                      │
│ Commit: git commit -m "feat(area-02): implement voice pipeline"     │
│                                                                      │
│ ════════════════════════════════════════════════════════════════    │
│ 🛑 MILESTONE 1: Voice in → text → voice out works                   │
│    Stop here so human can test the voice pipeline before continuing │
│ ════════════════════════════════════════════════════════════════    │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

### Phase 2: Backbone (Area 03 + 04)

```
┌─────────────────────────────────────────────────────────────────────┐
│ PHASE 2: Backbone                                                    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│ PHASE 2A: Intent Classification (Area 03)                           │
│ ─────────────────────────────────────────                           │
│ □ Step 2A.1: Implement fast pattern matcher                         │
│ □ Step 2A.2: Implement embedding classifier                         │
│ □ Step 2A.3: Implement LLM fallback                                 │
│ □ Step 2A.4: Implement entity extraction                            │
│ □ Step 2A.5: Create golden dataset v1 (50 examples)                 │
│ □ Step 2A.6: Write classifier tests                                 │
│                                                                      │
│ 🔑 STOP IF: Need Azure OpenAI credentials for LLM fallback          │
│                                                                      │
│ PHASE 2B: Home Assistant Integration (Area 04)                      │
│ ─────────────────────────────────────────────                       │
│ □ Step 2B.1: Implement HA WebSocket client                          │
│ □ Step 2B.2: Implement entity caching                               │
│ □ Step 2B.3: Implement context injection                            │
│ □ Step 2B.4: Implement command execution                            │
│ □ Step 2B.5: Test against real HA instance                          │
│                                                                      │
│ 🔑 STOP IF: Need HA long-lived access token                         │
│                                                                      │
│ ════════════════════════════════════════════════════════════════    │
│ 🛑 MILESTONE 2: Voice commands control Home Assistant               │
│    Stop here so human can test "turn on the lights" etc.            │
│ ════════════════════════════════════════════════════════════════    │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

### Phase 3-5: Remaining Areas

```
┌─────────────────────────────────────────────────────────────────────┐
│ PHASE 3: Data Layer (Area 05)                                        │
│ ─────────────────────────────                                        │
│ □ Memory system with embeddings                                      │
│ □ Memory retrieval with progressive narrowing                        │
│ □ Memory creation from conversations                                 │
│                                                                      │
│ ✅ Continue to Phase 4 (memory tested as part of Phase 4)           │
├─────────────────────────────────────────────────────────────────────┤
│ PHASE 4: Core Functionality (Area 06)                                │
│ ────────────────────────────────────                                 │
│ □ Barnabee persona implementation                                    │
│ □ Response generation with context                                   │
│ □ Voice optimization                                                 │
│                                                                      │
│ ════════════════════════════════════════════════════════════════    │
│ 🛑 MILESTONE 3: Full system working end-to-end                      │
│    Stop here - human tests complete voice + memory + persona flow   │
│ ════════════════════════════════════════════════════════════════    │
├─────────────────────────────────────────────────────────────────────┤
│ PHASE 5: Extended Features (Areas 07-22)                             │
│ ─────────────────────────────────────────                            │
│ □ Meeting/scribe system (Area 07)                                    │
│ □ Self-improvement pipeline (Area 08)                                │
│ □ Dashboard & admin UI (Area 09)                                     │
│ □ Calendar & email (Area 12)                                         │
│ □ Notifications (Area 13)                                            │
│ □ Multi-device (Area 14)                                             │
│ □ Extended features (Area 22)                                        │
│                                                                      │
│ 🔑 STOP IF: Need Google OAuth credentials (calendar/email)          │
│ 🔑 STOP IF: Need SMS credentials (notifications)                    │
│                                                                      │
│ ════════════════════════════════════════════════════════════════    │
│ 🛑 MILESTONE 4: Production ready                                    │
│    Stop here - human does final review before production deploy     │
│ ════════════════════════════════════════════════════════════════    │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 8. Dashboard Build Process

### 8.1 Dashboard Technology Stack

```
Frontend: Preact + TypeScript
Styling: Tailwind CSS
Build: Vite
Backend: FastAPI (already running)
```

### 8.2 Dashboard Setup

```bash
# Create dashboard directory
cd /opt/barnabee-v2
mkdir -p dashboard
cd dashboard

# Initialize Node project
npm create vite@latest . -- --template preact-ts

# Install dependencies
npm install
npm install -D tailwindcss postcss autoprefixer
npx tailwindcss init -p

# Configure Tailwind
cat > tailwind.config.js << 'EOF'
/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        barnabee: {
          primary: '#4F46E5',
          secondary: '#10B981',
        },
      },
    },
  },
  plugins: [],
}
EOF

# Add Tailwind to CSS
echo '@tailwind base;\n@tailwind components;\n@tailwind utilities;' > src/index.css

# Build
npm run build

# Output goes to dist/ - serve via nginx
```

### 8.3 Dashboard Pages to Implement

```
dashboard/src/pages/
├── Home.tsx              # Status overview
├── Memories.tsx          # Memory browser with search
├── Meetings.tsx          # Meeting list with playback
├── Conversations.tsx     # Recent conversations
├── Admin/
│   ├── Health.tsx        # System health dashboard
│   ├── Logs.tsx          # Operational logs
│   ├── LLMProviders.tsx  # Provider management
│   └── Recovery.tsx      # Deleted memory recovery
└── Settings.tsx          # User preferences
```

### 8.4 Dashboard Deployment

```nginx
# Add to nginx.conf
server {
    listen 443 ssl;
    server_name barnabee.local;

    # Dashboard static files
    location / {
        root /opt/barnabee-v2/dashboard/dist;
        try_files $uri $uri/ /index.html;
    }

    # API proxy
    location /api/ {
        proxy_pass http://api:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

---

## 9. Credential Management

### 9.1 Required Credentials

**Agent: These are the ONLY times you should stop and ask the human for input.**

| Credential | When Needed | Stop Message |
|------------|-------------|--------------|
| HA Long-lived token | Phase 2B | "🔑 Need HA long-lived access token to continue. Please add HA_TOKEN to .env" |
| Azure OpenAI key | Phase 2A | "🔑 Need Azure OpenAI credentials. Please add AZURE_OPENAI_* to .env" |
| Google OAuth | Phase 5 | "🔑 Need Google OAuth credentials for calendar/email. Please add GOOGLE_* to .env" |
| Backblaze B2 | Phase 1 | "🔑 Need B2 credentials for backup. Please add B2_* to .env (or skip backup for now)" |

**Note:** If B2 credentials aren't available, skip Litestream backup setup and continue. It's not blocking.

### 9.2 .env File Structure

```bash
# .env.example - Agent creates this, human fills in
# Copy to .env and fill in values

# Database
DATABASE_PATH=/data/barnabee.db

# Redis
REDIS_URL=redis://localhost:6379

# Home Assistant
HA_URL=http://homeassistant.local:8123
HA_TOKEN=<long-lived-access-token>

# Azure OpenAI
AZURE_OPENAI_ENDPOINT=https://<resource>.openai.azure.com
AZURE_OPENAI_KEY=<api-key>
AZURE_OPENAI_DEPLOYMENT=gpt-4o

# Backup
B2_ACCOUNT_ID=<account-id>
B2_APPLICATION_KEY=<application-key>
B2_BUCKET=barnabee-backups

# Google (for calendar/email)
GOOGLE_CLIENT_ID=<client-id>
GOOGLE_CLIENT_SECRET=<client-secret>
```

---

## 10. Error Handling Guidance

### 10.1 Common Errors and Solutions

| Error | Likely Cause | Agent Action |
|-------|--------------|--------------|
| `ModuleNotFoundError` | Missing dependency | `pip install <module>` |
| `Connection refused` | Service not running | Check `docker compose ps` |
| `CUDA out of memory` | GPU overloaded | Restart GPU service, reduce batch |
| `Permission denied` | File permissions | `chmod` or check user |
| `HA connection failed` | Wrong token/URL | Verify `.env` values |
| `pytest failures` | Code bug | Fix before proceeding |
| `Lint errors` | Code style | Run `ruff --fix` |

### 10.2 When to Stop and Ask

```
STOP AND ASK HUMAN ONLY IF:

1. Same error occurs 3+ times after DIFFERENT fix attempts
2. Need credentials/secrets you don't have
3. Network/firewall blocking external service access
4. Something needs to be purchased/paid for

DO NOT STOP FOR:
- Unclear error messages (research them)
- Minor design decisions (make a reasonable choice)
- Tests pass but behavior seems off (add more tests)
- Unsure which approach (pick the simpler one)
```

---

## 11. Verification Checklist

### 11.1 Phase Completion Checklist

Before moving to next phase (NO human approval needed):

```
□ All files for the phase are created
□ All tests pass (pytest -v)
□ Lint passes (ruff check src/)
□ Type check passes (mypy src/)
□ Coverage meets target (pytest --cov)
□ Services start successfully (docker compose up)
□ Health checks pass (curl /health)
□ Relevant integration tests pass
□ Changes are committed with descriptive message
□ No secrets in code or commits

If all boxes checked → CONTINUE to next phase automatically
```

### 11.2 Pre-Production Checklist

Before going to production:

```
□ All phases complete and approved
□ E2E tests pass
□ Load testing completed (k6)
□ Backup system verified
□ Systemd services configured
□ Monitoring dashboards working
□ Alert rules configured
□ Runbook documentation complete
□ Rollback procedure tested
□ Human has tested manually
```

---

## 12. File Reference Quick Guide

### 12.1 Key Files by Area

```
Area 01 - Core Data:
  src/barnabee/db/connection.py
  src/barnabee/db/migrations.py
  src/barnabee/memory/repository.py
  schema/*.sql

Area 02 - Voice:
  src/barnabee/voice/pipeline.py
  src/barnabee/voice/stt.py
  src/barnabee/voice/tts.py
  src/barnabee/voice/wake_word.py

Area 03 - Intent:
  src/barnabee/nlu/classifier.py
  src/barnabee/nlu/patterns.py
  src/barnabee/nlu/entities.py

Area 04 - Home Assistant:
  src/barnabee/ha/client.py
  src/barnabee/ha/cache.py
  src/barnabee/ha/commands.py

Area 05 - Memory:
  src/barnabee/memory/service.py
  src/barnabee/memory/embeddings.py
  src/barnabee/memory/search.py

Area 06 - Response:
  src/barnabee/response/generator.py
  src/barnabee/response/persona.py
  src/barnabee/response/templates.py
```

### 12.2 Configuration Files

```
/opt/barnabee-v2/
├── pyproject.toml          # Python dependencies
├── docker-compose.yml      # Service definitions
├── .env                    # Secrets (not in git)
├── .env.example            # Template (in git)
├── config/
│   ├── logging.yaml        # Log configuration
│   ├── models.yaml         # Model paths/versions
│   └── prompts.yaml        # LLM prompts
└── nginx/
    └── nginx.conf          # Reverse proxy config
```

---

## 13. Summary: Agent Quick Reference

```
┌─────────────────────────────────────────────────────────────────────┐
│                     AGENT QUICK REFERENCE                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│ PROGRESS TRACKING:                                                   │
│   📋 Maintain /opt/barnabee-v2/PROGRESS.md at all times             │
│   📋 Update after EVERY step (not just phases)                      │
│   📋 On resume: READ PROGRESS.md first, continue where left off     │
│                                                                      │
│ BE AUTONOMOUS:                                                       │
│   ✓ Complete phases without stopping for approval                   │
│   ✓ Fix failing tests yourself, then continue                       │
│   ✓ Make reasonable implementation decisions                        │
│   ✓ Only stop at the 4 major milestones                             │
│                                                                      │
│ ALWAYS:                                                              │
│   ✓ Update PROGRESS.md after each step                              │
│   ✓ Run tests after every feature                                   │
│   ✓ Commit with descriptive messages                                │
│   ✓ Verify services before testing them                             │
│   ✓ Read error messages carefully                                   │
│                                                                      │
│ STOP ONLY FOR:                                                       │
│   🔑 Missing credentials (HA token, Azure key, etc.)                │
│   🛑 Major milestones (4 total - for human testing)                 │
│   ❌ Stuck after 3+ different fix attempts                          │
│   ❓ Ambiguous requirement with significant impact                   │
│                                                                      │
│ NEVER:                                                               │
│   ✗ Stop just to report progress                                    │
│   ✗ Ask permission to start a phase                                 │
│   ✗ Wait for approval on obvious decisions                          │
│   ✗ Commit secrets to git                                           │
│   ✗ Retry the same failing approach 3+ times                        │
│                                                                      │
│ MILESTONES (only 4 stops):                                           │
│   1. End of Phase 1 → Voice pipeline works                          │
│   2. End of Phase 2 → HA commands work                              │
│   3. End of Phase 4 → Full system E2E works                         │
│   4. End of Phase 5 → Production ready                              │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

**End of Area 24: Agent Implementation Guide**
