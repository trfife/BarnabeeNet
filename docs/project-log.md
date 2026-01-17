# BarnabeeNet Project Log

**Started:** January 16, 2026  
**Goal:** Build a privacy-first, multi-agent AI smart home assistant

---

## Environment

| Name | Hardware | Role | IP |
|------|----------|------|-----|
| Man-of-war | Gaming PC (i9-14900KF, RTX 4070 Ti, 128GB) | Development + heavy compute | - |
| Battlestation | Beelink EQi12 (i5-1220P, 24GB, 500GB) | Proxmox host, BarnabeeNet runtime | 192.168.86.64 |

---

## Phase 0: Foundation Setup

### Step 1: Development Environment Setup
**Status:** ✅ Complete  
**Date:** January 16, 2026

#### Completed
- [x] Cursor installed on Windows 11
- [x] Anthropic API key created with credits
- [x] WSL2 with Ubuntu-24.04 installed
- [x] git, age, sops installed in WSL
- [x] SSH access to Battlestation verified

#### Commands Run
```bash
# PowerShell (Admin) - Install WSL
wsl --install -d Ubuntu-24.04

# WSL - Install tools
sudo apt update
sudo apt install git age -y
curl -LO https://github.com/getsops/sops/releases/download/v3.9.4/sops-v3.9.4.linux.amd64
sudo mv sops-v3.9.4.linux.amd64 /usr/local/bin/sops
sudo chmod +x /usr/local/bin/sops

# Test SSH
ssh root@192.168.86.64
```

---

### Step 2: Repository Initialization
**Status:** ✅ Complete  
**Date:** January 16, 2026

#### Completed
- [x] GitHub repository created: https://github.com/trfife/BarnabeeNet
- [x] Initial structure committed
- [x] SSH key configured for GitHub

---

### Step 3: Create BarnabeeNet VM on Proxmox
**Status:** Not Started

---

### Step 4: Base VM Configuration
**Status:** Not Started

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

---

## Issues Encountered

| Date | Issue | Resolution |
|------|-------|------------|
| 2026-01-16 | WSL showed "no installed distributions" | Ran `wsl --install -d Ubuntu-24.04` explicitly |

---

## Cost Tracking

### Development Costs
| Date | Item | Cost |
|------|------|------|
| 2026-01-16 | Cursor Pro (monthly) | $20 |
| 2026-01-16 | Anthropic API credits | $TBD |

### Running Total
- **Development:** ~$20/month + API usage
- **Runtime:** $0 (not yet running)
