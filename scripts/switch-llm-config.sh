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
    if grep -q "llama-3.3-70b-instruct:free" "$CURRENT_CONFIG" 2>/dev/null; then
        echo -e "Current mode: ${GREEN}FREE${NC}"
        echo ""
        echo "Free model in use:"
        echo "  - meta-llama/llama-3.3-70b-instruct:free (all agents)"
        echo ""
        echo -e "Cost: ${GREEN}\$0.00${NC} per query"
        echo ""
        echo "Note: Free tier may have rate limits during peak times"
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

switch_to_free() {
    if [ ! -f "$CHEAP_CONFIG" ]; then
        echo "Error: $CHEAP_CONFIG not found!"
        exit 1
    fi

    cp "$CHEAP_CONFIG" "$CURRENT_CONFIG"
    echo -e "${GREEN}✅ Switched to FREE configuration${NC}"
    echo ""
    echo "Model now active (all agents):"
    echo "  - meta-llama/llama-3.3-70b-instruct:free"
    echo ""
    echo -e "Cost: ${GREEN}\$0.00${NC} per query"
    echo ""
    echo "Note: Free tier may have rate limits during peak usage"
    echo ""
    echo -e "${YELLOW}Restart BarnabeeNet to apply changes:${NC}"
    echo "  bash scripts/restart.sh"
}

show_help() {
    echo "Usage: $0 [paid|free|status]"
    echo ""
    echo "Commands:"
    echo "  paid    Switch to paid models (best quality - Claude, GPT-4o)"
    echo "  free    Switch to free models (Llama 3.3 70B)"
    echo "  status  Show current configuration"
    echo ""
    echo "Cost Comparison:"
    echo "  PAID: ~\$0.001-0.002 per query (best quality)"
    echo "  FREE: \$0.00 per query (may have rate limits)"
    echo ""
    echo "Examples:"
    echo "  $0 paid     # Use premium models for best quality"
    echo "  $0 free     # Use free models (Llama 3.3 70B)"
    echo "  $0 status   # Check which mode is active"
}

case "${1:-status}" in
    paid)
        switch_to_paid
        ;;
    free|cheap)
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
