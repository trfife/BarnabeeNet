# BarnabeeNet Project Log

**Started:** January 16, 2026  
**Goal:** Build a privacy-first, multi-agent AI smart home assistant

---

## Environment

| Name | Hardware | Role | IP |
|------|----------|------|-----|
| Man-of-war | Gaming PC (i9-14900KF, RTX 4070 Ti, 128GB) | Development + heavy compute | - |
| Battlestation | Beelink EQi12 (i5-1220P, 24GB, 500GB) | Proxmox host | 192.168.86.64 |
| BarnabeeNet VM | VM 200 on Battlestation (6 cores, 8GB RAM, 100GB) | BarnabeeNet runtime | 192.168.86.51 |

---

## Phase 0: Foundation Setup

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
**Status:** 🔄 Ready to Start

### TODO
- [ ] Add Faster-Whisper container (STT)
- [ ] Add Piper container (TTS)
- [ ] Create Python virtual environment
- [ ] Install BarnabeeNet dependencies
- [ ] Create FastAPI scaffolding for BarnabeeNet core
- [ ] Basic end-to-end voice test (audio → text → audio)

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

## Access Quick Reference
```bash
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
```

---

## Cost Tracking

### Development Costs
| Date | Item | Cost |
|------|------|------|
| 2026-01-16 | Cursor Pro (monthly) | $20 |
| 2026-01-16 | Anthropic API credits | $TBD |

### Running Total
- **Development:** ~$20/month + API usage
- **Runtime:** $0 (Redis only, minimal resources)
