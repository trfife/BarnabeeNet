# BarnabeeNet Project Log

**Started:** January 16, 2026  
**Goal:** Build a privacy-first, multi-agent AI smart home assistant

---

## Environment

| Name | Hardware | Role | IP |
|------|----------|------|-----|
| Man-of-war | Gaming PC (i9-14900KF, RTX 4070 Ti, 128GB) | Development + GPU worker (Parakeet STT) | 192.168.86.100 |
| Battlestation | Beelink EQi12 (i5-1220P, 24GB, 500GB) | Proxmox host | 192.168.86.64 |
| BarnabeeNet VM | VM 200 on Battlestation (6 cores, 8GB RAM, 100GB) | BarnabeeNet runtime | 192.168.86.51 |

---

## Phase 0: Foundation Setup
**Status:** ✅ Complete  
**Date:** January 16, 2026

### Step 1: Development Environment Setup
**Status:** ✅ Complete  
**Date:** January 16, 2026

- [x] Cursor installed on Windows 11
- [x] Anthropic API key created with credits
- [x] WSL2 with Ubuntu-24.04 installed
- [x] git, age, sops installed in WSL
- [x] SSH access to Battlestation verified

---

### Step 2: Repository Initialization
**Status:** ✅ Complete  
**Date:** January 16, 2026

- [x] GitHub repository created: https://github.com/trfife/BarnabeeNet
- [x] SSH key configured for GitHub
- [x] Initial structure committed and pushed

---

### Step 3: Create BarnabeeNet VM on Proxmox
**Status:** ✅ Complete  
**Date:** January 16, 2026

- [x] Cleaned up unused VMs/containers
- [x] Downloaded NixOS 24.11 ISO to Proxmox
- [x] Created VM 200 (barnabeenet): 6 cores, 8GB RAM, 100GB disk
- [x] Installed NixOS with UEFI boot (systemd-boot)
- [x] SSH access as thom@192.168.86.51 verified
- [x] Nix flakes enabled

---

### Step 4: Base VM Configuration
**Status:** ✅ Complete  
**Date:** January 16, 2026

- [x] NixOS configuration updated with Podman + dev tools
- [x] Podman rootless with docker-compat enabled
- [x] SSH key generated for GitHub access from VM
- [x] BarnabeeNet repo cloned to ~/barnabeenet
- [x] Data directories created (~/data/redis, ~/data/models/*)
- [x] Redis 7-alpine container running via podman-compose
- [x] Systemd user service for auto-start on boot
- [x] Verified services survive reboot

#### Installed Packages
- podman, podman-compose
- python312, pip, virtualenv
- sqlite, redis-cli
- age, sops
- jq, yq, tree, ffmpeg

#### Running Services
| Service | Image | Port | Status |
|---------|-------|------|--------|
| Redis | redis:7-alpine | 6379 | Running (auto-start) |

---

## Phase 1: Core Services
**Status:** 🔄 In Progress

### Step 1: Project Structure + Configuration
**Status:** ✅ Complete  
**Date:** January 17, 2026

- [x] Created `pyproject.toml` with modern Python packaging
- [x] Created `requirements.txt` for Beelink CPU dependencies
- [x] Created `requirements-gpu.txt` for Man-of-war GPU dependencies
- [x] Created `.env.example` with all configuration options
- [x] Created project directory structure (`src/barnabeenet/`, `tests/`, `workers/`, `scripts/`)
- [x] Created package `__init__.py` files

### Step 2: Core Application
**Status:** ✅ Complete  
**Date:** January 17, 2026

- [x] Created `config.py` - Pydantic Settings with nested config classes
- [x] Created `main.py` - FastAPI app with lifespan management
- [x] Created `models/schemas.py` - All Pydantic request/response models
- [x] Created `api/routes/health.py` - Health check endpoints
- [x] Created `api/routes/voice.py` - STT, TTS, pipeline endpoints (placeholders)
- [x] Implemented background GPU worker health check (zero-latency routing)

### Step 3: STT Services
**Status:** ⏳ Not Started

- [ ] Implement Distil-Whisper CPU service
- [ ] Implement GPU worker client
- [ ] Implement routing logic

### Step 4: TTS Service
**Status:** ⏳ Not Started

- [ ] Implement Kokoro TTS service
- [ ] Add caching layer

### Step 5: GPU Worker (Man-of-war)
**Status:** ⏳ Not Started

- [ ] Create GPU worker FastAPI app
- [ ] Implement Parakeet TDT integration
- [ ] Setup WSL2 + CUDA on Man-of-war
- [ ] Create deployment script

### Step 6: Deployment Scripts
**Status:** ⏳ Not Started

- [ ] `deploy.sh` for Beelink
- [ ] `deploy-gpu-worker.sh` for Man-of-war
- [ ] `setup-wsl-cuda.ps1` for Windows

### Step 7: Tests
**Status:** ⏳ Not Started

- [ ] Unit tests
- [ ] Integration tests
- [ ] Latency benchmarks

### Current Blockers
- Man-of-war WSL needs Python environment setup:
  ```bash
  sudo apt update
  sudo apt install python3-pip python3-venv -y
  cd ~/projects/barnabeenet
  python3 -m venv .venv
  source .venv/bin/activate
  pip install -e .
  ```

---

## Phase 2: Voice Pipeline
**Status:** Not Started

---

## Phase 3: Agent Architecture
**Status:** Not Started

---

## Phase 4: Home Assistant Integration
**Status:** Not Started

---

## Phase 5: Multi-Modal & Advanced Features
**Status:** Not Started

---

## Phase 6: Hardening & Production
**Status:** Not Started

---

## Decisions Made

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-01-16 | Use Cursor as primary IDE | AI-assisted development with Claude integration |
| 2026-01-16 | Use WSL2 for dev tools | Better Linux tooling for infrastructure work |
| 2026-01-16 | Existing Proxmox stays as-is | Only greenfield the BarnabeeNet VM |
| 2026-01-16 | Private GitHub repo | Contains home network details |
| 2026-01-16 | NixOS over Ubuntu | Declarative config is better for AI-driven builds |
| 2026-01-16 | VM ID 200 | Clean numbering, away from existing IDs |
| 2026-01-16 | 8GB RAM, 6 cores | Conservative given Beelink memory constraints |
| 2026-01-16 | UEFI boot with OVMF | Required for systemd-boot |
| 2026-01-16 | Podman rootless over Docker | Security + NixOS compatibility |
| 2026-01-16 | Separate SSH key per machine | Security best practice |
| 2026-01-17 | **Kokoro over Piper for TTS** | Research shows Kokoro is faster (<0.3s) and better quality |
| 2026-01-17 | **Dual-path STT (Parakeet + Distil-Whisper)** | GPU primary for speed, CPU fallback for reliability |
| 2026-01-17 | **Man-of-war as GPU worker** | RTX 4070 Ti provides 10x faster STT than CPU |
| 2026-01-17 | **WSL2 for GPU worker** | No dual-boot needed, can game while worker runs |
| 2026-01-17 | **Zero-latency health check routing** | Background health check, cached state read on request path |
| 2026-01-17 | **Streaming STT, not batch** | Key insight: streaming gives ~100-300ms, batch gives 1-2s |

---

## Research Findings (January 17, 2026)

### TTS Comparison (2025 State of the Art)

| Model | Speed (CPU) | Quality | Voice Clone | License |
|-------|-------------|---------|-------------|---------|
| **Kokoro-82M** | <0.3s ⚡ | Good | No | Apache 2.0 |
| Piper | ~0.1-0.5s | Acceptable | No | MIT |
| XTTS-v2 | Slow (CPU) | Excellent | Yes | Coqui License |

**Decision:** Kokoro for speed, XTTS-v2 deferred to Phase 5 for voice cloning

### STT Comparison (2025 State of the Art)

| Model | WER | Speed (RTFx) | Hardware |
|-------|-----|--------------|----------|
| Parakeet TDT 0.6B v2 | 6.05% | 3386x ⚡ | GPU required |
| Distil-Whisper small.en | ~7% | Fast | CPU OK |
| Faster-Whisper | Varies | Good | CPU OK |

**Decision:** Parakeet on GPU (primary), Distil-Whisper on CPU (fallback)

### Key Insight: Streaming vs Batch STT
- User's existing HA setup achieves millisecond STT because it uses **streaming**
- Batch mode (record → send → process) takes 1-2 seconds
- Streaming mode (process as you speak) completes ~100-300ms after speech ends

---

## Architecture Summary

```
┌─────────────────────────────────────────────────────────────────────┐
│  BARNABEENET VOICE PIPELINE                                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   Audio In ──→ STT Router ──→ Processing ──→ TTS ──→ Audio Out     │
│                    │                                                │
│         ┌─────────┴─────────┐                                      │
│         ▼                   ▼                                       │
│   ┌───────────┐       ┌───────────┐                                │
│   │ Parakeet  │       │ Distil-   │                                │
│   │ (GPU)     │       │ Whisper   │                                │
│   │ PRIMARY   │       │ FALLBACK  │                                │
│   │ ~20-40ms  │       │ ~150-300ms│                                │
│   └───────────┘       └───────────┘                                │
│   Man-of-war          Beelink VM                                   │
│                                                                     │
│   TTS: Kokoro-82M (<300ms) on Beelink                              │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Development Environment Setup

### Cursor IDE
- [x] Installed
- [x] Connected to WSL
- [x] Opened ~/projects/barnabeenet
- [x] Anthropic API key configured (can use Cursor Pro's included access)

### Man-of-war WSL
- [x] Ubuntu 24.04
- [x] Git configured
- [x] SSH keys for GitHub
- [x] Repo cloned to ~/projects/barnabeenet
- [ ] Python venv setup (next step)

---

## Documentation Updates
**Status:** ✅ Complete  
**Date:** January 17, 2026

- [x] Created `docs/PATCH_Phase1_Updates.md` with surgical doc patches
- [x] Applied patches via Cursor to update:
  - Technology stack (Kokoro, Distil-Whisper, Parakeet)
  - GPU worker architecture
  - Implementation roadmap
  - SkyrimNet patterns

---

## Issues Encountered

| Date | Issue | Resolution |
|------|-------|------------|
| 2026-01-16 | WSL showed "no installed distributions" | Ran `wsl --install -d Ubuntu-24.04` explicitly |
| 2026-01-16 | Git push failed - SSH key not on GitHub | Added SSH key to GitHub settings |
| 2026-01-16 | `qm terminal` - no serial interface | Used Proxmox web console instead |
| 2026-01-16 | Can't paste in Proxmox console | Set root password, SSH in from WSL |
| 2026-01-16 | Mount by label failed | Used mount by device name instead |
| 2026-01-16 | Duplicate /boot entry in hardware-configuration.nix | Manually removed the bind mount entry |
| 2026-01-16 | VM stuck at "Booting from Hard Disk" | VM was using BIOS, not UEFI. Added EFI disk and changed to OVMF |
| 2026-01-16 | SSH key not being accepted | Key was in config but not applied. Ran `nixos-rebuild switch` |
| 2026-01-16 | SSH host key warnings | Expected after reinstalls. Used `ssh-keygen -R` to clear old keys |
| 2026-01-16 | Systemd user service couldn't find podman | Added PATH environment variable to service file |

---

## Proxmox Current State

### VMs
| VMID | Name | Status | Purpose |
|------|------|--------|---------|
| 100 | home-assistant | running | Home Assistant |
| 200 | barnabeenet | running | BarnabeeNet (NixOS) |

### Containers
| VMID | Name | Status | Purpose |
|------|------|--------|---------|
| 101 | node-red | running | Node-RED |
| 106 | homebox | running | Homebox |
| 107 | barnabee | stopped | Old version (kept for reference) |

---

## NixOS Configuration (Current)

**Location on VM:** `/etc/nixos/configuration.nix`
```nix
{ config, pkgs, ... }:

{
  imports = [
    ./hardware-configuration.nix
  ];

  boot.loader.systemd-boot.enable = true;
  boot.loader.efi.canTouchEfiVariables = true;

  networking.hostName = "barnabeenet";
  networking.networkmanager.enable = true;

  time.timeZone = "America/New_York";

  users.users.thom = {
    isNormalUser = true;
    extraGroups = [ "wheel" "networkmanager" ];
    openssh.authorizedKeys.keys = [
      "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOP6MkvsXW5bgQmDoSE6uWdckVgzhVFxh4xOuiiEpsBG thom.fife@gmail.com"
    ];
    subUidRanges = [{ startUid = 100000; count = 65536; }];
    subGidRanges = [{ startGid = 100000; count = 65536; }];
  };

  security.sudo.wheelNeedsPassword = false;

  services.openssh = {
    enable = true;
    settings = {
      PermitRootLogin = "prohibit-password";
      PasswordAuthentication = false;
    };
  };

  services.qemuGuest.enable = true;

  virtualisation.podman = {
    enable = true;
    dockerCompat = true;
    defaultNetwork.settings.dns_enabled = true;
  };

  environment.systemPackages = with pkgs; [
    vim git curl wget htop tmux
    podman-compose
    python312 python312Packages.pip python312Packages.virtualenv
    sqlite redis
    age sops
    jq yq tree unzip ffmpeg
  ];

  networking.firewall = {
    enable = true;
    allowedTCPPorts = [ 22 ];
  };

  nix.settings.experimental-features = [ "nix-command" "flakes" ];

  nix.gc = {
    automatic = true;
    dates = "weekly";
    options = "--delete-older-than 30d";
  };

  system.stateVersion = "24.11";
}
```

---

## Files Created This Session

```
barnabeenet/
├── pyproject.toml              # NEW
├── requirements.txt            # NEW
├── requirements-gpu.txt        # NEW
├── .env.example               # NEW
├── docs/
│   └── PATCH_Phase1_Updates.md # NEW
└── src/barnabeenet/
    ├── __init__.py             # UPDATED
    ├── config.py               # NEW
    ├── main.py                 # NEW
    ├── api/
    │   ├── __init__.py         # UPDATED
    │   └── routes/
    │       ├── __init__.py     # UPDATED
    │       ├── health.py       # NEW
    │       └── voice.py        # NEW
    ├── models/
    │   ├── __init__.py         # UPDATED
    │   └── schemas.py          # NEW
    └── services/
        ├── stt/
        │   └── __init__.py
        └── tts/
            └── __init__.py
```

---

## Next Session TODO

1. **Complete Python setup on Man-of-war WSL:**
   ```bash
   sudo apt update
   sudo apt install python3-pip python3-venv -y
   cd ~/projects/barnabeenet
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -e .
   ```

2. **Test the server locally:**
   ```bash
   barnabeenet
   # or: uvicorn barnabeenet.main:app --reload
   ```
   Then check: http://localhost:8000/health

3. **Continue Phase 1:**
   - Step 3: STT Services (Distil-Whisper implementation)
   - Step 4: TTS Service (Kokoro implementation)
   - Step 5: GPU Worker
   - Step 6: Deployment scripts
   - Step 7: Tests

4. **Deploy to BarnabeeNet VM** after local testing works

---

## Access Quick Reference

```bash
# Development (Man-of-war WSL)
cd ~/projects/barnabeenet
source .venv/bin/activate  # After setup

# SSH to BarnabeeNet VM
ssh thom@192.168.86.51

# SSH to Proxmox host
ssh root@192.168.86.64

# Proxmox Web UI
https://192.168.86.64:8006

# Check BarnabeeNet services
ssh thom@192.168.86.51 "podman ps"

# Redis CLI
ssh thom@192.168.86.51 "podman exec barnabeenet-redis redis-cli ping"

# Deploy to server (after git push)
ssh thom@192.168.86.51 "cd ~/barnabeenet && git pull"
```

---

## Cost Tracking

### Development Costs
| Date | Item | Cost |
|------|------|------|
| 2026-01-16 | Cursor Pro (monthly) | $20 |
| 2026-01-16 | Anthropic API credits | ~$5 used |

### Running Total
- **Development:** ~$25/month
- **Runtime:** $0 (not yet deployed)

---

*Last Updated: January 17, 2026*
