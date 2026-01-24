#!/bin/bash
# Stop the GPU STT worker

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}🛑 Stopping GPU STT Worker${NC}"

if pgrep -f "uvicorn workers.gpu_stt_worker:app" > /dev/null; then
    pkill -f "uvicorn workers.gpu_stt_worker:app"
    sleep 1
    echo -e "${GREEN}✓ GPU worker stopped${NC}"
else
    echo -e "${YELLOW}⚠ GPU worker was not running${NC}"
fi
