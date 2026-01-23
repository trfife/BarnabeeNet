#!/bin/bash
# Switch between LLM configurations (paid vs free)
#
# Usage:
#   ./scripts/switch-llm-config.sh paid   # Switch to paid models
#   ./scripts/switch-llm-config.sh free   # Switch to free models
#   ./scripts/switch-llm-config.sh status # Show current configuration

set -e

CONFIG_DIR="$(dirname "$0")/../config"
CURRENT_CONFIG="$CONFIG_DIR/llm.yaml"
PAID_CONFIG="$CONFIG_DIR/llm-paid.yaml"
FREE_CONFIG="$CONFIG_DIR/llm-free.yaml"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

show_status() {
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}                    LLM Configuration Status${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
    
    # Check which config is active by looking for key markers
    if grep -q ":free" "$CURRENT_CONFIG" 2>/dev/null; then
        echo -e "Current mode: ${GREEN}FREE${NC}"
        echo ""
        echo "Free models in use:"
        echo "  - google/gemini-2.0-flash-exp:free (routing, instant, memory)"
        echo "  - meta-llama/llama-3.3-70b-instruct:free (interaction, action)"
        echo ""
        echo -e "Cost: ${GREEN}\$0.00${NC} per query"
    else
        echo -e "Current mode: ${YELLOW}PAID${NC}"
        echo ""
        echo "Paid models in use:"
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
    echo -e "${GREEN}✅ Switched to PAID configuration${NC}"
    echo ""
    echo "Models now active:"
    echo "  - MetaAgent: google/gemini-2.0-flash-001"
    echo "  - InstantAgent: google/gemini-2.0-flash-001"
    echo "  - ActionAgent: openai/gpt-4o-mini"
    echo "  - InteractionAgent: anthropic/claude-3.5-haiku"
    echo "  - MemoryAgent: openai/gpt-4o-mini"
    echo ""
    echo -e "${YELLOW}Restart BarnabeeNet to apply changes:${NC}"
    echo "  bash scripts/restart.sh"
}

switch_to_free() {
    if [ ! -f "$FREE_CONFIG" ]; then
        echo "Error: $FREE_CONFIG not found!"
        exit 1
    fi
    
    cp "$FREE_CONFIG" "$CURRENT_CONFIG"
    echo -e "${GREEN}✅ Switched to FREE configuration${NC}"
    echo ""
    echo "Models now active:"
    echo "  - MetaAgent: google/gemini-2.0-flash-exp:free"
    echo "  - InstantAgent: google/gemini-2.0-flash-exp:free"
    echo "  - ActionAgent: meta-llama/llama-3.3-70b-instruct:free"
    echo "  - InteractionAgent: meta-llama/llama-3.3-70b-instruct:free"
    echo "  - MemoryAgent: google/gemini-2.0-flash-exp:free"
    echo ""
    echo -e "${YELLOW}Note: Free models may have rate limits and occasional availability issues${NC}"
    echo ""
    echo -e "${YELLOW}Restart BarnabeeNet to apply changes:${NC}"
    echo "  bash scripts/restart.sh"
}

show_help() {
    echo "Usage: $0 [paid|free|status]"
    echo ""
    echo "Commands:"
    echo "  paid    Switch to paid models (best quality)"
    echo "  free    Switch to free models (no cost)"
    echo "  status  Show current configuration"
    echo ""
    echo "Examples:"
    echo "  $0 paid     # Use paid models for best quality"
    echo "  $0 free     # Use free models to save money"
    echo "  $0 status   # Check which mode is active"
}

case "${1:-status}" in
    paid)
        switch_to_paid
        ;;
    free)
        switch_to_free
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
