#!/bin/bash
# Restart BarnabeeNet services (runs on VM)
# Called by deploy-vm.sh after pulling code

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

cd "$PROJECT_DIR"

# NixOS dynamic linking fix - find libstdc++ from gcc package
# This is needed for Python packages with native extensions
if [ -f /etc/NIXOS ]; then
    export LD_LIBRARY_PATH="$(nix-build '<nixpkgs>' -A stdenv.cc.cc.lib --no-out-link 2>/dev/null)/lib:${LD_LIBRARY_PATH:-}"
fi

echo -e "${YELLOW}🔄 Restarting BarnabeeNet services${NC}"
echo "================================"

# Check if podman-compose is available
if command -v podman-compose &> /dev/null; then
    echo "Using podman-compose..."

    # Restart containers
    if [ -f "infrastructure/podman-compose.yml" ]; then
        echo -e "\n${YELLOW}[1/2] Stopping services...${NC}"
        podman-compose -f infrastructure/podman-compose.yml down || true

        echo -e "\n${YELLOW}[2/2] Starting services...${NC}"
        podman-compose -f infrastructure/podman-compose.yml up -d

        echo -e "\n${GREEN}✓ Services restarted${NC}"
        echo ""
        podman-compose -f infrastructure/podman-compose.yml ps
    else
        echo -e "${YELLOW}⚠ No podman-compose.yml found${NC}"
    fi
elif command -v docker-compose &> /dev/null; then
    echo "Using docker-compose..."

    if [ -f "infrastructure/podman-compose.yml" ]; then
        echo -e "\n${YELLOW}[1/2] Stopping services...${NC}"
        docker-compose -f infrastructure/podman-compose.yml down || true

        echo -e "\n${YELLOW}[2/2] Starting services...${NC}"
        docker-compose -f infrastructure/podman-compose.yml up -d

        echo -e "\n${GREEN}✓ Services restarted${NC}"
    fi
else
    echo -e "${YELLOW}⚠ No container runtime found${NC}"
    echo "  Install podman-compose or docker-compose"
fi

# Restart BarnabeeNet FastAPI app
echo -e "\n${YELLOW}[3/3] Restarting BarnabeeNet app...${NC}"

# Check if virtual environment exists
if [ -d ".venv" ]; then
    # Kill existing process if running
    if pgrep -f "uvicorn barnabeenet.main:app" > /dev/null; then
        echo "Stopping existing BarnabeeNet process..."
        pkill -f "uvicorn barnabeenet.main:app" || true
        sleep 2
    fi

    # Ensure logs directory exists
    mkdir -p logs

    # Build the startup command with proper env for NixOS
    START_CMD="cd $PROJECT_DIR"
    # Load environment variables from .env if present
    if [ -f "$PROJECT_DIR/.env" ]; then
        START_CMD="$START_CMD && set -a && source .env && set +a"
    fi
    START_CMD="$START_CMD && source .venv/bin/activate"
    if [ -n "$LD_LIBRARY_PATH" ]; then
        START_CMD="export LD_LIBRARY_PATH='$LD_LIBRARY_PATH' && $START_CMD"
    fi
    START_CMD="$START_CMD && python -m uvicorn barnabeenet.main:app --host 0.0.0.0 --port 8000 2>&1 | tee logs/barnabeenet.log"

    # Start with tmux or nohup (tmux preferred, nohup as fallback)
    echo "Starting BarnabeeNet in background..."
    if command -v tmux &> /dev/null; then
        # Kill existing tmux session if exists
        tmux kill-session -t barnabeenet 2>/dev/null || true
        tmux new-session -d -s barnabeenet "$START_CMD"
        ATTACH_CMD="tmux attach -t barnabeenet"
    else
        # Fallback to nohup (</dev/null prevents SSH hanging)
        nohup bash -c "$START_CMD" </dev/null &
        ATTACH_CMD="tail -f logs/barnabeenet.log"
    fi

    sleep 3
    if pgrep -f "uvicorn barnabeenet.main:app" > /dev/null; then
        echo -e "${GREEN}✓ BarnabeeNet app started${NC}"
        echo "  Attach: $ATTACH_CMD"
    else
        echo -e "${RED}❌ BarnabeeNet app failed to start${NC}"
        echo "  Check logs: cat logs/barnabeenet.log"
    fi
else
    echo -e "${YELLOW}⚠ No .venv found - run 'python -m venv .venv && pip install -r requirements.txt' first${NC}"
fi

echo ""
echo -e "${GREEN}✅ Restart complete${NC}"
echo ""
echo "Services:"
echo "  - BarnabeeNet API: http://192.168.86.51:8000"
echo "  - Grafana:         http://192.168.86.51:3000"
echo "  - Prometheus:      http://192.168.86.51:9090"
