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

#### Completed
- [x] Cleaned up unused VMs/containers (removed 102, 103, 104, 105, 108, 109, 110)
- [x] Stopped old barnabee container (107) for reference
- [x] Downloaded NixOS 24.11 ISO to Proxmox
- [x] Created VM 200 (barnabeenet): 6 cores, 8GB RAM, 100GB disk
- [x] Booted NixOS live installer
- [x] SSH access to installer working
- [x] Disk partitioned (GPT, EFI + root)
- [x] Filesystems created (FAT32 boot, ext4 root)
- [x] Mounted and generated hardware config
- [x] Fixed duplicate /boot entry in hardware-configuration.nix
- [x] Wrote NixOS configuration with SSH key
- [x] Ran nixos-install
- [x] Fixed BIOS → UEFI boot (added EFI disk, changed to OVMF)
- [x] Ran nixos-rebuild switch to apply SSH keys
- [x] SSH access as thom@192.168.86.51 verified

#### Final VM Configuration
- **BIOS:** OVMF (UEFI)
- **Disks:** scsi0 (100GB root), efidisk0 (4MB EFI vars)
- **Boot:** systemd-boot
- **OS:** NixOS 24.11
- **Nix version:** 2.24.14
- **Flakes:** Enabled

---

### Step 4: Base VM Configuration
**Status:** 🔄 In Progress  
**Date:** January 16, 2026

#### TODO
- [ ] Set up directory structure for BarnabeeNet
- [ ] Install and configure Docker or Podman
- [ ] Clone BarnabeeNet repo to VM
- [ ] Initial service scaffolding

---

## Phase 1: Core Services
**Status:** Not Started

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

  # Bootloader
  boot.loader.systemd-boot.enable = true;
  boot.loader.efi.canTouchEfiVariables = true;

  # Networking
  networking.hostName = "barnabeenet";
  networking.networkmanager.enable = true;

  # Timezone
  time.timeZone = "America/New_York";

  # Users
  users.users.thom = {
    isNormalUser = true;
    extraGroups = [ "wheel" "networkmanager" ];
    openssh.authorizedKeys.keys = [
      "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOP6MkvsXW5bgQmDoSE6uWdckVgzhVFxh4xOuiiEpsBG thom.fife@gmail.com"
    ];
  };

  # Allow sudo without password for wheel group
  security.sudo.wheelNeedsPassword = false;

  # Enable SSH
  services.openssh = {
    enable = true;
    settings = {
      PermitRootLogin = "prohibit-password";
      PasswordAuthentication = false;
    };
  };

  # Enable QEMU guest agent
  services.qemuGuest.enable = true;

  # Basic packages
  environment.systemPackages = with pkgs; [
    vim
    git
    curl
    wget
    htop
    tmux
  ];

  # Firewall
  networking.firewall = {
    enable = true;
    allowedTCPPorts = [ 22 ];
  };

  # Enable flakes
  nix.settings.experimental-features = [ "nix-command" "flakes" ];

  # System version
  system.stateVersion = "24.11";
}
```

---

## Hardware Configuration (Current)

**Location on VM:** `/etc/nixos/hardware-configuration.nix`

```nix
{ config, lib, pkgs, modulesPath, ... }:

{
  imports =
    [ (modulesPath + "/profiles/qemu-guest.nix")
    ];

  boot.initrd.availableKernelModules = [ "ata_piix" "uhci_hcd" "virtio_pci" "virtio_scsi" "sd_mod" "sr_mod" ];
  boot.initrd.kernelModules = [ ];
  boot.kernelModules = [ "kvm-intel" ];
  boot.extraModulePackages = [ ];

  fileSystems."/" =
    { device = "/dev/disk/by-uuid/3fc1bab7-2ff7-4bb2-bbdf-05cc3cef7ca2";
      fsType = "ext4";
    };

  fileSystems."/boot" =
    { device = "/dev/disk/by-uuid/F3B2-B88D";
      fsType = "vfat";
      options = [ "fmask=0022" "dmask=0022" ];
    };

  swapDevices = [ ];

  networking.useDHCP = lib.mkDefault true;

  nixpkgs.hostPlatform = lib.mkDefault "x86_64-linux";
}
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
- **Runtime:** $0 (not yet running services)

---

## Access Quick Reference

```bash
# SSH to BarnabeeNet VM (from WSL on Man-of-war)
ssh thom@192.168.86.51

# SSH to Proxmox host
ssh root@192.168.86.64

# Proxmox Web UI
https://192.168.86.64:8006
```

---

## Next Session: Step 4 - Base VM Configuration

Ready to continue with:
1. Directory structure setup
2. Docker/Podman installation
3. Clone GitHub repo to VM
4. Initial service scaffolding
