#!/bin/bash
# Check status of all BarnabeeNet components

set -e

VM_HOST="thom@192.168.86.51"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}📊 BarnabeeNet Status${NC}"
echo "================================"

# GPU Worker (Man-of-war WSL)
echo -e "\n${YELLOW}[GPU Worker - Man-of-war]${NC}"
if curl -s --connect-timeout 2 http://localhost:8001/health > /tmp/gpu_health.json 2>/dev/null; then
    STATUS=$(cat /tmp/gpu_health.json | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('status','unknown'))" 2>/dev/null || echo "parse error")
    GPU=$(cat /tmp/gpu_health.json | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('gpu_name','unknown'))" 2>/dev/null || echo "unknown")
    MEM=$(cat /tmp/gpu_health.json | python3 -c "import sys,json; d=json.load(sys.stdin); print(f\"{d.get('gpu_memory_used_mb',0):.0f}/{d.get('gpu_memory_total_mb',0):.0f} MB\")" 2>/dev/null || echo "unknown")
    
    if [ "$STATUS" == "healthy" ]; then
        echo -e "  Status: ${GREEN}✓ healthy${NC}"
    else
        echo -e "  Status: ${RED}✗ $STATUS${NC}"
    fi
    echo "  GPU: $GPU"
    echo "  Memory: $MEM"
    echo "  URL: http://localhost:8001"
else
    echo -e "  Status: ${RED}✗ not running${NC}"
    echo "  Start: ./scripts/start-gpu-worker.sh"
fi

# VM Services
echo -e "\n${YELLOW}[VM Services - 192.168.86.51]${NC}"
if ssh -o ConnectTimeout=2 "$VM_HOST" "echo connected" > /dev/null 2>&1; then
    echo -e "  SSH: ${GREEN}✓ connected${NC}"
    
    # Redis
    if ssh "$VM_HOST" "redis-cli ping" 2>/dev/null | grep -q "PONG"; then
        echo -e "  Redis: ${GREEN}✓ running${NC}"
    else
        echo -e "  Redis: ${RED}✗ not responding${NC}"
    fi
    
    # Check if VM can reach GPU worker
    if ssh "$VM_HOST" "curl -s --connect-timeout 2 http://192.168.86.61:8001/health" 2>/dev/null | grep -q "healthy"; then
        echo -e "  GPU Worker Access: ${GREEN}✓ reachable${NC}"
    else
        echo -e "  GPU Worker Access: ${RED}✗ unreachable${NC}"
    fi
else
    echo -e "  SSH: ${RED}✗ cannot connect${NC}"
fi

# Local Redis (Docker)
echo -e "\n${YELLOW}[Local Redis - Docker]${NC}"
if docker ps 2>/dev/null | grep -q redis; then
    echo -e "  Status: ${GREEN}✓ running${NC}"
elif podman ps 2>/dev/null | grep -q redis; then
    echo -e "  Status: ${GREEN}✓ running (podman)${NC}"
else
    echo -e "  Status: ${YELLOW}⚠ not running${NC}"
fi

echo ""
echo "================================"
echo -e "${BLUE}Done${NC}"
