# VM Deployment Status

**Last Updated:** 2026-01-21  
**VM:** thom@192.168.86.51 (NixOS)  
**WSL:** Should only run GPU workers, NOT the main API

## Current Status

### ✅ VM (192.168.86.51) - Production Runtime
- **BarnabeeNet API:** Running on port 8000
- **Redis:** Running in podman container
- **Prometheus:** Running on port 9090
- **Grafana:** Running on port 3000
- **Code:** Synced to latest (commit 667fdf5)
- **Redis Data:** Cleared (521 keys deleted)

### ✅ WSL - Development Only
- **BarnabeeNet API:** NOT running (correct)
- **GPU Workers:** Can run here when needed (Parakeet STT, Kokoro TTS)

## Deployment Process

1. **Develop locally in WSL**
2. **Commit and push to GitHub**
3. **Deploy to VM:**
   ```bash
   ./scripts/deploy-vm.sh
   ```
   Or manually:
   ```bash
   ssh thom@192.168.86.51 'cd ~/barnabeenet && git pull && bash scripts/restart.sh'
   ```

## Verification

Check VM status:
```bash
ssh thom@192.168.86.51 'cd ~/barnabeenet && pgrep -f "uvicorn barnabeenet" | wc -l'
# Should show 5 processes (main + workers)
```

Check WSL status:
```bash
pgrep -f "uvicorn.*barnabeenet"
# Should return nothing
```

## Troubleshooting

If BarnabeeNet is running in WSL when it shouldn't be:
```bash
pkill -9 -f "uvicorn.*barnabeenet"
```

If VM service isn't running:
```bash
ssh thom@192.168.86.51 'cd ~/barnabeenet && bash scripts/restart.sh'
```
