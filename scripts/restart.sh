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

echo ""
echo -e "${GREEN}✅ Restart complete${NC}"
