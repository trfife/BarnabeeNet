#!/bin/bash
# Deploy BarnabeeNet to VM (192.168.86.51)
# Pulls latest code and restarts services

set -e

VM_HOST="thom@192.168.86.51"
VM_PROJECT_DIR="~/barnabeenet"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}🚀 Deploying to BarnabeeNet VM${NC}"
echo "================================"
echo "Target: $VM_HOST:$VM_PROJECT_DIR"
echo ""

# Check SSH connectivity
echo -e "${YELLOW}[1/4] Checking SSH connectivity...${NC}"
if ! ssh -o ConnectTimeout=5 "$VM_HOST" "echo 'connected'" > /dev/null 2>&1; then
    echo -e "${RED}❌ Cannot connect to VM${NC}"
    exit 1
fi
echo -e "${GREEN}✓ SSH connection OK${NC}"

# Pull latest code
echo -e "\n${YELLOW}[2/4] Pulling latest code...${NC}"
ssh "$VM_HOST" "cd $VM_PROJECT_DIR && git pull"
echo -e "${GREEN}✓ Code updated${NC}"

# Check if restart script exists on VM
echo -e "\n${YELLOW}[3/4] Checking for restart script...${NC}"
if ssh "$VM_HOST" "test -f $VM_PROJECT_DIR/scripts/restart.sh"; then
    echo -e "${GREEN}✓ Restart script found${NC}"
    
    echo -e "\n${YELLOW}[4/4] Restarting services...${NC}"
    ssh "$VM_HOST" "cd $VM_PROJECT_DIR && ./scripts/restart.sh"
else
    echo -e "${YELLOW}⚠ No restart script on VM yet${NC}"
    echo "  Create $VM_PROJECT_DIR/scripts/restart.sh to enable auto-restart"
fi

echo ""
echo -e "${GREEN}✅ Deployment complete${NC}"
echo ""
echo "Check VM status:"
echo "  ssh $VM_HOST 'cd $VM_PROJECT_DIR && podman-compose ps'"
echo ""
echo "View logs:"
echo "  ssh $VM_HOST 'cd $VM_PROJECT_DIR && podman-compose logs -f'"
