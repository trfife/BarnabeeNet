#!/bin/bash
# Switch between LLM configurations (paid vs low-cost)
#
# Usage:
#   ./scripts/switch-llm-config.sh paid    # Switch to paid models (best quality)
#   ./scripts/switch-llm-config.sh cheap   # Switch to low-cost models
#   ./scripts/switch-llm-config.sh status  # Show current configuration

set -e

CONFIG_DIR="$(dirname "$0")/../config"
CURRENT_CONFIG="$CONFIG_DIR/llm.yaml"
PAID_CONFIG="$CONFIG_DIR/llm-paid.yaml"
CHEAP_CONFIG="$CONFIG_DIR/llm-free.yaml"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

show_status() {
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}                    LLM Configuration Status${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
    
    # Check which config is active by looking for key markers
    if grep -q "deepseek/deepseek-chat" "$CURRENT_CONFIG" 2>/dev/null && grep -q "LOW-COST" "$CURRENT_CONFIG" 2>/dev/null; then
        echo -e "Current mode: ${CYAN}LOW-COST${NC}"
        echo ""
        echo "Low-cost models in use:"
        echo "  - google/gemini-2.0-flash-001 (routing, instant)"
        echo "  - deepseek/deepseek-chat (interaction, action, memory)"
        echo ""
        echo -e "Cost: ${CYAN}~\$0.0001-0.0005${NC} per query (10x cheaper than paid)"
    else
        echo -e "Current mode: ${YELLOW}PAID (Best Quality)${NC}"
        echo ""
        echo "Premium models in use:"
        echo "  - google/gemini-2.0-flash-001 (routing, instant)"
        echo "  - openai/gpt-4o-mini (action, memory)"
        echo "  - anthropic/claude-3.5-haiku (interaction)"
        echo ""
        echo -e "Cost: ${YELLOW}~\$0.001-0.002${NC} per query"
    fi
    echo ""
}

switch_to_paid() {
    if [ ! -f "$PAID_CONFIG" ]; then
        echo "Error: $PAID_CONFIG not found!"
        exit 1
    fi
    
    cp "$PAID_CONFIG" "$CURRENT_CONFIG"
    echo -e "${GREEN}✅ Switched to PAID (Best Quality) configuration${NC}"
    echo ""
    echo "Models now active:"
    echo "  - MetaAgent: google/gemini-2.0-flash-001"
    echo "  - InstantAgent: google/gemini-2.0-flash-001"
    echo "  - ActionAgent: openai/gpt-4o-mini"
    echo "  - InteractionAgent: anthropic/claude-3.5-haiku"
    echo "  - MemoryAgent: openai/gpt-4o-mini"
    echo ""
    echo -e "Cost: ${YELLOW}~\$0.001-0.002${NC} per query"
    echo ""
    echo -e "${YELLOW}Restart BarnabeeNet to apply changes:${NC}"
    echo "  bash scripts/restart.sh"
}

switch_to_cheap() {
    if [ ! -f "$CHEAP_CONFIG" ]; then
        echo "Error: $CHEAP_CONFIG not found!"
        exit 1
    fi
    
    cp "$CHEAP_CONFIG" "$CURRENT_CONFIG"
    echo -e "${GREEN}✅ Switched to LOW-COST configuration${NC}"
    echo ""
    echo "Models now active:"
    echo "  - MetaAgent: google/gemini-2.0-flash-001"
    echo "  - InstantAgent: google/gemini-2.0-flash-001"
    echo "  - ActionAgent: deepseek/deepseek-chat"
    echo "  - InteractionAgent: deepseek/deepseek-chat"
    echo "  - MemoryAgent: deepseek/deepseek-chat"
    echo ""
    echo -e "Cost: ${CYAN}~\$0.0001-0.0005${NC} per query (10x cheaper)"
    echo ""
    echo "Pricing per 1M tokens:"
    echo "  - Gemini Flash: \$0.10 input / \$0.40 output"
    echo "  - DeepSeek Chat: \$0.14 input / \$0.28 output"
    echo ""
    echo -e "${YELLOW}Restart BarnabeeNet to apply changes:${NC}"
    echo "  bash scripts/restart.sh"
}

show_help() {
    echo "Usage: $0 [paid|cheap|status]"
    echo ""
    echo "Commands:"
    echo "  paid    Switch to paid models (best quality - Claude, GPT-4o)"
    echo "  cheap   Switch to low-cost models (DeepSeek, Gemini Flash)"
    echo "  status  Show current configuration"
    echo ""
    echo "Cost Comparison:"
    echo "  PAID:     ~\$0.001-0.002 per query (best quality)"
    echo "  LOW-COST: ~\$0.0001-0.0005 per query (10x cheaper)"
    echo ""
    echo "Examples:"
    echo "  $0 paid     # Use premium models for best quality"
    echo "  $0 cheap    # Use low-cost models to save money"
    echo "  $0 status   # Check which mode is active"
}

case "${1:-status}" in
    paid)
        switch_to_paid
        ;;
    cheap|free|lowcost|low-cost)
        switch_to_cheap
        ;;
    status)
        show_status
        ;;
    -h|--help|help)
        show_help
        ;;
    *)
        echo "Unknown command: $1"
        echo ""
        show_help
        exit 1
        ;;
esac
