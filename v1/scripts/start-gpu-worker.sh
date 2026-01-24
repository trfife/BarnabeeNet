#!/bin/bash
# Start the GPU STT worker on Man-of-war (WSL)
# This runs the Parakeet TDT model for fast speech-to-text

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

cd "$PROJECT_DIR"

echo -e "${YELLOW}🚀 Starting GPU STT Worker${NC}"
echo "================================"

# Check if already running
if pgrep -f "uvicorn workers.gpu_stt_worker:app" > /dev/null; then
    echo -e "${YELLOW}⚠ GPU worker already running${NC}"
    PID=$(pgrep -f "uvicorn workers.gpu_stt_worker:app")
    echo "  PID: $PID"

    # Test health
    if curl -s http://localhost:8001/health | grep -q "healthy"; then
        echo -e "${GREEN}✓ Worker is healthy${NC}"
        exit 0
    else
        echo -e "${RED}Worker not responding, killing and restarting...${NC}"
        pkill -f "uvicorn workers.gpu_stt_worker:app" || true
        sleep 2
    fi
fi

# Check for GPU venv
if [ ! -d ".venv-gpu" ]; then
    echo -e "${RED}❌ GPU venv not found at .venv-gpu/${NC}"
    echo "  Run: python -m venv .venv-gpu && source .venv-gpu/bin/activate && pip install -r requirements-gpu.txt"
    exit 1
fi

# Activate GPU venv
source .venv-gpu/bin/activate

# Check CUDA
if ! python -c "import torch; assert torch.cuda.is_available()" 2>/dev/null; then
    echo -e "${RED}❌ CUDA not available${NC}"
    exit 1
fi

echo -e "${GREEN}✓ CUDA available${NC}"

# Start in background using nohup (simpler than screen for systemd-style operation)
echo "Starting worker on port 8001..."
nohup python -m uvicorn workers.gpu_stt_worker:app \
    --host 0.0.0.0 \
    --port 8001 \
    > "$PROJECT_DIR/logs/gpu-worker.log" 2>&1 &

WORKER_PID=$!
echo "Worker PID: $WORKER_PID"

# Wait for startup
echo "Waiting for model to load..."
for i in {1..60}; do
    if curl -s http://localhost:8001/health | grep -q "healthy"; then
        echo -e "${GREEN}✓ GPU worker started successfully${NC}"
        echo ""
        echo "Endpoints:"
        echo "  Health: http://localhost:8001/health"
        echo "  Transcribe: http://localhost:8001/transcribe"
        echo ""
        echo "From VM: http://192.168.86.61:8001/health"
        echo ""
        echo "Logs: tail -f $PROJECT_DIR/logs/gpu-worker.log"
        exit 0
    fi
    sleep 1
done

echo -e "${RED}❌ Worker failed to start in 60s${NC}"
echo "Check logs: cat $PROJECT_DIR/logs/gpu-worker.log"
exit 1
