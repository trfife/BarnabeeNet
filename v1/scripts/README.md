# Scripts

Utility scripts for development and deployment.

## Development

| Script | Description |
|--------|-------------|
| `validate.sh` | Run all checks before commit (format, lint, test) |
| `pre-commit.sh` | Git pre-commit hook |

## GPU Worker (Man-of-war WSL)

| Script | Description |
|--------|-------------|
| `start-gpu-worker.sh` | Start Parakeet TDT worker on port 8001 |
| `stop-gpu-worker.sh` | Stop the GPU worker |

## Deployment

| Script | Description |
|--------|-------------|
| `deploy-vm.sh` | Deploy to VM: git pull + restart services |
| `restart.sh` | Restart services (runs on VM) |

## Monitoring

| Script | Description |
|--------|-------------|
| `status.sh` | Check status of all components |

## Quick Start

```bash
# Start GPU worker locally
./scripts/start-gpu-worker.sh

# Check everything is running
./scripts/status.sh

# Deploy to VM
./scripts/deploy-vm.sh
```

