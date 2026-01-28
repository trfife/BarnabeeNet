# BarnabeeNet V2 - Agent Kickoff

## For the Human

When you're ready to build, open a new Cursor/Copilot session and paste the prompt below. The agent will read the planning docs and build the entire project autonomously, stopping only at 4 milestones for you to test.

---

## Pre-Flight Checklist

Run through this before starting. Check each box:

### AI Agent Access Requirements

**CRITICAL: The AI agent needs these permissions to work autonomously without blocking on password prompts or permission errors.**

#### Passwordless Sudo
- [ ] **Sudo without password** - Agent needs to run privileged commands
  ```bash
  # Add to /etc/sudoers.d/thom (run as root or with sudo visudo)
  sudo visudo -f /etc/sudoers.d/thom
  
  # Add this line (replace 'thom' with your username):
  thom ALL=(ALL) NOPASSWD: ALL
  
  # Verify it works:
  sudo -n true && echo "✅ Passwordless sudo works" || echo "❌ Still requires password"
  ```

#### Docker Without Sudo
- [ ] **User in docker group** - Avoid sudo for every docker command
  ```bash
  # Add user to docker group
  sudo usermod -aG docker $USER
  
  # IMPORTANT: Log out and back in, or run:
  newgrp docker
  
  # Verify:
  docker ps && echo "✅ Docker works without sudo" || echo "❌ Docker needs sudo"
  ```

#### File System Permissions
- [ ] **/opt writable** - Build location must be writable
  ```bash
  # Create and own the build directory
  sudo mkdir -p /opt/barnabee-v2
  sudo chown -R $USER:$USER /opt/barnabee-v2
  
  # Verify:
  touch /opt/barnabee-v2/.test && rm /opt/barnabee-v2/.test && echo "✅ /opt writable"
  ```

- [ ] **Home directory access** - Agent reads planning docs from here
  ```bash
  # Verify planning docs are readable
  ls /home/thom/projects/Planning/*.md && echo "✅ Planning docs accessible"
  ```

#### Git Configuration
- [ ] **Git identity configured** - Required for commits
  ```bash
  # Set if not already configured
  git config --global user.name "Thom"
  git config --global user.email "thom@example.com"
  
  # Verify:
  git config user.name && git config user.email && echo "✅ Git configured"
  ```

- [ ] **Git default branch** - Avoid warnings
  ```bash
  git config --global init.defaultBranch main
  ```

#### SSH Access to Beast (GPU Server)
- [ ] **SSH key-based auth to Beast** - No password prompts for remote commands
  ```bash
  # Generate key if needed
  [ -f ~/.ssh/id_ed25519 ] || ssh-keygen -t ed25519 -N "" -f ~/.ssh/id_ed25519
  
  # Copy to Beast (one-time, requires password)
  ssh-copy-id beast.local
  
  # Verify passwordless SSH:
  ssh -o BatchMode=yes beast.local "echo '✅ SSH to Beast works'" 2>/dev/null || echo "❌ SSH needs password"
  ```

- [ ] **Beast hostname resolves** - Or add to /etc/hosts
  ```bash
  # If beast.local doesn't resolve, add to /etc/hosts:
  echo "192.168.1.XX beast.local beast" | sudo tee -a /etc/hosts
  
  # Verify:
  ping -c 1 beast.local && echo "✅ Beast resolves"
  ```

#### Systemd Access (for service management)
- [ ] **Systemd user access** - For creating services later
  ```bash
  # Enable lingering so user services persist
  sudo loginctl enable-linger $USER
  
  # Verify:
  loginctl show-user $USER | grep Linger && echo "✅ Lingering enabled"
  ```

---

### Infrastructure
- [ ] **Build server accessible** - Can SSH into the machine where `/opt/barnabee-v2` will live
- [ ] **Docker installed** - `docker --version` shows 24+
- [ ] **Docker Compose installed** - `docker compose version` shows 2.20+
- [ ] **Python 3.11+** - `python3 --version`
- [ ] **Node 20+** - `node --version`
- [ ] **Git installed** - `git --version`
- [ ] **Disk space** - At least 50GB free (models are large)
  ```bash
  df -h /opt
  ```
- [ ] **pip/venv available** - For Python virtual environments
  ```bash
  python3 -m venv --help && echo "✅ venv available"
  python3 -m pip --version && echo "✅ pip available"
  ```

### GPU Server (Beast)
- [ ] **Beast server accessible** - Can reach it from build server
- [ ] **NVIDIA driver working** - `nvidia-smi` shows RTX 4070 Ti
- [ ] **CUDA 12.x installed** - `nvcc --version` or check nvidia-smi
- [ ] **nvidia-container-toolkit installed** - For Docker GPU access
  ```bash
  docker run --rm --gpus all nvidia/cuda:12.0-base nvidia-smi
  ```
- [ ] **Beast has passwordless sudo** - Same setup as build server
- [ ] **Beast user in docker group** - Same setup as build server

### Home Assistant
- [ ] **HA running** - Can access http://homeassistant.local:8123
- [ ] **Long-lived token ready** - Go to Profile → Security → Long-lived tokens → Create
- [ ] **Know some entity IDs** - For testing (e.g., `light.living_room`)

### Credentials (have these ready, agent will ask when needed)
- [ ] **HA long-lived access token** - Required for Phase 2B
- [ ] **Azure OpenAI** - Required for Phase 2A
  - Endpoint URL
  - API Key
  - Deployment name (e.g., `gpt-4o`)
- [ ] **Google OAuth** (optional) - For calendar/email in Phase 5
- [ ] **Backblaze B2** (optional) - For backups

### Network
- [ ] **Build server can reach HA** - `curl http://homeassistant.local:8123`
- [ ] **Build server can reach internet** - `curl https://github.com`
- [ ] **Build server can reach Beast** - `ping beast.local` (or whatever hostname)
- [ ] **Required ports open** - No firewall blocking these:
  - 6379 (Redis)
  - 8000 (API)
  - 8001 (GPU services)
  - 8123 (Home Assistant)

---

## Quick Agent Access Test

Run this script to verify the AI agent will have everything it needs:

```bash
#!/bin/bash
echo "=== AI Agent Access Verification ==="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

pass() { echo -e "${GREEN}✅ $1${NC}"; }
fail() { echo -e "${RED}❌ $1${NC}"; }

# Passwordless sudo
sudo -n true 2>/dev/null && pass "Passwordless sudo" || fail "Passwordless sudo - run: sudo visudo -f /etc/sudoers.d/$USER"

# Docker without sudo
docker ps >/dev/null 2>&1 && pass "Docker without sudo" || fail "Docker without sudo - run: sudo usermod -aG docker $USER && newgrp docker"

# /opt writable
[ -w /opt/barnabee-v2 ] 2>/dev/null || mkdir -p /opt/barnabee-v2 2>/dev/null
[ -w /opt/barnabee-v2 ] && pass "/opt/barnabee-v2 writable" || fail "/opt writable - run: sudo mkdir -p /opt/barnabee-v2 && sudo chown $USER:$USER /opt/barnabee-v2"

# Git configured
git config user.name >/dev/null 2>&1 && pass "Git user.name configured" || fail "Git user.name - run: git config --global user.name 'Your Name'"
git config user.email >/dev/null 2>&1 && pass "Git user.email configured" || fail "Git user.email - run: git config --global user.email 'you@example.com'"

# SSH to Beast
ssh -o BatchMode=yes -o ConnectTimeout=5 beast.local "true" 2>/dev/null && pass "SSH to Beast (passwordless)" || fail "SSH to Beast - run: ssh-copy-id beast.local"

# Planning docs readable
[ -r /home/thom/projects/Planning/00-v2-summary.md ] && pass "Planning docs readable" || fail "Planning docs not found at /home/thom/projects/Planning/"

echo ""
echo "=== Agent Access Check Complete ==="
```

Save as `agent-access-check.sh` and run: `bash agent-access-check.sh`

---

## Complete Pre-Flight Script

Run this comprehensive check on your build server before starting:

```bash
#!/bin/bash
echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║         BarnabeeNet V2 - Complete Pre-Flight Check               ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

pass() { echo -e "${GREEN}✅ PASS${NC} - $1"; }
fail() { echo -e "${RED}❌ FAIL${NC} - $1"; FAILED=1; }
warn() { echo -e "${YELLOW}⚠️  WARN${NC} - $1"; }

FAILED=0

echo "─── AI Agent Access ───"
sudo -n true 2>/dev/null && pass "Passwordless sudo" || fail "Passwordless sudo required"
docker ps >/dev/null 2>&1 && pass "Docker without sudo" || fail "User not in docker group"
[ -w /opt ] || sudo mkdir -p /opt/barnabee-v2 2>/dev/null
touch /opt/barnabee-v2/.writetest 2>/dev/null && rm /opt/barnabee-v2/.writetest && pass "/opt/barnabee-v2 writable" || fail "/opt/barnabee-v2 not writable"
git config user.name >/dev/null 2>&1 && pass "Git identity configured" || fail "Git user.name not set"
ssh -o BatchMode=yes -o ConnectTimeout=3 beast.local "true" 2>/dev/null && pass "SSH to Beast (no password)" || warn "SSH to Beast needs password (set up key auth)"

echo ""
echo "─── Infrastructure ───"
echo -n "Docker: "; docker --version 2>/dev/null && pass "Docker installed" || fail "Docker not found"
echo -n "Docker Compose: "; docker compose version 2>/dev/null && pass "Docker Compose installed" || fail "Docker Compose not found"
PYVER=$(python3 --version 2>/dev/null | grep -oP '\d+\.\d+')
[[ "$PYVER" > "3.10" ]] && pass "Python $PYVER (3.11+ required)" || fail "Python 3.11+ required, found $PYVER"
NODEVER=$(node --version 2>/dev/null | grep -oP '\d+' | head -1)
[[ "$NODEVER" -ge 20 ]] && pass "Node $NODEVER (20+ required)" || fail "Node 20+ required"
git --version >/dev/null 2>&1 && pass "Git installed" || fail "Git not found"

DISKFREE=$(df /opt | tail -1 | awk '{print $4}')
[[ "$DISKFREE" -gt 50000000 ]] && pass "Disk space: $(df -h /opt | tail -1 | awk '{print $4}') free" || warn "Low disk space (need 50GB+)"

python3 -m venv --help >/dev/null 2>&1 && pass "Python venv available" || fail "Python venv not available"
python3 -m pip --version >/dev/null 2>&1 && pass "pip available" || fail "pip not available"

echo ""
echo "─── GPU Server (Beast) ───"
if ssh -o BatchMode=yes -o ConnectTimeout=3 beast.local "true" 2>/dev/null; then
  ssh beast.local "nvidia-smi" >/dev/null 2>&1 && pass "Beast GPU accessible" || fail "Beast nvidia-smi failed"
  ssh beast.local "docker ps" >/dev/null 2>&1 && pass "Beast Docker works" || warn "Beast Docker may need sudo"
else
  warn "Cannot verify Beast (SSH not configured) - verify manually"
fi

echo ""
echo "─── Network Connectivity ───"
curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 http://homeassistant.local:8123 | grep -q "200\|401" && pass "Home Assistant reachable" || warn "Home Assistant not reachable at homeassistant.local:8123"
curl -s -o /dev/null --connect-timeout 5 https://github.com && pass "Internet access (github.com)" || fail "No internet access"
curl -s -o /dev/null --connect-timeout 5 https://pypi.org && pass "PyPI reachable" || fail "PyPI not reachable"
curl -s -o /dev/null --connect-timeout 5 https://registry.npmjs.org && pass "npm registry reachable" || fail "npm registry not reachable"

echo ""
echo "─── Planning Documents ───"
[ -d /home/thom/projects/Planning ] && pass "Planning directory exists" || fail "Planning directory not found"
[ -f /home/thom/projects/Planning/00-v2-summary.md ] && pass "Summary doc exists" || fail "00-v2-summary.md missing"
[ -f /home/thom/projects/Planning/24-agent-implementation-guide.md ] && pass "Agent guide exists" || fail "24-agent-implementation-guide.md missing"
DOCCOUNT=$(ls /home/thom/projects/Planning/*.md 2>/dev/null | wc -l)
[[ "$DOCCOUNT" -ge 24 ]] && pass "All $DOCCOUNT planning docs present" || warn "Only $DOCCOUNT docs found (expected 25)"

echo ""
echo "╔══════════════════════════════════════════════════════════════════╗"
if [ "$FAILED" -eq 0 ]; then
  echo -e "║  ${GREEN}ALL CRITICAL CHECKS PASSED - Ready to start!${NC}                    ║"
else
  echo -e "║  ${RED}SOME CHECKS FAILED - Fix issues above before starting${NC}           ║"
fi
echo "╚══════════════════════════════════════════════════════════════════╝"
```

Save as `/home/thom/projects/Planning/preflight.sh` and run:
```bash
chmod +x /home/thom/projects/Planning/preflight.sh
./preflight.sh
```

If all critical checks pass, you're ready to start.

---

## What the Agent Validates at Startup

When you paste the kickoff prompt, the agent will **automatically verify** these items before building:

| Check | Action if Failed |
|-------|------------------|
| Can write to `/opt/barnabee-v2` | STOP - ask human to fix permissions |
| Can run `docker` commands | STOP - ask human to add user to docker group |
| Can run `sudo` without password | STOP - ask human to configure sudoers |
| Python 3.11+ available | STOP - ask human to install |
| Node 20+ available | STOP - ask human to install |
| Git configured with name/email | Auto-configure with defaults, warn human |
| Internet connectivity | STOP - cannot download dependencies |
| Planning docs readable | STOP - cannot proceed without specs |

The agent will report any failures clearly and tell you exactly how to fix them before it can continue.

---

## Kickoff Prompt

Copy and paste this entire block to start the agent:

```
Build BarnabeeNet V2 from the planning documents in /home/thom/projects/Planning/

START BY READING THESE FILES IN ORDER:
1. /home/thom/projects/Planning/00-v2-summary.md - Project overview and architecture
2. /home/thom/projects/Planning/24-agent-implementation-guide.md - Your execution guide

Then follow the phased implementation in the agent guide. For each area, read the corresponding spec file (01-core-data-layer.md, 02-voice-pipeline.md, etc.) before implementing.

KEY RULES:
- Be autonomous. Complete phases without stopping for approval.
- Stop ONLY at the 4 major milestones (end of Phase 1, 2, 4, 5) so I can test.
- Stop ONLY if you need credentials I haven't provided.
- If tests fail, fix them yourself and continue.
- Commit frequently with good messages.

BUILD LOCATION: /opt/barnabee-v2/

GO. Start with Phase 0 (environment setup) and keep going until Milestone 1.
```

---

## What Happens Next

The agent will:

1. **Phase 0** (~30 min): Set up repo, virtual environment, pre-commit hooks
2. **Phase 1A** (~2-4 hrs): Build core data layer (SQLite, Redis, schemas)
3. **Phase 1B** (~2-4 hrs): Build voice pipeline (Pipecat, STT, TTS)
4. **🛑 MILESTONE 1**: Agent stops. You test voice in → text → voice out.

After you confirm Milestone 1 works:

5. **Phase 2A** (~2-3 hrs): Intent classification
6. **Phase 2B** (~2-3 hrs): Home Assistant integration
7. **🛑 MILESTONE 2**: Agent stops. You test "turn on the lights."

After you confirm Milestone 2 works:

8. **Phase 3-4** (~4-6 hrs): Memory system, response generation, persona
9. **🛑 MILESTONE 3**: Agent stops. You test full conversation flow.

After you confirm Milestone 3 works:

10. **Phase 5** (~6-10 hrs): Extended features, dashboard, meetings, etc.
11. **🛑 MILESTONE 4**: Agent stops. Full system ready for production.

---

## Credential Prompts

When the agent stops for credentials, it will say something like:

> "🔑 Need HA long-lived access token to continue. Please add HA_TOKEN to .env"

At that point:
1. Create/edit `/opt/barnabee-v2/.env`
2. Add the requested credential
3. Tell the agent: "Credentials added. Continue."

---

## Checking Progress

The agent maintains a progress log at `/opt/barnabee-v2/PROGRESS.md`. 

To check status anytime:
```bash
cat /opt/barnabee-v2/PROGRESS.md
```

Or ask the agent:
```
Show me the current PROGRESS.md and summarize where we are.
```

---

## Resuming After Interruption

If a session ends or times out, start a new session with:

```
Resume building BarnabeeNet V2.

Read /opt/barnabee-v2/PROGRESS.md to see where the last session left off.
Read /home/thom/projects/Planning/24-agent-implementation-guide.md for your execution rules.

Continue from where the progress file shows. Don't restart completed work.
```

---

## If Something Goes Wrong

If the agent gets stuck or confused:

```
Read /opt/barnabee-v2/PROGRESS.md to see current state.
Read /home/thom/projects/Planning/24-agent-implementation-guide.md for rules.
Continue from current step.
```

If you want to restart a phase:

```
Reset and rebuild Phase X from scratch. 
Update PROGRESS.md to mark Phase X as not started.
Read the spec at /home/thom/projects/Planning/XX-<area-name>.md
```

If you want detailed status:

```
Show me:
1. Contents of PROGRESS.md
2. Current git log (last 10 commits)
3. Test results (pytest -v)
4. Service status (docker compose ps)
```

---

## Document Reference

| Doc | Purpose |
|-----|---------|
| 00-v2-summary.md | Architecture overview, all areas listed |
| 01-core-data-layer.md | SQLite schema, Redis, migrations |
| 02-voice-pipeline.md | Pipecat, STT, TTS, WebRTC |
| 03-intent-classification.md | NLU, entity extraction, classifiers |
| 04-home-assistant.md | HA WebSocket, entity cache, commands |
| 05-memory-system.md | Memory storage, embeddings, retrieval |
| 06-response-generation.md | Persona, templates, LLM responses |
| 07-meeting-scribe.md | Transcription, speaker ID, action items |
| 08-self-improvement.md | Safe auto-improvement pipeline |
| 09-dashboard.md | Admin UI, memory browser |
| 10-testing-observability.md | Test strategy, monitoring |
| 11-deployment-infrastructure.md | Docker, Proxmox, GPU setup |
| 12-calendar-email.md | Google Calendar/Gmail |
| 13-notifications.md | Push, SMS, voice alerts |
| 14-multi-device.md | Wake word arbitration |
| 15-api-contracts.md | OpenAPI spec |
| 16-migration-runbook.md | V1 to V2 migration |
| 17-security.md | Auth, secrets, firewall |
| 18-cost-tracking.md | Operating costs |
| 19-personal-finance.md | SimpleFIN, budgets |
| 20-native-apps.md | Mobile apps |
| 21-user-profiles.md | Personalization |
| 22-extended-features.md | Shopping, recipes, routines, etc. |
| 23-implementation-additions.md | Concurrent sessions, GPU recovery, speed optimizations |
| 24-agent-implementation-guide.md | **Execution guide for the agent** |

---

## Quick Commands for Testing Milestones

**Milestone 1 - Voice Pipeline:**
```bash
cd /opt/barnabee-v2
docker compose up -d
curl http://localhost:8000/health
# Then test with a microphone or test audio file
```

**Milestone 2 - HA Commands:**
```bash
# Say "turn on the living room lights" 
# Or send via API:
curl -X POST http://localhost:8000/api/v2/voice/process \
  -H "Content-Type: application/json" \
  -d '{"text": "turn on the living room lights", "session_id": "test"}'
```

**Milestone 3 - Full System:**
```bash
# Test memory: "Remember that I like my coffee black"
# Test recall: "How do I like my coffee?"
# Test persona: Should respond as Barnabee consistently
```

**Milestone 4 - Production:**
```bash
# Full E2E test suite
cd /opt/barnabee-v2
pytest tests/e2e/ -v

# Load test
k6 run tests/load/basic.js

# Check dashboard
open https://barnabee.local/
```

---

**You're ready. Paste the kickoff prompt and let it build.**
